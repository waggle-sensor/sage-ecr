#!/usr/bin/env python3

import os
import tempfile

import pytest
import sys
from ecr_api import app
from config import dbFields
import json

test_app_def = '{"name" : "testapp", "description": "blabla", "architecture" : ["linux/amd64" , "linux/arm/v7"] , "version" : "1.0", "namespace":"sage", "source" :"https://github.com/user/repo.git#v1.0", "resources": [{"type":"RGB_image_producer", "view": "top", "min_resolution":"600x800"}], "inputs": [{"id":"speed" , "type":"int" }] , "metadata": {"my-science-data" : 12345} }'


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


def test_app_upload_and_download(client):
    """Start with a blank database."""

    
    headers = {"Authorization" : "sage user:testuser"}

    rv = client.post('/apps', data = test_app_def, headers=headers)
    assert rv.data != ""
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    
    result = rv.get_json()
    
    
    assert result != None
    assert result["name"] ==  "testapp"
    

    assert "id" in result
    app_id = result["id"]

    # test GET /apps/{app_id}
    ######################################################
    rv = client.get(f'/apps/{app_id}', headers=headers)
    
    result = rv.get_json()

    assert result != None
    assert result["name"] ==  "testapp"
    assert result["owner"] ==  "testuser"
    assert "id" in result
    app_get_id = result["id"]
    assert app_id == app_get_id


    for key in dbFields:
        assert key in result

    assert len(result["inputs"]) == 1
    assert len(result["inputs"][0]) == 2

    assert "my-science-data" in result["metadata"]
    assert result["metadata"]["my-science-data"] == 12345


    rv = client.delete(f'/apps/{app_id}', headers=headers)
    result = rv.get_json()
    assert "deleted" in result
    assert result["deleted"] == 1




def test_listApps(client):
    headers = {"Authorization" : "sage user:testuser"}

    rv = client.post('/apps', data = test_app_def, headers=headers)
    assert rv.data != ""
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    
    result = rv.get_json()

    assert "id" in result
    app_id = result["id"]


    rv = client.get('/apps', data = test_app_def, headers=headers)

    result = rv.get_json()

    found_app = False 
    for app in result:
        assert "id" in app
        if app["id"] == app_id:
            found_app = True
            break

    assert found_app


    assert len(result) > 0


def test_permissions(client):
    headers = {"Authorization" : "sage user:testuser"}

    # create app
    rv = client.post('/apps', data = test_app_def, headers=headers)
    assert rv.data != ""
    #print(f'rv.data: {rv.data}' , file=sys.stderr)
    
    result = rv.get_json()
   
    assert isinstance(result,dict) , "is not a dict"

    assert "id" in result #, f'response was: {rv.data}'
    app_id = result["id"]

    # verify app
    rv = client.get(f'/apps/{app_id}', headers=headers)
   
    result = rv.get_json()
    

    assert "id" in result

    assert result["id"] == app_id

    # make app public

    data = '{"granteeType": "GROUP", "grantee": "AllUsers", "permission": "READ"}'

    rv = client.put(f'/apps/{app_id}/permissions', data=data, headers=headers)

    result = rv.get_json()
    
    print(result)
    assert "added" in result

    # check app permissions
    rv = client.get(f'/apps/{app_id}/permissions', headers=headers)

    result = rv.get_json()

    assert len(result) ==2

    # get public app as authenticated user
    rv = client.get(f'/apps/{app_id}', headers=headers)

    result = rv.get_json()

    assert "id" in result


    # get public app anonymously
    rv = client.get(f'/apps/{app_id}')

    result = rv.get_json()

    assert "error"  not in result
    assert "id" in result

    # remove public permission
    rv = client.delete(f'/apps/{app_id}/permissions', data=data, headers=headers)

    result = rv.get_json()
    
    print(result)
    assert "deleted" in result
    assert result["deleted"] ==1


    # share with other people

    for user in ['other1', 'other2', 'other3']:
        other = {"granteeType": "USER", "grantee":  user , "permission": "READ"}
        rv = client.put(f'/apps/{app_id}/permissions', data=json.dumps(other), headers=headers)

        result = rv.get_json()
    
        added = result.get("added", -1)
        assert added == 1

    # check app permissions
    rv = client.get(f'/apps/{app_id}/permissions', headers=headers)

    result = rv.get_json()

    print(json.dumps(result), file=sys.stderr)

    assert len(result) ==4

    # remove all permissions (except owners FULL_CONTROLL)
    rv = client.delete(f'/apps/{app_id}/permissions', data=json.dumps({}), headers=headers)

    result = rv.get_json()

    deleted = result.get("deleted", -1)

    assert deleted == 3

    # check app permissions
    rv = client.get(f'/apps/{app_id}/permissions', headers=headers)

    result = rv.get_json()


    assert len(result) ==1

    assert result[0]["permission"]== "FULL_CONTROL"


    # check app without auth
    rv = client.get(f'/apps/{app_id}')

    result = rv.get_json()

    error_msg = result.get("error", "")
    assert "Not authorized" in  error_msg
    






def test_health(client):
    
    rv = client.get('/')
    assert rv.data == b"SAGE Edge Code Repository"
    
    rv = client.get('/healthy')

    assert rv.data == b"ok"

def test_error(client):
    
    rv = client.get('/apps/test')
    result = rv.get_json()

    assert "error" in result

    # this fails because app "test" does not exist and there is no permission
    assert "Not authorized" in result["error"]

