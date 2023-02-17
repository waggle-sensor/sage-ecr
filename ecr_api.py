#!/usr/bin/env python3


# ### mysqlclient ###
# pip install mysqlclient
# https://github.com/PyMySQL/mysqlclient-python
# https://mysqlclient.readthedocs.io/

import os
import sys
import logging

from flask import Flask
from flask_cors import CORS
from flask.views import MethodView


import MySQLdb
from flask import request, abort, jsonify


import re
#import uuid
import json
import time

import werkzeug
from werkzeug.wrappers import Request, Response, ResponseStream
from middleware import middleware
import requests

from error_response import ErrorResponse, ErrorWResponse

import jenkins_server

import xmltodict
import sys
from decorators import *

import config
import yaml
import base64

from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.exceptions import HTTPException

from prometheus_client import Counter, make_wsgi_app

import subprocess
import tempfile
import boto3
from botocore.exceptions import ClientError
import authenticators
from token_cache import TokenCache

RAW_GITHUB_URL = 'https://raw.githubusercontent.com'
DEFAULT_BRANCH = 'main'


app_submission_counter = Counter("app_submission_counter", "This metric counts the total number of successful app submissions.")
build_request_counter = Counter("build_request_counter", "This metric counts the total number of requested builds.")

# TODO(sean) make this part of the app config to allow selecting static for testing and sage for deployment.
if config.auth_method == "static":
    app_authenticator = authenticators.StaticAuthenticator(config.static_tokens)
elif config.auth_method == "sage":
    app_authenticator = authenticators.SageAuthenticator(url=config.tokenInfoEndpoint, password=config.tokenInfoPassword)
else:
    raise RuntimeError("invalid authenticator")

token_cache = TokenCache(
    host=config.redis_host,
    port=config.redis_port,
    ttl_seconds=config.redis_ttl_seconds,
)

class ECRAuthMiddleware:

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response): # pragma: no cover
        app.logger.info("auth middleware: starting request")

        request = Request(environ)

        try:
            authHeader = request.headers["Authorization"]
        except KeyError:
            app.logger.info("auth middleware: no auth provided")
            environ['authenticated'] = False
            return self.app(environ, start_response)

        authHeaderArray = authHeader.split(maxsplit=2)

        if len(authHeaderArray) != 2:
            app.logger.info("auth middleware: bad auth header size")
            return ErrorWResponse(f'Authorization failed (could not parse Authorization header)', status_code=HTTPStatus.UNAUTHORIZED)(environ, start_response)

        bearer, token = authHeaderArray
        bearer = bearer.lower()

        if bearer not in ["sage", "static"]:
            app.logger.info("auth middleware: bad realm")
            return ErrorWResponse(f'Authorization failed (Authorization bearer not supported)', status_code=HTTPStatus.UNAUTHORIZED)(environ, start_response)

        app.logger.info("auth middleware: getting token info")

        try:
            token_info = self.get_token_info_with_caching(token)
        except authenticators.TokenNotFound:
            return ErrorWResponse('Token not found', status_code=HTTPStatus.UNAUTHORIZED)(environ, start_response)

        app.logger.info("auth middleware: request authenticated as %s", token_info.user)
        environ['authenticated'] = True
        environ['user'] = token_info.user
        environ['scopes'] = token_info.scopes
        environ['is_admin'] = token_info.is_admin
        environ['is_approved'] = token_info.is_approved

        return self.app(environ, start_response)

    def get_token_info_with_caching(self, token):
        try:
            token_info = token_cache.get(token)
            app.logger.info("auth middleware: using cached token for %s", token_info.user)
            return token_info
        except KeyError:
            pass

        app.logger.info("auth middleware: requesting token")
        token_info = app_authenticator.get_token_info(token)

        app.logger.info("auth middleware: updating cached token for %s", token_info.user)
        token_cache.set(token, token_info)

        return token_info


def run_command_communicate(command, input_str=None, cwd=None, timeout=None):
    try:
        p = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except Exception as e:
        raise Exception(f"subprocess.Popen: {str(e)}")

    # returns output_stdout,output_stderr
    input=None
    if input_str:
        input=input_str.encode()

    try:
        stdout, stderr =  p.communicate(input=input, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        p.kill()
        raise e

    exit_code = p.wait()
    return stdout, stderr , exit_code



def preprocess_repository(url, branchOrTag, custom_version, namespace, repository):
    version = ""
    git_hash_long = ""

    temp_dir = config.ecr_temp_dir

    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    wait_count = 0

    with tempfile.TemporaryDirectory(dir=temp_dir) as tmpdirname:
        app.logger.debug(f"tmpdirname: {tmpdirname}")

        subprocess.run(["git", "clone", "--recursive", "-b", branchOrTag, url, str(tmpdirname)], env={"GIT_TERMINAL_PROMPT": "0"}, timeout=600, check=True, capture_output=True)

        #best solution, returns "0.0.0-0-g60c72a2" , or "g60c72a2"
        command = ["git", "describe", "--always", "--tags", "--long"]
        stdout, stderr , exit_code = run_command_communicate(command, cwd=tmpdirname)
        stdout_str = ""
        if stdout:
            stdout_str = stdout.decode("utf-8")
        if exit_code != 0 :

            stderr_str = ""

            if stderr:
                stderr_str = stderr.decode("utf-8")
            raise Exception(f"Extracting version number failed (stdout={ stdout_str }, stderr={stderr_str}, tmpdirname={tmpdirname})")


        version  = stdout_str.split('\n')[0]
        if len(version) == 8 or len(version) == 7:
            pass
        elif len(version) > 8:
            # example format "0.0.0-0-g60c72a2"
            version_ar  = version.split('-')
            if len(version_ar) != 3:
                raise Exception(f"Could not parse version string {version}")
            version = version_ar[0] + "-" + version_ar[1]

        else:
            raise Exception(f"Could not parse version string {version}")


        # git rev-parse HEAD for long git commit
        command = ["git", "rev-parse", "HEAD"]
        stdout, stderr , exit_code = run_command_communicate(command, cwd=tmpdirname)
        stdout_str = ""
        if stdout:
            stdout_str = stdout.decode("utf-8")
        if exit_code != 0 :

            stderr_str = ""

            if stderr:
                stderr_str = stderr.decode("utf-8")
            raise Exception(f"Extracting hash number failed (stdout={ stdout_str }, stderr={stderr_str}, tmpdirname={tmpdirname})")

        git_hash_long = stdout_str.split('\n')[0]

        if len(git_hash_long) != 40:
            raise Exception(f"git hash has wrong format ({git_hash_long})")


        final_version = ""
        if custom_version:
            final_version = custom_version
        else:
            final_version = version

        # tar -czvf file.tar.gz directory
        target_gzip = f"{temp_dir}/{namespace}_{repository}_{final_version}.tgz"
        command = ["tar", "-czvf", target_gzip, "."]
        stdout, stderr , exit_code = run_command_communicate(command, cwd=tmpdirname)
        stdout_str = ""
        if stdout:
            stdout_str = stdout.decode("utf-8")
        if exit_code != 0 :

            stderr_str = ""

            if stderr:
                stderr_str = stderr.decode("utf-8")
            raise Exception(f"Creating archive failed (stdout={ stdout_str }, stderr={stderr_str}, tmpdirname={tmpdirname})")

        # TODO upload (and store link (better: no link needed if filename is unique))

        if config.S3_ENDPOINT:
            s3_client = boto3.client(
                's3',
                endpoint_url=config.S3_ENDPOINT,
                aws_access_key_id=config.S3_ACCESS_KEY,
                aws_secret_access_key=config.S3_SECRET_KEY
            )

            object_name = f"{config.S3_FOLDER}/{namespace}/{repository}/{namespace}_{repository}_{final_version}.tgz"

            try:
                s3_client.upload_file(target_gzip, config.S3_BUCKET, object_name)
            except Exception as e:
                raise Exception(f"Upload to S3 failed ({str(e)})")





        # clean-up
        os.remove(target_gzip)


    return version, git_hash_long





def submit_app(requestUser, isAdmin, force_overwrite, postData, namespace=None, repository=None, version=None):

    ecr_db = ecrdb.EcrDB()

    ### namespace
    # check if namespace exists (create if not) and check permissions
    userHasNamespaceWritePermission = False
    if not namespace:
        namespace = postData.get("namespace", "")

    if not namespace:
        raise Exception("namespace missing")

    _, ok = ecr_db.getNamespace(namespace)
    if not ok:
        # namespace does not exist. Unless sage assigns usernames, any available namespace can be used
        try:
            ecr_db.addNamespace(namespace, requestUser)
        except Exception as e:
            raise Exception(f'Could not create namespace {namespace}: {str(e)}')
        userHasNamespaceWritePermission = True

    else:
        # Namespace exists. Check if User has permission to write.
        # If not, user may still have permission to write to existing Repo.

        userHasNamespaceWritePermission = ecr_db.hasPermission("namespace", namespace, "USER", requestUser, "WRITE")


    ### repository (app name, without version)
    if not repository:
        repository = postData.get("name", "")
    if not repository:
        raise Exception("repository name missing")

    # check if exists, create if needed
    _, ok = ecr_db.getRepository(namespace, repository)
    if not ok:
        # namespace does not exist. Unless sage assigns usernames, any available namespace can be used
        if userHasNamespaceWritePermission:
            try:
                ecr_db.addRepository(namespace, repository, requestUser)
            except Exception as e:
                raise Exception(f'Could not create repository {namespace}/{repository}: {str(e)}')
        else:
            raise ErrorResponse(f'Not authorized to access namespace {namespace}', status_code=HTTPStatus.UNAUTHORIZED)


    else:
        # repo exists, check if user has namespace or repo permission
        userHasRepoWritePermission = ecr_db.hasPermission("repository", f'{namespace}/{repository}', "USER", requestUser, "WRITE")
        if (not userHasNamespaceWritePermission ) and (not userHasRepoWritePermission):
            raise ErrorResponse(f'Not authorized to access repository {namespace}/{repository}', status_code=HTTPStatus.UNAUTHORIZED)

    ### check if versioned app already exists and if it can be overwritten

    if not version:
        version = postData.get("version", "")

    if version:  # if not, version will be extracted from git repo
        try:
            existing_app, found_app = ecr_db.listApps(user=requestUser, namespace=namespace, repository=repository, version=version)
        except Exception as e:
            raise Exception(f"ecr_db.listApps failed: {str(e)}")

        if found_app:
            raise Exception(f'App {namespace}/{repository}:{version} already exists.')


    # check if required fields are there

    for key in config.required_fields:
        if not key in postData:
            #return  {"error": f'Required field {key} is missing'}
            raise Exception(f'Required field {key} is missing')
        expected_type = config.required_fields[key]

        if not key in postData:
            raise Exception(f"key {key} is missing")

        value  = postData[key]
        if type(value).__name__ != expected_type :
            raise Exception(f'Field {key} has to be of type {expected_type}, got {type(value).__name__}')

        if len(value) == 0:
            #return  {"error": f'Required field {key} is missing'}
            raise Exception(f'Required field {key} is missing')


    # check for invalid fields
    for key in postData:
        if not key in config.valid_fields_set:
            #return  {"error": f'Field {key} not supported'}
            raise Exception(f'Field {key} not supported')

    ##### source
    # source
    # git@github.com:<user>/<repo>.git#<tag>
    # https://github.com/<user>/<repo>.git#<tag>
    # http://sagecontinuum.org/bucket/<bucket_id>


    build_source = postData.get("source",None)
    #sourcesArray = postData.get("source",[])
    #if len(sourcesArray) == 0:
    if not build_source:
        raise Exception("Field source is missing")



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

    for app_input in appInputs:
        for field in app_input:
            if not  field in  config.input_fields_valid:
                raise Exception(f'Input field {field} not supported')

        for expected in config.input_fields_expected:
            if not  expected in  app_input:
                raise Exception(f'Expected field {expected} missing')
            input_type = app_input["type"]
            if not input_type in config.input_valid_types:
                raise Exception(f'Input type {input_type} not supported')

    appInputs_str = json.dumps(appInputs)

    ##### resources

    #resources_str = None
    resourcesArray = postData.get("resources", [])
    if not isinstance(resourcesArray, list):
        raise Exception(f'Field resources has to be an array')

        #resources_str = json.dumps(resourcesArray)

    ##### metadata
    try:
        appMetadata = postData.get("metadata", {})
    except Exception:
        raise Exception(f'Could not retrieve metadata')

    if not isinstance(appMetadata, dict):
        raise Exception("metadata has to be an object")

    url = build_source.get("url") or ""
    if url == "":
        raise Exception("url missing in source")

    tag = build_source.get("tag") or ""
    branch = build_source.get("branch") or ""

    if branch == "" and tag == "":
        raise Exception("Neither tag nor branch specified")

    branch_or_tag = ""
    if tag != "":
        branch_or_tag = tag
    else:
        branch_or_tag = branch


    ### git clone, extract info, create archive, upload
    extracted_version, git_commit = preprocess_repository(url, branch_or_tag, version, namespace, repository)

    existing_app_id = None

    if not version:
        version = extracted_version

        try:
            existing_app, found_app = ecr_db.listApps(user=requestUser, namespace=namespace, repository=repository, version=version)
        except Exception as e:
            raise Exception(f"ecr_db.listApps failed: {str(e)}")


        if found_app:
            if (existing_app.get("frozen", False) and (not isAdmin)):
                raise Exception(f'App {namespace}/{repository}:{version} already exists and is frozen.')

            if not force_overwrite:
                raise Exception(f'App {namespace}/{repository}:{version} already exists but is not frozen. Use query force=true to overwrite.')

            existing_app_id = existing_app.get("id")




    ##### create dbObject
    dbObject = {}

    for key in config.valid_fields_set:
        dbObject[key] = ""


    dbObject["metadata"] = json.dumps(appMetadata) # should at least be an empty dictionary
    dbObject["namespace"] = namespace
    dbObject["name"] = repository
    dbObject["version"] = version

    dbObject["inputs"] = appInputs_str

    #copy fields
    for key in ["description", "keywords", "authors", "collaborators", "homepage", "funding", "license"]:
        dbObject[key] = postData.get(key, "")



    dbObject["frozen"] = postData.get("frozen", False)
    dbObject["owner"] = requestUser

    id_str = ""
    if existing_app_id:
        id_str = existing_app_id
    else:
        #newID = uuid.uuid4()
        #id_str = str(newID)
        id_str = f'{namespace}/{repository}:{version}'

    dbObject["id"] = id_str

    # create INSERT statement dynamically
    values =[]
    col_names = []
    variables = []
    #for key in config.mysql_Apps_fields.keys():
    for key in config.valid_fields + ["id", "owner"]:
        #print(f"key: {key} value: {dbObject[key]}", file=sys.stderr)
        if not key in config.mysql_Apps_fields:
            continue
        if not key in dbObject:
            raise Exception(f"key {key} not in dbObject")
        values.append(dbObject[key])
        col_names.append(key)
        variables.append("%s")

    variables_str = ",".join(variables)
    col_names_str = ",".join(col_names)

    ecr_db = ecrdb.EcrDB()


    #for build_source in sourcesArray:

    architectures_array = build_source.get("architectures", [])

    if len(architectures_array) == 0:
        raise Exception("architectures missing in source")

    ##### architecture


    for arch in architectures_array:
        if not arch in config.architecture_valid:
            valid_arch_str = ",".join(config.architecture_valid)
            raise Exception(f'Architecture {arch} not supported, valid values: {valid_arch_str}')



    architectures = json.dumps(architectures_array)




    directory = build_source.get("directory") or "."
    dockerfile = build_source.get("dockerfile") or "Dockerfile"


    build_args_dict = build_source.get("build_args", {})
    if not isinstance(build_args_dict, dict):
        raise Exception(f'build_args needs to be a dictionary')

    for key in build_args_dict:
        value = build_args_dict[key]
        if not isinstance(value, str):
            raise Exception(f'build_args values have to be strings')

    build_args_str = json.dumps(build_args_dict)

    sources_values = [id_str, architectures , url, branch, tag, git_commit, directory, dockerfile, build_args_str]

    try:
        ecr_db.insertApp(col_names_str, values, variables_str, sources_values, resourcesArray)
    except Exception as e:
        raise Exception(f"insertApp returned: {type(e).__name__},{str(e)}")

    #dbObject["id"] = newID

    #content = {}
    #content["data"] = dbObject

    returnObj, ok=ecr_db.listApps(user=requestUser, namespace=namespace, repository=repository, version=version, isAdmin=isAdmin)
    #returnObj, ok=ecr_db.getApp(id_str)
    if not ok:
        raise Exception(f'app not found after inserting, something went wrong')


    # save meta files
    try:
        import_meta_files(returnObj, namespace=namespace, repository=repository, version=version)
    except Exception as e:
        raise Exception(f'import_meta_files failed: {str(e)}')

    app_submission_counter.inc(1)



    #args = parser.parse_args()
    return returnObj

# /apps
class Submit(MethodView):

    @login_required
    def post(self):
        app.logger.info("submit: processing request")
        requestUser = request.environ.get('user', "")
        isAdmin = request.environ.get('is_admin', False)
        force_overwrite = request.args.get("force", "").lower() in ["true", "1"]

        app.logger.info("submit: trying to load app spec as json")
        postData = request.get_json(force=True, silent=True)

        if not postData:
            app.logger.info("submit: trying to load app spec as yaml")
            # try yaml
            yaml_str = request.get_data().decode()
            postData = yaml.safe_load(yaml_str)

        if not postData:
            app.logger.info("submit: could not load app spec")
            raise ErrorResponse(f'Could not parse app spec', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        try:
            app.logger.info("submit: submitting app")
            return_obj = submit_app(requestUser, isAdmin, force_overwrite, postData)
        except subprocess.TimeoutExpired as e:
            app.logger.error("submit: submitting app timed")
            raise ErrorResponse(f'{str(e)}', status_code=HTTPStatus.REQUEST_TIMEOUT)
        except ErrorResponse as e:
            app.logger.error("submit: submitting app error response")
            raise e
        except Exception as e:
            app.logger.exception("submit: submitting app exception")
            raise ErrorResponse(f'{str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        app.logger.info("submit: success")
        return jsonify(return_obj)


def import_meta_files(app_obj, namespace=None, repository=None, version=None):
    ecr_db = ecrdb.EcrDB()

    # use app source.url as source of meta files; todo(nc): support tags
    repo_url = app_obj['source']['url']
    branch = app_obj['source'].get('branch', DEFAULT_BRANCH)

    # parse github username/repo_name
    if 'git@github.com:' in repo_url:
        repo_path = repo_url.split(':')[1].replace('.git', '')
    else:
        repo_path = '/'.join(repo_url.split('/')[3:]).replace('.git', '')

    meta_path = f'{RAW_GITHUB_URL}/{repo_path}/{branch}/ecr-meta'

    # files we'll grab from github and their associated kind
    file_dicts = [{
        'name': 'ecr-icon.jpg',
        'kind': 'thumb'
    }, {
        'name': 'ecr-science-image.jpg',
        'kind': 'image'
    }, {
        'name': 'ecr-science-description.md',
        'kind': 'science_description'
    }]

    for f_dict in file_dicts:
        f_name = f_dict['name']
        kind = f_dict['kind']

        url = f'{meta_path}/{f_name}'
        res = requests.get(url)

        if res.status_code != 200:
            continue

        blob = res.content

        # insert the data
        ecr_db.addMetaFile(namespace, repository, version, f_name, blob, kind)




# /apps/<string:namespace>/<string:repository>/<string:version>
class Apps(MethodView):

    @login_required
    @has_resource_permission("FULL_CONTROL")
    def delete(self, namespace, repository, version):
        isAdmin = request.environ.get('is_admin', False)
        requestUser = request.environ.get('user', "")

        ecr_db = ecrdb.EcrDB()
        try:
            ecr_db.deleteApp(user=requestUser, isAdmin=isAdmin, namespace=namespace, repository=repository, version=version, force=isAdmin)
        except Exception as e:
            app.logger.error("failed to delete app %s/%s:%s by %s: %s", namespace, repository, version, requestUser, e)
            # TODO(sean) use different error codes to indicate why request failed: 401 vs 403 vs 404 vs 5xx
            raise ErrorResponse(f'Error deleting app: {e}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        return jsonify({"deleted": 1})

    @has_resource_permission("READ")
    def get(self, namespace, repository, version):
        requestUser = request.environ.get('user', "")
        isAdmin = request.environ.get('is_admin', False)

        view = request.args.get('view', "")


        ecr_db = ecrdb.EcrDB()

        #returnObj, ok=ecr_db.getApp(namespace=namespace, name=repository, version=version)

        returnObj, ok =ecr_db.listApps(user=requestUser, namespace=namespace, repository=repository, version=version, isAdmin=isAdmin, view=view)
        if not ok:
            raise ErrorResponse(f'App not found', status_code=HTTPStatus.NOT_FOUND)


        return jsonify(returnObj)


    @has_resource_permission("WRITE")
    def put(self, namespace, repository, version):
        ecr_db = ecrdb.EcrDB()

        if "frozen" in request.args:
            frozen = (request.args.get("frozen", "") in ["true", "1"])

            if not isinstance(frozen, bool):
                raise ErrorResponse(f'frozen is not bool', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

            result = ecr_db.setAppField(namespace, repository, version, "frozen", frozen)
            result_obj = {"modified": result}
        else:
            raise ErrorResponse(f'Not sure what to do', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        return jsonify(result_obj)

    # auth disabled because user can create namespace
    # @has_resource_permission("WRITE")
    def post(self, namespace, repository, version):
        app.logger.info("POST apps")
        requestUser = request.environ.get('user', "")
        isAdmin = request.environ.get('is_admin', False)

        force_overwrite = request.args.get("force", "").lower() in ["true", "1"]

        postData = request.get_json(force=True, silent=True)
        if not postData:
            # try yaml
            yaml_str = request.get_data().decode("utf-8")
            print(f"yaml_str: {yaml_str} ", file=sys.stderr)
            postData = yaml.load(yaml_str , Loader=yaml.FullLoader)

        if not postData:
            raise ErrorResponse(f'Could not parse app spec', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


        # save yaml
        try:
            app_obj = submit_app(requestUser, isAdmin, force_overwrite, postData, namespace=namespace, repository=repository, version=version)
        except ErrorResponse as e:
            raise e
        except Exception as e:
            raise ErrorResponse(f'{str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)



        return jsonify(app_obj)



# Lists all apps, the user has permission to see
# /apps
class AppsGlobal(MethodView):
    # simulate many submissions
    # for i in {1..10} ; do cat ./example_app.yaml | sed -e "s/version :.*/version: \"${i}.0\"/" | curl -X POST ${ECR_API}/submit -H "Authorization: sage ${SAGE_USER_TOKEN}" --data-binary  @- ; done

    def get(self, namespace=None, repository=None, version=None):
        requestUser = request.environ.get('user', "")
        isAdmin = request.environ.get('is_admin', False)


        limit = request.args.get('limit', 1000)
        if limit:
            limit = int(limit)
            if limit > 1000:
                limit = 1000

        continueT = request.args.get('continue', None)

        ecr_db = ecrdb.EcrDB()

        filter = {}
        filter["public"] = request.args.get('public', "") in ["true", "1"]
        filter["shared"] = request.args.get('shared', "") in ["true", "1"]
        filter["owner"] = request.args.get('owner', "") in ["true", "1"]

        view = request.args.get('view', "")

        try:
            returnList=ecr_db.listApps(user=requestUser, namespace=namespace, repository=repository, isAdmin=isAdmin, limit=limit, continuationToken=continueT, filter=filter, view=view)
        except Exception as e:
            raise ErrorResponse(f'listApps returned: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        return_obj = {
                'pagination': {},
                'data': returnList
                }

        if len(returnList) > 0:
            if len(returnList) == limit:
                last = returnList[-1]
                last_id = last["id"]

                return_obj['pagination']['continuationToken'] = base64.b64encode(str.encode(last_id)).decode() # b64 is just to make it look cooler
            else:
                return_obj['pagination']['continuationToken'] = "N/A"

        return jsonify(return_obj)



def get_build(requestUser, isAdmin, namespace, repository, version):
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
    #app_spec, ok = ecr_db.getApp(namespace=namespace, name=repository, version=version)
    app_spec, ok = ecr_db.listApps(user=requestUser , isAdmin=isAdmin, namespace=namespace, repository=repository, version=version)
    if not ok:
        #return {"error":f"app_spec not found {namespace}/{repository}:{version}"}
        return ErrorResponse(f"app_spec not found {namespace}/{repository}:{version}", status_code=HTTPStatus.NOT_FOUND)
    app_id = app_spec.get("id", "")
    if not app_id:
        return ErrorResponse(f"app id not found", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
        #return {"error":"app not found"}



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



def build_app(requestUser, isAdmin, namespace, repository, version, skip_image_push=False):
    host = config.jenkins_server
    username = config.jenkins_user
    password = config.jenkins_token

    try:
        app.logger.info("build_app: connecting to %s as %s", host, username)
        js = jenkins_server.JenkinsServer(host, username, password)
    except Exception as e:
        app.logger.exception("build_app: failed to connect to jenkins")
        raise ErrorResponse(f'JenkinsServer({host}, {username}) returned: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

    ecr_db = ecrdb.EcrDB()
    app_spec, ok = ecr_db.listApps(user=requestUser , namespace=namespace, repository=repository, version=version, isAdmin=isAdmin)
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
        js.createJob(app_human_id, app_spec, overwrite=overwrite, skip_image_push=skip_image_push)
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
        requestUser = request.environ.get('user', "")
        isAdmin = request.environ.get('is_admin', False)

        try:
            result = get_build(requestUser,isAdmin, namespace, repository, version)
        except ErrorResponse as e:
            raise e
        except Exception as e:
            raise ErrorResponse(f"get_build returned: {type(e).__name__},{str(e)}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


        return jsonify(result)

    @login_required
    @approval_required
    @has_resource_permission( "FULL_CONTROL" )
    def post(self, namespace, repository, version):
        requestUser = request.environ.get('user', "")
        isAdmin = request.environ.get('is_admin', False)

        skip_image_push = request.args.get('skip_image_push', "") in ["true", "1"]

        result = build_app(requestUser, isAdmin, namespace, repository, version, skip_image_push=skip_image_push)
        return jsonify(result)


# /namespaces
class NamespacesList(MethodView):

    def get(self):


        requestUser = request.environ.get('user', "")


        ecr_db = ecrdb.EcrDB()
        namespaces = ecr_db.listNamespaces(user=requestUser)

        returnObj = {"data":namespaces}
        return jsonify(returnObj)

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
            result = ecr_db.addNamespace(requestNamespace, requestUser)
        except Exception as e:
            raise ErrorResponse(f'Could not create namespace {requestNamespace}: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        return jsonify(result)



# /x/<namespace>
class Namespace(MethodView):

    @has_resource_permission( "READ" )
    def get(self, namespace, repository = None):
        # list repositories

        requestUser = request.environ.get('user', "")

        if not namespace:
            raise ErrorResponse(f'Namespace not found', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

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
        isAdmin = request.environ.get('is_admin', "")

        # check permission
        ecr_db = ecrdb.EcrDB()
        #if (not isAdmin) and (not ecr_db.hasPermission("namespace", namespace, "USER", requestUser, "FULL_CONTROL")):
        #    raise ErrorResponse(f'Not authorized', status_code=HTTPStatus.UNAUTHORIZED)

        # check if empty
        repo_count = ecr_db.countRepositories(namespace)
        if repo_count > 0:
            raise ErrorResponse(f'Namespace is not empty, {repo_count} repositories found', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)



        # delete namespace
        ecr_db.deleteNamespace(namespace)

        return jsonify({"deleted": 1})

class RepositoriesList(MethodView):

    def get(self, namespace=None):

        requestUser = request.environ.get('user', "")

        if not namespace:
            namespace = request.args.get('namespace', None)

        isAdmin = request.environ.get('is_admin', "")

        filter = {}
        filter["public"] = request.args.get('public', "") in ["true", "1"]
        filter["shared"] = request.args.get('shared', "") in ["true", "1"]
        filter["owner"] = request.args.get('owner', "") in ["true", "1"]
        filter["nopublic"] = request.args.get('nopublic', "") in ["true", "1"]

        view = request.args.get('view', "")

        ecr_db = ecrdb.EcrDB()
        repList = ecr_db.listRepositories(user=requestUser, namespace=namespace, isAdmin=isAdmin, filter=filter)


        if view == "permissions":

            perms = ecr_db.getRepoPermissionsByOwner(requestUser)
            perms_dict = {}
            for p in perms:

                r_namespace = p["namespace"]
                r_name = p["name"]

                new_p = {}
                new_p["grantee"] = p.get("Permissions.grantee", "")
                new_p["granteeType"] = p.get("Permissions.granteeType", "")
                new_p["permission"] = p.get("Permissions.permission", "")
                new_p["resourceName"] = p.get("Permissions.resourceName", "")
                new_p["resourceType"] = p.get("Permissions.resourceType", "")

                if r_namespace not in perms_dict:
                    perms_dict[r_namespace] = {}
                if r_name not in perms_dict[r_namespace]:
                    perms_dict[r_namespace][r_name] = []

                perms_dict[r_namespace][r_name].append(new_p)

            for rep in repList:
                r_namespace = rep["namespace"]
                if not r_namespace in perms_dict:
                    continue
                r_name = rep["name"]
                if not r_name in perms_dict[r_namespace]:
                    continue

                rep["permissions"] = perms_dict[r_namespace][r_name]

            #obj = {"data":perms}
            #return jsonify(obj)



        obj = {"data":repList}
        return jsonify(obj)




class Repository(MethodView):
    def get(self, namespace, repository):
        requestUser = request.environ.get('user', "")
        isAdmin = request.environ.get('is_admin', "")

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
        #isAdmin = request.environ.get('is_admin', "")

        ecr_db = ecrdb.EcrDB()

        # check that repository is empty:
        app_count = ecr_db.countApps(namespace,repository)
        if app_count > 0:
            raise ErrorResponse(f'Repository {namespace}/{repository} not empty. It contains {app_count} apps', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


        count = ecr_db.deleteRepository(namespace,repository )

        return jsonify({"deleted": count})




# /permissions/{namespace}
# /permissions/{namespace}/{repository}
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


        try:
            postData = request.get_json(force=True)
        except Exception as e:
            raise ErrorResponse(f'request.get_json returned: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        for key in postData:
            if key not in ["granteeType", "grantee", "permission", "operation"]:
                raise ErrorResponse(f'Key {key} not supported', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)


        if not "operation" in postData:
            raise ErrorResponse(f'Field operation missing', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)



        operation = postData.get("operation", None)
        granteeType = postData.get("granteeType", None)
        grantee = postData.get("grantee", None)
        permission = postData.get("permission", None)

        ecr_db = ecrdb.EcrDB()

        resource_type = "namespace"
        resource_name = namespace

        if repository:
            resource_type = "repository"
            resource_name = f'{namespace}/{repository}'

        if operation == "add":
            for key in ["granteeType", "grantee", "permission", "operation"]:
                if not key in postData:
                    raise ErrorResponse(f'Field {key} missing', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

            try:
                result = ecr_db.addPermission(resource_type, resource_name, granteeType, grantee, permission)
            except Exception as e:
                raise ErrorResponse(f'ecr_db.addPermissionreturned: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

            #result = ecr_db.addPermission(app_id, postData["granteeType"], postData["grantee"], postData["permission"])

            obj= {"added": result }

        elif operation == "delete":
            if repository:

                # repository
                repo_obj , ok = ecr_db.getRepository(namespace, repository)
                if not ok:
                    raise ErrorResponse(f'No owner found for repository {namespace}/{repository}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

                owner = repo_obj["owner_id"]

            else:
                # namespace
                app.logger.debug("namespace")
                n_obj, found = ecr_db.getNamespace(namespace)
                if not found:
                    raise ErrorResponse(f'Namespace {namespace} not found', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

                owner = n_obj["owner_id"]

            try:
                result = ecr_db.deletePermissions(owner, resource_type, resource_name, granteeType=granteeType, grantee=grantee, permission=permission)
            except Exception as e:
                raise ErrorResponse(f'ecr_db.deletePermissions: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

            obj= {"deleted": result }

        else:
            raise ErrorResponse(f'Operation can only be add or delete.', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)



        return jsonify(obj)


# /meta-files/<namespace>/<name>/<version>/<file_name>
class MetaFiles(MethodView):
    def get(self, namespace, name, version, file_name):
        ecr_db = ecrdb.EcrDB()
        return ecr_db.getMetaFile(namespace, name, version, file_name)


# /
class Base(MethodView):

    def get(self):
        return "SAGE Edge Code Repository"


# /healthy
class Healthy(MethodView):
    def get(self):

        # example:  curl localhost:5000/healthy
        try:
            ecr_db = ecrdb.EcrDB(retries=1)
        except Exception as e: # pragma: no cover
            return f'error ({e})'

        return jsonify({"status" : "ok"})

# /archive/<string:namespace>/<string:repository>/<string:version>.tgz
class CodeArchive(MethodView):


    @has_resource_permission( "READ" )
    def get(self, namespace, repository, filename):

        #TODO implement method to download code archive file
        return jsonify({"status" : "hello"})


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

class CatchAll(MethodView):

    def get(self, path):
        raise ErrorResponse(f"Resource not supported", status_code=HTTPStatus.NOT_FOUND)

    def put(self, path):
        raise ErrorResponse(f"Resource not supported", status_code=HTTPStatus.NOT_FOUND)

    def post(self, path):
        raise ErrorResponse(f"Resource not supported", status_code=HTTPStatus.NOT_FOUND)

    def delete(self, path):
        raise ErrorResponse(f"Resource not supported", status_code=HTTPStatus.NOT_FOUND)




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
app.config["MAX_CONTENT_LENGTH"] = 32*1024 # 32K
app.wsgi_app = ECRAuthMiddleware(app.wsgi_app)


@app.errorhandler(ErrorResponse)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.content_type = "application/json"
    return response


app.add_url_rule('/', view_func=Base.as_view('appsBase'))
app.add_url_rule('/healthy', view_func=Healthy.as_view('healthy'), strict_slashes=False)
app.add_url_rule('/submit', view_func=Submit.as_view('submitAPI'), strict_slashes=False)   #  this is a shortcut, replacing POST to /apps/<string:namespace>/<string:repository>

app.add_url_rule('/apps', view_func=AppsGlobal.as_view('appsGlobal'), strict_slashes=False)
app.add_url_rule('/apps/<string:namespace>', view_func=AppsGlobal.as_view('AppsGlobal_namespaces'), strict_slashes=False)
app.add_url_rule('/apps/<string:namespace>/<string:repository>', view_func=AppsGlobal.as_view('AppsGlobal_repo'), strict_slashes=False)
app.add_url_rule('/apps/<string:namespace>/<string:repository>/<string:version>', view_func=Apps.as_view('appsAPI'))

app.add_url_rule('/namespaces', view_func=NamespacesList.as_view('namespacesListAPI'), strict_slashes=False)
app.add_url_rule('/namespaces/<string:namespace>', view_func=Namespace.as_view('namespacesAPI'))

app.add_url_rule('/repositories', view_func=RepositoriesList.as_view('repositoriesListAPI'), strict_slashes=False)
app.add_url_rule('/repositories/<string:namespace>', view_func=RepositoriesList.as_view('repositoryAPI_namespaced'))
app.add_url_rule('/repositories/<string:namespace>/<string:repository>', view_func=Repository.as_view('repositoryAPI'))

app.add_url_rule('/permissions/<string:namespace>/<string:repository>', view_func=Permissions.as_view('permissionsAPI_2'), methods=['GET', 'PUT', 'DELETE'], strict_slashes=False)
app.add_url_rule('/permissions/<string:namespace>', view_func=Permissions.as_view('permissionsAPI_3'), methods=['GET', 'PUT', 'DELETE'], strict_slashes=False)

app.add_url_rule('/builds/<string:namespace>/<string:repository>/<string:version>', view_func=Builds.as_view('buildsAPI'))

app.add_url_rule('/archive/<string:namespace>/<string:repository>/<string:version>.tgz', view_func=CodeArchive.as_view('codeArchiveAPI'))


# endpoint used by docker_auth to verify access rights
app.add_url_rule('/authz', view_func=AuthZ.as_view('authz'))

app.add_url_rule('/<path:path>', view_func=CatchAll.as_view('catchAll'))

app.add_url_rule('/meta-files/<string:namespace>/<string:name>/<string:version>/<string:file_name>', view_func=MetaFiles.as_view('metaFilesAPI'), strict_slashes=False)

app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
    '/metrics': make_wsgi_app()
})

gunicorn_logger = logging.getLogger('gunicorn.error')

app.logger.handlers = gunicorn_logger.handlers
app.logger.setLevel(gunicorn_logger.level)

ecrdb.logger.handlers = gunicorn_logger.handlers
ecrdb.logger.setLevel(gunicorn_logger.level)

authenticators.logger.handlers = gunicorn_logger.handlers
authenticators.logger.setLevel(gunicorn_logger.level)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
