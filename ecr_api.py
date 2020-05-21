#!/usr/bin/env python3

from flask import Flask
from flask.views import MethodView

import MySQLdb
from flask import request
import re
import uuid
import json


import os
import sys
app = Flask(__name__)

# https://mysqlclient.readthedocs.io/user_guide.html#mysqldb-mysql
mysql_host = os.getenv('MYSQL_HOST')
mysql_db =os.getenv('MYSQL_DATABASE')
mysql_user =  os.getenv('MYSQL_USER')
mysql_password =  os.getenv('MYSQL_PASSWORD')
#app.config['MYSQL_DATABASE_HOST'] = os.getenv('MYSQL_HOST')
#app.config['MYSQL_DATABASE_DB'] = os.getenv('MYSQL_DATABASE')
#app.config['MYSQL_DATABASE_USER'] = os.getenv('MYSQL_USER')
#app.config['MYSQL_DATABASE_PASSWORD'] = os.getenv('MYSQL_PASSWORD')






# app definition
valid_fields =["name", "description", "version", "source", "depends_on", "architecture" , "baseCommand", "arguments", "inputs", "metadata"]
valid_fields_set = set(valid_fields)
required_fields = set(["name", "description", "version", "source"])

# architecture https://github.com/docker-library/official-images#architectures-other-than-amd64
architecture_valid = ["linux/amd64", "linux/arm64", "linux/arm/v6", "linux/arm/v7", "linux/arm/v8"]


# app input
input_fields_valid = ["id", "type"]
# "Directory" not suypported yet # ref: https://www.commonwl.org/v1.1/CommandLineTool.html#CWLType
input_valid_types = ["boolean", "int", "long", "float", "double", "string", "File"] 


# database fields
dbFields = valid_fields + ["owner"]
dbFields_str  = ",".join(dbFields)


class EcrDB():
    def __init__ ( self ) :
        self.db =MySQLdb.connect(host=mysql_host,user=mysql_user,
                  passwd=mysql_password,db=mysql_db)
        self.cur=self.db.cursor()

    def getApp(self, app_id):
        stmt = f'SELECT  BIN_TO_UUID(id), {dbFields_str} FROM Apps WHERE BIN_TO_UUID(id) = %s'
        print(f'stmt: {stmt} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt, (app_id, ))

        returnFields = ["id"] + dbFields
        returnObj={}
        row = self.cur.fetchone()
        i = 0
        if row == None:
            raise Exception(f'App {app_id} not found')
        for value in row:
            print(f'value: {value}', file=sys.stderr)
            returnObj[returnFields[i]] = value
            i+=1

        #decode embedded json
        for field in ["inputs", "metadata"]:
            if field in returnObj:
                returnObj[field] = json.loads(returnObj[field])

        return returnObj
    
    def listApps(self):
        stmt = f'SELECT  BIN_TO_UUID(id), name, version FROM Apps'
        print(f'stmt: {stmt}', file=sys.stderr)
        self.cur.execute(stmt)

        rows = self.cur.fetchall()

        app_list = []

        for row in rows:
            print(f'row: {row}', file=sys.stderr)

            app_list.append({"id": row[0], "name": row[1], "version":row[2]})
        
        return app_list




class AppList(MethodView):
    def get(self):
        ecr_db = EcrDB()
        app_list = ecr_db.listApps()
        return { "data" : app_list} 

    def post(self):
        # example
       
        # curl -X POST localhost:5000/apps -d '{"name" : "testapp", "description": "blabla", "architecture" : ["linux/amd64" , "linux/arm/v7"] , "version" : "1.0", "source" :"https://github.com/user/repo.git#v1.0", "inputs": [{"id":"speed" , "type":"int" }] , "metadata": {"my-science-data" : 12345} }'


        # TODO authentication
        # TODO set owner
        authenticated = False
        postData = request.get_json(force=True)

        for key in postData:
            if not key in valid_fields_set:
                return  {"error": f'Field {key} not supported'}

        # if required
        for key in required_fields:
            if not key in postData:
                return  {"error": f'Required field {key} is missing'}
            value  = postData[key]
            if len(value) == 0:
                return  {"error": f'Required field {key} is missing'}


        

        ##### name
        appName = postData["name"]
        appNameArray = appName.split("/", 2)
        appUser = "user"
        if len(appNameArray) == 2:
            appUser = appNameArray[0]
            appName = appNameArray[1]

        if not authenticated:
            appUser = "unknown"
        # TODO check if appUser is correct
        # either owner or group name user has permisson to


        if len(appName) < 4:
           return  {"error": f'Name has to be at least 4 characters long'}  

        
        vc = '[.a-zA-Z0-9_-]'
        p = re.compile(f'[a-zA-Z0-9_]{vc}+', re.ASCII)
        if not p.match(appName):
            return  {"error": f'Name can only consist of [0-9a-zA-Z-_.] characters and only start with [0-9a-zA-Z] characters.'}  


        ##### architecture
        
        architecture_str = ""
        if "architecture" in postData:
            appArchitecture  = postData["architecture"]
            for arch in appArchitecture:
                if not arch in architecture_valid:
                    valid_arch_str = ",".join(architecture_valid)
                    return  {"error": f'Architecture {arch} not supported, valid values: {valid_arch_str}'}

            architecture_str = ",".join(appArchitecture)


        architecture_valid

        ##### source
        # source
        # git@github.com:<user>/<repo>.git#<tag>
        # https://github.com/<user>/<repo>.git#<tag>
        # http://sagecontinuum.org/bucket/<bucket_id>

        appSource = postData["source"]
        source_public_git_pattern = re.compile(f'https://github.com/{vc}+/{vc}+.git#{vc}+')
        source_private_git_pattern = re.compile(f'git@github.com/{vc}+/{vc}+.git#{vc}+') 
        source_sage_store_pattern = re.compile(f'http://sagecontinuum.org/bucket/[0-9a-z.]+') 
        source_matched = False
        for p in [source_public_git_pattern, source_private_git_pattern , source_sage_store_pattern]:
            if p.match(appSource):
                source_matched = True
                break
        
        if not source_matched:
            return  {"error": f'Could not parse source field'}

        ##### inputs
        
        # inputs validation
        appInputs = None
        if "inputs" in postData:
            appInputs = postData["inputs"]
            for app_input in appInputs:
                for field in app_input:
                    if not  field in  input_fields_valid:
                        return  {"error": f'Input field {field} not supported'} 
                for expected in input_fields_valid:
                    if not  expected in  app_input:
                        return  {"error": f'Expected field {expected} missing'} 
                    input_type = app_input["type"]
                    if not input_type in input_valid_types:
                        return  {"error": f'Input type {input_type} not supported'} 

            appInputs_str = json.dumps(appInputs) 

        ##### metadata
        appMetadata_str = ""
        if "metadata" in postData:
            appMetadata = postData["metadata"]
            appMetadata_str = json.dumps(appMetadata) 

        ##### create dbObject
        dbObject = {}
        for key in valid_fields_set:
            dbObject[key] = ""

        dbObject["name"] = f'{appUser}/{appName}'
        dbObject["architecture"] = architecture_str
        dbObject["inputs"] = appInputs_str
        dbObject["metadata"] = appMetadata_str
        #copy fields
        for key in ["description", "version", "source"]:
            dbObject[key] = postData[key]

        dbObject["owner"] = "unknown"
        
        # create INSERT statment dynamically
        values =[]
        variables = []
        for key in dbFields:
            values.append(dbObject[key])
            variables.append("%s")

        variables_str = ",".join(variables)

        newID = uuid.uuid4()
        newID_str = str(newID)
        stmt = f'INSERT INTO Apps ( id, {dbFields_str}) VALUES (UUID_TO_BIN(%s) ,{variables_str})'
        print(f'stmt: {stmt}', file=sys.stderr)
        
        ecr_db = EcrDB()
        
        
        ecr_db.cur.execute(stmt, (newID_str, *values))
      
        ecr_db.db.commit()
        #print(f'row: {row}', file=sys.stderr)

        #dbObject["id"] = newID

        #content = {} 
        #content["data"] = dbObject
        
        returnObj=ecr_db.getApp(newID_str)
        


        #args = parser.parse_args()
        return returnObj
    

class Apps(MethodView):
    def get(self, app_id):

        # example:  curl localhost:5000/app/{}

        ecr_db = EcrDB()


        returnObj=ecr_db.getApp(app_id)

        return returnObj

class Base(MethodView):
    def get(self):

        # example:  curl localhost:5000/

        return "SAGE Edge Code Repository"

        
app.add_url_rule('/', view_func=Base.as_view('appsBase'))
app.add_url_rule('/apps', view_func=AppList.as_view('appsListAPI'))
app.add_url_rule('/apps/<string:app_id>', view_func=Apps.as_view('appsAPI'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')