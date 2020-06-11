#!/bin/bash


# this script starts Jenkins as an independent docker container, waits until it is up and running,
#  extracts the user token and passes the token to the docker-compose environment

export JENKINS_SERVER=http://host.docker.internal:8082
export JENKINS_USER=ecrdb
export JENKINS_TOKEN=""

docker-compose down --remove-orphans


docker rm -fv jenkins
set -x
docker run -d --name jenkins --env JAVA_OPTS=-Dhudson.footerURL=http://localhost:8082 -p 8082:8080  -p 50000:50000 -v `pwd`/temp:/docker:rw -v /var/run/docker.sock:/var/run/docker.sock sagecontinuum/jenkins 
set +x

echo "waiting for jenkins..."

while [ 1 ] ; do 

    docker exec -ti jenkins test -f /var/jenkins_home/secrets/ecrdb_token.txt
    if [ $? -eq 0 ] ; then
        JENKINS_TOKEN=$(docker exec -ti jenkins cat /var/jenkins_home/secrets/ecrdb_token.txt)
        echo "JENKINS_TOKEN: _${JENKINS_TOKEN}_"
        break
    fi
    
    sleep 2
done

set -x
docker-compose up
set +x


# docker exec -ti jenkins cat /var/jenkins_home/secrets/initialAdminPassword
# docker exec -ti jenkins cat /var/jenkins_home/secrets/ecrdb_token.txt

# export JENKINS_ADMIN_PWD=$(echo $(docker exec -ti jenkins cat /var/jenkins_home/secrets/initialAdminPassword) | grep -o "[0-9a-z]\+" | tr -d '\n')
# echo "JENKINS_ADMIN_PWD: ${JENKINS_ADMIN_PWD}"
# export JENKINS_TOKEN=${JENKINS_ADMIN_PWD}
 



