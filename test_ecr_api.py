#!/usr/bin/env python3

import os
import tempfile

import pytest
import sys
from ecr_api import app
from config import dbFields
import json
import time

import requests
import yaml



test_app_def_obj = yaml.load(open('example_app.yaml', 'r').read(), Loader=yaml.FullLoader)

test_app_def = json.dumps(test_app_def_obj)

app_namespace = test_app_def_obj["namespace"]
app_repository = test_app_def_obj["name"]
app_version = test_app_def_obj["version"]


# from https://flask.palletsprojects.com/en/1.1.x/testing/
@pytest.fixture
def client():
    db_fd, app.config['DATABASE'] = tempfile.mkstemp()
    app.config['TESTING'] = True

    with app.test_client() as client:
        #with app.app_context():
        #    init_db()
        yield client

    os.close(db_fd)
    os.unlink(app.config['DATABASE'])


def test_connect(client):
    """Start with a blank database."""

    rv = client.get('/')
    assert b'SAGE Edge Code Repository' in rv.data


def upload_and_build(client, test_failure=False):
    headers = {"Authorization" : "sage token1"}

    #global test_app_def
    
    

    local_test_app_def = None

    if test_failure:
        # make copy
        test_app_def_failure_obj  = json.loads(json.dumps(test_app_def_obj))

        test_app_def_failure_obj["name"] = "test_app_fail"
        test_app_def_failure_obj["sources"][0]["url"] = "https://github.com/waggle-sensor/does_not_exist.git"
        test_app_def_failure_obj["sources"][1]["url"] = "https://github.com/waggle-sensor/does_not_exist.git"

        local_test_app_def = json.dumps(test_app_def_failure_obj)
        
    else:
        local_test_app_def = test_app_def


    print(f'local_test_app_def rv.data: {local_test_app_def}' , file=sys.stderr)

    rv = client.post('/submit', data = local_test_app_def, headers=headers)
    assert rv.data != ""
    print(f'upload_and_build rv.data: {rv.data}' , file=sys.stderr)
    
    result = rv.get_json()
    
    
    assert result != None

    if test_failure:
        assert result["sources"][0]["url"] == "https://github.com/waggle-sensor/does_not_exist.git"

    if not test_failure:
        assert result["name"] ==  test_app_def_obj["name"]
    


    # build "default"
    if True:
        rv = client.post(f'/builds/{app_namespace}/{app_repository}/{app_version}', headers=headers)
        
        assert rv.data != ""
        print(f'rv.data: {rv.data}' , file=sys.stderr)
        
        result = rv.get_json()

        assert "error" not in result
        assert "build_number" in result

        
        while True:
            rv = client.get(f'/builds/{app_namespace}/{app_repository}/{app_version}', headers=headers)
        
            assert rv.data != ""
            print(f'rv.data: {rv.data}' , file=sys.stderr)
        
            result = rv.get_json()

            assert "error" not in result
            assert "result" in result

            result_status = result["result"]

            if result_status == None:
                time.sleep(2)
                continue
            
            print(f'result_status: {result_status}' , file=sys.stderr)

            if not test_failure:
                if not result_status == "SUCCESS":
                    assert "url" in result
                    build_log_url = result["url"]
                    consoleTextURL = f'{build_log_url}/consoleText' 
                    r = requests.get(consoleTextURL)
                    print("consoleText:", file=sys.stderr)
                    print("--------------------------------------", file=sys.stderr)
                    print(r.text, file=sys.stderr)
                    print("--------------------------------------", file=sys.stderr)

            
                    assert result_status == "SUCCESS"

            break


    if test_failure:
        # extract build log
        assert "url" in result
        build_log_url = result["url"]
        consoleTextURL = f'{build_log_url}/consoleText' 
        r = requests.get(consoleTextURL)
        print("consoleText:", file=sys.stderr)
        print("--------------------------------------", file=sys.stderr)
        print(r.text, file=sys.stderr)
        print("--------------------------------------", file=sys.stderr)
        assert not "Finished: SUCCESS" in r.text
        assert ("ERROR: Error cloning remote repo 'origin'" in r.text) or ("ERROR: Error fetching remote repo 'origin'" in r.text)
        assert result_status == "FAILURE"

    rv = client.delete(f'/builds/{app_namespace}/{app_repository}/{app_version}', headers=headers)


    return
    # build "armv7"
    
    rv = client.post(f'/builds/{app_namespace}/{app_repository}/{app_version}?source=armv7', headers=headers)
    
    assert rv.data != ""
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    
    result = rv.get_json()

    assert "build_number" in result

    
    while True:
        rv = client.get(f'/builds/{app_namespace}/{app_repository}/{app_version}?source=armv7', headers=headers)
    
        assert rv.data != ""
        print(f'rv.data: {rv.data}' , file=sys.stderr)
    
        result = rv.get_json()

        assert "result" in result

        result_status = result["result"]

        if result_status == None:
            time.sleep(2)
            continue
        
        print(f'result_status: {result_status}' , file=sys.stderr)

        if not result_status == "SUCCESS":
            assert "url" in result
            build_log_url = result["url"]
            consoleTextURL = f'{build_log_url}/consoleText' 
            r = requests.get(consoleTextURL)
            print("consoleText:", file=sys.stderr)
            print("--------------------------------------", file=sys.stderr)
            print(r.text, file=sys.stderr)
            print("--------------------------------------", file=sys.stderr)
            
            

        assert result_status == "SUCCESS"
        break


@pytest.mark.slow
def test_upload_and_build(client):
    return upload_and_build(client)


# not sure why this test still uses the correct git url
#@pytest.mark.slow
#def test_upload_and_build_failure(client):
#    return upload_and_build(client, test_failure=True)
    




def test_app_upload_and_download(client):
    """Start with a blank database."""

    
    headers = {"Authorization" : "sage token1"}
    admin_headers = {"Authorization" : "sage token2"}

    
    # delete app in case app already exists and is frozen
    rv = client.delete(f'/apps/{app_namespace}/{app_repository}/{app_version}', data = test_app_def, headers=admin_headers)
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    if not "App not found" in  str(rv.data):
        assert rv.status_code == 200

    # delete repository:
    rv = client.delete(f'/apps/{app_namespace}/{app_repository}', data = test_app_def, headers=admin_headers)
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    assert rv.status_code == 200

    # delete namespace:
    rv = client.delete(f'/apps/{app_namespace}', data = test_app_def, headers=admin_headers)
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    assert rv.status_code == 200

    rv = client.post('/submit', data = test_app_def, headers=headers)
    assert rv.data != ""
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    
    result = rv.get_json()
    
    
    assert result != None
    assert "name" in result
    assert result["name"] ==  test_app_def_obj["name"]
    

    assert "id" in result
    app_id = result["id"]

    # test GET /apps/{app_id}
    ######################################################
    rv = client.get(f'/apps/{app_namespace}/{app_repository}/{app_version}', headers=headers)
    
    result = rv.get_json()

    assert result != None
    assert "error"  not in result

    assert "name" in result
    assert result["name"] ==  test_app_def_obj["name"]

    assert "owner" in result
    assert result["owner"] ==  "testuser"
    assert "id" in result
    app_get_id = result["id"]
    assert app_id == app_get_id


    for key in dbFields:
        assert key in result

    assert len(result["inputs"]) == 1
    assert len(result["inputs"][0]) == 2

    assert "metadata" in result
    assert "my-science-data" in result["metadata"]
    assert result["metadata"]["my-science-data"] == 12345


    rv = client.delete(f'/apps/{app_namespace}/{app_repository}/{app_version}', headers=headers)
    result = rv.get_json()
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    assert "deleted" in result
    assert result["deleted"] == 1




def test_listApps(client):
    headers = {"Authorization" : "sage token1"}
    admin_headers = {"Authorization" : "sage token2"}

    # delete in case app already exists and is frozen
    rv = client.delete(f'/apps/{app_namespace}/{app_repository}/{app_version}', data = test_app_def, headers=admin_headers)

    rv = client.post('/submit', data = test_app_def, headers=headers)
    assert rv.data != ""
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    
    result = rv.get_json()

    assert "id" in result
    app_id = result["id"]


    rv = client.get(f'/apps/{app_namespace}/{app_repository}', data = test_app_def, headers=headers)
    print(f'get list rv.data: {rv.data}' , file=sys.stderr)
    result = rv.get_json()

    assert "versions" in result
    assert len(result["versions"]) > 0
    found_app = False 
    for app in result["versions"]:
        assert "id" in app
        if app["id"] == app_id:
            found_app = True
            break

    assert found_app


    assert len(result) > 0


def test_permissions(client):
    headers = {"Authorization" : "sage token1"}

    # create app
    rv = client.post('/submit', data = test_app_def, headers=headers)
    assert rv.data != ""
    #print(f'rv.data: {rv.data}' , file=sys.stderr)
    
    result = rv.get_json()
   
    assert isinstance(result,dict) , "is not a dict"

    assert "id" in result #, f'response was: {rv.data}'
    app_id = result["id"]

    # verify app
    rv = client.get(f'/apps/{app_namespace}/{app_repository}/{app_version}', headers=headers)
   
    result = rv.get_json()
    

    assert "id" in result

    assert result["id"] == app_id


    # remove all permissions from repo
    data = '{}'
    rv = client.delete(f'/permissions/{app_namespace}/{app_repository}', data=data, headers=headers)


    # check repo permissions: only owner should have permission
    rv = client.get(f'/permissions/{app_namespace}/{app_repository}', headers=headers)

    result = rv.get_json()

    print(f'permissons after first clean-up: {json.dumps(result)}', file=sys.stderr)

    assert len(result) ==1


    # make repo public

    data = '{"granteeType": "GROUP", "grantee": "AllUsers", "permission": "READ"}'

    rv = client.put(f'/permissions/{app_namespace}/{app_repository}', data=data, headers=headers)
    print(f'make repo public, resut: {rv.data}', file=sys.stderr)
    result = rv.get_json()
   

    assert result != None
    print(result, file=sys.stderr)


    assert "added" in result

    # check repo permissions
    rv = client.get(f'/permissions/{app_namespace}/{app_repository}', headers=headers)

    result = rv.get_json()
    print(f'check repo permissions: {json.dumps(result)}', file=sys.stderr)

    assert len(result) ==2

    # get public app as authenticated user
    rv = client.get(f'/apps/{app_namespace}/{app_repository}/{app_version}', headers=headers)

    result = rv.get_json()

    assert "id" in result


    # get public app anonymously
    rv = client.get(f'/apps/{app_namespace}/{app_repository}/{app_version}')

    result = rv.get_json()

    assert "error"  not in result
    assert "id" in result

    # remove public permission
    rv = client.delete(f'/permissions/{app_namespace}/{app_repository}', data=data, headers=headers)

    result = rv.get_json()
    
    print(result)
    assert "deleted" in result
    assert result["deleted"] ==1


    # share with other people

    for user in ['other1', 'other2', 'other3']:
        other = {"granteeType": "USER", "grantee":  user , "permission": "READ"}
        rv = client.put(f'/permissions/{app_namespace}/{app_repository}', data=json.dumps(other), headers=headers)

        result = rv.get_json()
    
        added = result.get("added", -1)
        assert added == 1

    # check app permissions
    rv = client.get(f'/permissions/{app_namespace}/{app_repository}', headers=headers)

    result = rv.get_json()

    print(json.dumps(result), file=sys.stderr)

    assert len(result) ==4

    # remove all permissions (except owners FULL_CONTROLL)
    rv = client.delete(f'/permissions/{app_namespace}/{app_repository}', data=json.dumps({}), headers=headers)

    result = rv.get_json()
    print(f'Deletion result: {json.dumps(result)}', file=sys.stderr)
    deleted = result.get("deleted", -1)

    assert deleted == 3

    # check app permissions
    rv = client.get(f'/permissions/{app_namespace}/{app_repository}', headers=headers)

    result = rv.get_json()


    assert len(result) ==1

    assert result[0]["permission"]== "FULL_CONTROL"


    # check app without auth
    rv = client.get(f'/apps/{app_namespace}/{app_repository}/{app_version}')

    result = rv.get_json()

    error_msg = result.get("error", "")
    assert "Not authorized" in  error_msg
    

def test_namespaces(client):
    headers = {"Authorization" : "sage token1"}

    rv = client.get(f'/apps/', headers=headers)
   
    result = rv.get_json()
    
    print(f'Namespaces list: {json.dumps(result)}', file=sys.stderr)

    assert rv.status_code != 200


def test_repositories(client):
    headers = {"Authorization" : "sage token1"}

    rv = client.get(f'/apps/{app_namespace}', headers=headers)
    assert rv.status_code == 200
    result = rv.get_json()
    
    print(f'Repositories list: {json.dumps(result)}', file=sys.stderr)

    assert rv.status_code == 200




def test_health(client):
    
    rv = client.get('/')
    assert rv.data == b"SAGE Edge Code Repository"
    
    rv = client.get('/healthy')

    assert rv.data == b"ok"


def test_error(client):
    
    rv = client.get('/apps/test/test/test')
    result = rv.get_json()
    print(f'Test result: {json.dumps(result)}', file=sys.stderr)
    assert "error" in result

    # this fails because app "test" does not exist and there is no permission
    assert "Not authorized" in result["error"]




