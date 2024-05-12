import logging
import os
from kubernetes import client, config as kubeconfig
import yaml

class KubeCrew:
    def __init__(self):
        # Load Kubeconfig (assumes in-cluster or configured environment)
        kubeconfig.load_kube_config()

        # get the namespace from the environment
        self.namespace = os.environ.get('POD_NAMESPACE', 'b4mad-racing')

    def stop_coach(self, driver_name):
        namespace = self.namespace
        name = f"pitcrew-{driver_name}"

        logging.info(f"Stopping deployment {name} in namespace {namespace}")
        v1 = client.AppsV1Api()
        try:
            api_response = v1.read_namespaced_deployment(namespace=namespace, name=name)
            logging.info(f"Deployment deleted. status={api_response}")
        except client.rest.ApiException as e:
            logging.error(f"Exception when calling AppsV1Api->read_namespaced_deployment: {e}")

    def start_coach(self, driver_name):
        namespace = self.namespace
        name = f"pitcrew-{driver_name}"
        v1 = client.AppsV1Api()

        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(
                name=name,
                annotations={
                    "image.openshift.io/triggers": '[{"from":{"kind":"ImageStreamTag","name":"paddock:latest"},"fieldPath":"spec.template.spec.containers[?(@.name==\\"coach\\")].image"}]'
                }),
            spec=client.V1DeploymentSpec(
                replicas=2,
                selector=client.V1LabelSelector(match_labels={"app": "pitcrew"}),
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(labels={"app": "pitcrew"}),
                    spec=client.V1PodSpec(containers=[
                        client.V1Container(name="coach", image="paddock:latest")
                    ])
                )
            )
        )

        logging.info(f"Creating deployment {name} in namespace {namespace}")
        try:
            api_response = v1.create_namespaced_deployment(namespace=namespace, body=deployment)
            logging.info(f"Deployment created. status={api_response}")
        except client.rest.ApiException as e:
            logging.error(f"Exception when calling AppsV1Api->read_namespaced_deployment: {e}")
