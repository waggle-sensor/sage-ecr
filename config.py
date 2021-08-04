import os, sys
# https://mysqlclient.readthedocs.io/user_guide.html#mysqldb-mysql
mysql_host = os.getenv('MYSQL_HOST')
mysql_db =os.getenv('MYSQL_DATABASE')
mysql_user =  os.getenv('MYSQL_USER')
mysql_password =  os.getenv('MYSQL_PASSWORD')
#app.config['MYSQL_DATABASE_HOST'] = os.getenv('MYSQL_HOST')
#app.config['MYSQL_DATABASE_DB'] = os.getenv('MYSQL_DATABASE')
#app.config['MYSQL_DATABASE_USER'] = os.getenv('MYSQL_USER')
#app.config['MYSQL_DATABASE_PASSWORD'] = os.getenv('MYSQL_PASSWORD')





# app definition , these are the app fields (as seen by user) that are stored in the tables Apps
valid_fields =["namespace", "name", "version", "description" , "source", "depends_on", "baseCommand", "arguments", "inputs", "resources", "metadata", "frozen","testing","profiling"]
valid_fields_set = set(valid_fields)

# app definition for profiling 
valid_profile_fields = ["namespace", "name", "version","app_profile"]
valid_profile_fields_set = set(valid_profile_fields)



app_view_fields = ["namespace", "name", "version", "description" , "source", "depends_on", "baseCommand", "arguments", "inputs", "resources", "metadata","testing","profiling"]

required_fields = { "description" : "str",
                    "source" : "dict"}


mysql_Apps_fields = {
                "id"            : "str",
                "namespace"     : "str",
                "name"          : "str",
                "version"       : "str",
                "description"   : "str",
                "depends_on"    : "str",
                "baseCommand"   : "str",
                "arguments"     : "str",
                "inputs"        : "json",
                "metadata"      : "json",
                "frozen"        : "bool",
                "testing"       : "json",
                "profiling"     : "json",
                "owner"         : "str",
                "time_created"  : "datetime",
                "time_last_updated"        : "datetime",
                }


mysql_Sources_fields = {
                "architectures": "json",
                "url":"str",
                "branch":"str",
                "directory":"str",
                "dockerfile":"str",
                "build_args":"json"
            }



mysql_Profile_fields = {
                "id"            : "str",
                "namespace"     : "str",
                "name"          : "str",
                "version"       : "str",
                "time_created"  : "datetime",
                "time_last_updated"        : "datetime",
                "app_profile": "json",
            }
#mysql_Apps_fields_set = set(valid_fields)

# architecture https://github.com/docker-library/official-images#architectures-other-than-amd64
architecture_valid = ["linux/amd64", "linux/arm64", "linux/arm/v6", "linux/arm/v7", "linux/arm/v8"]


# app input
input_fields_valid = ["id", "type"]
# "Directory" not suypported yet # ref: https://www.commonwl.org/v1.1/CommandLineTool.html#CWLType
input_valid_types = ["boolean", "int", "long", "float", "double", "string", "File"]


# Apps table fields
#dbAppsFields = mysql_Apps_fields.keys()
dbAppsFields_str  = ",".join(mysql_Apps_fields.keys())
dbSourcesFields_str  = ",".join(mysql_Sources_fields.keys())



auth_method = os.getenv('AUTH_METHOD', default="static") # or sage
if auth_method=="":
    auth_method = "static"
if auth_method != "static" and auth_method != "sage":
    sys.exit(f"AUTH_METHOD {auth_method} invalid")

# for auth_method==sage
tokenInfoEndpoint = os.getenv('tokenInfoEndpoint')
tokenInfoUser = os.getenv('tokenInfoUser')
tokenInfoPassword = os.getenv('tokenInfoPassword')

if auth_method == "sage":
    if tokenInfoEndpoint == "":
        sys.exit("tokenInfoEndpoint not defined")
    if tokenInfoUser == "":
        sys.exit("tokenInfoUser not defined")
    if tokenInfoPassword == "":
        sys.exit("tokenInfoPassword not defined")



# static_tokens: only used for testing
static_tokens = {   "token1" : { "id": "testuser"} ,
                    "admin_token" : { "id":"admin", "is_admin": True} ,
                    "token3" : { "id": "sage_docker_auth", "scopes":"ecr_authz_introspection"} ,
                    "token2" : { "id": "testuser2"}
                }

add_user=os.getenv('ADD_USER', default="")
if add_user:
    add_user_array = add_user.split(",")
    if len(add_user_array) != 2:
        sys.exit(f"Cannot parse ADD_USER")

    x_token = add_user_array[0]
    x_user_id = add_user_array[1]
    static_tokens[x_token] = {  "id":x_user_id }
    print(f'added token {x_token} for user {x_user_id}', file=sys.stderr)



# jenkins
jenkins_user = os.environ.get("JENKINS_USER", "ecrdb")
jenkins_token = os.environ.get("JENKINS_TOKEN", "")
jenkins_server = os.getenv('JENKINS_SERVER', default="http://localhost:8082")

docker_build_args= os.environ.get("DOCKER_BUILD_ARGS", "")


# docker registry
docker_registry_url = os.environ.get("DOCKER_REGISTRY_URL", "")
if docker_registry_url == "":
        sys.exit("docker_registry_url not defined")


docker_registry_push_allowed = os.environ.get("DOCKER_REGISTRY_PUSH_ALLOWED", "0") == "1"



jenkinsfileTemplate = ''' pipeline{

    agent any
    stages {
        stage ('Write') {
            steps{

                script{

                    for (arch in ${platforms_list}){

                        stage('Build') {

                            currentBuild.displayName = "${version}"

                            git branch: '${branch}',
                            url: '${url}'
                            dir("$${env.WORKSPACE}/${directory}"){
                                sh "docker version"
                                sh "docker buildx version"
                                ${docker_login}
                                sh "docker buildx build --pull --load --builder sage --platform $$arch ${build_args_command_line} -t ${docker_registry_url}/${namespace}/${name}:${version} -f ${dockerfile} ."

                            }

                        }

                        stage('Test') {

                            currentBuild.displayName = "${version}"

                            git branch: '${branch}',
                            url: '${url}'
                            dir("$${env.WORKSPACE}/${directory}"){
                                sh "docker version"
                                sh "docker buildx version"
                                ${docker_login}

                                script{
                                        if ( "${command}" == "''" ){
                                            ;
                                        }
                                        else{
                                            sh "docker run -i --rm ${entrypoint} ${docker_registry_url}/${namespace}/${name}:${version} \'${command}\'"
                                        }
                                }
                            }

                        }

                    }
                    stage ('Multi Arch Build'){
                        git branch: '${branch}',
                        url: '${url}'
                        dir("$${env.WORKSPACE}/${directory}"){
                            sh "docker version"
                            sh "docker buildx version"
                            ${docker_login}
                            sh "docker buildx build --pull --builder sage --platform ${platform} ${build_args_command_line} -t ${docker_registry_url}/${namespace}/${name}:${version} -f ${dockerfile} ."

                        }
                    }



                }




            }

        }


}
post {
                       always {
                            cleanWs(cleanWhenNotBuilt: true)
                        }
                    }

    }
'''




jenkinsfileTemplateProfile = '''
  node('master') {        
            stage ('Profile Build'){

                    git branch: '${branch}',
                        url: '${url}'
                    dir("$${env.WORKSPACE}/${directory}"){
                        docker.withRegistry('https://localhost:5002') {
                            def customImage = docker.build("${c}")
                            customImage.push()
                        }
                }
            }

            stage ('Profiler Image'){
                git branch: '${app_branch}',
                    url: '${app_url}'

                docker.withRegistry('https://localhost:5002') {
                    def Image = docker.image("${c}")
                    Image.pull()
                             
                    dir("$${env.WORKSPACE}/${app_dir}"){  
                        def server_container_build = docker.build('profiling-agent', '--build-arg APP_NAME=${c} .')
                          server_container_build.push('latest')
                    }    

                }

            }

             stage ('Profiling'){
                    git branch: '${branch}',
                        url: '${url}'
                     dir("$${env.WORKSPACE}/${directory}"){
                    docker.withRegistry('https://localhost:5002') {

                        docker.image('profiling-agent'). withRun('-t --entrypoint /bin/bash --volumes-from jenkins --network host ${app_docker_args}') {
                              // sh 'mkdir profile_output'
                               echo "The Docker container has finished, stashing profile metrics..."
                               sh 'ls -l'
                                
                        }

                    }
                }
            }

        stage ('Saving Profile Output'){
                sh """
                    if [ -d "$${env.WORKSPACE}/profile_output" ] 
                    then
                         docker exec -i sage-ecr_db_1 mysql -usage -ptest -e 'USE SageECR;UPDATE Profiles SET app_profile = "${namespace}/${name}/profile_output" WHERE namespace = "sage" ; '
                    else
                        echo "Error: Directory profile_output does not exists."
                    fi
                """
                sh 'ls -l'

        }
        
}
        
'''

