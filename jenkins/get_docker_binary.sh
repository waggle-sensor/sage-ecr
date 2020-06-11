#!/bin/bash


# target location
if [ -z "${DATADIR}" ]; then
  DATADIR=/docker/
fi


export DOCKER_VERSION=$(curl --unix-socket /var/run/docker.sock http://localhost/version | jq -r '.Version')
export DOCKER_BINARY=${DATADIR}/docker-${DOCKER_VERSION}

mkdir -p ${DATADIR}
mkdir -p /tmp

if [ ! -e ${DOCKER_BINARY} ] ; then

  curl -fsSL -o ${DOCKER_BINARY}.part  https://web.lcrc.anl.gov/public/waggle/docker_binaries/x86_64/docker-${DOCKER_VERSION}
  mv ${DOCKER_BINARY}.part ${DOCKER_BINARY}
  chmod +x ${DOCKER_BINARY}
  ln -sf ${DOCKER_BINARY} /usr/local/bin/docker
fi

echo "DOCKER_BINARY=${DOCKER_BINARY}"
