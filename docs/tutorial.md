# Tutorial

## Start ECR
```bash
git clone https://github.com/sagecontinuum/sage-ecr.git
cd sage-ecr
./run.sh -d
```

## Define ECR_API, SAGE_USER_TOKEN variables
```bash
export ECR_API="localhost:5000"
export SAGE_USER_TOKEN="testuser_token"
```

Optional: Use `jq` for pretty formatting of json output. [jq installation instructions](https://stedolan.github.io/jq/download/)

## upload "simple plugin" under the namespace "sage"
```bash
curl -X POST ${ECR_API}/apps/sage/simple/1.0 -H "Authorization: sage ${SAGE_USER_TOKEN}" --data-binary  @./example_app.yaml | jq .
```

Note: repeating this call will re-upload the app, as long as the field "frozen" is false


## get app
```bash
curl -X GET  ${ECR_API}/apps/sage/simple/1.0 -H "Authorization: sage ${SAGE_USER_TOKEN}" | jq .
```


## share repository sage/simple with testuser2
```bash
curl -X PUT  ${ECR_API}/permissions/sage/simple -H "Authorization: sage ${SAGE_USER_TOKEN}" -d '{"operation":"add", "granteeType": "USER", "grantee": "testuser2", "permission":"WRITE"}' | jq .
```

verify (view permissions as testuser):
```bash
curl ${ECR_API}/permissions/sage/simple -H "Authorization: sage ${SAGE_USER_TOKEN}"  | jq .
```

verify (view app as testuser2)
```bash
curl ${ECR_API}/apps/sage/simple/1.0 -H "Authorization: sage testuser2_token"  | jq .
```

## share namespace sage with testuser2
```bash
curl -X PUT  ${ECR_API}/permissions/sage -H "Authorization: sage ${SAGE_USER_TOKEN}" -d '{"operation":"add", "granteeType": "USER", "grantee": "testuser2", "permission":"WRITE"}' | jq .
```

verify
```bash
curl ${ECR_API}/permissions/sage -H "Authorization: sage ${SAGE_USER_TOKEN}" | jq .
```

## list all namespaces

```bash
curl ${ECR_API}/namespaces -H "Authorization: sage ${SAGE_USER_TOKEN}" | jq .
```

## list all repositories in a given namespace

```bash
curl  ${ECR_API}/repositories/sage -H "Authorization: sage ${SAGE_USER_TOKEN}" | jq .
```


## trigger build for specific app
```bash
curl -X POST ${ECR_API}/builds/sage/simple/1.0 -H "Authorization: sage ${SAGE_USER_TOKEN}" | jq .
```

## get build status

```bash
curl -X GET ${ECR_API}/builds/sage/simple/1.0 -H "Authorization: sage ${SAGE_USER_TOKEN}" | jq .
```


## open Jenkins UI in browser
[http://localhost:8082](http://localhost:8082)

Note: After the start of Jenkins you have to login as user ecrdb with password test. You can skip the "Getting Started" dialogue but clicking the `X` in the upper right corner. Then click on the blue button `Start using Jenkins`. After that your are logged in. Users can view the Jenkins instance without logging in.

