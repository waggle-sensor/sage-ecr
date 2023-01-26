#!/usr/bin/env python3

import os
import tempfile

import pytest
import sys
from ecr_api import app
#from config import dbFields
import json
import time

import requests
import yaml
from ecrdb import EcrDB



test_app_def_obj = yaml.load(open('example_app.yaml', 'r').read(), Loader=yaml.FullLoader)

test_app_def = json.dumps(test_app_def_obj)


#app_namespace = test_app_def_obj["namespace"]
#app_repository = test_app_def_obj["name"]
#app_version = test_app_def_obj["version"]


def load_app_def(filename):
    with open(filename) as f:
        return yaml.safe_load(f.read())


# from https://flask.palletsprojects.com/en/1.1.x/testing/
@pytest.fixture
def client():
    # WARNING! DO NOT RUN IN PRODUCTION AS DEFAULT CONFIG USES PRODUCTION DATABASE!!!
    db = EcrDB()
    db.deleteAllData()

    with app.test_client() as client:
        #with app.app_context():
        #    init_db()
        yield client


def test_homepage(client):
    rv = client.get('/')
    assert rv.status_code == 200
    assert rv.data == b"SAGE Edge Code Repository"


def test_upload_and_build_success(client):
    """
    Test that successful builds correctly report back to users.
    """
    headers = {"Authorization" : "sage token1"}
    app_yaml = """
name: simple
description: "very important app"
version: "1.0.0"
namespace: sagebuildtest
authors: "Princess Zelda <zelda@hyrule.org>, King Rhoam <rhoam@hyrule.org> (https://hyrule.org)"
keywords: "machine learning, audio, birds, some keyword"
license: "MIT license"
collaborators: "link <link@hyrule.org>"
funding: 'NSF'
homepage: "https://github.com/waggle-sensor/edge-plugins.git"
source:
  url: "https://github.com/waggle-sensor/edge-plugins.git"   # required
  branch: "master"  # optional, default: main  (better use tag instead)
  architectures:
  - "linux/amd64"
  - "linux/arm64"
  #tag: "v0.5"  # recommended
  directory : "plugin-simple"  # optional, default: root of git repository
  dockerfile : "Dockerfile"   # optional, default: Dockerfile , relative to context directory
  build_args: # optional, key-value pairs for docker build
    VARIABLE1: "value1"
resources:  # future feature
- type: "RGB_image_producer"
  view: "top"
  min_resolution: "600x800"
# future feature
inputs:
- id: "speed"
  type: "int"
# custom key-value pairs
metadata:
  my-science-data: 12345
"""

    # submit app
    r = client.post("/submit/", data=app_yaml, headers=headers)
    assert r.status_code == 200
    result = r.get_json()
    assert "error" not in result
    assert "version" in result

    # start build
    r = client.post("/builds/sagebuildtest/simple/1.0.0?skip_image_push=false", headers=headers)
    assert r.status_code == 200
    result = r.get_json()
    assert "error" not in result
    assert "build_number" in result

    # wait for build to finish
    while True:
        r = client.get("/builds/sagebuildtest/simple/1.0.0", headers=headers)
        assert r.status_code == 200
        result = r.get_json()
        assert "error" not in result
        assert "result" in result
        result_status = result["result"]
        if result_status is not None:
            break
        time.sleep(1)

    # build should succeed
    assert result_status == "SUCCESS"

    # build log should indicate success
    assert "url" in result
    build_log_url = result["url"]
    consoleTextURL = f'{build_log_url}/consoleText'
    r = requests.get(consoleTextURL)
    assert "Finished: SUCCESS" in r.text


def test_upload_and_build_failure(client):
    """
    Test that failed builds correctly report back to users. We are intentionally using a missing directory to cause the build to fail.
    """
    headers = {"Authorization" : "sage token1"}
    app_yaml = """
name: failure
description: "very unimportant app"
version: "1.0.0"
namespace: sagebuildtest
source:
  url: "https://github.com/waggle-sensor/edge-plugins.git"
  branch: "master"  # optional, default: main  (better use tag instead)
  architectures:
  - "linux/amd64"
  - "linux/arm64"
  directory : "plugin-should-not-exist-1234123"
"""

    # submit app
    r = client.post("/submit/", data=app_yaml, headers=headers)
    assert r.status_code == 200
    result = r.get_json()
    assert "error" not in result
    assert "version" in result

    # start build
    r = client.post("/builds/sagebuildtest/failure/1.0.0?skip_image_push=false", headers=headers)
    assert r.status_code == 200
    result = r.get_json()
    assert "error" not in result
    assert "build_number" in result

    # wait for build to finish
    while True:
        r = client.get("/builds/sagebuildtest/failure/1.0.0", headers=headers)
        assert r.status_code == 200
        result = r.get_json()
        assert "error" not in result
        assert "result" in result
        result_status = result["result"]
        if result_status is not None:
            break
        time.sleep(1)

    # build should fail
    assert result_status == "FAILURE"

    # build log should indicate failure
    assert "url" in result
    build_log_url = result["url"]
    consoleTextURL = f'{build_log_url}/consoleText'
    r = requests.get(consoleTextURL)
    assert "Finished: FAILURE" in r.text


def test_upload_fail_on_invalid_url(client):
    headers = {"Authorization" : "sage token1"}
    app_yaml = """
name: test_app_fail
description: "an app with an invalid url"
version: "1.0.0"
namespace: sagebuildtest
source:
  url: "https://github.com/waggle-sensor/does_not_exist.git"
  branch: "main"
  architectures:
  - "linux/amd64"
  - "linux/arm64"
"""

    # submit app
    r = client.post("/submit/", data=app_yaml, headers=headers)
    assert r.status_code == 500

    # extract build log
    # assert "url" in result
    # build_log_url = result["url"]
    # consoleTextURL = f'{build_log_url}/consoleText'
    # r = requests.get(consoleTextURL)
    # print("consoleText:", file=sys.stderr)
    # print("--------------------------------------", file=sys.stderr)
    # print(r.text, file=sys.stderr)
    # print("--------------------------------------", file=sys.stderr)
    # assert not "Finished: SUCCESS" in r.text
    # assert ("ERROR: Error cloning remote repo 'origin'" in r.text) or ("ERROR: Error fetching remote repo 'origin'" in r.text)
    # assert result_status == "FAILURE"

    # assert ("ERROR: Error cloning remote repo 'origin'" in r.text) or ("ERROR: Error fetching remote repo 'origin'" in r.text)
    # assert result_status == "FAILURE"


def test_app_upload_multiple(client):
    headers = {"Authorization" : "sage token1"}
    admin_headers = {"Authorization" : "sage admin_token"}

    app_namespace = "sageother"
    app_repository = "simple_other"
    app_version = "1.0"

    #this_test_app = json.dumps(test_app_def_obj)
    this_test_app_obj = json.loads(json.dumps(test_app_def_obj))
    del this_test_app_obj["metadata"]


    # delete app in case app already exists and is frozen
    rv = client.delete(f'/apps/{app_namespace}/{app_repository}/{app_version}', headers=admin_headers)
    result = rv.get_json()

    if "error" in result:
        assert "App not found" in result["error"]
    else:
        assert rv.status_code == 200

    # delete repository:
    rv = client.delete(f'/repositories/{app_namespace}/{app_repository}', headers=admin_headers)
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    assert rv.status_code == 200

    # delete namespace
    rv = client.get(f'/namespaces/{app_namespace}', headers=admin_headers)
    if rv.status_code == 200:
        rv = client.delete(f'/namespaces/{app_namespace}', headers=admin_headers)
        print(f'rv.data: {rv.data}' , file=sys.stderr)
        assert rv.status_code == 200
        result = rv.get_json()
        assert result != None
        assert "error"  not in result

    # create namespace (not needed, but increases test coverage)
    rv = client.put(f'/namespaces', data = json.dumps({"id":app_namespace}), headers=headers)
    print(f'(create namespace) rv.data: {rv.data}' , file=sys.stderr)
    assert rv.data != ""
    assert rv.status_code == 200
    result = rv.get_json()
    assert result != None
    assert "error"  not in result


    # submit
    rv = client.post(f'/apps/{app_namespace}/{app_repository}/{app_version}', data = json.dumps(this_test_app_obj), headers=headers)
    assert rv.data != ""
    print(f'rv.data: {rv.data}' , file=sys.stderr)

    result = rv.get_json()


    assert result != None
    assert "error" not in result
    assert "name" in result
    assert result["name"] ==  app_repository



def test_app_upload_and_download(client):
    """Start with a blank database."""


    headers = {"Authorization" : "sage token1"}
    admin_headers = {"Authorization" : "sage admin_token"}

    app_namespace = "sage"
    app_repository = "simple"
    app_version = "1.0"


    # delete app in case app already exists and is frozen
    rv = client.delete(f'/apps/{app_namespace}/{app_repository}/{app_version}', headers=admin_headers)
    result = rv.get_json()

    if "error" in result:
        assert "App not found" in result["error"]
    else:
        assert rv.status_code == 200

    # delete repository:
    rv = client.delete(f'/repositories/{app_namespace}/{app_repository}', headers=admin_headers)
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    assert rv.status_code == 200

    # delete namespace
    rv = client.get(f'/namespaces/{app_namespace}', headers=admin_headers)
    if rv.status_code == 200:
        rv = client.delete(f'/namespaces/{app_namespace}', headers=admin_headers)
        print(f'rv.data: {rv.data}' , file=sys.stderr)
        assert rv.status_code == 200
        result = rv.get_json()
        assert result != None
        assert "error"  not in result

    # create namespace (not needed, but increases test coverage)
    rv = client.put(f'/namespaces', data = json.dumps({"id":app_namespace}), headers=headers)
    print(f'(create namespace) rv.data: {rv.data}' , file=sys.stderr)
    assert rv.data != ""
    assert rv.status_code == 200
    result = rv.get_json()
    assert result != None
    assert "error"  not in result


    # submit
    rv = client.post(f'/apps/{app_namespace}/{app_repository}/{app_version}', data = test_app_def, headers=headers)
    assert rv.data != ""
    print(f'rv.data: {rv.data}' , file=sys.stderr)

    result = rv.get_json()


    assert result != None
    assert "error" not in result
    assert "name" in result
    assert result["name"] ==  app_repository


    assert "id" in result
    app_id = result["id"]

    # test GET /apps/{app_id}
    ######################################################
    rv = client.get(f'/apps/{app_namespace}/{app_repository}/{app_version}', headers=headers)

    result = rv.get_json()

    assert result != None
    assert "error"  not in result

    assert "name" in result
    assert result["name"] == app_repository

    assert "owner" in result
    assert result["owner"] ==  "testuser"
    assert "id" in result
    app_get_id = result["id"]
    assert app_id == app_get_id


    #for key in dbFields:
    #    assert key in result

    assert len(result["inputs"]) == 1
    assert len(result["inputs"][0]) == 2

    assert "metadata" in result
    assert "my-science-data" in result["metadata"]
    assert result["metadata"]["my-science-data"] == 12345


    rv = client.delete(f'/apps/{app_namespace}/{app_repository}/{app_version}', headers=headers)
    result = rv.get_json()
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    if "error" in result:
        assert "App not found" in result["error"]
    else:
        assert result["deleted"] == 1




def test_list_apps(client):
    headers = {"Authorization" : "sage token1"}
    admin_headers = {"Authorization" : "sage admin_token"}
    headers_testuser2 = {"Authorization" : "sage token2"}

    mars_namespace = "planetmars"

    app_repository = "simple"
    app_version = "1.0"

    #test_app_def_obj["namespace"] = mars_namespace
    #mars_app_def = json.dumps(test_app_def_obj)

    # delete in case app already exists and is frozen
    rv = client.delete(f'/apps/{mars_namespace}/{app_repository}/{app_version}', headers=admin_headers)
    result = rv.get_json()
    if "error" in result:
        assert "App not found" in result["error"]
    else:
        assert result["deleted"] == 1


     # clean-up repo permissions
    data = {"operation":"delete"}
    rv = client.put(f'/permissions/{mars_namespace}/{app_repository}', data=json.dumps(data), headers=admin_headers)

    # clean-up namespace permissions
    rv = client.put(f'/permissions/{mars_namespace}', data=json.dumps(data), headers=admin_headers)


    rv = client.post(f'/apps/{mars_namespace}/{app_repository}/{app_version}', data = test_app_def, headers=headers)
    assert rv.data != ""
    print(f'rv.data: {rv.data}' , file=sys.stderr)

    result = rv.get_json()
    assert "error" not in result
    assert "id" in result
    app_id = result["id"]


    rv = client.get(f'/apps/{mars_namespace}/{app_repository}', headers=headers)
    print(f'get list rv.data: {rv.data}' , file=sys.stderr)
    result = rv.get_json()

    assert "data" in result
    data = result["data"]
    assert len(data) == 1

    found_app = False
    for app in data:
        assert "id" in app
        if app["id"] == app_id:
            found_app = True
            break

    assert found_app

    # List public repositories (in planetmars)
    # query as public user
    rv = client.get(f'/repositories/{mars_namespace}')
    print(f'get list rv.data: {rv.data}' , file=sys.stderr)
    result = rv.get_json()

    assert "data" in result
    assert len(result["data"]) == 0

    # query as user/owner
    rv = client.get(f'/repositories/{mars_namespace}', headers=headers)
    result = rv.get_json()

    assert "data" in result
    assert len(result["data"]) == 1


    # query as user/owner , ask for public repos
    rv = client.get(f'/repositories/{mars_namespace}?public=1', headers=headers)
    result = rv.get_json()

    assert "data" in result
    assert len(result["data"]) == 0

    # query as user/owner , ask for public apps
    rv = client.get(f'/apps/{mars_namespace}?public=1', headers=headers)
    result = rv.get_json()

    assert "data" in result
    assert len(result["data"]) == 0

    ## shared feature

    # check as testuser2 if repo has been shared (via /repositories)
    rv = client.get(f'/repositories/{mars_namespace}?shared=1', headers=headers_testuser2)
    result = rv.get_json()

    assert "data" in result
    assert len(result["data"]) == 0

    # check as testuser2 if repo has been shared (via /app)
    rv = client.get(f'/apps/{mars_namespace}?shared=1', headers=headers_testuser2)
    result = rv.get_json()

    assert "data" in result
    assert len(result["data"]) == 0

    #share with testuser2

    rv = client.put(f'/permissions/{mars_namespace}', data=json.dumps({"operation":"add", "granteeType": "USER", "grantee": "testuser2", "permission":"READ"}), headers=headers)
    result = rv.get_json()
    assert "error" not in result

    # check again if testuser2 has access
    rv = client.get(f'/repositories/{mars_namespace}?shared=1', headers=headers_testuser2)
    result = rv.get_json()

    assert "data" in result
    assert len(result["data"]) == 1

    # check as testuser2 if repo has been shared (via /app)
    rv = client.get(f'/apps/{mars_namespace}?shared=1', headers=headers_testuser2)
    result = rv.get_json()

    assert "data" in result
    assert len(result["data"]) == 1


def test_permissions(client):
    headers = {"Authorization" : "sage token1"}
    headers_testuser2 = {"Authorization" : "sage token2"}
    admin_headers = {"Authorization" : "sage admin_token"}

    grimm_namespace = "brothersgrimm"
    grimm_repo = "hansel_and_gretel"
    grimm_v = "1.0"
    #test_app_def_obj["namespace"] = grimm_namespace
    #grimm_app_def = json.dumps(test_app_def_obj)

    # clean-up repo permissions
    data = {"operation":"delete"}
    rv = client.put(f'/permissions/{grimm_namespace}/{grimm_repo}', data=json.dumps(data), headers=admin_headers)

    # clean-up namespace permissions
    rv = client.put(f'/permissions/{grimm_namespace}', data=json.dumps(data), headers=admin_headers)

    rv = client.delete(f'/apps/{grimm_namespace}/{grimm_repo}/{grimm_v}', headers=admin_headers)
    result = rv.get_json()


    # create app
    rv = client.post(f'/apps/{grimm_namespace}/{grimm_repo}/{grimm_v}', data = test_app_def, headers=headers)
    assert rv.data != ""
    #print(f'rv.data: {rv.data}' , file=sys.stderr)

    result = rv.get_json()

    assert isinstance(result,dict) , "is not a dict"

    assert "id" in result #, f'response was: {rv.data}'
    app_id = result["id"]

    # verify app
    rv = client.get(f'/apps/{grimm_namespace}/{grimm_repo}/{grimm_v}', headers=headers)

    result = rv.get_json()


    assert "id" in result

    assert result["id"] == app_id

    # (1/2) verify that the app (repository to be precise) is private
    rv = client.get(f'/apps/{grimm_namespace}/{grimm_repo}/{grimm_v}', headers=headers_testuser2)

    result = rv.get_json()

    assert "error" in result

    # (1/2) verify that the app (repository to be precise) is private
    rv = client.get(f'/apps/{grimm_namespace}/{grimm_repo}', headers=headers_testuser2)

    result = rv.get_json()

    assert "data" in result
    assert  len(result["data"]) == 0

    #verify that testuser2 cannot yet see the app in the listing
    rv = client.get(f'/apps/', headers=headers_testuser2)

    result = rv.get_json()

    assert "data" in result

    for app in result["data"]:
        assert "id" in app
        assert app["id"] != f"{grimm_namespace}/{grimm_repo}:{grimm_v}"




    # remove all permissions from repo
    data ={"operation":"delete"}
    rv = client.put(f'/permissions/{grimm_namespace}/{grimm_repo}', data=json.dumps(data), headers=headers)


    # check repo permissions: only owner should have permission
    rv = client.get(f'/permissions/{grimm_namespace}/{grimm_repo}', headers=headers)

    result = rv.get_json()

    print(f'permissons after first clean-up: {json.dumps(result)}', file=sys.stderr)

    assert len(result) ==1


    # make repo public

    data = {"operation":"add", "granteeType": "GROUP", "grantee": "AllUsers", "permission": "READ"}

    rv = client.put(f'/permissions/{grimm_namespace}/{grimm_repo}', data=json.dumps(data), headers=headers)
    print(f'make repo public, resut: {rv.data}', file=sys.stderr)
    result = rv.get_json()


    assert result != None
    print(result, file=sys.stderr)


    assert "added" in result

    # check repo permissions
    rv = client.get(f'/permissions/{grimm_namespace}/{grimm_repo}', headers=headers)

    result = rv.get_json()
    print(f'check repo permissions: {json.dumps(result)}', file=sys.stderr)

    assert len(result) ==2

    # get public app as authenticated user
    rv = client.get(f'/apps/{grimm_namespace}/{grimm_repo}/1.0', headers=headers)

    result = rv.get_json()

    assert "id" in result


    # get public app anonymously
    rv = client.get(f'/apps/{grimm_namespace}/{grimm_repo}/{grimm_v}')

    result = rv.get_json()

    assert "error"  not in result
    assert "id" in result

    # remove public permission
    data["operation"] = "delete"
    rv = client.put(f'/permissions/{grimm_namespace}/{grimm_repo}', data=json.dumps(data), headers=headers)

    result = rv.get_json()

    print(result)
    assert "deleted" in result
    assert result["deleted"] ==1


    # share with other people

    for user in ['other1', 'other2', 'other3', 'testuser2']:
        other = {"operation":"add", "granteeType": "USER", "grantee":  user , "permission": "READ"}
        rv = client.put(f'/permissions/{grimm_namespace}/{grimm_repo}', data=json.dumps(other), headers=headers)

        result = rv.get_json()
        assert "error" not in result
        assert "added" in result
        assert result["added"] == 1

    # check app permissions
    rv = client.get(f'/permissions/{grimm_namespace}/{grimm_repo}', headers=headers)

    result = rv.get_json()

    print(json.dumps(result), file=sys.stderr)

    assert len(result) ==5

    # remove all permissions (except owners FULL_CONTROLL)

    rv = client.put(f'/permissions/{grimm_namespace}/{grimm_repo}', data=json.dumps({"operation":"delete"}), headers=headers)

    result = rv.get_json()
    print(f'Deletion result: {json.dumps(result)}', file=sys.stderr)
    deleted = result.get("deleted", -1)

    assert deleted == 4

    # check app permissions
    rv = client.get(f'/permissions/{grimm_namespace}/{grimm_repo}', headers=headers)

    result = rv.get_json()


    assert len(result) ==1

    assert result[0]["permission"]== "FULL_CONTROL"


    # check app without auth
    rv = client.get(f'/apps/{grimm_namespace}/{grimm_repo}/{grimm_v}')

    result = rv.get_json()

    error_msg = result.get("error", "")
    assert "Not authorized" in  error_msg


    # check namespace permission, give testuser2 WRITE permission for namespace


    acl = {"operation":"add", "granteeType": "USER", "grantee":  "testuser2" , "permission": "WRITE"}
    rv = client.put(f'/permissions/{grimm_namespace}', data=json.dumps(acl), headers=headers)

    result = rv.get_json()

    added = result.get("added", -1)
    assert added == 1


    # verify testuser2 can see repository inside of namespace
    rv = client.get(f'/repositories/{grimm_namespace}', headers=headers_testuser2)
    result = rv.get_json()


    assert "data" in result
    assert len(result["data"]) > 0
    assert "name" in result["data"][0]
    assert result["data"][0]["name"] == grimm_repo

    # list all namespaces
    rv = client.get(f'/namespaces', headers=headers)


    result = rv.get_json()
    print(f'result: {json.dumps(result)}', file=sys.stderr)

    assert "data" in result
    assert len(result["data"]) >= 1
    found_namespace = False
    for n in result["data"]:
        if n["id"] == grimm_namespace and n["owner_id"] == "testuser" and n["type"] == "namespace":
            found_namespace = True

    assert found_namespace

    # check namespace permission, give testuser2 FULL_CONTROL permission for namespace
    acl = {"operation": "add", "granteeType": "USER", "grantee":  "testuser2" , "permission": "FULL_CONTROL"}
    rv = client.put(f'/permissions/{grimm_namespace}', data=json.dumps(acl), headers=headers)

    result = rv.get_json()

    added = result.get("added", -1)
    assert added == 1

    assert "error" not in result
    print(f'result: {json.dumps(result)}', file=sys.stderr)

    # view permissions as testuser2
    rv = client.get(f'/permissions/{grimm_namespace}/{grimm_repo}', headers=headers_testuser2)

    result = rv.get_json()
    print(f'result: {json.dumps(result)}', file=sys.stderr)
    assert "error" not in result

    # test repository permissions view
    rv = client.get(f'/repositories?view=permissions', headers=headers_testuser2)

    result = rv.get_json()
    print(f'result: {json.dumps(result)}', file=sys.stderr)
    assert "error" not in result


    # delete app

    rv = client.delete(f'/apps/{grimm_namespace}/{grimm_repo}/{grimm_v}', headers=headers_testuser2)
    result = rv.get_json()

    assert "deleted" in result


def test_namespaces(client):
    headers = {"Authorization" : "sage token1"}

    rv = client.get(f'/namespaces/', headers=headers)

    result = rv.get_json()

    print(f'Namespaces list: {json.dumps(result)}', file=sys.stderr)

    assert rv.status_code == 200




def test_repositories(client):
    headers = {"Authorization" : "sage token1"}

    app_namespace = "sageX"



    rv = client.get(f'/apps/{app_namespace}', headers=headers)
    assert rv.status_code == 200
    result = rv.get_json()

    print(f'Repositories list: {json.dumps(result)}', file=sys.stderr)

    assert rv.status_code == 200


def test_meta_file_import(client, test_failure=False):
    headers = {"Authorization" : "sage token1"}
    admin_headers = {"Authorization" : "sage admin_token"}
    app_namespace = "sagebuildtest"
    app_version = "1.0"

    # copy example app spec
    app_def = json.loads(test_app_def)

    app_repository = "example_with_meta_files"
    app_def["name"] = app_repository
    app_def["description"] = "a very important app (with meta files)"

    # use a remote repo for testing meta import
    # todo: update hello-world-ml with meta and use that for testing instead
    app_def["source"]["url"] = "https://github.com/nconrad/Bird-Song-Classifier-Plugin.git"
    app_def["source"]["branch"] = "main"
    app_def_str = json.dumps(app_def)


    # delete app first
    rv = client.delete(f'/apps/{app_namespace}/{app_repository}/{app_version}', headers=admin_headers)
    result = rv.get_json()

    if "error" in result:
        assert "App not found" in result["error"]
    else:
        assert rv.status_code == 200


    # register app
    rv = client.post(f'/apps/{app_namespace}/{app_repository}/{app_version}', data = app_def_str, headers=headers)
    result = rv.get_json()
    assert "error" not in result
    assert result != None


    # ensure files are retrievable
    file_dicts = [{
        'name': 'ecr-icon.jpg',
        'size': 9237
    }, {
        'name': 'ecr-science-image.jpg',
        'size': 29888
    }, {
        'name': 'ecr-science-description.md',
        'size': 4157
    }]

    for f in file_dicts:
        name = f['name']
        rv = client.get(f'/meta-files/{app_namespace}/{app_repository}/{app_version}/{name}', data = app_def_str, headers=headers)
        result = rv.get_data()

        assert result != None
        assert sys.getsizeof(result) == f['size']


def test_authz(client):
    headers = {"Authorization" : "sage token3"}

    # wait... shouldn't the api handle the data???
    # app_def = load_app_def("example_app.yaml")

    # r = client.post(f'/submit/', data=app_def, headers=headers)
    # assert rv.status_code == 200

    sample_request = {
        "account": "testuser",
        "type": "repository",
        "name": "sage/simple",
        "service": "Docker registry",
        "actions": ["pull"]
    }

    rv = client.post(f'/authz', headers=headers,  data=json.dumps(sample_request))
    print(f'rv.data: {rv.data}', file=sys.stderr)
    assert rv.status_code == 200


def test_health(client):
    rv = client.get('/healthy')
    assert rv.status_code == 200
    result = rv.get_json()
    assert "error" not in result
    assert "status" in result
    assert result["status"] == "ok"


def test_error(client):
    rv = client.get('/apps/test/test/test')
    result = rv.get_json()
    print(f'Test result: {json.dumps(result)}', file=sys.stderr)
    assert "error" in result

    # this fails because app "test" does not exist and there is no permission
    assert "Not authorized" in result["error"]
