#!/usr/bin/env python3

from flask import Flask
from flask.views import MethodView

import MySQLdb
from flask import request
import re
import uuid

#from flask import g

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







valid_fields =["name", "description", "version", "source", "depends_on", "architecture" , "baseCommand", "arguments", "inputs", "metadata"]
valid_fields_set = set(valid_fields)
required_fields = set(["name", "description", "version", "source"])


class AppList(MethodView):
    def get(self):
        return {'hello': 'world'}

    def post(self):
        # example
        #curl -X POST localhost:5000/apps -d '{"name" : "testapp", "description": "blabla", "version" : "1.0", "source" :"https://github.com/user/repo.git#v1.0"}'

        


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

        # \w = [a-zA-Z0-9_]
        vc = '[.a-zA-Z0-9_-]'
        p = re.compile(f'\w{vc}+', re.ASCII)
        if not p.match(appName):
            return  {"error": f'Name can only consist of [0-9a-zA-Z-_.] characters and only start with [0-9a-zA-Z] characters.'}  

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

        
        # create dbObject
        dbObject = {}
        for key in valid_fields_set:
            dbObject[key] = ""

        dbObject["name"] = f'{appUser}/{appName}'
        #copy fields
        for key in ["description", "version", "source"]:
            dbObject[key] = postData[key]

        dbObject["owner"] = "unknown"
        
        dbFields = valid_fields + ["owner"]

        # create INSERT statment dynamically
        dbFields_str  = ",".join(dbFields)
        values =[]
        variables = []
        for key in dbFields:
            values.append(dbObject[key])
            variables.append("%s")

        variables_str = ",".join(variables)

        newID = uuid.uuid4()
        
        stm = f'INSERT INTO Apps ( id, {dbFields_str}) VALUES (UUID_TO_BIN(%s) ,{variables_str})'
        print(f'stm: {stm}', file=sys.stderr)
        
        db=MySQLdb.connect(host=mysql_host,user=mysql_user,
                  passwd=mysql_password,db=mysql_db)
        
        c=db.cursor()
        c.execute(stm, (newID, *values))

        dbObject["id"] = newID

        content = {} 
        content["data"] = dbObject
        #args = parser.parse_args()
        return content
    

class Apps(MethodView):
    def get(self, app_id):
        return {'hello': 'world'}

    
        

app.add_url_rule('/apps', view_func=AppList.as_view('appsListAPI'))
app.add_url_rule('/apps/<string:app_id>', view_func=Apps.as_view('appsAPI'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')