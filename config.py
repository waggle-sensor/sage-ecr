import os
# https://mysqlclient.readthedocs.io/user_guide.html#mysqldb-mysql
mysql_host = os.getenv('MYSQL_HOST')
mysql_db =os.getenv('MYSQL_DATABASE')
mysql_user =  os.getenv('MYSQL_USER')
mysql_password =  os.getenv('MYSQL_PASSWORD')
#app.config['MYSQL_DATABASE_HOST'] = os.getenv('MYSQL_HOST')
#app.config['MYSQL_DATABASE_DB'] = os.getenv('MYSQL_DATABASE')
#app.config['MYSQL_DATABASE_USER'] = os.getenv('MYSQL_USER')
#app.config['MYSQL_DATABASE_PASSWORD'] = os.getenv('MYSQL_PASSWORD')






# app definition
valid_fields =["name", "description", "version", "namespace", "sources", "depends_on", "baseCommand", "arguments", "inputs", "resources", "metadata"]
valid_fields_set = set(valid_fields)
required_fields = set(["name", "description", "version", "sources"])

mysql_fields = ["name", "description", "version", "namespace", "depends_on", "baseCommand", "arguments", "inputs", "metadata"]
mysql_fields_det = set(valid_fields)

# architecture https://github.com/docker-library/official-images#architectures-other-than-amd64
architecture_valid = ["linux/amd64", "linux/arm64", "linux/arm/v6", "linux/arm/v7", "linux/arm/v8"]


# app input
input_fields_valid = ["id", "type"]
# "Directory" not suypported yet # ref: https://www.commonwl.org/v1.1/CommandLineTool.html#CWLType
input_valid_types = ["boolean", "int", "long", "float", "double", "string", "File"] 


# database fields
dbFields = mysql_fields + ["owner"]
dbFields_str  = ",".join(dbFields)


tokenInfoEndpoint = os.getenv('tokenInfoEndpoint')
tokenInfoUser = os.getenv('tokenInfoUser')
tokenInfoPassword = os.getenv('tokenInfoPassword')
auth_disabled = os.getenv('DISABLE_AUTH', default="0") == "1"


# jenkins
jenkins_user = os.environ.get("JENKINS_USER", "anonymous")
jenkins_token = os.environ.get("JENKINS_TOKEN", "")
jenkins_server = os.getenv('JENKINS_SERVER', default="http://localhost:8082")

docker_build_args= os.environ.get("DOCKER_BUILD_ARGS", "")


# docker registry
docker_registry_url = os.environ.get("DOCKER_REGISTRY_URL", "registry.local:5001")


jenkinsfileTemplate = '''pipeline {
    agent any
    
    stages {
        stage('Build') {
            steps {
                git branch: '${branch}',
                    url: '${url}'
                dir("$${env.WORKSPACE}/${directory}"){
                    sh "docker version"
                    sh "docker buildx version"
                    sh "docker buildx build --pull --platform ${platforms} ${build_args_command_line} -t ${namespace}/${name} ."
                    sh "docker tag ${namespace}/${name} ${docker_registry_url}/${namespace}/${name}"
                    ${docker_login} 
                    sh "docker push ${docker_registry_url}/${namespace}/${name}"
                }
                sleep 10
                echo 'Building..'
            }
        }
        stage('Test') {
            steps {
                echo 'Testing..'
            }
        }
    }
}
'''
