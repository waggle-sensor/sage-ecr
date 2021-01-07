#!/bin/bash


# target location
if [ -z "${DATADIR}" ]; then
  DATADIR=/docker/
fi

export DOCKER_VERSION=$(curl --silent --unix-socket /var/run/docker.sock http://localhost/version | jq -r '.Version')
echo "DOCKER_VERSION: ${DOCKER_VERSION}"


if [[ ${DOCKER_VERSION} == *"azure"* ]]; then
  echo "Azure...skip docker"
  exit 0
fi

echo "USE_HOST_DOCKER: ${USE_HOST_DOCKER}"

if [ "${USE_HOST_DOCKER}_" != "1_" ] ; then
  
  export DOCKER_BINARY=${DATADIR}/docker-${DOCKER_VERSION}

  mkdir -p ${DATADIR}
  mkdir -p /tmp

  if [ ! -e ${DOCKER_BINARY} ] ; then
    set -e
    set -x
    curl --fail --silent --show-error --location -o ${DOCKER_BINARY}.part  https://web.lcrc.anl.gov/public/waggle/docker_binaries/x86_64/docker-${DOCKER_VERSION}
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

if [ ! -e /usr/local/bin/docker  ] ; then
  echo "/usr/local/bin/docker not found"
  set -x
  which docker
  set +x
  #exit 1
fi


ls -latr /usr/local/bin/docker


set -x

file /usr/local/bin/docker

/usr/local/bin/docker --help



# the default builder does not support multi-arch images

echo "docker buildx inspect sage"
docker buildx inspect sage
if [[ ! $? -eq 0 ]] ; then  
  set +e # ignore error

  if [ "${DOCKER_REGISTRY_INSECURE}_" == "1_" ] ; then
    set -x
    /usr/local/bin/docker buildx create --name sage --use --config /buildx.config
    set +x
  else
    set -x
    /usr/local/bin/docker buildx create --name sage --use --buildkitd-flags '--allow-insecure-entitlement network.host'
    set +x
  fi

  
 
fi

echo '{ "experimental":"enabled" } ' > /var/jenkins_home/config.json


#echo "DOCKER_BINARY=${DOCKER_BINARY}"
