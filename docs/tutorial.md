# Tutorial

## Start ECR
```bash
git clone https://github.com/sagecontinuum/sage-ecr.git
cd sage-ecr
./run.sh -d
```

## Define ECR_API and SAGE_USER_TOKEN variables
```bash
export ECR_API="localhost:5000"
export SAGE_USER_TOKEN="token1"
```

Optional: Use `jq` for pretty formatting of json output. [installation instructions](https://stedolan.github.io/jq/download/)

## upload "simple plugin"
```bash
curl -X POST ${ECR_API}/submit -H "Authorization: sage ${SAGE_USER_TOKEN}" --data-binary  @./example_app.yaml

# Note: repeating this call will re-upload the app, as long as the field "frozen" is false


# save the app id you got from the previous call:
export APP_ID=<...>
```
## get app
```bash
curl -X GET  ${ECR_API}/apps/sage/simple/1.0 -H "Authorization: sage ${SAGE_USER_TOKEN}" | jq .
```


## share sage/simple with testuser2
```bash
curl -X PUT  ${ECR_API}/permissions/sage/simple -H "Authorization: sage ${SAGE_USER_TOKEN}" -d '{"granteeType": "USER", "grantee": "testuser2", "permission":"WRITE"}'
```

verify (view permissions as testuser):
```bash
curl ${ECR_API}/permissions/sage/simple -H "Authorization: sage ${SAGE_USER_TOKEN}"
```

verify (view app as testuser2)
```bash
curl ${ECR_API}/apps/sage/simple/1.0 -H "Authorization: sage token10"
```

## share namespace sage with testuser2
```bash
curl -X PUT  ${ECR_API}/permissions/sage -H "Authorization: sage ${SAGE_USER_TOKEN}" -d '{"granteeType": "USER", "grantee": "testuser2", "permission":"WRITE"}'
```

verify
```bash
curl ${ECR_API}/permissions/sage -H "Authorization: sage ${SAGE_USER_TOKEN}"
```

## list all namespaces

```bash
curl ${ECR_API}/apps -H "Authorization: sage ${SAGE_USER_TOKEN}"
```

## list all repositories in a given namespace

```bash
curl  ${ECR_API}/apps/sage -H "Authorization: sage ${SAGE_USER_TOKEN}"
```


## trigger build for specific app
```bash
curl -X POST ${ECR_API}/builds/sage/simple/1.0 -H "Authorization: sage ${SAGE_USER_TOKEN}"
```

## get build status

```bash
curl -X GET ${ECR_API}/builds/sage/simple/1.0 -H "Authorization: sage ${SAGE_USER_TOKEN}"
```


## open Jenkins UI in browser
[http://localhost:8082](http://localhost:8082)

Note: After the start of Jenkins you have to login as user ecrdb with password test. You can skip the "Getting Started" dialogue but clicking the `X` in the upper right corner. Then click on the blue button `Start using Jenkins`. After that your are logged in. Users can view the Jenkins instance without logging in.

