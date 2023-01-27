#!/usr/bin/env python3
import pytest
import sys
from ecr_api import app
import json
import time
import requests
from ecrdb import EcrDB


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
    r = client.get("/")
    assert r.status_code == 200
    assert r.data == b"SAGE Edge Code Repository"


def test_app_submit_view_delete_lifecycle(client):
    headers = {"Authorization" : "sage testuser_token"}

    def assert_matches_app(data):
        assert data["id"] == "sage/simple:1.2.3"
        assert data["owner"] ==  "testuser"
        assert data["name"] == "simple"
        assert data["description"] == "a simple app"
        assert data["version"] == "1.2.3"
        assert data["namespace"] == "sage"
        assert data["source"]["url"] == "https://github.com/waggle-sensor/edge-plugins.git"
        assert data["source"]["branch"] == "master"
        assert data["source"]["architectures"] == ["linux/amd64", "linux/arm64"]
        assert data["source"]["directory"] == "plugin-simple"
        assert data["frozen"] is False

    # submit app and check response
    result = must_submit_app_and_get_json(client, headers=headers, app_yaml="""
name: simple
description: "a simple app"
version: "1.2.3"
namespace: sage
source:
  url: "https://github.com/waggle-sensor/edge-plugins.git"
  branch: "master"
  architectures:
  - "linux/amd64"
  - "linux/arm64"
  directory : "plugin-simple"
""")
    assert_matches_app(result)

    # check that detail view matches app
    r = client.get("/apps/sage/simple/1.2.3", headers=headers)
    assert r.status_code == 200
    result = r.get_json()
    assert "error" not in result
    assert_matches_app(result)

    # check that list view agrees with results
    r = client.get("/apps/sage/simple", headers=headers)
    assert r.status_code == 200
    result = r.get_json()
    assert "error" not in result
    assert len(result["data"]) == 1
    assert_matches_app(result["data"][0])

    # delete app
    r = client.delete("/apps/sage/simple/1.2.3", headers=headers)
    assert r.status_code == 200

    # check app gone
    r = client.get("/apps/sage/simple/1.2.3", headers=headers)
    assert r.status_code == 404

    # check that list view is now empty
    r = client.get("/apps/sage/simple", headers=headers)
    assert r.status_code == 200
    result = r.get_json()
    assert "error" not in result
    assert len(result["data"]) == 0

    # consider splitting these into tests of the individual list and detail views


def test_app_build_on_success(client):
    headers = {"Authorization" : "sage testuser_token"}

    # submit app
    must_submit_app_and_get_json(client, headers=headers, app_yaml="""
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
""")

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


def test_app_build_on_failure(client):
    headers = {"Authorization" : "sage testuser_token"}

    # submit app
    must_submit_app_and_get_json(client, headers=headers, app_yaml="""
name: failure
description: "very nonexistant app"
version: "1.0.0"
namespace: sagebuildtest
source:
  url: "https://github.com/waggle-sensor/edge-plugins.git"
  branch: "master"  # optional, default: main  (better use tag instead)
  architectures:
  - "linux/amd64"
  - "linux/arm64"
  directory : "plugin-should-not-exist-1234123"
""")

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


def test_app_submit_fails_on_invalid_url(client):
    headers = {"Authorization" : "sage testuser_token"}

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
    r = client.post("/submit/", headers=headers, data=app_yaml)
    assert r.status_code == 500


def test_app_submit_multiple(client):
    headers = {"Authorization" : "sage testuser_token"}

    must_submit_app_and_get_json(client, headers=headers, app_yaml="""
name: first
description: "the first app"
version: "1.0.0"
namespace: sagefirst
source:
  url: "https://github.com/waggle-sensor/edge-plugins.git"   # required
  branch: "master"  # optional, default: main  (better use tag instead)
  architectures:
  - "linux/amd64"
  - "linux/arm64"
  directory : "plugin-simple"  # optional, default: root of git repository
""")

    must_submit_app_and_get_json(client, headers=headers, app_yaml="""
name: second
description: "the first app"
version: "2.0.0"
namespace: sagesecond
source:
  url: "https://github.com/waggle-sensor/edge-plugins.git"   # required
  branch: "master"  # optional, default: main  (better use tag instead)
  architectures:
  - "linux/amd64"
  - "linux/arm64"
  directory : "plugin-simple"  # optional, default: root of git repository
""")

    # what are we actually checking here???


def test_list_apps_user_visibilty(client):
    admin_headers = {"Authorization" : "sage admin_token"}
    headers_testuser = {"Authorization" : "sage testuser_token"}
    headers_testuser2 = {"Authorization" : "sage testuser2_token"}

    # delete in case app already exists and is frozen
    r = client.delete('/apps/planetmars/simple/1.0', headers=admin_headers)
    result = r.get_json()
    if "error" in result:
        assert "App not found" in result["error"]
    else:
        assert result["deleted"] == 1

     # clean-up repo permissions
    data = {"operation":"delete"}
    r = client.put(f'/permissions/planetmars/simple/1.0', data=json.dumps(data), headers=admin_headers)

    # clean-up namespace permissions
    r = client.put(f'/permissions/planetmars', data=json.dumps(data), headers=admin_headers)

    # submit app as testuser
    must_submit_app_and_get_json(client, headers=headers_testuser, app_yaml="""
name: simple
description: "a simple app"
version: "1.0"
namespace: planetmars
source:
  url: "https://github.com/waggle-sensor/edge-plugins.git"
  branch: "master"
  architectures:
  - "linux/amd64"
  - "linux/arm64"
  directory : "plugin-simple"
""")

    # testuser should see app in planetmars/simple
    r = client.get('/apps/planetmars/simple', headers=headers_testuser)
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert len(data) == 1

    # testuser should not have any public apps
    r = client.get('/apps/planetmars?public=1', headers=headers_testuser)
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert len(data) == 0

    # testuser should not have any public repos
    r = client.get('/repositories/planetmars?public=1', headers=headers_testuser)
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert len(data) == 0

    # testuser2 should not see app in planetmars/simple
    r = client.get(f'/apps/planetmars/simple', headers=headers_testuser2)
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert len(data) == 0

    # testuser2 should not have any shared apps
    r = client.get(f'/apps/planetmars?shared=1', headers=headers_testuser2)
    assert r.status_code == 200
    result = r.get_json()
    data = r.get_json()["data"]
    assert len(data) == 0

    # testuser2 should not have any shared repos
    r = client.get(f'/repositories/planetmars?shared=1', headers=headers_testuser2)
    assert r.status_code == 200
    result = r.get_json()
    data = r.get_json()["data"]
    assert len(data) == 0

    # share testuser's planetmars namespace with testuser2
    r = client.put(f'/permissions/planetmars', data=json.dumps({"operation":"add", "granteeType": "USER", "grantee": "testuser2", "permission":"READ"}), headers=headers_testuser)
    assert r.status_code == 200
    result = r.get_json()
    assert "error" not in result

    # app should be shared and visible to testuser2
    r = client.get(f'/apps/planetmars?shared=1', headers=headers_testuser2)
    assert r.status_code == 200
    result = r.get_json()
    data = r.get_json()["data"]
    assert len(data) == 1

    # repo should be shared and visible to testuser2
    r = client.get(f'/repositories/planetmars?shared=1', headers=headers_testuser2)
    assert r.status_code == 200
    result = r.get_json()
    data = r.get_json()["data"]
    assert len(data) == 1


def test_permissions(client):
    headers_testuser = {"Authorization" : "sage testuser_token"}
    headers_testuser2 = {"Authorization" : "sage testuser2_token"}

    must_submit_app_and_get_json(client, headers=headers_testuser, app_yaml="""
name: hansel_and_gretel
description: "a simple app"
version: "1.0"
namespace: brothersgrimm
source:
  url: "https://github.com/waggle-sensor/edge-plugins.git"
  branch: "master"
  architectures:
  - "linux/amd64"
  - "linux/arm64"
  directory : "plugin-simple"
""")

    # testuser should be only user with brothersgrimm/hansel_and_gretel repo permissions
    r = client.get(f'/permissions/brothersgrimm/hansel_and_gretel', headers=headers_testuser)
    assert r.status_code == 200
    result = r.get_json()
    assert len(result) == 1

    # testuser2 should not be able to see app
    r = client.get(f'/apps/brothersgrimm/hansel_and_gretel/1.0', headers=headers_testuser2)
    assert r.status_code == 401
    assert r.data == b'{"error":"Not authorized. (User testuser2 does not have permission READ for repository brothersgrimm/hansel_and_gretel)"}\n'

    # testuser2 should not be able to see app listed in repo
    r = client.get(f'/apps/brothersgrimm/hansel_and_gretel', headers=headers_testuser2)
    assert r.status_code == 200
    result = r.get_json()
    visible_ids = {item["id"] for item in result["data"]}
    assert "brothersgrimm/hansel_and_gretel:1.0" not in visible_ids

    # testuser2 should not see app in global listing
    r = client.get(f'/apps/', headers=headers_testuser2)
    assert r.status_code == 200
    result = r.get_json()
    visible_ids = {item["id"] for item in result["data"]}
    assert "brothersgrimm/hansel_and_gretel:1.0" not in visible_ids

    # make repo public
    data = {"operation":"add", "granteeType": "GROUP", "grantee": "AllUsers", "permission": "READ"}
    r = client.put(f'/permissions/brothersgrimm/hansel_and_gretel', data=json.dumps(data), headers=headers_testuser)
    assert r.status_code == 200
    result = r.get_json()
    assert "added" in result

    # check that all users should have permissions on repo
    r = client.get('/permissions/brothersgrimm/hansel_and_gretel', headers=headers_testuser)
    assert r.status_code == 200
    result = r.get_json()
    assert len(result) == 2
    assert {'grantee': 'testuser', 'granteeType': 'USER', 'permission': 'FULL_CONTROL', 'resourceName': 'brothersgrimm/hansel_and_gretel', 'resourceType': 'repository'} in result
    assert {'grantee': 'AllUsers', 'granteeType': 'GROUP', 'permission': 'READ', 'resourceName': 'brothersgrimm/hansel_and_gretel', 'resourceType': 'repository'} in result

    # get public app as owner
    r = client.get('/apps/brothersgrimm/hansel_and_gretel/1.0', headers=headers_testuser)
    assert r.status_code == 200

    # get public app as another user
    r = client.get('/apps/brothersgrimm/hansel_and_gretel/1.0', headers=headers_testuser2)
    assert r.status_code == 200

    # get public app anonymously
    r = client.get('/apps/brothersgrimm/hansel_and_gretel/1.0')
    assert r.status_code == 200

    # remove public permission
    data["operation"] = "delete"
    r = client.put('/permissions/brothersgrimm/hansel_and_gretel', data=json.dumps(data), headers=headers_testuser)
    assert r.status_code == 200
    result = r.get_json()
    assert result["deleted"] == 1

    # check that only owner has permissions on repo again
    r = client.get('/permissions/brothersgrimm/hansel_and_gretel', headers=headers_testuser)
    assert r.status_code == 200
    result = r.get_json()
    assert result == [{'grantee': 'testuser', 'granteeType': 'USER', 'permission': 'FULL_CONTROL', 'resourceName': 'brothersgrimm/hansel_and_gretel', 'resourceType': 'repository'}]

    # share with other people
    for user in ['other1', 'other2', 'other3', 'testuser2']:
        other = {"operation":"add", "granteeType": "USER", "grantee":  user , "permission": "READ"}
        r = client.put(f'/permissions/brothersgrimm/hansel_and_gretel', data=json.dumps(other), headers=headers_testuser)
        assert r.status_code == 200
        result = r.get_json()
        assert "error" not in result
        assert "added" in result
        assert result["added"] == 1

    # check app permissions
    r = client.get(f'/permissions/brothersgrimm/hansel_and_gretel', headers=headers_testuser)
    assert r.status_code == 200
    result = r.get_json()
    assert len(result) == 5
    assert {'grantee': 'testuser', 'granteeType': 'USER', 'permission': 'FULL_CONTROL', 'resourceName': 'brothersgrimm/hansel_and_gretel', 'resourceType': 'repository'} in result
    assert {'grantee': 'other1', 'granteeType': 'USER', 'permission': 'READ', 'resourceName': 'brothersgrimm/hansel_and_gretel', 'resourceType': 'repository'} in result
    assert {'grantee': 'other2', 'granteeType': 'USER', 'permission': 'READ', 'resourceName': 'brothersgrimm/hansel_and_gretel', 'resourceType': 'repository'} in result
    assert {'grantee': 'other3', 'granteeType': 'USER', 'permission': 'READ', 'resourceName': 'brothersgrimm/hansel_and_gretel', 'resourceType': 'repository'} in result
    assert {'grantee': 'testuser2', 'granteeType': 'USER', 'permission': 'READ', 'resourceName': 'brothersgrimm/hansel_and_gretel', 'resourceType': 'repository'} in result

    # remove all nonowner permissions
    r = client.put(f'/permissions/brothersgrimm/hansel_and_gretel', data=json.dumps({"operation":"delete"}), headers=headers_testuser)
    assert r.status_code == 200
    result = r.get_json()
    assert result["deleted"] == 4

    # check app permissions
    r = client.get('/permissions/brothersgrimm/hansel_and_gretel', headers=headers_testuser)
    assert r.status_code == 200
    result = r.get_json()
    assert result == [{'grantee': 'testuser', 'granteeType': 'USER', 'permission': 'FULL_CONTROL', 'resourceName': 'brothersgrimm/hansel_and_gretel', 'resourceType': 'repository'}]

    # check visibility for anonymous user
    r = client.get(f'/apps/brothersgrimm/hansel_and_gretel/1.0')
    assert r.status_code == 401
    assert r.data == b'{"error":"Not authorized."}\n'

    # check namespace permission, give testuser2 WRITE permission for namespace
    acl = {"operation":"add", "granteeType": "USER", "grantee":  "testuser2" , "permission": "WRITE"}
    r = client.put(f'/permissions/brothersgrimm', data=json.dumps(acl), headers=headers_testuser)
    assert r.status_code == 200
    result = r.get_json()
    assert result["added"] == 1

    # verify testuser2 can see repository inside of namespace
    r = client.get(f'/repositories/brothersgrimm', headers=headers_testuser2)
    assert r.status_code == 200
    result = r.get_json()
    visible_ids = {item["id"] for item in result["data"]}
    assert "brothersgrimm/hansel_and_gretel:1.0" not in visible_ids

    # list all namespaces
    r = client.get(f'/namespaces', headers=headers_testuser)
    result = r.get_json()
    assert "data" in result
    assert len(result["data"]) >= 1
    found_namespace = False
    for n in result["data"]:
        if n["id"] == "brothersgrimm" and n["owner_id"] == "testuser" and n["type"] == "namespace":
            found_namespace = True

    assert found_namespace

    # check namespace permission, give testuser2 FULL_CONTROL permission for namespace
    acl = {"operation": "add", "granteeType": "USER", "grantee":  "testuser2" , "permission": "FULL_CONTROL"}
    r = client.put(f'/permissions/brothersgrimm', data=json.dumps(acl), headers=headers_testuser)

    result = r.get_json()

    added = result.get("added", -1)
    assert added == 1

    assert "error" not in result
    print(f'result: {json.dumps(result)}', file=sys.stderr)

    # view permissions as testuser2
    r = client.get(f'/permissions/brothersgrimm/hansel_and_gretel', headers=headers_testuser2)

    result = r.get_json()
    print(f'result: {json.dumps(result)}', file=sys.stderr)
    assert "error" not in result

    # test repository permissions view
    r = client.get(f'/repositories?view=permissions', headers=headers_testuser2)

    result = r.get_json()
    print(f'result: {json.dumps(result)}', file=sys.stderr)
    assert "error" not in result


    # delete app

    r = client.delete(f'/apps/brothersgrimm/hansel_and_gretel/1.0', headers=headers_testuser2)
    result = r.get_json()

    assert "deleted" in result


def test_namespaces(client):
    headers = {"Authorization" : "sage testuser_token"}

    r = client.get(f'/namespaces/', headers=headers)
    assert r.status_code == 200
    result = r.get_json()
    assert result == {"data": []}


def test_list_repositories(client):
    headers = {"Authorization" : "sage testuser_token"}

    r = client.get("/apps/sageX", headers=headers)
    assert r.status_code == 200
    result = r.get_json()
    assert result == {"data": [], "pagination": {}}


def test_meta_file_import(client, test_failure=False):
    headers = {"Authorization" : "sage testuser_token"}

    # submit app
    must_submit_app_and_get_json(client, headers=headers, app_yaml="""
name: "example_with_meta_files"
description: "a very important app (with meta files)"
version: "1.2.3"
namespace: sage
source:
  url: "https://github.com/nconrad/Bird-Song-Classifier-Plugin.git"
  branch: "main"
  architectures:
  - "linux/amd64"
""")

    # check that all meta files exist and have the expected size
    file_dicts = [
        {'name': 'ecr-icon.jpg', 'size': 9237},
        {'name': 'ecr-science-image.jpg', 'size': 29888},
        {'name': 'ecr-science-description.md', 'size': 4157},
    ]

    for f in file_dicts:
        name = f['name']
        r = client.get(f'/meta-files/sage/example_with_meta_files/1.2.3/{name}', headers=headers)
        assert r.status_code == 200
        result = r.get_data()
        assert sys.getsizeof(result) == f['size']


def test_authz(client):
    headers_testuser = {"Authorization" : "sage testuser_token"}
    headers_sage_docker_auth = {"Authorization" : "sage sage_docker_auth"}

    # submit app as testuser
    must_submit_app_and_get_json(client, headers=headers_testuser, app_yaml="""
name: simple
description: "a simple app"
version: "1.2.3"
namespace: sage
source:
  url: "https://github.com/waggle-sensor/edge-plugins.git"
  branch: "master"
  architectures:
  - "linux/amd64"
  - "linux/arm64"
  directory : "plugin-simple"
""")

    # check permissions as sage_docker_auth user
    sample_request = {
        "account": "testuser",
        "type": "repository",
        "name": "sage/simple",
        "service": "Docker registry",
        "actions": ["pull"]
    }    
    r = client.post(f'/authz', headers=headers_sage_docker_auth, data=json.dumps(sample_request))
    print(f'r.data: {r.data}', file=sys.stderr)
    assert r.status_code == 200


def test_health(client):
    r = client.get('/healthy')
    assert r.status_code == 200
    result = r.get_json()
    assert "error" not in result
    assert "status" in result
    assert result["status"] == "ok"


def test_error(client):
    r = client.get('/apps/test/test/test')
    result = r.get_json()
    print(f'Test result: {json.dumps(result)}', file=sys.stderr)
    assert "error" in result

    # this fails because app "test" does not exist and there is no permission
    assert "Not authorized" in result["error"]


def must_submit_app_and_get_json(client, headers, app_yaml):
    r = client.post("/submit/", headers=headers, data=app_yaml)
    assert r.status_code == 200
    result = r.get_json()
    assert "error" not in result
    return result
