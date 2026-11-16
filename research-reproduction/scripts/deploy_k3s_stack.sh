#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
K3S=/opt/guruge-reproduction/bin/k3s
export KUBECONFIG=/opt/guruge-reproduction/kubeconfig.yaml
mkdir -p "$ROOT/kubernetes-autoscaling/manifests/vendor"
curl -fL --retry 2 https://github.com/kedacore/keda/releases/download/v2.18.0/keda-2.18.0.yaml -o "$ROOT/kubernetes-autoscaling/manifests/vendor/keda-2.18.0.yaml"
"$K3S" kubectl apply --server-side -f "$ROOT/kubernetes-autoscaling/manifests/vendor/keda-2.18.0.yaml"
test -f "$ROOT/kubernetes-autoscaling/manifests/stack-built-app.yaml" || { echo 'Run build_author_app.sh first'; exit 1; }
"$K3S" kubectl apply -f "$ROOT/kubernetes-autoscaling/manifests/stack-built-app.yaml"
# The unchanged author scaler runs on this WSL node with compatible stubs.
host_ip=$(hostname -I | awk '{print $1}')
cat > "$ROOT/kubernetes-autoscaling/manifests/scaler-endpoint.yaml" <<EOF
apiVersion: v1
kind: Service
metadata: {name: author-scaler, namespace: guruge-repro}
spec:
  ports: [{port: 50051, targetPort: 50051}]
---
apiVersion: v1
kind: Endpoints
metadata: {name: author-scaler, namespace: guruge-repro}
subsets:
- addresses: [{ip: $host_ip}]
  ports: [{port: 50051}]
EOF
"$K3S" kubectl apply -f "$ROOT/kubernetes-autoscaling/manifests/scaler-endpoint.yaml"
"$K3S" kubectl rollout status deployment/sample-api -n guruge-repro --timeout=180s
"$K3S" kubectl rollout status deployment/prometheus -n guruge-repro --timeout=180s
