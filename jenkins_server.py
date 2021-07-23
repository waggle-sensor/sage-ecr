
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





    def createJob(self, id, app_spec, overwrite=False, skip_image_push=False):



        # format https://github.com/user/repo.git#v1.0


        version = app_spec["version"]

        source=app_spec.get("source", None)
        if not source :
            raise Exception("field source empty")

        ###
        run_test = "\'echo No test defined\'"
        run_entrypoint = ""
        test = app_spec.get("testing")
        if test:


            test_command = test.get("command")

            if "mask_entrypoint" in test.keys() and test.get("mask_entrypoint"):
                    run_entrypoint = ' --entrypoint=\'\''


            #if entrypoint_command:
            #    all_entrypoint_command = " ".join(entrypoint_command)
            #    run_entrypoint = "\'" + all_entrypoint_command + "\'"
            if test_command:
                all_test_command = " ".join(test_command)
                run_test = "\'" +  all_test_command + "\'"




        # t = " \' rm -rf \' "




        #sourceArray = source.split("#", 3)

        git_url = source.get("url", "")
        git_branch = source.get("branch", "")
        if git_branch == "":
            raise Exception("branch not specified")

        git_directory = source.get("directory", ".")
        if git_directory.startswith("/"):
            git_directory=git_directory[1:]

        git_dockerfile = source.get("dockerfile", "./Dockerfile")

        platforms = source.get("architectures", [])
        if len(platforms) == 0:
            raise Exception("No architectures specified")
        platforms_str = ",".join(platforms)

        platforms_list = " ".join(platforms)

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




        # The registry user credentials are defined in the casc_jenkins.yaml file.
        docker_login='''withCredentials([usernamePassword(credentialsId: 'registry-user', passwordVariable: 'REGISTRY_USER_PWD', usernameVariable: 'REGISTRY_USERNAME')]) {
                sh 'echo $REGISTRY_USER_PWD | docker login -u $REGISTRY_USERNAME --password-stdin ''' +docker_registry_url +''''
            }
        '''


        do_push="--push"
        if skip_image_push:
            docker_login = ""
            do_push =""

        name = app_spec["name"]


        jenkinsfileTemplate = ""

        if test:
            jenkinsfileTemplate = jenkinsfileTemplatePrefix + jenkinsfileTemplateTestStage + jenkinsfileTemplateSuffix
        else:
            jenkinsfileTemplate = jenkinsfileTemplatePrefix + jenkinsfileTemplateSuffix

        template = Template(jenkinsfileTemplate)
        try:
            jenkinsfile = template.substitute(  url=git_url,
                                                branch=git_branch,
                                                directory=git_directory,
                                                dockerfile=git_dockerfile,
                                                namespace=actual_namespace,
                                                name=name,
                                                version=version,
                                                platforms=platforms_str,
                                                build_args_command_line=build_args_command_line,
                                                docker_registry_url=docker_registry_url,
                                                docker_login=docker_login,
                                                command = run_test,
                                                platforms_list = platforms,
                                                platform = platforms_str,
                                                entrypoint =run_entrypoint,
                                                do_push=do_push)
        except Exception as e:
            raise Exception(f'  url={git_url}, branch={git_branch}, directory={git_directory}  e={str(e)}')

        #print(jenkins.EMPTY_CONFIG_XML)
        newJob = createPipelineJobConfig(jenkinsfile, f'{actual_namespace}/{name}')
        print(newJob)




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


def createPipelineJobConfig(jenkinsfile, displayName):
    jenkins_job_example_xml = '''<?xml version='1.1' encoding='UTF-8'?>
    <flow-definition plugin="workflow-job@2.39">
    <displayName>overwrite_me</displayName>
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
    job["flow-definition"]["displayName"] = displayName
    #job["project"]["scm"]["userRemoteConfigs"]["hudson.plugins.git.UserRemoteConfig"]["url"] = 'https://github.com/sagecontinuum/sage-cli.git'


    print(json.dumps(job, indent=4))
    return job