#!/bin/bash


# this script starts Jenkins as an independent docker container, waits until it is up and running,
#  extracts the user token and passes the token to the docker-compose environment

export JENKINS_SERVER=http://host.docker.internal:8082
export JENKINS_USER=ecrdb
export JENKINS_TOKEN=""



if [ "$1"_ == "stop_" ] ; then

    set -x
    docker-compose down --remove-orphans
    docker rm -fv jenkins
    set +x

    exit 0
fi

docker-compose down --remove-orphans
docker rm -fv jenkins

cd jenkins/
docker build -t sagecontinuum/ecr-jenkins .
cd ..



DOCKER_MOUNT=""
if [ "${USE_HOST_DOCKER}_" == "1_" ] ; then

    DOCKER_MOUNT="-v $(which docker):/usr/local/bin/docker"

else
    USE_HOST_DOCKER=0
fi



set -x
docker run -d --name jenkins --env USE_HOST_DOCKER=${USE_HOST_DOCKER} --env JAVA_OPTS=-Dhudson.footerURL=http://localhost:8082 -p 8082:8080  -p 50000:50000 -v `pwd`/jenkins/casc_jenkins.yaml:/casc_jenkins.yaml:ro -v `pwd`/temp:/docker:rw -v /var/run/docker.sock:/var/run/docker.sock ${DOCKER_MOUNT} sagecontinuum/ecr-jenkins 
set +x

echo "waiting for jenkins..."
sleep 3



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
    export DOCKER_INTERNAL=$(ip -4 addr show docker0 | grep -Po 'inet \K[\d.]+')
    echo "DOCKER_INTERNAL=${DOCKER_INTERNAL}"
    set -x
    docker-compose -f docker-compose.yaml -f docker-compose.extra_hosts.yaml up $@
    set +x
fi




# docker exec -ti jenkins cat /var/jenkins_home/secrets/initialAdminPassword
# docker exec -ti jenkins cat /var/jenkins_home/secrets/ecrdb_token.txt

# export JENKINS_ADMIN_PWD=$(echo $(docker exec -ti jenkins cat /var/jenkins_home/secrets/initialAdminPassword) | grep -o "[0-9a-z]\+" | tr -d '\n')
# echo "JENKINS_ADMIN_PWD: ${JENKINS_ADMIN_PWD}"
# export JENKINS_TOKEN=${JENKINS_ADMIN_PWD}
 



