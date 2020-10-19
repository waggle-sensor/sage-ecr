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
[./tutorial.md](./tutorial.md)


# API Specification

[./api_spec.md](./api_spec.md)


# testing


for an existing docker-compose enviornment:

```bash
docker exec -ti sage-ecr_sage-ecr_1 /bin/ash -c 'coverage run -m pytest -v --runslow  &&  coverage report -m'
```


# debugging MySQL

```bash
docker exec -ti sage-ecr_db_1 mysql -u sage -p SageECR
```
