# sage-ecr
SAGE Edge Code Repository

![CI](https://github.com/sagecontinuum/sage-ecr/workflows/CI/badge.svg)


# Test environment

Add `registry.local` to docker daemon settings: (OSX -> Docker Desktop -> Preferences... -> Docker Engine)
```bash
{
  "experimental": true,
  "debug": true,
  "insecure-registries" : ["registry.local:5002"]
}
```

Add `registry.local` to `/etc/hosts`:
```bash
sudo ./scripts/add_etc_hosts_entry.sh 
```

Important: Note that pushing to the insecure registry using `docker buildx build --push` within the Jenkins container currently [does not work](https://github.com/docker/buildx/issues/218). A simple `docker push` does work, but is not used right now as it would not support multi-arch docker images. 


The test environment uses docker-compose but has to be invoked by a wrapper script:

```
./run.sh -d --build
```

Option `-d` will deamonize the docker-compose environment.
Option `--build` will build docker images first.


To stop:
```bash
./run.sh stop
```

Note that this test environment does not run the registry with authorization enabled. To start a registry with authorization enabled follow instructions in `docker_auth` subfolder. For production deployments use the kubernetes config files.

## Jenkins
Visit Jenkins in your browser via: [http://localhost:8082](http://localhost:8082)

Note: After the start of Jenkins you have to login as user `ecrdb` with password `test`. You can skip the "Getting Started" dialogue but clicking the `X` in the upper right corner. Then click on the blue button `Start using Jenkins`. After that your are logged in, but that is not a requirement. Users can view the Jenkins instance without logging in.

# Tutorial
[./docs/tutorial.md](./docs/tutorial.md)


# API Specification

[./docs/api_spec.md](./docs/api_spec.md)


# testing


for an existing docker-compose enviornment:

```bash
docker exec -ti sage-ecr_sage-ecr_1 /bin/ash -c 'coverage run -m pytest -v --runslow  &&  coverage report -m'
```

# Building Multi-Architecture Docker Images With Buildx

The ECR uses buildx to build multi-arch docker images. This requires not only that docker is installed on the host, but also:

- Experimental mode for the docker CLI needs to be turned on (described above)
- QEMU installed (`apt-get install qemu`)
- binfmt, e.g. `docker run --privileged --rm tonistiigi/binfmt --install all`



# debugging MySQL

```bash
docker exec -ti sage-ecr_db_1 mysql -u sage -p SageECR
```
