import os, sys


def parsebool(s):
    if s.lower() in ["1", "t", "true"]:
        return True
    if s.lower() in ["0", "f", "false"]:
        return False
    raise ValueError("invalid boolean flag")


# https://mysqlclient.readthedocs.io/user_guide.html#mysqldb-mysql
mysql_host = os.getenv('MYSQL_HOST')
mysql_db = os.getenv('MYSQL_DATABASE')
mysql_user =  os.getenv('MYSQL_USER')
mysql_password =  os.getenv('MYSQL_PASSWORD')
#app.config['MYSQL_DATABASE_HOST'] = os.getenv('MYSQL_HOST')
#app.config['MYSQL_DATABASE_DB'] = os.getenv('MYSQL_DATABASE')
#app.config['MYSQL_DATABASE_USER'] = os.getenv('MYSQL_USER')
#app.config['MYSQL_DATABASE_PASSWORD'] = os.getenv('MYSQL_PASSWORD')


S3_ENDPOINT = os.getenv('S3_ENDPOINT')
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY')
S3_BUCKET=os.getenv('S3_BUCKET')
S3_FOLDER=os.getenv('S3_FOLDER')


# directory to clone and zip git repositories (not used by jenkins)
ecr_temp_dir = "/temp/ecr/"


# app definition , these are the app fields (as seen by user) that are stored in the tables Apps
valid_fields =[
    "namespace", "name", "version", "description",
    "keywords", "authors", "collaborators", "homepage", "funding", "license",
    "source", "depends_on", "baseCommand", "arguments", "inputs", "resources", "metadata", "frozen", "testing"
]

valid_fields_set = set(valid_fields)

app_view_fields = ["namespace", "name", "version", "description" , "source", "depends_on", "baseCommand", "arguments", "inputs", "resources", "metadata","testing"]

required_fields = { "description" : "str",
                    "source" : "dict"}


mysql_Apps_fields = {
                "id"            : "str",
                "namespace"     : "str",
                "name"          : "str",
                "version"       : "str",
                "description"   : "str",
                "keywords"   : "str",
                "authors"   : "str",
                "collaborators"   : "str",
                "homepage"   : "str",
                "funding"   : "str",
                "license"   : "str",
                "depends_on"    : "str",
                "baseCommand"   : "str",
                "arguments"     : "str",
                "inputs"        : "json",
                "metadata"      : "json",
                "frozen"        : "bool",
                "testing"       : "json",
                "owner"         : "str",
                "time_created"  : "datetime",
                "time_last_updated"        : "datetime",
                }


mysql_Sources_fields = {
                "architectures": "json",
                "url":"str",
                "branch":"str",
                "tag":"str",
                "git_commit":"str",
                "directory":"str",
                "dockerfile":"str",
                "build_args":"json"
            }
#mysql_Apps_fields_set = set(valid_fields)

# architecture https://github.com/docker-library/official-images#architectures-other-than-amd64
architecture_valid = ["linux/amd64", "linux/arm64", "linux/arm/v6", "linux/arm/v7", "linux/arm/v8"]


# app input
input_fields_expected = ["id", "type"]
input_fields_valid = ["id", "type", "description", "default"]

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
static_tokens = {
    "testuser_token": {
        "id": "testuser",
        "is_approved": True,
    },
    "testuser2_token": {
        "id": "testuser2",
        "is_approved": True,
    },
    "notapproved_token": {
        "id": "notapproved",
        "is_approved": False,
    },
    "admin_token": {
        "id":"admin",
        "is_admin": True,
        "is_approved": True,
    },
    "sage_docker_auth_token": {
        "id": "sage_docker_auth",
        "scopes":"ecr_authz_introspection",
        "is_approved": False,
    },
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

docker_build_args = os.environ.get("DOCKER_BUILD_ARGS", "")
docker_run_args =os.environ.get("DOCKER_RUN_ARGS", "")

# docker registry
docker_registry_url = os.environ.get("DOCKER_REGISTRY_URL")
docker_registry_push_allowed = parsebool(os.environ.get("DOCKER_REGISTRY_PUSH_ALLOWED", "0"))
docker_registry_insecure = parsebool(os.environ.get("DOCKER_REGISTRY_INSECURE", "0"))

# buildkitd settings
buildkitd_address = os.environ.get("BUILDKITD_ADDR")

# redis cache settings
redis_host = os.environ.get("REDIS_HOST", "localhost")
redis_port = int(os.environ.get("REDIS_PORT", "6379"))
redis_ttl_seconds = int(os.environ.get("REDIS_TTL_SECONDS", "60"))
