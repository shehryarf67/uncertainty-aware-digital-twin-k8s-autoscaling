#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
K=/opt/guruge-reproduction/bin/k3s
export KUBECONFIG=/opt/guruge-reproduction/kubeconfig.yaml
python3 -m venv /opt/guruge-reproduction/twin-venv
PY=/opt/guruge-reproduction/twin-venv/bin/python
"$PY" -m pip install numpy==1.26.4 pandas==2.2.2 scikit-learn==1.5.1 httpx==0.27.2 matplotlib==3.9.2 > "$ROOT/logs/install.log" 2>&1
"$PY" -m pip check
"$PY" -m pip freeze > "$ROOT/requirements-linux-working.txt"
"$K" kubectl create namespace twin-research --dry-run=client -o yaml | "$K" kubectl apply -f -
"$K" kubectl create configmap twin-service --from-file=service.py="$ROOT/service.py" -n twin-research --dry-run=client -o yaml | "$K" kubectl apply -f -
"$K" kubectl apply -f "$ROOT/deployment.yaml"
cat > /etc/systemd/system/guruge-research-proxy.service <<'EOF'
[Unit]
Description=Loopback-only Kubernetes proxy for local research
After=guruge-k3s.service
[Service]
ExecStart=/opt/guruge-reproduction/bin/k3s kubectl --kubeconfig /opt/guruge-reproduction/kubeconfig.yaml proxy --address=127.0.0.1 --port=8001
Restart=on-failure
EOF
systemctl daemon-reload
systemctl start guruge-research-proxy
"$K" kubectl rollout status deployment/twin-service -n twin-research --timeout=180s
