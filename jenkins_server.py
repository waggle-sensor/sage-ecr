
import jenkins
# https://python-jenkins.readthedocs.io/en/latest/
# https://opendev.org/jjb/python-jenkins
# pip install python-jenkins


import time
import xmltodict
import json
from config import *
import requests
import sys
from string import Template

class JenkinsServer():
    def __init__ ( self , host, username, password, retries=5) :


        if not host: 
            raise Exception("Jenkins host not defined")

        #self.host = host
        #self.username = username
        #self.password = password
        count = 0
        while True:
            try:
                self.server = jenkins.Jenkins(host, username=username, password=password)

                user = self.server.get_whoami()
                version = self.server.get_version()

            except Exception as e: # pragma: no cover
                if count > retries:
                    raise
                print(f'Could not connnect to Jenkins ({host}), error={e}, retry in 2 seconds', file=sys.stderr)
                time.sleep(2)
                count += 1
                continue
            break

        
        return
    
    def hasJenkinsJob(self, id):
        

        try:
            job_exists = self.server.job_exists(id)
        except Exception as e:
            raise
            #raise ErrorResponse(f'(server.get_job_config) got exception: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        return job_exists  


    def build_job(self, job_id):
        

        # https://python-jenkins.readthedocs.io/en/latest/api.html#jenkins.Jenkins.build_job
        queue_item_number = self.server.build_job(job_id)
        return queue_item_number

    
    def get_job_info(self, job_id):
        
    
        return self.server.get_job_info(job_id, depth=0, fetch_all_builds=False)





    def createJob(self, id, app_spec, source_name, overwrite=False):

       

        # format https://github.com/user/repo.git#v1.0

        
        version = app_spec["version"]

        sources=app_spec.get("sources", [])
        if len(sources) == 0 :
            raise Exception("field sources empty")

        source = None
        for src in sources:
            if src.get("name", "") == source_name:
                source = src
                break

        if not source :
            raise Exception(f'Source with name {source_name} not found')

        #sourceArray = source.split("#", 3)

        git_url = source.get("url", "")
        git_branch = source.get("branch", "master")
        git_directory = source.get("directory", ".")
        if git_directory.startswith("/"):
            git_directory=git_directory[1:]

        platforms = source.get("architectures", [])
        if len(platforms) == 0:
            raise Exception("No architectures specified")
        platforms_str = ",".join(platforms)

        build_args = source.get("build_args", {})
        build_args_command_line = ""
        for key in build_args:
            value = build_args[key]
            build_args_command_line += f" --build-arg {key}={value}"

        if docker_build_args != "":
            build_args_command_line += f" {docker_build_args}"


        actual_namespace = ""
        namespace = app_spec.get("namespace", "")
        if len(namespace) > 0:
            actual_namespace = namespace
        else:
            actual_namespace = app_spec.get("owner", "")
        

        
      
            
        docker_login='''withCredentials([usernamePassword(credentialsId: 'registry-user', passwordVariable: 'REGISTRY_USER_PWD', usernameVariable: 'REGISTRY_USERNAME')]) {
                sh "echo $REGISTRY_USER_PWD | docker login -u $REGISTRY_USERNAME --password-stdin ''' +docker_registry_url +'''"
            }
        '''
        
        

        name = app_spec["name"]
        template = Template(jenkinsfileTemplate)
        try:
            jenkinsfile = template.substitute(  url=git_url, 
                                                branch=git_branch,
                                                directory=git_directory,
                                                namespace=actual_namespace, 
                                                name=name,
                                                version=version,
                                                platforms=platforms_str,
                                                build_args_command_line=build_args_command_line,
                                                docker_registry_url=docker_registry_url,
                                                docker_login=docker_login)
        except Exception as e:
            raise Exception(f'  url={git_url}, branch={git_branch}, directory={git_directory}  e={str(e)}')

        #print(jenkins.EMPTY_CONFIG_XML)
        newJob = createPipelineJobConfig(jenkinsfile)
        #print(newJob)


    

        newJob_xml = xmltodict.unparse(newJob) #.decode("utf-8") 
        #print("------")
        #print(newJob_xml)
        #print("------")
        #print(jenkins.EMPTY_CONFIG_XML)
        #print("------")
        
        if overwrite:
            self.server.reconfig_job(id , newJob_xml) 
        else:
            self.server.create_job(id, newJob_xml)
        

        timeout = 10

        while True:
            try:

                my_job = self.server.get_job_config(id)
                return my_job
            except jenkins.NotFoundException as e: # pragma: no cover
                pass
            except Exception as e: # pragma: no cover
                raise
           
            if True: # pragma: no cover
                time.sleep(2)
                timeout -= 2

                if timeout <= 0:
                    raise Exception(f'timout afer job creation')
                continue


        return 1
        #print("jobs: "+server.jobs_count())

    
def createPipelineJobConfig(jenkinsfile):
    jenkins_job_example_xml = '''<?xml version='1.1' encoding='UTF-8'?>
    <flow-definition plugin="workflow-job@2.39">
    <description></description>
    <keepDependencies>false</keepDependencies>
    <properties/>
    <definition class="org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition" plugin="workflow-cps@2.80">
        <script>pipeline {
    agent any

    stages {
        stage(&apos;Hello&apos;) {
            steps {
                echo &apos;Hello World&apos;
            }
        }
    }
    }
    </script>
        <sandbox>true</sandbox>
    </definition>
    <triggers/>
    <quietPeriod>0</quietPeriod>
    <disabled>false</disabled>
    </flow-definition>
    '''



    job = xmltodict.parse(jenkins_job_example_xml)

    #jenkinsfile = 'pipeline {}'
    print(json.dumps(job, indent=4))

    job["flow-definition"]["definition"]["script"] = jenkinsfile # cgi.escape(jenkinsfile)
    #job["project"]["scm"]["userRemoteConfigs"]["hudson.plugins.git.UserRemoteConfig"]["url"] = 'https://github.com/sagecontinuum/sage-cli.git'


    print(json.dumps(job, indent=4))
    return job