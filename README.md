# sage-ecr
SAGE Edge Code Repository

![docker-compose test](https://github.com/sagecontinuum/sage-storage-api/workflows/docker-compose%20test/badge.svg)

# usage


## POST /apps
```bash
curl -X POST localhost:5000/apps -d '{"name" : "testapp1", "description": "blabla", "architecture" : ["linux/amd64" , "linux/arm/v7"] , "version" : "1.0", "source" :"https://github.com/user/repo.git#v1.0", "inputs": [{"id":"speed" , "type":"int" }] , "metadata": {"my-science-data" : 12345} }'
```

returns:
```json5
{
  "architecture": "linux/amd64,linux/arm/v7", 
  "arguments": "", 
  "baseCommand": "", 
  "depends_on": "", 
  "description": "blabla", 
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
  "name": "unknown/testapp1", 
  "owner": "unknown", 
  "source": "https://github.com/user/repo.git#v1.0", 
  "version": "1.0"
}

```

## GET /apps/{id}

```bash
curl localhost:5000/app/<id>
```

returns same as above


## GET /apps

```bash
curl localhost:5000/app/<id>
```

returns
```json5
[
  {
    "id": "7133719e-7049-4bcb-a699-ed8fab8be346", 
    "name": "unknown/testapp1", 
    "version": "1.0"
  }, 
  {
    "id": "8717a431-49ce-49da-a710-0590281dc6e9", 
    "name": "unknown/testapp2", 
    "version": "1.0"
  }, 
  {
    "id": "e9f98c56-fbde-41d9-a6ec-e2c0dfa32352", 
    "name": "unknown/testapp3", 
    "version": "1.0"
  }
]
```

# testing


```bash
docker-compose build
docker-compose run --rm  sage-ecr  pytest -v
```


# debugging

```bash
docker exec -ti sage-ecr_db_1 mysql -u sage -p SageECR
```
