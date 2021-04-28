# ECR API specification

Please define these variables to be able to copy-and-paste the curl examples below.

```bash
export ECR_API="localhost:5000"
export SAGE_USER_TOKEN="token1"
export APP_NAMESPACE="sage"
export APP_REPOSITORY="simple"
export APP_VERSION="1.0"
```


## POST /apps/{namespace}/{repository}/{version} OR  /submit

```bash
curl -X POST ${ECR_API}/apps/${APP_NAMESPACE}/${APP_REPOSITORY}/${APP_VERSION} -H "Authorization: sage ${SAGE_USER_TOKEN}" --data-binary  @./example_app.yaml
```


Alternatively, if namespace, repository("name"), and version are specified in the app:

```bash
curl -X POST ${ECR_API}/submit -H "Authorization: sage ${SAGE_USER_TOKEN}" --data-binary  @./example_app.yaml
curl -X POST ${ECR_API}/submit -H "Authorization: sage ${SAGE_USER_TOKEN}" -d '{...}'
```

Input can be either JSON or YAML format. As long as apps are not frozen, they can be overwritten with query `?force=true`.


Example repsonse:
```json5
{
  "arguments": "",
  "baseCommand": "",
  "depends_on": "",
  "description": "very important app",
  "id": "f59a7edf-8ca3-4557-83be-e3e1f60dee38",
  "inputs": [
    {
      "id": "speed",
      "type": "int"
    }
  ],
  "metadata": {
    "my-science-data": 12345
  },
  "name": "simple",
  "namespace": "sage",
  "owner": "testuser",
  "resources": [
    {
      "min_resolution": "600x800",
      "type": "RGB_image_producer",
      "view": "top"
    }
  ],
  "source":
    {
      "architectures": [
        "linux/arm/v7"
      ],
      "branch": "master",
      "directory": "plugin-simple",
      "dockerfile": "Dockerfile_sage",
      "name": "armv7",
      "url": "https://github.com/waggle-sensor/edge-plugins.git"
    },
  "version": "1.0"
}
```

## GET /apps/{namespace}/{repository}/{version}
```bash
curl ${ECR_API}/apps/${APP_NAMESPACE}/${APP_REPOSITORY}/${APP_VERSION} -H "Authorization: sage ${SAGE_USER_TOKEN}"
```

## DELETE /apps/{namespace}/{repository}/{version}
Note: You cannot delete a frozen app, even if you are owner. This requires admin permissions.
```bash
curl -X DELETE ${ECR_API}/apps/${APP_NAMESPACE}/${APP_REPOSITORY}/${APP_VERSION} -H "Authorization: sage ${SAGE_USER_TOKEN}"
```


## GET /namespaces
List namespaces:
```bash
curl ${ECR_API}/namespaces -H "Authorization: sage ${SAGE_USER_TOKEN}"
```

Example repsonse:
```json5
[
  {
    "id": "sage",
    "owner_id": "testuser"
  }
]
```


## PUT /namespaces/
Create namespace:
```bash
curl -X PUT ${ECR_API}/namespaces -d "{\"id\":\"${APP_NAMESPACE}\"}" -H "Authorization: sage ${SAGE_USER_TOKEN}"
```

Example repsonse:
```json5
{
  "id": "testtest",
  "owner_id": "testuser"
}
```

## GET /namespaces/{namespace}
List repositories in namespace:
```bash
curl ${ECR_API}/namespaces/${APP_NAMESPACE} -H "Authorization: sage ${SAGE_USER_TOKEN}"
```

Example repsonse:
```json5
{
  "id": "sage",
  "owner_id": "testuser",
  "repositories": [
    {
      "name": "simple",
      "namespace": "sage",
      "owner_id": "testuser"
    }
  ]
}
```

## DELETE /namespaces/{namespace}
```bash
curl -X DELETE ${ECR_API}/namespaces/${APP_NAMESPACE} -H "Authorization: sage ${SAGE_USER_TOKEN}"
```


## GET /apps/{namespace}/{repository}
List all versions in repository:
```bash
curl ${ECR_API}/apps/${APP_NAMESPACE}/${APP_REPOSITORY} -H "Authorization: sage ${SAGE_USER_TOKEN}"
```

Example repsonse:
```json5
[
  {
    "id": "b4006eb1-8435-4e64-b11b-0984563f4946",
    "name": "simple",
    "namespace": "sage",
    "version": "1.0"
  }
]
```

## GET /permissions/{namespace}/{repository}
Show permissions for repository
```bash
curl ${ECR_API}/permissions/${APP_NAMESPACE}/${APP_REPOSITORY} -H "Authorization: sage ${SAGE_USER_TOKEN}"
```
Example repsonse:
```json5
[
  {
    "grantee": "testuser",
    "granteeType": "USER",
    "permission": "FULL_CONTROL",
    "resourceName": "sage/simple",
    "resourceType": "repository"
  }
]
```

## PUT /permissions/{namespace}/{repository}
Make repository public:
```bash
curl -X PUT ${ECR_API}/permissions/${APP_NAMESPACE}/${APP_REPOSITORY} -H "Authorization: sage ${SAGE_USER_TOKEN}" -d '{"operation":"add", "granteeType": "GROUP", "grantee": "AllUsers", "permission": "READ"}'
```

Example repsonse:
```json5
{
  "added": 1
}
```


Share repository with another user:
```bash
curl -X PUT ${ECR_API}/permissions/${APP_NAMESPACE}/${APP_REPOSITORY} -H "Authorization: sage ${SAGE_USER_TOKEN}" -d '{"operation":"add", "granteeType": "USER", "grantee": "OtherUser", "permission": "READ"}'
```

Example repsonse:
```json5
{
  "added": 1
}
```

Delete permissions (this uses `PUT` !)
```bash
curl -X PUT ${ECR_API}/permissions/${APP_NAMESPACE}/${APP_REPOSITORY} -H "Authorization: sage ${SAGE_USER_TOKEN}" -d '{"operation":"delete", "granteeType": "USER", "grantee": "OtherUser", "permission": "READ"}'
-X PUT -d '{"operation" : "delete"}'
```

Delete all permissions (excluding owner permissions) (this uses `PUT` !)
```bash
curl -X PUT ${ECR_API}/permissions/${APP_NAMESPACE}/${APP_REPOSITORY} -H "Authorization: sage ${SAGE_USER_TOKEN}" -d '{"operation":"delete"}'
-X PUT -d '{"operation" : "delete"}'
```


## POST /builds/{namespace}/{repository}/{version}
trigger build for specific app
```bash
curl -X POST ${ECR_API}/builds/sage/simple/1.0 -H "Authorization: sage token1"
```

## GET /builds/{namespace}/{repository}/{version}
Get build status

```bash
curl -X GET ${ECR_API}/builds/sage/simple/1.0 -H "Authorization: sage token1"
```

Example repsonse:
```json5
...
  "queueId": 1,
  "result": "SUCCESS",
  "timestamp": 1602797073592,
...
```

