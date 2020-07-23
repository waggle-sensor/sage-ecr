#!/bin/bash


# this script starts Jenkins as an independent docker container, waits until it is up and running,
#  extracts the user token and passes the token to the docker-compose environment



if [ "$1"_ == "stop_" ] ; then

    set -x
    docker-compose down --remove-orphans
    docker rm -fv jenkins
    set +x

    exit 0
fi

echo "cleanup... (ignore warnings)"
docker-compose down --remove-orphans
docker rm -fv jenkins
echo "cleanup done"

# because we want to extract the docker IP from the docker network (linux), we have to create the nwteork first and control the name of the newtork.
ECR_NETWORK_NAME=sage-ecr
if [ $(docker network list --filter name=${ECR_NETWORK_NAME} -q | wc -l ) -eq 0 ] ; then
    docker network create ${ECR_NETWORK_NAME}
fi

export DOCKER_GATEWAY_HOST=""  # this is cleaner, but --add-host option requires IP address
export DOCKER_GATEWAY_IP=""


export DOCKER_GATEWAY_IP=$(docker network inspect ${ECR_NETWORK_NAME} -f '{{(index .IPAM.Config 0).Gateway}}')

if [ ${DOCKER_GATEWAY_IP}x == x ] ; then
# try another method of extracting ip address
export DOCKER_GATEWAY_IP=$(docker network inspect ${ECR_NETWORK_NAME} | grep Gateway | cut -d : -f 2 | cut -d '"' -f 2)
fi


if [ ${DOCKER_GATEWAY_IP}x == x ] ; then
echo "DOCKER_GATEWAY_IP could not be obtained."
exit 1
fi

if [[ "$OSTYPE" == "darwin"* ]] ; then
    DOCKER_GATEWAY_HOST="host.docker.internal"
else 
    DOCKER_GATEWAY_HOST = DOCKER_GATEWAY_IP

fi    


export JENKINS_SERVER=http://${DOCKER_GATEWAY_HOST}:8082


echo "DOCKER_GATEWAY_HOST: ${DOCKER_GATEWAY_HOST}"
echo "DOCKER_GATEWAY_IP: ${DOCKER_GATEWAY_IP}"
echo "JENKINS_SERVER: ${JENKINS_SERVER}"

cd jenkins/
docker build -t sagecontinuum/ecr-jenkins .
cd ..



DOCKER_MOUNT=""
if [ "${USE_HOST_DOCKER}_" == "1_" ] ; then

    DOCKER_PATH=$(which docker)
    if [ ${DOCKER_PATH}_ == "_" ] ; then
        echo "docker binary not found on host"
        exit 1
    fi

    DOCKER_MOUNT="-v ${DOCKER_PATH}:/usr/local/bin/docker:ro"

else
    USE_HOST_DOCKER=0
fi



set -x
docker run -d --name jenkins --env USE_HOST_DOCKER=${USE_HOST_DOCKER} --add-host registry.local:${DOCKER_GATEWAY_IP} --env JAVA_OPTS=-Dhudson.footerURL=http://localhost:8082 -p 8082:8080  -p 50000:50000 -v `pwd`/jenkins/casc_jenkins.yaml:/casc_jenkins.yaml:ro -v `pwd`/temp:/docker:rw -v /var/run/docker.sock:/var/run/docker.sock ${DOCKER_MOUNT} sagecontinuum/ecr-jenkins 
set +x

echo "waiting for jenkins..."
sleep 3


export JENKINS_TOKEN=""

while [ 1 ] ; do 

    docker exec jenkins test -f /var/jenkins_home/secrets/ecrdb_token.txt
    if [ $? -eq 0 ] ; then
        JENKINS_TOKEN=$(docker exec jenkins cat /var/jenkins_home/secrets/ecrdb_token.txt)
        if [ ! ${JENKINS_TOKEN}_ == "_" ] ; then
          echo "JENKINS_TOKEN: _${JENKINS_TOKEN}_"
          break
        else
          echo "JENKINS_TOKEN empty"
          sleep 2
          continue
        fi
    fi
    
    # check if container exists
    docker container inspect jenkins > /dev/null
    if [ ! $? -eq 0 ] ; then
        echo "Jenkins container not found"
        docker logs jenkins
        exit 1
    fi

    # check if container is in state "running"
    if [ $(docker container inspect -f '{{.State.Status}}' jenkins)_ != "running_" ] ; then
        echo "Jenkins container not running"
        docker logs jenkins
        exit 1
    fi

    sleep 2
done

echo "staring docker-compose..."

if [[ "$OSTYPE" == "darwin"* ]] ; then
    set -x
    docker-compose up $@
    set +x
else 
    
    # this requires DOCKER_INTERNAL
    export DOCKER_INTERNAL=${DOCKER_GATEWAY_HOST}
    set -x
    docker-compose -f docker-compose.yaml -f docker-compose.extra_hosts.yaml up $@
    set +x
fi




# docker exec -ti jenkins cat /var/jenkins_home/secrets/initialAdminPassword
# docker exec -ti jenkins cat /var/jenkins_home/secrets/ecrdb_token.txt

# export JENKINS_ADMIN_PWD=$(echo $(docker exec -ti jenkins cat /var/jenkins_home/secrets/initialAdminPassword) | grep -o "[0-9a-z]\+" | tr -d '\n')
# echo "JENKINS_ADMIN_PWD: ${JENKINS_ADMIN_PWD}"
# export JENKINS_TOKEN=${JENKINS_ADMIN_PWD}
 



