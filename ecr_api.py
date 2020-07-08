#!/usr/bin/env python3


# ### mysqlclient ###
# pip install mysqlclient
# https://github.com/PyMySQL/mysqlclient-python
# https://mysqlclient.readthedocs.io/

import os
import sys


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

from error_response import ErrorResponse

import jenkins_server

import xmltodict
import sys
from decorators import * 

import config



# refs/tags/<tagName> or  refs/heads/<branchName>
#t.substitute({'git_url' : 'https://github.com/sagecontinuum/sage-cli.git'})












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

        if config.auth_disabled:
            # "user:"
            tokenArray = token.split(":")
            if tokenArray[0] != "user" or len(tokenArray) < 2 or  len(tokenArray) > 3:
                res = Response(f'Authorization is disabled but token requires format user:<name>', mimetype= 'text/plain', status=401)
                return res(environ, start_response)

            if len(tokenArray) == 3:
                if tokenArray[2] == "admin":
                    environ['admin'] = True

           # self.authenticated
            environ['authenticated'] = True
            environ['user'] = tokenArray[1]
            return self.app(environ, start_response)
        
        headers = {"Accept":"application/json; indent=4", "Authorization": f"Basic {config.tokenInfoPassword}" , "Content-Type":"application/x-www-form-urlencoded"}
        data=f"token={token}"
        r = requests.post(config.tokenInfoEndpoint, data = data, headers=headers, timeout=5)

        

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
        



# /apps
class AppList(MethodView):
    def get(self):

       
        requestUser = request.environ.get('user', "")


        ecr_db = ecrdb.EcrDB()
        app_list = ecr_db.listApps(user=requestUser)
        return jsonify(app_list) 

    @login_required
    def post(self):
        # example
       
        # curl -X POST localhost:5000/apps -d '{"name" : "testapp", "description": "blabla", "version" : "1.0", "source" :"https://github.com/user/repo.git#v1.0", "inputs": [{"id":"speed" , "type":"int" }] , "metadata": {"my-science-data" : 12345} }'


        # TODO authentication
        # TODO set owner
        
        
        requestUser = request.environ.get('user', "")


        postData = request.get_json(force=True)

        for key in postData:
            if not key in config.valid_fields_set:
                #return  {"error": f'Field {key} not supported'}
                raise ErrorResponse(f'Field {key} not supported', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        # if required
        for key in config.required_fields:
            if not key in postData:
                #return  {"error": f'Required field {key} is missing'}
                raise ErrorResponse(f'Required field {key} is missing', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
            value  = postData[key]
            if len(value) == 0:
                #return  {"error": f'Required field {key} is missing'}
                raise ErrorResponse(f'Required field {key} is missing', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        

        ##### name
        appName = postData.get("name", "")

        appNameArray = appName.split("/", 2)
        if len(appNameArray) > 1:
            raise ErrorResponse(f'Name should not contain a slash', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
      
  
        
        
        vc = '[.a-zA-Z0-9_-]'
        p = re.compile(f'[a-zA-Z0-9_]{vc}+', re.ASCII)
        if not p.match(appName):
            #return  {"error": f'Name can only consist of [0-9a-zA-Z-_.] characters and only start with [0-9a-zA-Z] characters.'}  
            raise ErrorResponse(f'Name can only consist of [0-9a-zA-Z-_.] characters and only start with [0-9a-zA-Z] characters.', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        


    

        ##### source
        # source
        # git@github.com:<user>/<repo>.git#<tag>
        # https://github.com/<user>/<repo>.git#<tag>
        # http://sagecontinuum.org/bucket/<bucket_id>

        

        sourcesArray = postData.get("sources",[])
        if len(sourcesArray) == 0:
            raise ErrorResponse("Field source is missing")



        #source_public_git_pattern = re.compile(f'https://github.com/{vc}+/{vc}+.git#{vc}+')
        #source_private_git_pattern = re.compile(f'git@github.com/{vc}+/{vc}+.git#{vc}+') 
        #source_sage_store_pattern = re.compile(f'http://sagecontinuum.org/bucket/[0-9a-z.]+') 
        #source_matched = False
        #for p in [source_public_git_pattern, source_private_git_pattern , source_sage_store_pattern]:
        #    if p.match(appSource):
        #        source_matched = True
        #        break
        
        #if not source_matched:
        #    raise ErrorResponse('Could not parse source field', status_code=HTTPStatus.INTERNAL_SERVER_ERROR) 

        ##### inputs
        
        # inputs validation
        appInputs = postData.get("inputs", [])
        if len(appInputs) > 0:
            for app_input in appInputs:
                for field in app_input:
                    if not  field in  config.input_fields_valid:
                        raise ErrorResponse(f'Input field {field} not supported', status_code=HTTPStatus.INTERNAL_SERVER_ERROR) 

                for expected in config.input_fields_valid:
                    if not  expected in  app_input:
                        raise ErrorResponse(f'Expected field {expected} missing', status_code=HTTPStatus.INTERNAL_SERVER_ERROR) 
                    input_type = app_input["type"]
                    if not input_type in config.input_valid_types:
                        raise ErrorResponse(f'Input type {input_type} not supported', status_code=HTTPStatus.INTERNAL_SERVER_ERROR) 

            appInputs_str = json.dumps(appInputs) 

        ##### resources

        #resources_str = None
        resourcesArray = postData.get("resources", [])
        if not isinstance(resourcesArray, list):
            raise ErrorResponse(f'Field resources has to be an array', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

            #resources_str = json.dumps(resourcesArray)

        ##### metadata
        appMetadata = postData.get("metadata", None)
        

        

        ##### create dbObject
        dbObject = {}
        
        for key in config.valid_fields_set:
            dbObject[key] = ""
        
        if appMetadata:
            #raise ErrorResponse(f'metadata is missing', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
            if not isinstance(appMetadata, dict):
                raise ErrorResponse(f'Field metadata has to be an object, got {str(appMetadata)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
            dbObject["metadata"] = json.dumps(appMetadata) 
            
 

        dbObject["name"] = appName
        
        dbObject["inputs"] = appInputs_str
        
        #copy fields
        for key in ["description", "version", "namespace"]:
            dbObject[key] = postData[key]

        dbObject["owner"] = requestUser
        
        # create INSERT statment dynamically
        values =[]
        variables = []
        for key in config.dbFields:
            values.append(dbObject[key])
            variables.append("%s")

        variables_str = ",".join(variables)

        newID = uuid.uuid4()
        newID_str = str(newID)
        
        
        ecr_db = ecrdb.EcrDB()
        

        for build_source in sourcesArray:


            source_name = build_source.get("name", "default")
            
            
            architectures_array = build_source.get("architectures", [])
    
            if len(architectures_array) == 0:
                raise ErrorResponse("architectures missing in source")

            ##### architecture
        
        
            for arch in architectures_array:
                if not arch in config.architecture_valid:
                    valid_arch_str = ",".join(config.architecture_valid)
                    raise ErrorResponse(f'Architecture {arch} not supported, valid values: {valid_arch_str}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
                
            

            architectures = json.dumps(architectures_array)    

            url = build_source.get("url", "")
            if url == "":
                raise ErrorResponse("url missing in source")


            branch = build_source.get("branch", "master")
            if branch == "":
                raise ErrorResponse("branch missing in source")


            directory = build_source.get("directory", ".")
            if directory == "":
                directory = "."

            dockerfile = build_source.get("dockerfile", "Dockerfile")
            if dockerfile == "":
                dockerfile = "Dockerfile"


            #appSources = postData["sources"]
            stmt = f'INSERT INTO Sources ( id, name, architectures , url, branch, directory, dockerfile ) VALUES (UUID_TO_BIN(%s) , %s , %s, %s, %s, %s, %s)'
            ecr_db.cur.execute(stmt, (newID_str, source_name, architectures , url, branch, directory, dockerfile,))

       
        for res in resourcesArray:
            res_str = json.dumps(res)
            stmt = f'INSERT INTO Resources ( id, resource) VALUES (UUID_TO_BIN(%s) , %s)'
            ecr_db.cur.execute(stmt, (newID_str, res_str,))
        

        stmt = f'INSERT INTO Apps ( id, {config.dbFields_str}) VALUES (UUID_TO_BIN(%s) ,{variables_str})'
        print(f'stmt: {stmt}', file=sys.stderr)



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
    @login_required
    @has_permission( "FULL_CONTROL" )
    def delete(self, app_id):
        

        ecr_db = ecrdb.EcrDB()


        try:
            ecr_db.deleteApp(app_id)
        except Exception as e:
            raise ErrorResponse(f'Error deleting app: {e}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        return {"deleted": 1}

    @has_permission( "READ", "FULL_CONTROL" )
    def get(self, app_id):


        ecr_db = ecrdb.EcrDB()

        returnObj=ecr_db.getApp(app_id)

        return returnObj




# /apps/{app_id}/builds/
class Builds(MethodView):
    @login_required
    @has_permission( "READ", "FULL_CONTROL" )
    def get(self, app_id):

        try:
            js = jenkins_server.JenkinsServer(host=config.jenkins_server, username=config.jenkins_user, password=config.jenkins_token)
        except Exception as e:
            raise ErrorResponse(f'JenkinsServer({config.jenkins_server}, {config.jenkins_user}) returned: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        source_name= request.values.get("source", "default")
        #source_name = "default"

        # strategy to find last build
        # 1. check db field "number"
        # 2. use global queue id to map to app-specific build number
        # 3. take whatever is reported as last build (IS MISLEADING, returns previous build)

        

        ecr_db = ecrdb.EcrDB()
        app_spec = ecr_db.getApp(app_id)

        app_human_id = createJenkinsName(app_spec, source_name)


        # strategy 1: try to find build number in database

        number = -1
        architectures = ""
        try:
            number, architectures = ecr_db.getBuildInfo(app_id, source_name)
        except Exception as e:
            raise ErrorResponse(f'Could not get build number: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        if number != -1:
            # get Jenkins build info
            try:
                buildInfo = js.server.get_build_info(app_human_id, number)
            except Exception as e:
                raise Exception(f'js.server.get_build_info returned: {str(e)}')
            return buildInfo
            

        return {"error": f"number is negative"}

        # strategy 2: try to use  last_queue_id to find "number"

        # queue_item = None
        # try:
        #     queue_item = js.server.get_queue_item(last_queue_id)   
        # except Exception as e:

        #     if not "does not exist" in str(e):
        #         raise ErrorResponse(f'get_queue_item() returned: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
        

        # if queue_item:

        #     executable= queue_item.get("executable", None)

        #     if not executable:
        #         return {"error": queue_item["why"], "data": queue_item}


        #     executable= queue_item["executable"]
        #     if not "number" in executable:
        #         return {"error": queue_item["why"], "data": queue_item}

        #     number = executable["number"]

        #     ecr_db.setLastBuildID(app_id, last_queue_id, number)
        
        #     verify_last_queue_id, verify_number = ecr_db.getLastBuildID(app_id)

        #     if verify_last_queue_id != last_queue_id:
        #         return {"error": "last_queue_id does not match"}

        #     if verify_number != number:
        #         return {"error": "number does not match"}

        #     buildInfo = js.server.get_build_info(app_human_id, number)
        #     return buildInfo


        
        # return {"error": f"queue_item for id {last_queue_id} not found"}
        #show = request.values.get("show", default="")

        # job_info = js.get_job_info(app_id)
        # #if show=="job_info":
        # #    return job_info

        # lastBuild = job_info["lastBuild"]
        # number= lastBuild["number"]
        
        # ecr_db.setLastBuildID(app_id, last_queue_id, number)


        # buildInfo = js.server.get_build_info(app_human_id, number)
        # return buildInfo


        


        
    
    @login_required
    @has_permission( "FULL_CONTROL" )
    def post(self, app_id):

        host = config.jenkins_server
        username = config.jenkins_user
        password = config.jenkins_token

        try:
            
            js = jenkins_server.JenkinsServer(host, username, password)
        except Exception as e:
            raise ErrorResponse(f'JenkinsServer({host}, {username}) returned: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        ecr_db = ecrdb.EcrDB()
        app_spec = ecr_db.getApp(app_id)


        source_name= request.values.get("source", "default")

        #source_name = "default"

        sources = app_spec.get("sources", [])
        source = None
        for src in sources:
            src_name = src.get("name", "none")
            if src_name == source_name:
                source = src
                break

        if not source:
            raise ErrorResponse(f'No source found in app spec', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        app_human_id = createJenkinsName(app_spec, source_name)
        


        overwrite=False
        if js.hasJenkinsJob(app_human_id):
            overwrite =  True
        
       
        
        
        try:
            js.createJob(app_human_id, app_spec, source_name, overwrite=overwrite)
        except Exception as e:
            raise ErrorResponse(f'createJob() returned: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR) 



        queue_item_number = js.build_job(app_human_id)


        queue_item = None

        # this loop will waitb for Jenkins to return build number
        # note that the previous queue_item_number is a temporary global queue number which will be useless after some time.
        number = -1
        while number == -1:
            time.sleep(2)

            try:
                queue_item = js.server.get_queue_item(queue_item_number)   
            except Exception as e: # pragma: no cover

                if not "does not exist" in str(e):
                    raise ErrorResponse(f'get_queue_item() returned: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
            
            if not queue_item:
                continue
           
            executable=queue_item.get("executable", None)
            if not executable:
                continue

            number = executable.get("number", None)
            if not number: # pragma: no cover
                continue

            break

            

        architectures = source.get("architectures", None)
        if not architectures:
            raise ErrorResponse(f'architectures not specified in source', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        try:
            ecr_db.SaveBuildInfo(app_id, source_name, number, architectures)
        
        except Exception as e:
            raise ErrorResponse(f'error inserting build info for {app_id}, {source_name}, {number} , SaveBuildInfo: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
        #time.sleep(6)

        #queued_item = js.server.get_queue_item(queue_item_number)

        #returnObj = {"queue_item_number":queue_item_number, "queued_item": queued_item}
        #return returnObj
        return {"build_number": number }




# /apps/{app_id}/permissions
class Permissions(MethodView):
    @login_required
    @has_permission( "ACL_READ", "FULL_CONTROL" )
    def get(self, app_id):
        

        ecr_db = ecrdb.EcrDB()
        result = ecr_db.getPermissions(app_id)
        
        return jsonify(result)

    @login_required
    @has_permission( "ACL_WRITE", "FULL_CONTROL" )
    def put(self, app_id):
        # example to make app public:
        # curl -X PUT localhost:5000/permissions/{id} -H "Authorization: sage user:testuser" -d '{"granteeType": "GROUP", "grantee": "AllUsers", "permission": "READ"}'
       

        postData = request.get_json(force=True)
        for key in ["granteeType", "grantee", "permission"]:
            if not key in postData:
                raise ErrorResponse(f'Field {key} missing', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
        
        
        ecr_db = ecrdb.EcrDB()
        result = ecr_db.addPermission(app_id, postData["granteeType"], postData["grantee"], postData["permission"])
        
        obj= {"added": result }

        return jsonify(obj)

    @login_required
    @has_permission( "ACL_WRITE", "FULL_CONTROL" )
    def delete(self, app_id):
        


        ecr_db = ecrdb.EcrDB()
        
        postData = request.get_json(force=True)
            
        granteeType = postData.get("granteeType", None)
        grantee = postData.get("grantee", None)
        permission = postData.get("permission", None)

        result = ecr_db.deletePermissions(app_id, granteeType, grantee, permission)
        
        obj= {"deleted": result }

        return jsonify(obj)



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
            ecr_db = ecrdb.EcrDB(retries=1)
        except Exception as e: # pragma: no cover
            return f'error ({e})'

        return "ok"




def createJenkinsName(app_spec, source_name):
    import urllib.parse

    namespace = ""
    if "namespace" in app_spec and len(app_spec["namespace"]) > 0:
        namespace = app_spec["namespace"]
    else:
        namespace = app_spec["owner"]
       

    return f'{namespace}_{app_spec["name"]}_{app_spec["version"]}_{source_name}'




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
#app.add_url_rule('/permissions/<string:app_id>', view_func=Permissions.as_view('permissionsAPI'))
app.add_url_rule('/apps/<string:app_id>/permissions', view_func=Permissions.as_view('permissionsAPI'))

app.add_url_rule('/apps/<string:app_id>/builds', view_func=Builds.as_view('buildsAPI'))



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')