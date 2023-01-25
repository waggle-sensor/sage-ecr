import hudson.model.*
import jenkins.model.*
import jenkins.security.*
import jenkins.security.apitoken.*
import jenkins.install.*;
import hudson.util.*;

println "setting up ecr token"
def userName = 'ecrdb'
def tokenName = 'ecrdb-token'
def tokenValue = System.getenv("JENKINS_TOKEN")

if (tokenValue == null) {
    println "ERROR! JENKINS_TOKEN must be set! Stopping..."
    System.exit(1)
}

def user = User.get(userName, false)
def apiTokenProperty = user.getProperty(ApiTokenProperty.class)
// TODO(sean) check if fails if already exists
apiTokenProperty.tokenStore.addFixedNewToken(tokenName, tokenValue)

// from https://riptutorial.com/jenkins/example/24925/disable-setup-wizard
println "setting up jenkins"
def instance = Jenkins.getInstance()
instance.setInstallState(InstallState.INITIAL_SETUP_COMPLETED)

println "init.groovy is done"
