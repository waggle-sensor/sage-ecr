#!/bin/bash

for arch in x86_64 ; do 
    mkdir -p ${arch}

    for DOCKER_VERSION in  $(curl -s https://download.docker.com/linux/static/stable/${arch}/ | grep -o "docker-[0-9]\+.[0-9]\+.[0-9]\+.tgz" | grep -o "[0-9]\+.[0-9]\+.[0-9]\+" | sort -u) ; do
        
        DOCKER_BINARY=docker-${DOCKER_VERSION}
        if [ -e ${arch}/${DOCKER_BINARY} ] ; then
            continue
        fi

        rm -f ./docker-${DOCKER_VERSION}.tgz ./docker-${DOCKER_VERSION}.tgz_part
        curl -fsSL -o ./docker-${DOCKER_VERSION}.tgz_part https://download.docker.com/linux/static/stable/${arch}/docker-${DOCKER_VERSION}.tgz
        mv ./docker-${DOCKER_VERSION}.tgz_part ./docker-${DOCKER_VERSION}.tgz
        tar -xvzf docker-${DOCKER_VERSION}.tgz -C /tmp docker/docker 
        mv /tmp/docker/docker ${arch}/docker-${DOCKER_VERSION}
        rm ./docker-${DOCKER_VERSION}.tgz
    done

done