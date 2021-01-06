

# docker build -t sagecontinuum/ecr-jenkins .


FROM jenkins/jenkins:lts-alpine
#FROM jenkins/jenkins:alpine

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
    configuration-as-code-groovy \
    credentials-binding                 # required for ecr-registry credentials 



COPY ./get_docker_binary.sh /

# Jenkins: Configuration as Code
#COPY casc_jenkins.yaml /     # this config should better be mounted into container as is contains passwords
ENV CASC_JENKINS_CONFIG /config/casc_jenkins.yaml

# Jenkins: groovy, create token
#COPY init.groovy /var/jenkins_home/ # Volumes would overwrite this
COPY init.groovy /

# this is needed to for docker
USER root

RUN sed -i '2icp /init.groovy /var/jenkins_home/' /usr/local/bin/jenkins.sh



RUN apk update && apk add jq curl file

#ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false"


ENV DOCKER_BUILDKIT 1

RUN mkdir -p ~/.docker/cli-plugins/
RUN curl --silent -L -o ~/.docker/cli-plugins/docker-buildx https://github.com/docker/buildx/releases/download/v0.4.1/buildx-v0.4.1.linux-amd64
RUN chmod a+x ~/.docker/cli-plugins/docker-buildx

RUN echo '{ "experimental":"enabled" } ' > /root/config.json
