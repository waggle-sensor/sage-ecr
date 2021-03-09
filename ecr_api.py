#!/usr/bin/env python3


# ### mysqlclient ###
# pip install mysqlclient
# https://github.com/PyMySQL/mysqlclient-python
# https://mysqlclient.readthedocs.io/

import os
import sys


from flask import Flask
from flask_cors import CORS
from flask.views import MethodView
from flask import jsonify

import MySQLdb
from flask import request
from flask import abort, jsonify

import re
import uuid
import json
import time

import werkzeug
from werkzeug.wrappers import Request, Response, ResponseStream
from middleware import middleware
import requests

from error_response import ErrorResponse

import jenkins_server

import xmltodict
import sys
from decorators import * 

import config
import yaml

from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import HTTPException

from prometheus_client import Counter, make_wsgi_app

app_submission_counter = Counter("app_submission_counter", "This metric counts the total number of successful app submissions.")
build_request_counter = Counter("build_request_counter", "This metric counts the total number of requested builds.")


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

        if authHeaderArray[0].lower() != "sage" and authHeaderArray[0].lower() != "static":
            res = Response(f'Authorization failed (Authorization bearer not supported)', mimetype= 'text/plain', status=401)
            return res(environ, start_response)

        token = authHeaderArray[1]
        if token == "":
            res = Response(f'Authorization failed (token empty)', mimetype= 'text/plain', status=401)
            return res(environ, start_response)

        # example: curl -X POST -H 'Accept: application/json; indent=4' -H "Authorization: Basic c2FnZS1hcGktc2VydmVyOnRlc3Q=" -d 'token=<SAGE-USER-TOKEN>'  <sage-ui-hostname>:80/token_info/
        # https://github.com/sagecontinuum/sage-ui/#token-introspection-api

        
        
        USE_TOKEN_CACHE=False
        ecr_db = None
        user_id = ""
        scopes = ""
        is_admin = False

        # check token cache
        if USE_TOKEN_CACHE:
            ecr_db = ecrdb.EcrDB()
            user_id, scopes , is_admin = ecr_db.getTokenInfo(token)
            if user_id != "":
                print(f'found cached token', file=sys.stderr)
                environ['authenticated'] = True
                environ['user'] = user_id
                return self.app(environ, start_response)

            print(f'did not find cached token...', file=sys.stderr)
        

        if config.auth_method == "static":
            # "user:"
            # tokenArray = token.split(":")
            # if tokenArray[0] != "user" or len(tokenArray) < 2 or  len(tokenArray) > 3:
            #     res = Response(f'Authorization is disabled but token requires format user:<name>', mimetype= 'text/plain', status=401)
            #     return res(environ, start_response)

            # if len(tokenArray) == 3:
            #     if tokenArray[2] == "admin":
            #         environ['admin'] = True
            userObj = config.static_tokens.get(token)
            if not userObj:
                res = Response(f'Token not found', mimetype= 'text/plain', status=401)
                return res(environ, start_response)

            
           


           # self.authenticated
            user_id = userObj.get("id", "")
            if not user_id:
                res = Response(f'id missing in user object', mimetype= 'text/plain', status=401)
                return res(environ, start_response)



            is_admin = userObj.get("is_admin", False)
            scopes = userObj.get("scopes", "")
            

        if config.auth_method == "sage":

            # ask sage token introspection
            headers = {"Accept":"application/json; indent=4", "Authorization": f"Basic {config.tokenInfoPassword}" , "Content-Type":"application/x-www-form-urlencoded"}
            data=f"token={token}"
            r = requests.post(config.tokenInfoEndpoint, data = data, headers=headers, timeout=5)

            

            result_obj = r.json()
            if not "active" in result_obj:
                res = Response(f'Authorization failed (broken response) {result_obj}', mimetype= 'text/plain', status=500)
                return res(environ, start_response)

            is_active = result_obj.get("active", False)
            if not is_active:
                res = Response(f'Authorization failed (token not active)', mimetype= 'text/plain', status=401)
                return res(environ, start_response)
            
            
            
            user_id = result_obj.get("username")
        
        
        if USE_TOKEN_CACHE:
            ecr_db.setTokenInfo(token, user_id, scopes, is_admin)

        if not user_id:
            res= Response("something went wrong, user_id is missing", status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return res(environ, start_response)

        environ['authenticated'] = True
        environ['user'] = user_id
        environ['scopes'] = scopes 
        environ['admin'] = is_admin
        print(f'environ:{environ}', file=sys.stderr)
        return self.app(environ, start_response)

            
        






# /apps
class Submit(MethodView):
    
    @login_required
    def post(self):
        
                
        requestUser = request.environ.get('user', "")
        isAdmin = request.environ.get('admin', False)
        
        
        postData = request.get_json(force=True, silent=True)
        if not postData:
            # try yaml
            yaml_str = request.get_data().decode("utf-8") 
            print(f"yaml_str: {yaml_str} ", file=sys.stderr)
            postData = yaml.load(yaml_str , Loader=yaml.FullLoader)
        
        if not postData:
            raise ErrorResponse(f'Could not parse app spec', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        ecr_db = ecrdb.EcrDB()

        ### namespace
        # check if namespace exists (create if not) and check permissions
        userHasNamespaceWritePermission = False
        namespace = postData.get("namespace", "")
        _, ok = ecr_db.getNamespace(namespace)
        if not ok: 
            # namespace does not exist. Unless sage assigns usernames, any available namespace can be used
            try:
                ecr_db.addNamespace(namespace, requestUser, public=True)
            except Exception as e:
                raise ErrorResponse(f'Could not create namespace {namespace}: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
            userHasNamespaceWritePermission = True

        else: 
            # Namespace exists. Check if User has permission to write.
            # If not, user may still have permission to write to existing Repo.

            userHasNamespaceWritePermission = ecr_db.hasPermission("namespace", namespace, "USER", requestUser, "WRITE")
            

        ### repository (app name, without version)
        repo_name = postData.get("name", "")

        # check if exists, create if needed
        _, ok = ecr_db.getRepository(namespace, repo_name)
        if not ok: 
            # namespace does not exist. Unless sage assigns usernames, any available namespace can be used
            if userHasNamespaceWritePermission:
                try:
                    ecr_db.addRepository(namespace, repo_name, requestUser)
                except Exception as e:
                    raise ErrorResponse(f'Could not create repository {namespace}/{repo_name}: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
            else:
               raise ErrorResponse(f'Not authorized to access namespace {namespace}', status_code=HTTPStatus.UNAUTHORIZED) 


        else: 
            # repo exists, check if user has namespace or repo permission
            userHasRepoWritePermission = ecr_db.hasPermission("repository", f'{namespace}/{repo_name}', "USER", requestUser, "WRITE")
            if (not userHasNamespaceWritePermission ) and (not userHasRepoWritePermission):
                raise ErrorResponse(f'Not authorized to access repository {namespace}/{repo_name}', status_code=HTTPStatus.UNAUTHORIZED)
        
        ### check if versioned app already exists and if it can be overwritten

        version = postData.get("version", "")
        
        existing_app, ok = ecr_db.getApp(namespace=namespace, name=repo_name, version=version)
        

        existing_app_id = None
        if ok:
            if existing_app.get("frozen", False) and (not isAdmin):
                raise ErrorResponse(f'App {namespace}/{repo_name}:{version} already exists and is frozen.', status_code=HTTPStatus.UNAUTHORIZED)

            existing_app_id = existing_app.get("id")

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

        

        


    

        ##### source
        # source
        # git@github.com:<user>/<repo>.git#<tag>
        # https://github.com/<user>/<repo>.git#<tag>
        # http://sagecontinuum.org/bucket/<bucket_id>

        
        build_source = postData.get("source",None)
        #sourcesArray = postData.get("source",[])
        #if len(sourcesArray) == 0:
        if not build_source:
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
            
 

        dbObject["name"] = repo_name
        
        dbObject["inputs"] = appInputs_str
        
        #copy fields
        for key in ["description", "version", "namespace"]:
            dbObject[key] = postData.get(key, "")

        dbObject["frozen"] = postData.get("frozen", False)
        dbObject["owner"] = requestUser
        
        # create INSERT statment dynamically
        values =[]
        variables = []
        for key in config.dbFields:
            print(f"key: {key} value: {dbObject[key]}", file=sys.stderr)
            values.append(dbObject[key])
            variables.append("%s")

        variables_str = ",".join(variables)
        id_str = ""
        if existing_app_id:
            id_str = existing_app_id
        else:
            newID = uuid.uuid4()
            id_str = str(newID)
        
        
        ecr_db = ecrdb.EcrDB()
        

        #for build_source in sourcesArray:


        #source_name = build_source.get("name", "default")
        
        
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

        
        build_args_dict = build_source.get("build_args", {})
        if not isinstance(build_args_dict, dict):
            raise ErrorResponse(f'build_args needs to be a dictonary', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
        
        for key in build_args_dict:
            value = build_args_dict[key]
            if not isinstance(value, str):
                raise ErrorResponse(f'build_args values have to be strings', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


        build_args_str = json.dumps(build_args_dict) 
        
        
        stmt = f'REPLACE INTO Sources ( id, architectures , url, branch, directory, dockerfile, build_args ) VALUES (UUID_TO_BIN(%s) , %s, %s, %s, %s, %s, %s)'
        print(f"replace statement: {stmt}", file=sys.stderr)
        print(f"build_args_str: {build_args_str}", file=sys.stderr)
        ecr_db.cur.execute(stmt, (id_str, architectures , url, branch, directory, dockerfile, build_args_str))

       
        for res in resourcesArray:
            res_str = json.dumps(res)
            stmt = f'REPLACE INTO Resources ( id, resource) VALUES (UUID_TO_BIN(%s) , %s)'
            ecr_db.cur.execute(stmt, (id_str, res_str,))
        

        print(f'values: {values}', file=sys.stderr)

        
        stmt = f'REPLACE INTO Apps ( id, {config.dbFields_str}) VALUES (UUID_TO_BIN(%s) ,{variables_str})'
        print(f'stmt: {stmt}', file=sys.stderr)
        ecr_db.cur.execute(stmt, (id_str, *values))


        

        ecr_db.db.commit()
        #print(f'row: {row}', file=sys.stderr)

        #dbObject["id"] = newID

        #content = {} 
        #content["data"] = dbObject
        
        returnObj, ok=ecr_db.getApp(id_str)
        if not ok:
            raise ErrorResponse(f'app not found', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        app_submission_counter.inc(1)

        #args = parser.parse_args()
        return returnObj
    

# /apps/<string:namespace>/<string:repository>/<string:version>
class Apps(MethodView):
    @login_required
    @has_resource_permission( "FULL_CONTROL" )
    def delete(self, namespace, repository, version):
        
        isAdmin = request.environ.get('admin', False)
        ecr_db = ecrdb.EcrDB()


        try:
            ecr_db.deleteApp(namespace=namespace, repository=repository, version=version, force = isAdmin)
        except Exception as e:
            raise ErrorResponse(f'Error deleting app: {e}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        return {"deleted": 1}

    @has_resource_permission( "READ")
    def get(self, namespace, repository, version):


        ecr_db = ecrdb.EcrDB()

        returnObj, ok=ecr_db.getApp(namespace=namespace, name=repository, version=version)

        if not ok:
            raise ErrorResponse(f'App not found', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        return returnObj



def get_build(namespace, repository, version):
    try:
        js = jenkins_server.JenkinsServer(host=config.jenkins_server, username=config.jenkins_user, password=config.jenkins_token)
    except Exception as e:
        raise ErrorResponse(f'JenkinsServer({config.jenkins_server}, {config.jenkins_user}) returned: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    #source_name= request.values.get("source", "default")
    #source_name = "default"

    # strategy to find last build
    # 1. check db field "number"
    # 2. use global queue id to map to app-specific build number
    # 3. take whatever is reported as last build (IS MISLEADING, returns previous build)

    

    ecr_db = ecrdb.EcrDB()
    app_spec, ok = ecr_db.getApp(namespace=namespace, name=repository, version=version)
    if not ok:
        return {"error":f"app_spec not found {namespace}/{repository}:{version}"}

    app_id = app_spec.get("id", "")
    if not app_id:
        return {"error":"app not found"}

    

    app_human_id = createJenkinsName(app_spec)


    # strategy 1: try to find build number in database

    number = -1
    architectures = ""
    try:
        number, architectures = ecr_db.getBuildInfo(app_id, "some name")
    except Exception as e:
        raise ErrorResponse(f'Could not get build number: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    if number != -1:
        # get Jenkins build info
        try:
            buildInfo = js.server.get_build_info(app_human_id, number)
        except Exception as e:
            raise Exception(f'js.server.get_build_info returned: {str(e)}')
        return buildInfo
            

    #return {"error": f"number is negative"}



def build_app(namespace, repository, version):

    host = config.jenkins_server
    username = config.jenkins_user
    password = config.jenkins_token

    try:
        
        js = jenkins_server.JenkinsServer(host, username, password)
    except Exception as e:
        raise ErrorResponse(f'JenkinsServer({host}, {username}) returned: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    ecr_db = ecrdb.EcrDB()
    app_spec, ok = ecr_db.getApp(namespace=namespace, name=repository, version=version)
    if not ok:
        return {"error":f"app_spec not found {namespace}/{repository}:{version}"}

    app_id = app_spec.get("id", "")
    if not app_id:
        return {"error":"app id not found"}

    source = app_spec.get("source", None)
    if not source:
        return {"error":"source  not found"}
    

    
    app_human_id = createJenkinsName(app_spec)
    


    overwrite=False
    if js.hasJenkinsJob(app_human_id):
        overwrite =  True
    
    
    
    
    try:
        js.createJob(app_human_id, app_spec, overwrite=overwrite)
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

        
    build_name = "some name"
    architectures = source.get("architectures", None)
    if not architectures:
        raise ErrorResponse(f'architectures not specified in source', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    try:
        ecr_db.SaveBuildInfo(app_id, build_name, number, architectures)
    
    except Exception as e:
        raise ErrorResponse(f'error inserting build info for {app_id}, {build_name}, {number} , SaveBuildInfo: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
    
    #time.sleep(6)

    #queued_item = js.server.get_queue_item(queue_item_number)

    #returnObj = {"queue_item_number":queue_item_number, "queued_item": queued_item}
    #return returnObj
    build_request_counter.inc(1)
    return {"build_number": number }

# OLD /apps/{app_id}/builds/
# maybe: /apps/<string:namespace>/<string:repository>/<version>/build
# maybe /build/<string:app_id>
# /builds/<string:namespace>/<string:repository>/<version>
class Builds(MethodView):
    @login_required
    @has_resource_permission( "READ" )  
    #def get(self, app_id):
    def get(self, namespace, repository, version):

        #namespace, repository, version


        result = get_build(namespace, repository, version)

        return result


        
    
    @login_required
    @has_resource_permission( "FULL_CONTROL" )
    def post(self, namespace, repository, version):

       result = build_app(namespace, repository, version)
       return result

# /apps
class NamespacesList(MethodView):

    def get(self):


        requestUser = request.environ.get('user', "")


        ecr_db = ecrdb.EcrDB()
        namespaces = ecr_db.listNamespaces(user=requestUser)

        return jsonify(namespaces) 

    @login_required
    def put(self):

        requestUser = request.environ.get('user', "")
        #requestNamespace = request.environ.get('namespace', "")

        postData = request.get_json(force=True, silent=True)

        if not "id"  in postData:
            raise ErrorResponse(f'Field \"id\" missing in json', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        requestNamespace = postData["id"]

        

        if not requestNamespace:
            raise ErrorResponse(f'Field \"namespace\" missing in request', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        ecr_db = ecrdb.EcrDB()
        
        _, ok = ecr_db.getNamespace(requestNamespace)

        if ok:
            raise ErrorResponse(f'Namespace {requestNamespace} already exists', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        #result = None
        try:
            result = ecr_db.addNamespace(requestNamespace, requestUser, public=True)
        except Exception as e:
            raise ErrorResponse(f'Could not create namespace {requestNamespace}: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        return jsonify(result) 



# /x/<namespace>
class Namespace(MethodView):

    @has_resource_permission( "READ" )
    def get(self, namespace, repository = None):
        # list repositories

        requestUser = request.environ.get('user', "")


        ecr_db = ecrdb.EcrDB()

        nameObj , ok = ecr_db.getNamespace(namespace)
        if not ok:
            raise ErrorResponse(f'Namespace not found', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        repList = ecr_db.listRepositories(user=requestUser, namespace=namespace)

        for rep in repList:
            if rep["namespace"] != namespace:
                raise ErrorResponse(f'Namespace does not match', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        nameObj["type"] = "namespace"
        nameObj["repositories"] = repList
        #app_list = ecr_db.listApps(user=requestUser)
        return jsonify(nameObj) 

    @has_resource_permission( "WRITE" )
    def delete(self, namespace, repository = None):

        requestUser = request.environ.get('user', "")
        isAdmin = request.environ.get('admin', "")

        # check permission
        ecr_db = ecrdb.EcrDB()
        #if (not isAdmin) and (not ecr_db.hasPermission("namespace", namespace, "USER", requestUser, "FULL_CONTROL")):
        #    raise ErrorResponse(f'Not authorized', status_code=HTTPStatus.UNAUTHORIZED)

        # check if empty
        repo_list = ecr_db.listRepositories(namespace=namespace)
        if len(repo_list) > 0:
            raise ErrorResponse(f'Namespace is not empty', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        # delete namespace
        ecr_db.deleteNamespace(namespace)

        return jsonify({"deleted": 1}) 



class Repository(MethodView):
    def get(self, namespace, repository):

       
        requestUser = request.environ.get('user', "")
        isAdmin = request.environ.get('admin', "")

        ecr_db = ecrdb.EcrDB()

        repo_obj ,ok = ecr_db.getRepository(namespace = namespace, name = repository)
        if not ok :
            raise ErrorResponse(f'Repository {namespace}/{repository} not found', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        app_list = ecr_db.listApps(user=requestUser, namespace=namespace, repository=repository, isAdmin=isAdmin)


        repo_obj["versions"] = app_list
        return jsonify(repo_obj) 

    # delete repository (and permissions) if it is empty
    @login_required
    @has_resource_permission( "FULL_CONTROL" )  
    def delete(self, namespace, repository, version=None):

        #requestUser = request.environ.get('user', "")
        #isAdmin = request.environ.get('admin', "")

        ecr_db = ecrdb.EcrDB()

        # check that repository is empty:
        apps = ecr_db.listApps(namespace=namespace,repository=repository)
        if len(apps) > 0:
            raise ErrorResponse(f'Repository {repository} not empty. It contains {len(apps)} apps', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


        ecr_db.deleteRepository(namespace,repository )

        return {"deleted": 1}




# /apps/{app_id}/permissions
class Permissions(MethodView):
    @login_required
    @has_resource_permission( "READ_ACP" )
    def get(self, namespace, repository=None, version=None):
        

        if repository:
            repository_full = f'{namespace}/{repository}'

            ecr_db = ecrdb.EcrDB()
            result = ecr_db.getPermissions("repository", repository_full)
            
            return jsonify(result)

        ecr_db = ecrdb.EcrDB()
        result = ecr_db.getPermissions("namespace", namespace)
            
        return jsonify(result)

    @login_required
    @has_resource_permission( "WRITE_ACP" )
    def put(self, namespace, repository=None, version=None):
        # example to make app public:
        # curl -X PUT localhost:5000/permissions/{id} -H "Authorization: sage token1" -d '{"granteeType": "GROUP", "grantee": "AllUsers", "permission": "READ"}'
       

        postData = request.get_json(force=True)
        for key in ["granteeType", "grantee", "permission"]:
            if not key in postData:
                raise ErrorResponse(f'Field {key} missing', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
        
        
        ecr_db = ecrdb.EcrDB()

        resource_type = "namespace"
        resource_name_full = namespace
        
        if repository:
            resource_type = "repository"
            resource_name_full = f'{namespace}/{repository}'
         

        result = ecr_db.addPermission(resource_type, resource_name_full, postData["granteeType"], postData["grantee"], postData["permission"])

        #result = ecr_db.addPermission(app_id, postData["granteeType"], postData["grantee"], postData["permission"])
        
        obj= {"added": result }

        return jsonify(obj)

        


    @login_required
    @has_resource_permission( "WRITE_ACP" )
    def delete(self, namespace, repository, version=None):
        


        ecr_db = ecrdb.EcrDB()
        
        postData = request.get_json(force=True)

        #requestUser = request.environ.get('user', "")


        repo_obj , ok = ecr_db.getRepository(namespace, repository)
        if not ok:
            raise ErrorResponse(f'No owner found for repository {namespace}/{repository}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)    

        owner = repo_obj["owner_id"]


        granteeType = postData.get("granteeType", None)
        grantee = postData.get("grantee", None)
        permission = postData.get("permission", None)
        
        repository_full = f'{namespace}/{repository}'
        result = ecr_db.deletePermissions(owner, "repository", repository_full, granteeType=granteeType, grantee=grantee, permission=permission)
        
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


# /authz
class AuthZ(MethodView):


    # incoming request that asks if user has permission
    # type AuthRequestInfo struct {
    # 	Account string     `json:"account"`
    # 	Type    string     `json:"type"`
    # 	Name    string     `json:"name"`
    # 	Service string     `json:"service"`
    # 	IP      net.IP     `json:"ip"`
    # 	Actions []string   `json:"actions"`
    # 	Labels  api.Labels `json:"labels"`
    # }

    # example api.AuthRequestInfo
    # ------------
    # Account: <username>
    # Type: repository
    # Name: test/alpine
    # Service: Docker registry
    # IP: 172.20.0.1
    # Actions: pull,push
    # Labels:
    # ------------

    @login_required
    def post(self):

        print(f"AuthZ request received", file=sys.stderr)
        
        user_scopes = request.environ.get('scopes', "")
        user_scopes_array = user_scopes.split()
        if not "ecr_authz_introspection" in user_scopes_array:
            print(f"AuthZ rejected, user is not allowed to ask, got user_scopes: {user_scopes}", file=sys.stderr)
            raise ErrorResponse("User does not have permission to access the introspection", status_code=HTTPStatus.UNAUTHORIZED)

        postData = request.get_json(force=True)
        
        if postData.get("type", "") != "repository":
            print(f"AuthZ rejected, type not supported", file=sys.stderr)
            raise ErrorResponse("This type is not supported", status_code=HTTPStatus.UNAUTHORIZED)

        print(f"AuthZ request object: {postData}", file=sys.stderr)

        actions = postData.get("actions", [])
        request_user_id = postData.get("account", "")
        registry_repository_name = postData.get("name", "")

        
        ecr_db = ecrdb.EcrDB()

        perm_table = {
            "pull" : "READ",
            "push" : "WRITE"
        }

        approved_permissions = []

        
        for act in actions:

            if act == "push" and (not config.docker_registry_push_allowed):
                continue

            asking_permission = perm_table.get(act, "")
            if not asking_permission:
                print(f"AuthZ rejected, action {act} unknown", file=sys.stderr)
                raise ErrorResponse(f"Action {act} unknown", status_code=HTTPStatus.UNAUTHORIZED)

            if ecr_db.hasPermission("repository", registry_repository_name, "USER", request_user_id, asking_permission):
                print(f"AuthZ {act} request approved", file=sys.stderr)
                approved_permissions.append(act)
                continue
            
            print(f"AuthZ {act} request NOT approved", file=sys.stderr)
            
        if len(approved_permissions) == 0:
            raise ErrorResponse(f"No actions approved", status_code=HTTPStatus.UNAUTHORIZED)
        
        response_str = ",".join(approved_permissions)
        print(f"response_str: {response_str}", file=sys.stderr)


        return response_str
        


def createJenkinsName(app_spec):
    import urllib.parse

    namespace = ""
    if "namespace" in app_spec and len(app_spec["namespace"]) > 0:
        namespace = app_spec["namespace"]
    else:
        namespace = app_spec["owner"]
       

    return f'{namespace}.{app_spec["name"]}'




app = Flask(__name__)
CORS(app)
app.config["PROPAGATE_EXCEPTIONS"] = True
app.wsgi_app = ecr_middleware(app.wsgi_app)


@app.errorhandler(ErrorResponse)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


    
#@app.errorhandler(ErrorResponse)
#@app.errorhandler(Exception)
#def handle_invalid_usage(error):
#    print(f"HELLO ***********************************", file=sys.stderr)
#    response = error.get_response()
    #response.data = jsonify(error.to_dict())
    #response.status_code = error.status_code
    #response.content_type = "application/json"
#    return response


#@app.errorhandler(ErrorResponse)
#def resource_not_found(e):
#    return jsonify(error=str(e)), 404



app.add_url_rule('/', view_func=Base.as_view('appsBase'))
app.add_url_rule('/healthy', view_func=Healthy.as_view('healthy'))
app.add_url_rule('/submit', view_func=Submit.as_view('submitAPI'))   #  this is a shortcut, replacing POST to /apps/<string:namespace>/<string:repository>
#app.add_url_rule('/apps/<string:app_id>', view_func=Apps.as_view('appsAPI'))

app.add_url_rule('/apps', view_func=NamespacesList.as_view('namespacesListAPI'))
app.add_url_rule('/apps/<string:namespace>', view_func=Namespace.as_view('namespacesAPI'))
app.add_url_rule('/apps/<string:namespace>/<string:repository>', view_func=Repository.as_view('repositoryAPI'))
app.add_url_rule('/apps/<string:namespace>/<string:repository>/<string:version>', view_func=Apps.as_view('appsAPI'))

app.add_url_rule('/permissions/<string:namespace>/<string:repository>/<string:version>', view_func=Permissions.as_view('permissionsAPI'))
app.add_url_rule('/permissions/<string:namespace>/<string:repository>', view_func=Permissions.as_view('permissionsAPI_2'))
app.add_url_rule('/permissions/<string:namespace>', view_func=Permissions.as_view('permissionsAPI_3'))

#app.add_url_rule('/apps/<string:namespace>/<string:repository>/<version>/build', view_func=Builds.as_view('buildAPI'))

#app.add_url_rule('/permissions/<string:app_id>', view_func=Permissions.as_view('permissionsAPI'))
#app.add_url_rule('/apps/<string:app_id>/permissions', view_func=Permissions.as_view('permissionsAPI'))

app.add_url_rule('/builds/<string:namespace>/<string:repository>/<string:version>', view_func=Builds.as_view('buildsAPI'))

# endpoint used by docker_auth to verify access rights
app.add_url_rule('/authz', view_func=AuthZ.as_view('authz'))



app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})




if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')