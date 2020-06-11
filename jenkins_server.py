
import jenkins
# https://python-jenkins.readthedocs.io/en/latest/
# pip install python-jenkins


import time
import xmltodict
import json
from config import *
import requests
import sys
from string import Template

class JenkinsServer():
    def __init__ ( self , host, username, password, retries=60) :
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





    def createJob(self, id, app_spec, overwrite=False):

       

        # format https://github.com/user/repo.git#v1.0
        if not "source" in app_spec:
            raise Exception("field source missing")


        source=app_spec["source"]
        sourceArray = source.split("#", 3)

        git_url = sourceArray[0]
        git_branch = sourceArray[1]
        git_directory = ""
        if len(sourceArray) > 2:
            git_directory = sourceArray[2]
            if git_directory.startswith("/"):
                git_directory=git_directory[1:]
        #git_direcory =
        
        namespace = app_spec["owner"]
        if "namespace" in app_spec and len(app_spec["namespace"]) > 0:
            namespace = app_spec["namespace"]
        
        name = app_spec["name"]
        template = Template(jenkinsfileTemplate)
        try:
            jenkinsfile = template.substitute(url=git_url, branch=git_branch, directory=git_directory, namespace=namespace,  name=name)
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
            except jenkins.NotFoundException as e:
                pass
            except Exception as e:
                raise
                #raise ErrorResponse(f'(server.get_job_config 2) got exception: {str(e)}', status_code=HTTPStatus.INTERNAL_SERVER_ERROR)
            
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