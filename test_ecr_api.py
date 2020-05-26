#!/usr/bin/env python3

import os
import tempfile

import pytest
import sys
from ecr_api import app , dbFields

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

    test_app_def = '{"name" : "testapp", "description": "blabla", "architecture" : ["linux/amd64" , "linux/arm/v7"] , "version" : "1.0", "source" :"https://github.com/user/repo.git#v1.0", "inputs": [{"id":"speed" , "type":"int" }] , "metadata": {"my-science-data" : 12345} }'


    rv = client.post('/apps', data = test_app_def)
    assert rv.data != ""
    print(f'rv.data: {rv.data}' , file=sys.stderr)
    
    result = rv.get_json()
    
    
    assert result != None
    assert result["name"] ==  "testapp"
    

    assert "id" in result
    app_id = result["id"]

    # test GET /apps/{app_id}
    ######################################################
    rv = client.get(f'/apps/{app_id}')
    
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
