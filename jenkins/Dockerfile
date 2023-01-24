FROM moby/buildkit:latest as buildkit
# buildkit is used as a convinient way to copy builtctl into the main image

FROM jenkins/jenkins:2.375.2-lts-jdk11

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

# Jenkins: groovy, create token
#COPY init.groovy /var/jenkins_home/ # Volumes would overwrite this
COPY init.groovy /

# this is needed to for docker
USER root

RUN sed -i '2icp /init.groovy /var/jenkins_home/' /usr/local/bin/jenkins.sh

RUN apt-get update && apt-get install -y jq curl file

# copy all buildkit tools into jenkins image
COPY --from=buildkit /usr/bin/buildkit* /usr/bin/buildctl* /usr/bin/

# buildkit cmds:
# buildctl                buildkit-qemu-arm       buildkit-qemu-mips64    buildkit-qemu-ppc64le   buildkit-qemu-s390x     buildkit-runc
# buildctl-daemonless.sh  buildkit-qemu-i386      buildkit-qemu-mips64el  buildkit-qemu-riscv64   buildkit-qemu-x86_64    buildkitd
# / # /usr/bin/buildctl -h
