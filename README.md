# sage-ecr
SAGE Edge Code Repository

![CI](https://github.com/sagecontinuum/sage-ecr/workflows/CI/badge.svg)


# Test environment

The test environment uses docker-compose but has to be invoked by a wrapper script:

```
./run.sh -d
```

Option -d will deamonize the docker-compose environment.


# usage

These usage examples assume you are running ECR locally via `./run.sh`.

```bash
export ECR_API="localhost:5000"
```

After uploading an app (explained below), defining enviornment variable `APP_ID` makes it easier to use the example API calls below.
```bash
export APP_ID='3a7ea5da-517e-4d00-8fcc-1f3e78aca85e'
```

## Jenkins
Visit Jenkins in your browser via: [http://localhost:8082](http://localhost:8082)

Note: After the start of Jenkins you have to login as user `ecrdb` with password `test`. You can skip the "Getting Started" dialogue but clicking the `X` in the upper right corner. Then click on the blue button `Start using Jenkins`. After that your are logged in, but that is not a requirement. Users can view the Jenkins instance without logging in.



## POST /apps
```bash
curl -X POST ${ECR_API}/apps -H "Authorization: sage user:testuser" -d '{"name":"simple","description":"very important app","version":"1.0","namespace":"sage","sources":[{"name":"default","architectures":["linux/amd64"],"url":"https://github.com/waggle-sensor/edge-plugins.git","branch":"master","directory":"plugin-simple","dockerfile":"Dockerfile_sage"},{"name":"armv7","architectures":["linux/arm/v7"],"url":"https://github.com/waggle-sensor/edge-plugins.git","branch":"master","directory":"plugin-simple","dockerfile":"Dockerfile_sage"}],"resources":[{"type":"RGB_image_producer","view":"top","min_resolution":"600x800"}],"inputs":[{"id":"speed","type":"int"}],"metadata":{"my-science-data":12345}}'
```

returns:
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
  "sources": [
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
    {
      "architectures": [
        "linux/amd64"
      ], 
      "branch": "master", 
      "directory": "plugin-simple", 
      "dockerfile": "Dockerfile_sage", 
      "name": "default", 
      "url": "https://github.com/waggle-sensor/edge-plugins.git"
    }
  ], 
  "version": "1.0"
}
```

## GET /apps/{id}

```bash
curl ${ECR_API}/apps/${APP_ID} -H "Authorization: sage user:testuser"
```

returns same as above


## DELETE /apps/{id}

```bash
curl -X DELETE ${ECR_API}/apps/${APP_ID} -H "Authorization: sage user:testuser"
```

returns
```json5
{
  "deleted": 1
}
```

## GET /apps

```bash
curl ${ECR_API}/apps
curl ${ECR_API}/apps -H "Authorization: sage user:testuser"
```

returns
```json5
[
  {
    "id": "7133719e-7049-4bcb-a699-ed8fab8be346", 
    "name": "testapp1", 
    "version": "1.0"
  }, 
  {
    "id": "8717a431-49ce-49da-a710-0590281dc6e9", 
    "name": "testapp2", 
    "version": "1.0"
  }, 
  {
    "id": "e9f98c56-fbde-41d9-a6ec-e2c0dfa32352", 
    "name": "testapp3", 
    "version": "1.0"
  }
]
```

## GET /apps/{id}/permissions

```bash
curl -X GET ${ECR_API}/apps/${APP_ID}/permissions -H "Authorization: sage user:testuser" 
```
returns
```json5
[
  {
    "grantee": "testuser", 
    "granteeType": "USER", 
    "id": "4992a806-5f16-45b3-a177-f22677b5889b", 
    "permission": "FULL_CONTROL"
  }
]
```

## PUT /apps/{id}/permissions

```bash
curl -X PUT ${ECR_API}/apps/${APP_ID}/permissions -H "Authorization: sage user:testuser" -d '{"granteeType": "GROUP", "grantee": "AllUsers", "permission": "READ"}'
```

returns
```json5
{
  "added": 1
}
```

## DELETE /apps/{id}/permissions

```bash
curl -X PUT ${ECR_API}/apps/${APP_ID}/permissions -H "Authorization: sage user:testuser" -d '{"granteeType": "GROUP", "grantee": "AllUsers", "permission": "READ"}'
```

returns
```json5
{
  "deleted": 1
}
```



## POST /apps/${APP_ID}/builds

Triggers a new build
```bash
curl -X POST ${ECR_API}/apps/${APP_ID}/builds -H "Authorization: sage user:testuser"
```

## GET /apps/${APP_ID}/builds

Returns state of last build.

```bash
curl ${ECR_API}/apps/${APP_ID}/builds -H "Authorization: sage user:testuser"
```



# testing


for an existing docker-compose enviornment:

```bash
docker exec -ti sage-ecr_sage-ecr_1 /bin/ash -c 'coverage run -m pytest -v --runslow  &&  coverage report -m'
```


# debugging

```bash
docker exec -ti sage-ecr_db_1 mysql -u sage -p SageECR
```
