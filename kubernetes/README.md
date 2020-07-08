
# Kubernetes deployment of ECR

WARNING: THIS IS WORK-IN-PROGRESS

```bash
kubectl config use-context minikube

kubectl create namespace sage

# permanently save the namespace for all subsequent kubectl commands in that context.
kubectl config set-context --current --namespace=sage
```


## Deploy
```
kubectl create configmap ecr-db-initdb-config -n sage --from-file=../schema.sql

kubectl kustomize . | kubectl apply -f -

```

## IP address

In case of a minikube deployment:

```bash
minikube ip
```

Visit `<IP>/jenkins` to access the Jenkins instance.



# testing

```bash
kubectl exec -ti $(kubectl get pods | grep "^ecr-api-" | cut -f 1 -d ' ') -- /bin/ash -c 'coverage run -m pytest -v --runslow  &&  coverage report -m'
```