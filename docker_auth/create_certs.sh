#!/bin/bash

# This script creates self-signed certificates needed for token verfication between docker registry and docker auth server.

if [ -z "$1" ]
  then
    echo "No argument supplied"
    exit 1
fi

DOCKER_AUTH_DOMAIN=$1
# e.g. registry.local



# SSL doc: https://deliciousbrains.com/ssl-certificate-authority-for-local-https-development/
# private key (creates myCA.key)

openssl genrsa -out myCA.key 2048

# create root certififcate (creates myCA.pem)
openssl req -x509 -new -nodes -key myCA.key -sha256 -days 1825 -out myCA.pem -subj "/C=US/ST=Illinois/L=Lemont/O=Argonne National Laboratory/OU=SAGE project/CN=${DOCKER_AUTH_DOMAIN}"


# create server key 

openssl genrsa -out server.key 2048

# create server cert request (server.csr)
openssl req -new -key server.key -out server.csr -subj "/C=US/ST=Illinois/L=Lemont/O=Argonne National Laboratory/OU=SAGE project/CN=${DOCKER_AUTH_DOMAIN}"

# create server cert (server.crt)

openssl x509 -req -in server.csr -CA myCA.pem -CAkey myCA.key -CAcreateserial -out server.crt -days 825 -sha256 

