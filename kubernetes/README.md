
# Kubernetes deployment of ECR


WARNING: this is currently not working with a local docker registry. It will work with a local docker registry only if the registry can be reached by a unique global url (hostname or domain) that can be reached from the docker engine as well as the docker client (engine and client run in different networks in kubernetes).


The following instructions are targeted at a local test deployment via [minikube](https://kubernetes.io/docs/tasks/tools/install-minikube/). Everything is already pre-configured and should run as is. For a production deployment the configuration should be overwritten with kubernetes kustomize overlays.


## Preparation (Minikube example)

```bash
minikube start
minikube start --insecure-registry "10.0.0.0/24" --insecure-registry "ecr-registry:5000"


kubectl config use-context minikube

#kubectl create namespace sage

# permanently save the namespace for all subsequent kubectl commands in that context.
#kubectl config set-context --current --namespace=sage



```

## MySQL

Install MySQL, e.g.
```bash
helm install mysql --set image.tag=8.0.23-debian-10-r30 --set primary.persistence.size=1Gi bitnami/mysql
```

load schema
```bash
MYSQL_ROOT_PASSWORD=$(kubectl get secret --namespace default mysql -o jsonpath="{.data.mysql-root-password}" | base64 --decode)
echo "MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}"

kubectl exec -i mysql-0 -- mysql -u root -p${MYSQL_ROOT_PASSWORD} < ../schema.sql
#verify database and tables exist now:
kubectl exec -i mysql-0 -- mysql -u root -p${MYSQL_ROOT_PASSWORD} -e 'show databases;'
kubectl exec -i mysql-0 -- mysql -u root -p${MYSQL_ROOT_PASSWORD} -e 'use SageECR; show tables;'
```

Create MySQL user
```bash

MYSQL_ROOT_PASSWORD=$(kubectl get secret --namespace default mysql -o jsonpath="{.data.mysql-root-password}" | base64 --decode)
echo "MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD}"

kubectl exec -ti mysql-0 -- mysql -u root -p${MYSQL_ROOT_PASSWORD}
```

Inside of MySQL create user with password: (In test environment use "test" as password)
```bash
CREATE USER 'ecr-user'@'%' identified by '<NEW_USER_PASSWORD>';
GRANT ALL PRIVILEGES ON Beekeeper.* TO 'ecr-user'@'%';
#verify:
SELECT User, Host  FROM mysql.user;
exit
```
Save the `<NEW_USER_PASSWORD>` as an overlay in the ecr-api secret.

## Deploy

For prodcution deployment it is recommended to copy the overlay-example directory contents and create a new overlay directory in a secure location.

```bash
#verify overlay
kubectl kustomize ./overlay-example/

# this starts all services, but ECR will be missing a Jenkins token!
kubectl apply -k ./overlay-example/
```

## Inject token

To let `ecr-api` talk to Jenkins a token is needed. Because Jenkins does not let us inject a token on startup, it is automatically generated when Jenkins starts. After Jenkins has started and generated a token for user `ecrdb`, the token has to be extracted from the Jenkins pod (container) and stored as a secret.

Get token from Jenkins or user ecrdb  (fix namespace if needed)
```bash
export JENKINS_TOKEN=$(kubectl exec -ti $(kubectl get pods -n default | grep "^ecr-jenkins-" | cut -f 1 -d ' ') -n default -- /bin/cat /var/jenkins_home/secrets/ecrdb_token.txt)
echo "JENKINS_TOKEN=${JENKINS_TOKEN}"
```

Two options to inject secret:
a) only in test environment, without overlay:
```bash
kubectl patch secret ecr-api-secret -p='{"stringData":{"JENKINS_TOKEN": "'${JENKINS_TOKEN}'"}}'
```
The default kustomize ecr-api-secret will overwrite that!

b) Store token in secret / generate
```bash
sed -i -e 's/JENKINS_TOKEN: .*/JENKINS_TOKEN: "'${JENKINS_TOKEN}'"/' overlay/ecr-api.secret.yaml
kubectl apply -k ./overlay/
```

Restart ecr-api to use new token from secret
```bash
kubectl rollout restart deployment ecr-api
```

## Ingress Controller

### minikube
```bash
minikube addons enable ingress
minikube ip
```

Visit `<IP>/jenkins` to access the Jenkins instance.

### docker desktop

Install ingress-nginx
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v0.45.0/deploy/static/provider/cloud/deploy.yaml
```

visit:
- http://localhost:80/ecr/jenkins/
- http://localhost:80/ecr/api/

# testing

```bash
kubectl exec -ti $(kubectl get pods | grep "^ecr-api-" | cut -f 1 -d ' ') -- /bin/ash -c 'coverage run -m pytest -v --runslow  &&  coverage report -m'
```