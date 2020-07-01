
import hudson.model.*
import jenkins.model.*
import jenkins.security.*
import jenkins.security.apitoken.*
import jenkins.install.*;
import hudson.util.*;

// create token

// script parameters
def userName = 'ecrdb'
def tokenName = 'ecrdb-token'

def user = User.get(userName, false)
def apiTokenProperty = user.getProperty(ApiTokenProperty.class)
def result = apiTokenProperty.tokenStore.generateNewToken(tokenName)

user.save()

println "Got token: $result.plainValue"

File file = new File("/var/jenkins_home/secrets/ecrdb_token.txt")
file.write result.plainValue
//return result.plainValue

// get docker binary
def cmd = ["/get_docker_binary.sh"]

cmd.execute().with{
    def output = new StringWriter()
    def error = new StringWriter()
    //wait for process ended and catch stderr and stdout.
    it.waitForProcessOutput(output, error)
    //check there is no error
    println "error=$error"
    println "output=$output"
    println "code=${it.exitValue()}"
}


// from https://riptutorial.com/jenkins/example/24925/disable-setup-wizard
def instance = Jenkins.getInstance()
instance.setInstallState(InstallState.INITIAL_SETUP_COMPLETED)