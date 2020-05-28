# sage-ecr
SAGE Edge Code Repository

![CI](https://github.com/sagecontinuum/sage-ecr/workflows/CI/badge.svg)

# usage


## POST /apps
```bash
curl -X POST localhost:5000/apps -H "Authorization: sage user:testuser" -d '{"name" : "testapp1", "description": "very important app", "architecture" : ["linux/amd64" , "linux/arm/v7"] , "version" : "1.0", "source" :"https://github.com/user/repo.git#v1.0", "inputs": [{"id":"speed" , "type":"int" }] , "metadata": {"my-science-data" : 12345} }'
```

returns:
```json5
{
  "architecture": "linux/amd64,linux/arm/v7", 
  "arguments": "", 
  "baseCommand": "", 
  "depends_on": "", 
  "description": "very important app", 
  "id": "7133719e-7049-4bcb-a699-ed8fab8be346", 
  "inputs": [
    {
      "id": "speed", 
      "type": "int"
    }
  ], 
  "metadata": {
    "my-science-data": 12345
  }, 
  "name": "testapp1", 
  "owner": "unknown", 
  "source": "https://github.com/user/repo.git#v1.0", 
  "version": "1.0"
}

```

## GET /apps/{id}

```bash
curl localhost:5000/apps/${APP_ID}
```

returns same as above


## GET /apps

```bash
curl localhost:5000/apps
curl localhost:5000/apps -H "Authorization: sage user:testuser"
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
curl -X GET localhost:5000/apps/${APP_ID}/permissions -H "Authorization: sage user:testuser" 
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
curl -X PUT localhost:5000/apps/${APP_ID}/permissions -H "Authorization: sage user:testuser" -d '{"granteeType": "GROUP", "grantee": "AllUsers", "permission": "READ"}'
```

returns
```json5
{
  "added": 1
}
```

## DELETE /apps/{id}/permissions

```bash
curl -X PUT localhost:5000/apps/${APP_ID}/permissions -H "Authorization: sage user:testuser" -d '{"granteeType": "GROUP", "grantee": "AllUsers", "permission": "READ"}'
```

returns
```json5
{
  "deleted": 1
}
```





# testing


```bash
docker-compose build
docker-compose run --rm  sage-ecr /bin/ash -c 'coverage run -m pytest -v &&  coverage report -m'
```


# debugging

```bash
docker exec -ti sage-ecr_db_1 mysql -u sage -p SageECR
```
