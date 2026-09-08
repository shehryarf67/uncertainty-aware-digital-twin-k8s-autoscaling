# Uncertainty-Aware Digital Twin for Kubernetes Autoscaling

This repository contains the implementation, experimental setup, and reproducibility materials for our Cloud Computing research project:

**An Uncertainty-Aware Digital Twin for SLO-Constrained Predictive Autoscaling in Kubernetes**

## Research Area

Digital Twins and Cloud Computing

## Research Question

Can an uncertainty-aware Digital Twin reduce SLO violations and resource over-provisioning compared with reactive and conventional predictive Kubernetes autoscaling under dynamic workloads?

## Project Overview

Kubernetes commonly relies on reactive autoscaling mechanisms such as the Horizontal Pod Autoscaler (HPA), which respond to resource utilization after workload changes have already occurred. Predictive autoscaling can improve responsiveness by forecasting future demand, but its effectiveness depends heavily on the accuracy of workload predictions.

This research proposes an uncertainty-aware Digital Twin that models the state and behaviour of a Kubernetes-hosted application and evaluates possible scaling decisions before they are applied to the real system. The goal is to determine whether Digital Twin-guided scaling can improve service-level objective compliance while reducing unnecessary resource provisioning under dynamic and unpredictable workloads.

## Objectives

- Design a Digital Twin representation of a Kubernetes-hosted application and its resource state.
- Develop an uncertainty-aware predictive autoscaling mechanism using the Digital Twin.
- Compare the proposed approach with Kubernetes HPA and a conventional predictive autoscaler.
- Evaluate the approaches using performance, resource-efficiency, and scaling-stability metrics.

## Proposed Experimental Environment

The study is expected to use:

- Kubernetes
- Docker
- Prometheus
- Python
- Locust or an equivalent workload-generation tool
- A workload prediction model
- A Digital Twin-based what-if evaluation component

The exact implementation and experimental configuration may be refined as the research progresses.

## Planned Evaluation Metrics

The evaluation may include:

- P95 and P99 response latency
- SLO violation rate
- CPU and memory utilization
- Resource consumption / pod-minutes
- Scaling response time
- Number of scaling actions
- Scaling oscillations
- Workload prediction error
- Digital Twin decision overhead

## Repository Structure

The repository will be expanded during the project and is expected to contain:

```text
.
├── README.md
├── src/
├── experiments/
├── configs/
├── workloads/
├── results/
├── scripts/
├── docs/
└── requirements.txt
```

## Reproducibility

All implementation code, experiment configurations, workload-generation scripts, and result-generation instructions required to reproduce the reported experiments will be added to this repository as the project progresses.

## Academic Project

This research is being conducted as part of the **Cloud Computing 100-Day Research Assignment, 2026**.

The repository will be maintained throughout the research period in accordance with the course reproducibility requirements.
