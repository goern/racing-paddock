import logging
import os
import re

import yaml
from kubernetes import client
from kubernetes import config as kubeconfig


class KubeCrew:
    def __init__(self):
        # Load Kubeconfig (assumes in-cluster or configured environment)
        try:
            kubeconfig.load_kube_config()
        except kubeconfig.config_exception.ConfigException:
            kubeconfig.load_incluster_config()

        # get the namespace from the environment
        self.namespace = os.environ.get("POD_NAMESPACE", "b4mad-racing")
        # Read the YAML file
        path = os.path.dirname(os.path.abspath(__file__))
        with open(f"{path}/deployment_pitcrew.yaml", "r") as file:
            deployment_yaml = yaml.safe_load(file)
            # Create a V1Deployment object from the YAML data
            self.deployment_obj = client.V1Deployment(**deployment_yaml)
            # logging.debug(f"Deployment object: {self.deployment_obj}")

        self.drivers = set()

    def sanitize_name(self, name):
        # Kubernetes names must be valid DNS subdomains / a lowercase RFC 1123 subdomain
        # and must start and end with an alphanumeric character
        # regexp: '[a-z0-9]([-a-z0-9]*[a-z0-9])?(\\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*'

        return re.sub(r"[^a-zA-Z0-9]+", "-", name).lower()

    def stop_coach(self, driver_name):
        namespace = self.namespace
        name = f"pitcrew-{driver_name}"
        name = self.sanitize_name(name)

        logging.info(f"Stopping deployment {name} in namespace {namespace}")
        v1 = client.AppsV1Api()
        try:
            api_response = v1.delete_namespaced_deployment(namespace=namespace, name=name)
            logging.info("Deployment deleted.")
            logging.debug(f"Deployment deleted. status={api_response}")
            return True
        except client.rest.ApiException as e:
            logging.error(f"Exception deleting deployment: {e}")
            return False

    def start_coach(self, driver_name):
        namespace = self.namespace
        name = f"pitcrew-{driver_name}"
        name = self.sanitize_name(name)
        v1 = client.AppsV1Api()

        deployment = self.deployment_obj
        deployment.metadata["name"] = name
        deployment.metadata["labels"]["app.kubernetes.io/component"] = name
        deployment.metadata["labels"]["b4mad.racing/driver"] = name
        deployment.metadata["labels"]["b4mad.racing/component"] = "pitcrew"
        deployment.spec["selector"]["matchLabels"]["app.kubernetes.io/component"] = name
        deployment.spec["template"]["metadata"]["labels"]["app.kubernetes.io/component"] = name

        # set spec.template.spec.containers[0].env[-1].value to the driver name
        deployment.spec["template"]["spec"]["containers"][0]["env"][-1]["value"] = driver_name

        logging.info(f"Creating deployment {name} in namespace {namespace}")
        try:
            api_response = v1.create_namespaced_deployment(namespace=namespace, body=deployment)
            logging.info(f"Deployment created. status={api_response}")
            return True
        except client.rest.ApiException as e:
            logging.error(f"Exception creating deployment: {e}")
            return False

    def get_coach_status(self, driver_name):
        namespace = self.namespace
        name = f"pitcrew-{driver_name}"
        name = self.sanitize_name(name)
        v1 = client.AppsV1Api()

        try:
            api_response = v1.read_namespaced_deployment(namespace=namespace, name=name)
            # logging.debug(f"Deployment found. status={api_response}")
            return api_response
        except client.rest.ApiException as e:
            logging.error(f"Exception reading deployment: {e}")
            return False

    def get_all_coaches(self) -> list[str]:
        namespace = self.namespace
        v1 = client.AppsV1Api()
        label_selector = "b4mad.racing/component=pitcrew"

        try:
            api_response = v1.list_namespaced_deployment(namespace=namespace, label_selector=label_selector)
            # logging.debug(f"Deployments found. status={api_response}")
            # return a list of all deployment names
            return [item.metadata.name for item in api_response.items]
        except client.rest.ApiException as e:
            logging.error(f"Exception listing deployments: {e}")
            return []

    def sync_deployments(self):
        # get all deployments
        deployments = self.get_all_coaches()
        # sanitized drivers
        sanitized_drivers = [self.sanitize_name(driver) for driver in self.drivers]
        # stop deployments that are not in self.drivers
        for deployment in deployments:
            driver_name = deployment.replace("pitcrew-", "")
            if driver_name not in sanitized_drivers:
                self.stop_coach(driver_name)
        # start deployments that are in self.drivers
        for driver_name in self.drivers:
            self.start_coach(driver_name)
