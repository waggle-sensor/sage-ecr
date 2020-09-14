

# this Dockerfile creates a dynamically built binary with a plugin for SAGE authentication

# docker build -t cesanta/docker_auth:latest -f auth_server/Dockerfile_sage .


ARG BASE_IMAGE=scratch


FROM golang:1.15-alpine AS build-env
RUN apk --no-cache add git make py3-pip && \
    pip3 install gitpython
RUN apk add gcc musl-dev  # for plugin
COPY . /go/src/app
WORKDIR /go/src/app/auth_server


RUN make deps

RUN make generate

# has to dynamically for plugin
RUN CGO_ENABLED=1 go build -v --ldflags=--s
RUN cd plugins && go build -buildmode=plugin sage_plugin.go


WORKDIR /go/src/app/
EXPOSE 5001
ENTRYPOINT ["/go/src/app/auth_server/auth_server"]
CMD ["/config/auth_config.yml"]
