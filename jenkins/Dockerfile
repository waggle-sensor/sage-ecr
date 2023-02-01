FROM moby/buildkit:latest as buildkit
# buildkit is used as a convinient way to copy builtctl into the main image

FROM jenkins/jenkins:lts-jdk11

RUN jenkins-plugin-cli \
    --plugins \
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
    ws-cleanup \
    credentials-binding                 # required for ecr-registry credentials

# the follow steps require root permission to perform
USER root

# install additional system utils
RUN apt-get update && apt-get install -y jq curl file

# copy all buildkit tools into jenkins image
COPY --from=buildkit /usr/bin/buildkit* /usr/bin/buildctl* /usr/bin/

USER jenkins
