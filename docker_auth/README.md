
# docker registry with auth for ECR


SAGE uses [docker_auth](https://github.com/cesanta/docker_auth) for authentication and authorization of the ECR docker registry. SAGE specific code is integrated as plugins into docker_auth. One plugin is for authentication (`sage_plugin`) and one plugin is for authorization `sage_plugin_z`.

The latest docker_auth image with SAGE plugin is `sagecontinuum/docker_auth:latest`.


Before you run ECR in test enviornment, you can add a custom user/token. That is useful if you test docker_auth with a production SAGE token introspection.
```bash
export ADD_USER="mytoken,your-user-id"
```


## build docker_auth image with sage plugin


Clone docker_auth and move files into the build context:
```bash
git clone https://github.com/sagecontinuum/docker_auth.git
mkdir -p docker_auth/auth_server/plugins
cp sage_plugin.go sage_plugin_z.go docker_auth/auth_server/plugins/
```

Build image:
```bash
docker build -t sagecontinuum/docker_auth:latest -f ./Dockerfile ./docker_auth/
```

Notes:

In contrast to the offical docker_auth image, this Dockerfile builds a dynamically compiled binary of docker_auth together with the plugins required for SAGE.



## SSL certificates for token validation
These SSL certificate are not used for https, but for token signing. (But it is possible to use them also for https)
```bash
cd ssl
../create_certs.sh registry.local
```

The argument to `create_certs.sh` is the domain name used by the docker_auth server. For a local test deployment you can use `registry.local`, after modifying your `/etc/hosts`. Domain `localhost` should not work with docker_auth running in a container.



# local test/dev deployment
Docker client and registry need to be able to reach the auth server under a globally unique domain name. To achieve this with docker an entry to `/etc/hosts` has to be added, the docker containers have to run in a docker network, and the conatiners have to be started with the argument `--add-host registry.local:${DOCKER_GATEWAY_IP}`. We are using the domain `registry.local` for both the registry and the docker_auth server.

Add to your /etc/hosts
```test
127.0.0.1	registry.local
```

## docker network

```bash
docker network create sage-ecr
```


## start registry
Delete previous registry first
```bash
docker rm -f sage-ecr_registry.local_1

export DOCKER_GATEWAY_IP=$(docker network inspect sage-ecr -f '{{(index .IPAM.Config 0).Gateway}}')
echo ${DOCKER_GATEWAY_IP}

docker run -ti --rm --network sage-ecr --name registry -p 5002:5000  --add-host registry.local:${DOCKER_GATEWAY_IP}  -v ${PWD}/registry.conf:/etc/docker/registry/config.yml -v ${PWD}/ssl/server.crt:/server.crt registry:2
```
Note: Port 5000 conflicts with ECR port.


## start docker_auth

```bash
export tokenInfoEndpoint=".../token_info/"
export tokenInfoUser="XXX"
export tokenInfoPassword="XXX"

export ecrAuthZEndpoint="http://sage-ecr:5000/authz"
#export ecrAuthZEndpoint="http://${DOCKER_GATEWAY_IP}:5000/authz"
export ecrAuthZToken="token3"


export DOCKER_GATEWAY_IP=$(docker network inspect sage-ecr -f '{{(index .IPAM.Config 0).Gateway}}')
echo ${DOCKER_GATEWAY_IP}

docker run \
    --env tokenInfoEndpoint=${tokenInfoEndpoint} \
    --env tokenInfoUser=${tokenInfoUser} \
    --env tokenInfoPassword=${tokenInfoPassword} \
    --env ecrAuthZEndpoint=${ecrAuthZEndpoint} \
    --env ecrAuthZToken=${ecrAuthZToken} \
    --env DEBUG_MODE=1 \
    --network sage-ecr \
    --add-host registry.local:${DOCKER_GATEWAY_IP} \
    --rm -it --name docker_auth -p 5001:5001 \
    -v ${PWD}/ssl/server.key:/server.key \
    -v ${PWD}/ssl/server.crt:/server.crt  \
    -v ${PWD}/docker-auth.yml:/config/auth_config.yml:ro \
    sagecontinuum/docker_auth:latest
     /config/auth_config.yml

```

# login with username and password

```bash
docker login registry.local:5002

docker tag alpine:latest registry.local:5002/test/alpine:latest
docker push registry.local:5002/test/alpine:latest
```