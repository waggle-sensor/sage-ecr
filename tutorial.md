# Tutorial

## Start ECR
```bash
git clone https://github.com/sagecontinuum/sage-ecr.git
cd sage-ecr
./run.sh -d
```

## Define ECR_API variable
```bash
export ECR_API="localhost:5000"
```

## upload "simple plugin"
```bash
curl -X POST ${ECR_API}/apps -H "Authorization: sage token1" -d '{"name":"simple","description":"very important app","version":"1.0","namespace":"sage","sources":[{"name":"default","architectures":["linux/amd64"],"url":"https://github.com/waggle-sensor/edge-plugins.git","branch":"master","directory":"plugin-simple","dockerfile":"Dockerfile_sage"},{"name":"armv7","architectures":["linux/arm/v7"],"url":"https://github.com/waggle-sensor/edge-plugins.git","branch":"master","directory":"plugin-simple","dockerfile":"Dockerfile_sage"}],"resources":[{"type":"RGB_image_producer","view":"top","min_resolution":"600x800"}],"inputs":[{"id":"speed","type":"int"}],"metadata":{"my-science-data":12345}}'
# save the app id you got from the previous call:
export APP_ID=<...>
```

## trigger build
```bash
curl -X POST ${ECR_API}/apps/${APP_ID}/builds -H "Authorization: sage token1"
```

## open Jenkins in browser
[http://localhost:8082](http://localhost:8082)

Note: After the start of Jenkins you have to login as user ecrdb with password test. You can skip the "Getting Started" dialogue but clicking the X in the upper right corner. Then click on the blue button Start using Jenkins. After that your are logged in, but that is not a requirement. Users can view the Jenkins instance without logging in.

