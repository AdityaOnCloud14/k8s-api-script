import subprocess
import time
from kubernetes import client, config
from kubernetes.client.rest import ApiException

def connect_to_cluster():
    """Connect to the Kubernetes cluster using kubeconfig."""
    try:
        config.load_kube_config()
        print("✅ Connected to the Kubernetes cluster.")
    except Exception as e:
        raise RuntimeError(f"Failed to connect to the cluster. Ensure 'kubectl' is configured correctly. Error: {e}")

def install_helm_and_keda():
    """Install or upgrade Helm and KEDA in the Kubernetes cluster."""
    try:
        # Add the KEDA Helm repository
        print("🔄 Adding KEDA Helm repository...")
        subprocess.run(["helm", "repo", "add", "kedacore", "https://kedacore.github.io/charts"], check=True)
        subprocess.run(["helm", "repo", "update"], check=True)

        # Upgrade or install KEDA
        print("🔄 Installing or upgrading KEDA...")
        subprocess.run(
            ["helm", "upgrade", "--install", "keda", "kedacore/keda", "-n", "keda", "--create-namespace"],
            check=True,
        )
        print("✅ KEDA installed or upgraded successfully.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to install or upgrade Helm or KEDA. Command error: {e}")

def create_deployment(name, namespace, image, cpu_request, memory_request, cpu_limit, memory_limit, ports, scale_metric_type, scale_metric_value):
    """Create or update a deployment with KEDA scaling."""
    apps_api = client.AppsV1Api()
    custom_objects_api = client.CustomObjectsApi()

    # Define deployment spec
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {
                    "containers": [
                        {
                            "name": name,
                            "image": image,
                            "resources": {
                                "requests": {"cpu": cpu_request, "memory": memory_request},
                                "limits": {"cpu": cpu_limit, "memory": memory_limit},
                            },
                            "ports": [{"containerPort": port} for port in ports],
                        }
                    ]
                },
            },
        },
    }

    try:
        # Check if the deployment already exists
        existing_deployment = apps_api.read_namespaced_deployment(name, namespace)
        print(f"🔄 Deployment '{name}' already exists. Updating...")
        apps_api.patch_namespaced_deployment(name, namespace, deployment)
        print(f"✅ Deployment '{name}' updated.")
    except ApiException as e:
        if e.status == 404:  # Deployment does not exist, create it
            print(f"🔄 Creating deployment '{name}'...")
            apps_api.create_namespaced_deployment(namespace=namespace, body=deployment)
            print(f"✅ Deployment '{name}' created.")
        else:
            raise RuntimeError(f"Failed to create or update deployment '{name}'. Kubernetes API error: {e}")

    # Define KEDA ScaledObject
    scaled_object = {
        "apiVersion": "keda.sh/v1alpha1",
        "kind": "ScaledObject",
        "metadata": {"name": f"{name}-scaled-object", "namespace": namespace},
        "spec": {
            "scaleTargetRef": {"name": name},
            "minReplicaCount": 1,  # Set minimum replicas to 1
            "maxReplicaCount": 5,  # Optional: Set maximum replicas
            "triggers": [{"type": scale_metric_type, "metadata": {"value": str(scale_metric_value)}}],
        },
    }

    try:
        # Create or update ScaledObject
        print(f"🔄 Creating or updating KEDA ScaledObject for '{name}'...")
        custom_objects_api.create_namespaced_custom_object(
            group="keda.sh",
            version="v1alpha1",
            namespace=namespace,
            plural="scaledobjects",
            body=scaled_object,
        )
        print(f"✅ KEDA ScaledObject for '{name}' created or updated.")
    except ApiException as e:
        raise RuntimeError(f"Failed to create or update KEDA ScaledObject for '{name}'. Kubernetes API error: {e}")

def monitor_health_status(deployment_name, namespace, interval=5):
    """
    Monitor the health status of a deployment until all pods are in the 'Running' state.
    Args:
        deployment_name (str): The name of the deployment.
        namespace (str): The namespace of the deployment.
        interval (int): Time (in seconds) to wait between checks.
    """
    apps_api = client.AppsV1Api()
    core_api = client.CoreV1Api()
    custom_objects_api = client.CustomObjectsApi()

    try:
        while True:
            # Fetch deployment details
            print(f"🔄 Checking deployment '{deployment_name}' in namespace '{namespace}'...")
            deployment = apps_api.read_namespaced_deployment(deployment_name, namespace)
            replicas = deployment.status.replicas or 0
            available_replicas = deployment.status.available_replicas or 0

            # Fetch pods for the deployment
            pods = core_api.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app={deployment_name}",
            )
            pod_statuses = []
            all_running = True

            for pod in pods.items:
                pod_status = {
                    "name": pod.metadata.name,
                    "status": pod.status.phase,
                    "node": pod.spec.node_name,
                    "cpu_usage": "Unavailable",  # Placeholder
                    "memory_usage": "Unavailable",  # Placeholder
                }

                # Check if any pod is not running
                if pod.status.phase != "Running":
                    all_running = False

                # Attempt to fetch metrics for the pod
                try:
                    metrics = custom_objects_api.get_namespaced_custom_object(
                        group="metrics.k8s.io",
                        version="v1beta1",
                        namespace=namespace,
                        plural="pods",
                        name=pod.metadata.name,
                    )
                    container_metrics = metrics["containers"][0]["usage"]
                    pod_status["cpu_usage"] = container_metrics.get("cpu", "Unknown")
                    pod_status["memory_usage"] = container_metrics.get("memory", "Unknown")
                except ApiException:
                    pod_status["cpu_usage"] = "Unavailable"
                    pod_status["memory_usage"] = "Unavailable"

                pod_statuses.append(pod_status)

            # Report current status
            print(f"📊 Deployment: replicas={replicas}, available={available_replicas}")
            print("Pods:")
            for pod_status in pod_statuses:
                print(
                    f"  - Pod: {pod_status['name']}, Status: {pod_status['status']}, Node: {pod_status['node']}, "
                    f"CPU: {pod_status['cpu_usage']}, Memory: {pod_status['memory_usage']}"
                )

            # Check if all pods are running
            if all_running and available_replicas == replicas:
                print(f"✅ All pods for deployment '{deployment_name}' are running!")
                break

            # Wait before the next check
            print(f"⏳ Waiting for {interval} seconds before the next check...")
            time.sleep(interval)

    except ApiException as e:
        raise RuntimeError(
            f"Failed to fetch health status for deployment '{deployment_name}'. Kubernetes API error: {e}"
        )
    
if __name__ == "__main__":
    try:
        # Connect to the cluster
        connect_to_cluster()

        # Install or upgrade Helm and KEDA
        install_helm_and_keda()

        # Deployment configuration
        deployment_name = "foo5-app"
        namespace = "default"
        image = "nginx:latest"
        cpu_request = "100m"
        memory_request = "128Mi"
        cpu_limit = "200m"
        memory_limit = "256Mi"
        ports = [80]
        scale_metric_type = "cpu"
        scale_metric_value = "50"

        # Create deployment and KEDA ScaledObject
        create_deployment(
            deployment_name,
            namespace,
            image,
            cpu_request,
            memory_request,
            cpu_limit,
            memory_limit,
            ports,
            scale_metric_type,
            scale_metric_value,
        )

        # Get and print health status
        health_status = monitor_health_status(deployment_name, namespace, interval=5)
        print("📊 Deployment Health Status:", health_status)

    except RuntimeError as e:
        print(f"❌ Runtime Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")
