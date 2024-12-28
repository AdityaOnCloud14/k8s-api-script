Project Overview
This project provides a Python-based script to automate operations on a Kubernetes cluster, including:

Connecting to a Kubernetes cluster.
Installing and configuring necessary tools like Helm and KEDA (Kubernetes Event-Driven Autoscaler).
Deploying applications with event-driven scaling capabilities.
Continuously monitoring the health status of a deployment, including real-time updates for pod states, CPU, and memory usage.
The script is designed to work on a bare Kubernetes cluster and can be executed in local or cloud-based environments like Minikube or managed Kubernetes services.

Features
Cluster Connection: Establishes connection to the Kubernetes cluster using kubectl and Python Kubernetes API client.
Helm and KEDA Installation: Automates the installation of Helm and KEDA using Helm charts.
Application Deployment: Creates a Kubernetes deployment, service, and KEDA ScaledObject for autoscaling based on resource usage or external events.
Health Monitoring: Provides real-time updates for deployment health, including pod states and resource metrics (CPU, Memory).
Error Handling: Includes comprehensive error handling for robust automation.
Prerequisites
Kubernetes Cluster:
A running Kubernetes cluster (e.g., Minikube, GKE, EKS).
Metrics Server installed for resource usage monitoring.
Tools:
kubectl: Command-line tool for interacting with Kubernetes.
Helm: Kubernetes package manager.
Python:
Python 3.9+.
Required Python libraries: kubernetes.