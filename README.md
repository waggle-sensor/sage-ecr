# sage-ecr
SAGE Edge Code Repository

![CI](https://github.com/sagecontinuum/sage-ecr/workflows/CI/badge.svg)

# Dev environment commands

To start the dev environment run:

```sh
make start
```

To stop the dev environment run:

```bash
make stop
```

To run the test suite run:

```bash
make test
```

To open a database shell for debugging run:

```sh
make dbshell
```

Note that this test environment does not run the registry with authorization enabled. To start a registry with authorization enabled follow instructions in `docker_auth` subfolder. For production deployments use the kubernetes config files.

## Jenkins

Visit Jenkins in your browser via: [http://localhost:8082](http://localhost:8082)

Note: After the start of Jenkins you have to login as user `ecrdb` with password `test`. You can skip the "Getting Started" dialogue but clicking the `X` in the upper right corner. Then click on the blue button `Start using Jenkins`. After that your are logged in, but that is not a requirement. Users can view the Jenkins instance without logging in.

# Tutorial

[./docs/tutorial.md](./docs/tutorial.md)

# API Specification

[./docs/api_spec.md](./docs/api_spec.md)
