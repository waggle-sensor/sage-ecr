
import hudson.model.*
import jenkins.model.*
import jenkins.security.*
import jenkins.security.apitoken.*
import jenkins.install.*;
import hudson.util.*;

println "setting up ecr token..."
def userName = 'ecrdb'
def tokenName = 'ecrdb-token'
// TODO(sean) read this from secret
def tokenValue = '114df297873d76b7865486b00e28afa881'

def user = User.get(userName, false)
def apiTokenProperty = user.getProperty(ApiTokenProperty.class)
// TODO(sean) check if fails if already exists
apiTokenProperty.tokenStore.addFixedNewToken(tokenName, tokenValue)

// from https://riptutorial.com/jenkins/example/24925/disable-setup-wizard
def instance = Jenkins.getInstance()
instance.setInstallState(InstallState.INITIAL_SETUP_COMPLETED)

println "init.groovy is done"
