#!/usr/bin/env python3

from flask import Flask
from flask.views import MethodView
from flask import jsonify

import MySQLdb
from flask import request
import re
import uuid
import json
import time

from werkzeug.wrappers import Request, Response, ResponseStream
from middleware import middleware
import requests
from http import HTTPStatus

import os
import sys




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


tokenInfoEndpoint = os.getenv('tokenInfoEndpoint')
tokenInfoUser = os.getenv('tokenInfoUser')
tokenInfoPassword = os.getenv('tokenInfoPassword')
auth_disabled = os.getenv('DISABLE_AUTH', default="0") == "1"


# from https://flask.palletsprojects.com/en/1.1.x/patterns/apierrors/
class ErrorResponse(Exception): # pragma: no cover
    status_code = HTTPStatus.BAD_REQUEST 

    def __init__(self, message, status_code=None, payload=None): 
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv



# do token introspection
# from https://medium.com/swlh/creating-middlewares-with-python-flask-166bd03f2fd4
class ecr_middleware():
    '''
    Simple WSGI middleware
    '''

    def __init__(self, app):
        self.app = app
        self.userName = ''
        self.password = ''
        #self.authenticated = False

    def __call__(self, environ, start_response): # pragma: no cover
        # reminder: -H "Authorization: sage ${SAGE_USER_TOKEN}"
        request = Request(environ)
        authHeader = request.headers.get("Authorization", default = "")

        if auth_disabled:
           # self.authenticated
            environ['authenticated'] = True
            environ['user'] = "testuser"
            return self.app(environ, start_response)


        environ['authenticated'] = False
        #print(f"Authorization: {authHeader}", file=sys.stderr)

        if authHeader == "":
            return self.app(environ, start_response)

        authHeaderArray = authHeader.split(" ", 2)
        if len(authHeaderArray) != 2:
            res = Response(f'Authorization failed (could not parse Authorization header)', mimetype= 'text/plain', status=401)
            return res(environ, start_response)

        if authHeaderArray[0].lower() != "sage":
            res = Response(f'Authorization failed (Authorization bearer not supported)', mimetype= 'text/plain', status=401)
            return res(environ, start_response)

        token = authHeaderArray[1]
        if token == "":
            res = Response(f'Authorization failed (token empty)', mimetype= 'text/plain', status=401)
            return res(environ, start_response)


        
        
        
        # example: curl -X POST -H 'Accept: application/json; indent=4' -H "Authorization: Basic c2FnZS1hcGktc2VydmVyOnRlc3Q=" -d 'token=<SAGE-USER-TOKEN>'  <sage-ui-hostname>:80/token_info/
        # https://github.com/sagecontinuum/sage-ui/#token-introspection-api


        headers = {"Accept":"application/json; indent=4", "Authorization": f"Basic {tokenInfoPassword}" , "Content-Type":"application/x-www-form-urlencoded"}
        data=f"token={token}"
        r = requests.post(tokenInfoEndpoint, data = data, headers=headers, timeout=5)

        

        result_obj = r.json()
        if not "active" in result_obj:
            res = Response(f'Authorization failed (broken response) {result_obj}', mimetype= 'text/plain', status=500)
            return res(environ, start_response)

        is_active = result_obj["active"]
        if is_active:
            environ['authenticated'] = True
            environ['user'] = result_obj["username"]
            return self.app(environ, start_response)

        res = Response(f'Authorization failed (token not active)', mimetype= 'text/plain', status=401)
        return res(environ, start_response)
        


class EcrDB():
    def __init__ ( self , retries=60) :
        count = 0
        while True:
            try:
                self.db=MySQLdb.connect(host=mysql_host,user=mysql_user,
                  passwd=mysql_password,db=mysql_db)
            except Exception as e: # pragma: no cover
                if count > retries:
                    raise
                print(f'Could not connnect to database, error={e}, retry in 2 seconds', file=sys.stderr)
                time.sleep(2)
                count += 1
                continue
            break

        self.cur=self.db.cursor()
        return

    def hasPermission(self, app_id, granteeType, grantee, permission):


        stmt = f'SELECT BIN_TO_UUID(id) FROM AppPermissions WHERE BIN_TO_UUID(id) = %s AND granteeType = %s AND grantee = %s AND (permission="FULL_CONTROL" OR permission = %s)'
        print(f'stmt: {stmt} app_id={app_id} granteeType={granteeType} grantee={grantee} permission={permission}', file=sys.stderr)
        self.cur.execute(stmt, (app_id, granteeType, grantee,  permission ))

        row = self.cur.fetchone()
        if row == None:
            #print(f'row empty', file=sys.stderr)
            return False

        if len(row) > 0:
            return True

        #print(f'row len 0', file=sys.stderr)
        return False




    def getApp(self, app_id):
        stmt = f'SELECT  BIN_TO_UUID(id), {dbFields_str} FROM Apps WHERE BIN_TO_UUID(id) = %s'
        print(f'stmt: {stmt} app_id={app_id}', file=sys.stderr)
        self.cur.execute(stmt, (app_id, ))

        returnFields = ["id"] + dbFields
        returnObj={}
        row = self.cur.fetchone()
        i = 0
        if row == None:
            raise ErrorResponse(f'App {app_id} not found', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
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





# /apps
class AppList(MethodView):
    def get(self):
        authenticated = request.environ['authenticated']
        if not authenticated:
            raise ErrorResponse('Not authenticated', status_code=HTTPStatus.UNAUTHORIZED)

        # TODO allow unauthenticated users to get public apps

        ecr_db = EcrDB()
        app_list = ecr_db.listApps()
        return jsonify(app_list) 

    def post(self):
        # example
       
        # curl -X POST localhost:5000/apps -d '{"name" : "testapp", "description": "blabla", "architecture" : ["linux/amd64" , "linux/arm/v7"] , "version" : "1.0", "source" :"https://github.com/user/repo.git#v1.0", "inputs": [{"id":"speed" , "type":"int" }] , "metadata": {"my-science-data" : 12345} }'


        # TODO authentication
        # TODO set owner
        authenticated = request.environ['authenticated']
        if not authenticated:
            raise ErrorResponse('Not authenticated', status_code=HTTPStatus.UNAUTHORIZED)

        
        requestUser = request.environ['user']

        postData = request.get_json(force=True)

        for key in postData:
            if not key in valid_fields_set:
                #return  {"error": f'Field {key} not supported'}
                raise ErrorResponse(f'Field {key} not supported', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        # if required
        for key in required_fields:
            if not key in postData:
                #return  {"error": f'Required field {key} is missing'}
                raise ErrorResponse(f'Required field {key} is missing', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
            value  = postData[key]
            if len(value) == 0:
                #return  {"error": f'Required field {key} is missing'}
                raise ErrorResponse(f'Required field {key} is missing', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        

        ##### name
        appName = postData["name"]
        appNameArray = appName.split("/", 2)
        if len(appNameArray) > 1:
            raise ErrorResponse(f'Name should not contain a slash', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
      
  
        
        
        vc = '[.a-zA-Z0-9_-]'
        p = re.compile(f'[a-zA-Z0-9_]{vc}+', re.ASCII)
        if not p.match(appName):
            #return  {"error": f'Name can only consist of [0-9a-zA-Z-_.] characters and only start with [0-9a-zA-Z] characters.'}  
            raise ErrorResponse(f'Name can only consist of [0-9a-zA-Z-_.] characters and only start with [0-9a-zA-Z] characters.', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        ##### architecture
        
        architecture_str = ""
        if "architecture" in postData:
            appArchitecture  = postData["architecture"]
            for arch in appArchitecture:
                if not arch in architecture_valid:
                    valid_arch_str = ",".join(architecture_valid)
                    #return  {"error": f'Architecture {arch} not supported, valid values: {valid_arch_str}'}
                    raise ErrorResponse(f'Architecture {arch} not supported, valid values: {valid_arch_str}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
                
            architecture_str = ",".join(appArchitecture)


    

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
            raise ErrorResponse('Could not parse source field', status_code=HTTPStatus.INTERNAL_SERVER_ERROR) 

        ##### inputs
        
        # inputs validation
        appInputs = None
        if "inputs" in postData:
            appInputs = postData["inputs"]
            for app_input in appInputs:
                for field in app_input:
                    if not  field in  input_fields_valid:
                        raise ErrorResponse(f'Input field {field} not supported', status_code=HTTPStatus.INTERNAL_SERVER_ERROR) 

                for expected in input_fields_valid:
                    if not  expected in  app_input:
                        raise ErrorResponse(f'Expected field {expected} missing', status_code=HTTPStatus.INTERNAL_SERVER_ERROR) 
                    input_type = app_input["type"]
                    if not input_type in input_valid_types:
                        raise ErrorResponse(f'Input type {input_type} not supported', status_code=HTTPStatus.INTERNAL_SERVER_ERROR) 

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

        dbObject["name"] = appName
        dbObject["architecture"] = architecture_str
        dbObject["inputs"] = appInputs_str
        dbObject["metadata"] = appMetadata_str
        #copy fields
        for key in ["description", "version", "source"]:
            dbObject[key] = postData[key]

        dbObject["owner"] = requestUser
        
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
      
        stmt = f'INSERT INTO AppPermissions ( id, granteeType , grantee, permission) VALUES (UUID_TO_BIN(%s) , %s,  %s, %s)'
        ecr_db.cur.execute(stmt, (newID_str, "USER", requestUser , "FULL_CONTROL"))

        ecr_db.db.commit()
        #print(f'row: {row}', file=sys.stderr)

        #dbObject["id"] = newID

        #content = {} 
        #content["data"] = dbObject
        
        returnObj=ecr_db.getApp(newID_str)
        


        #args = parser.parse_args()
        return returnObj
    

# /apps/{id}
class Apps(MethodView):
    def get(self, app_id):

        # example:  curl localhost:5000/app/{}
        authenticated = request.environ['authenticated']
        if not authenticated:
            raise ErrorResponse('Not authenticated', status_code=HTTPStatus.UNAUTHORIZED)

        # TODO make sure user has permissions to view

        requestUser = request.environ['user']

        ecr_db = EcrDB()


        print(requestUser, file=sys.stderr)
        if not ecr_db.hasPermission(app_id, "USER", requestUser , "READ"):
            raise ErrorResponse(f'Not authorized. ({requestUser})', status_code=HTTPStatus.UNAUTHORIZED)

        returnObj=ecr_db.getApp(app_id)

        return returnObj

# /
class Base(MethodView):
    def get(self):

        # example:  curl localhost:5000/

        return "SAGE Edge Code Repository"

# /healthy
class Healthy(MethodView):
    def get(self):

        # example:  curl localhost:5000/healthy
        try:
            ecr_db = EcrDB(retries=1)
        except Exception as e:
            return f'error ({e})'

        return "ok"


app = Flask(__name__)
app.wsgi_app = ecr_middleware(app.wsgi_app)

@app.errorhandler(ErrorResponse)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

app.add_url_rule('/', view_func=Base.as_view('appsBase'))
app.add_url_rule('/healthy', view_func=Healthy.as_view('healthy'))
app.add_url_rule('/apps', view_func=AppList.as_view('appsListAPI'))
app.add_url_rule('/apps/<string:app_id>', view_func=Apps.as_view('appsAPI'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')