#!/bin/bash


# target location
if [ -z "${DATADIR}" ]; then
  DATADIR=/docker/
fi

if [ ! ${USE_HOST_DOCKER} == "1" ] ; then
  export DOCKER_VERSION=$(curl --unix-socket /var/run/docker.sock http://localhost/version | jq -r '.Version')
  export DOCKER_BINARY=${DATADIR}/docker-${DOCKER_VERSION}

  mkdir -p ${DATADIR}
  mkdir -p /tmp

  if [ ! -e ${DOCKER_BINARY} ] ; then
    set -e
    set -x
    curl -fsSL -o ${DOCKER_BINARY}.part  https://web.lcrc.anl.gov/public/waggle/docker_binaries/x86_64/docker-${DOCKER_VERSION}
    set +x
    set +e
    mv ${DOCKER_BINARY}.part ${DOCKER_BINARY}
    chmod +x ${DOCKER_BINARY}  
  fi

  ln -sf ${DOCKER_BINARY} /usr/local/bin/docker

fi

# install build plugin
# https://github.com/docker/buildx/#with-buildx-or-docker-1903
#set -e
#export DOCKER_BUILDKIT=1
#docker build --platform=local -o . git://github.com/docker/buildx
#mkdir -p ~/.docker/cli-plugins
#mv buildx ~/.docker/cli-plugins/docker-buildx

#set +e
# moved to dockerfile



docker buildx create --name sage --use

#echo "DOCKER_BINARY=${DOCKER_BINARY}"
