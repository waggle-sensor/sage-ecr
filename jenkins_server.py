import jenkins

# https://python-jenkins.readthedocs.io/en/latest/
# https://opendev.org/jjb/python-jenkins
# pip install python-jenkins


import time
import xmltodict
import json
from config import *
from string import Template
import shlex


class JenkinsServer:
    def __init__(self, host, username, password, retries=5):
        self.server = jenkins.Jenkins(host, username=username, password=password)

    def hasJenkinsJob(self, id):
        return self.server.job_exists(id)

    def build_job(self, job_id):
        # https://python-jenkins.readthedocs.io/en/latest/api.html#jenkins.Jenkins.build_job
        return self.server.build_job(job_id)

    def get_job_info(self, job_id):
        return self.server.get_job_info(job_id, depth=0, fetch_all_builds=False)

    def createJob(self, id, app_spec, overwrite=False, skip_image_push=False):
        # format https://github.com/user/repo.git#v1.0
        version = app_spec["version"]

        source = app_spec.get("source", None)
        if not source:
            raise Exception("field source empty")

        git_url = source.get("url", "")

        tag = source.get("tag") or ""
        branch = source.get("branch") or ""

        if tag != "":
            git_branch = f"refs/tags/{tag}"
        elif branch != "":
            git_branch = branch
        else:
            raise Exception("neither tag nor branch specified")

        git_directory = source.get("directory", ".")
        git_directory = git_directory.removeprefix("/")

        git_dockerfile = source.get("dockerfile", "./Dockerfile")

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

        name = app_spec["name"]

        # TODO(sean) Decide if / host to restore test feature and understand its relationship to profiling. We should consider a unified approach to those.
        # TODO(sean) Add test case for submodule clone.
        # fix dockerfile support
        template = Template(
            """pipeline {
    agent any
    stages {
        stage ("Checkout") {
            steps {
                checkout scmGit(
                    branches: [[name: '${branch}']],
                    extensions: [cloneOption(shallow: true)],
                    userRemoteConfigs: [[url: '${url}']],
                    poll: false)
                script {
                    dir("$${env.WORKSPACE}") {
                        sh "git submodule update --init --recursive"
                    }
                }
            }
        }
        stage ("Build") {
            steps {
                script {
                    stage("Build") {
                        currentBuild.displayName = "${version}"
                        dir("$${env.WORKSPACE}/${directory}") {
                            sh "${build_command}"
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
"""
        )

        # add validation here!!!

        options = ["--opt", f"platform={','.join(platforms)}"]

        # specifies an alternative dockerfile filename
        if git_dockerfile and git_dockerfile != "":
            options += ["--opt", f"filename={git_dockerfile}"]

        output_args = [
            "type=image",
            f"name={docker_registry_url}/{actual_namespace}/{name}:{version}",
        ]

        # specifies that we should push the image to the registry
        if docker_registry_push_allowed:
            output_args += ["push=true"]

        # specifies that the registry is insecure (served over http instead of https). should only be used for local testing!
        if docker_registry_insecure:
            output_args += ["registry.insecure=true"]

        build_command = shlex.join(
            [
                "buildctl",
                "--addr",
                buildkitd_address,
                "build",
                "--frontend=dockerfile.v0",
                "--local",
                "context=.",
                "--local",
                "dockerfile=.",
                *options,
                "--output",
                ",".join(output_args),
            ]
        )

        try:
            jenkinsfile = template.substitute(
                url=git_url,
                branch=git_branch,
                directory=git_directory,
                # dockerfile=git_dockerfile, # add this back in
                version=version,
                build_command=build_command,
            )
        except Exception as e:
            raise Exception(
                f"template failed: url={git_url}, branch={git_branch}, directory={git_directory}, e={str(e)}"
            )

        # print(jenkins.EMPTY_CONFIG_XML)
        newJob = createPipelineJobConfig(jenkinsfile, f"{actual_namespace}/{name}")
        print(newJob)

        newJob_xml = xmltodict.unparse(newJob)  # .decode("utf-8")
        # print("------")
        # print(newJob_xml)
        # print("------")
        # print(jenkins.EMPTY_CONFIG_XML)
        # print("------")

        if overwrite:
            self.server.reconfig_job(id, newJob_xml)
        else:
            self.server.create_job(id, newJob_xml)

        timeout = 10

        while True:
            try:
                return self.server.get_job_config(id)
            except jenkins.NotFoundException as e:  # pragma: no cover
                pass
            except Exception as e:  # pragma: no cover
                raise

            time.sleep(2)
            timeout -= 2
            if timeout <= 0:
                raise Exception(f"timout afer job creation")


def createPipelineJobConfig(jenkinsfile, displayName):
    jenkins_job_example_xml = """<?xml version='1.1' encoding='UTF-8'?>
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
    """

    job = xmltodict.parse(jenkins_job_example_xml)

    # jenkinsfile = 'pipeline {}'
    print(json.dumps(job, indent=4))

    job["flow-definition"]["definition"][
        "script"
    ] = jenkinsfile  # cgi.escape(jenkinsfile)
    job["flow-definition"]["displayName"] = displayName
    # job["project"]["scm"]["userRemoteConfigs"]["hudson.plugins.git.UserRemoteConfig"]["url"] = 'https://github.com/sagecontinuum/sage-cli.git'

    print(json.dumps(job, indent=4))
    return job
