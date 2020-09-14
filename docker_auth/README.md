
# docker registry with auth for ECR


SAGE uses [docker_auth](https://github.com/cesanta/docker_auth) for authentication and authorization of the ECR docker registry. SAGE specific code is integrated as a plugin into docker_auth. 




git clone https://github.com/cesanta/docker_auth.git
cd docker_auth
git checkout 519c5d79072481d6312a57673e3f6ab242e66514  # this is from Jul 13, 2020






## SSL certificates for token validation (not used for https)
cd ssl
./create_certs.sh registry.local  # registry.local for local test deployment



# local test/dev deployment 
Docker client and registry need to be able to reach the auth server under a globally unique domain name. To achieve this with docker an entry to /etc/hosts has to be added, the docker containers have to run in a docker network, and the conatiners have to be started with the argument `--add-host registry.local:${DOCKER_GATEWAY_IP}`

Add to your /etc/hosts 
```test
127.0.0.1	registry.local
```

## docker network

docker network create registrytest
export DOCKER_GATEWAY_IP=$(docker network inspect registrytest -f '{{(index .IPAM.Config 0).Gateway}}')
echo ${DOCKER_GATEWAY_IP}

## start registry
cd ..
docker run -ti --rm --network registrytest --name registry -p 5000:5000  --add-host registry.local:${DOCKER_GATEWAY_IP}  -v ${PWD}/registry.conf:/etc/docker/registry/config.yml -v ${PWD}/ssl/server.crt:/server.crt registry:2


## start docker_auth


export tokenInfoEndpoint=".../token_info/" 
export tokenInfoUser="XXX"  
export tokenInfoPassword="XXX"

# prod
docker run \
    --env tokenInfoEndpoint=${tokenInfoEndpoint} \
    --env tokenInfoUser=${tokenInfoUser} \
    --env tokenInfoPassword=${tokenInfoPassword} \
    --network registrytest \
    --add-host registry.local:${DOCKER_GATEWAY_IP} \
    --rm -it --name docker_auth -p 5001:5001 \
    -v ${PWD}/ssl/server.key:/server.key \
    -v ${PWD}/ssl/server.crt:/server.crt  \
    -v ${PWD}/docker-auth.yml:/config/auth_config.yml:ro \
    cesanta/docker_auth:latest
     /config/auth_config.yml

# dev
docker run \
    --env tokenInfoEndpoint=${tokenInfoEndpoint} \
    --env tokenInfoUser=${tokenInfoUser} \
    --env tokenInfoPassword=${tokenInfoPassword} \
    --network registrytest \
    --add-host registry.local:${DOCKER_GATEWAY_IP} \
    --rm -it --name docker_auth -p 5001:5001 \
    -v ${HOME}/git/docker_auth:/go/src/app \
    -v ${PWD}/ssl/server.key:/server.key \
    -v ${PWD}/ssl/server.crt:/server.crt  \
    -v ${PWD}/docker-auth.yml:/config/auth_config.yml:ro \
    --entrypoint /bin/ash \
    cesanta/docker_auth:latest
     /config/auth_config.yml


# login with username and password
docker login registry.local:5000

docker tag alpine:latest registry.local:5000/test/alpine:latest
docker push registry.local:5000/test/alpine:latest
