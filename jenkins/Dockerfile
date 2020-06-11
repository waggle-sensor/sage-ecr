

# docker build -t sagecontinuum/jenkins .


#FROM jenkins/jenkins:lts-alpine
FROM jenkins/jenkins:alpine

RUN install-plugins.sh \
    build-timeout \
    timestamper \
    workflow-aggregator \
    github-branch-source \
    pipeline-stage-view \
    git \
    ssh-slaves \
    email-ext \
    mailer \
    configuration-as-code \
    configuration-as-code-groovy



COPY ./get_docker_binary.sh /

# Jenkins: Configuration as Code
COPY casc_jenkins.yaml /
ENV CASC_JENKINS_CONFIG /casc_jenkins.yaml

# Jenkins: groovy, create token
COPY init.groovy /var/jenkins_home/


# this is needed to for docker
USER root

RUN apk update && apk add jq

# ugly hack to make sure docker binary is downloaded on start of container
# this injects get_docker_binary.sh into the entrypoint script
RUN sed -i 's/exec java/\/get_docker_binary.sh\n  exec java/'  /usr/local/bin/jenkins.sh