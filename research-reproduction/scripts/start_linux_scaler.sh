#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
apt-get update -qq
apt-get install -y python3.12-venv > "$ROOT/logs/linux-venv-install.log" 2>&1
python3 -m venv /opt/guruge-reproduction/scaler-venv
PY=/opt/guruge-reproduction/scaler-venv/bin/python
"$PY" -m pip install -r "$ROOT/kubernetes-autoscaling/requirements-linux.txt" > "$ROOT/logs/linux-scaler-install.log" 2>&1
"$PY" -m pip check
"$PY" -m pip freeze > "$ROOT/kubernetes-autoscaling/requirements-linux-working.txt"
cd "$ROOT/kubernetes-autoscaling/runtime-scaler"
"$PY" -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. externalscaler.proto
cat > /etc/systemd/system/guruge-scaler.service <<EOF
[Unit]
Description=Unchanged author forecasting gRPC scaler
After=guruge-k3s.service
[Service]
WorkingDirectory=$PWD
Environment=TF_NUM_INTRAOP_THREADS=4
Environment=TF_NUM_INTEROP_THREADS=2
Environment=OMP_NUM_THREADS=4
Environment=TZ=Asia/Karachi
ExecStart=$PY -X utf8 keda-grpc-server.py
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl start guruge-scaler
node_ip=$(hostname -I | awk '{print $1}')
sed -i "s/ip: [0-9.]*/ip: $node_ip/" "$ROOT/kubernetes-autoscaling/manifests/scaler-endpoint.yaml"
sed -i "s|serverAddress: http://[^ ]*|serverAddress: http://$node_ip:30909|" "$ROOT/kubernetes-autoscaling/manifests/forecast.yaml"
/opt/guruge-reproduction/bin/k3s kubectl --kubeconfig /opt/guruge-reproduction/kubeconfig.yaml apply -f "$ROOT/kubernetes-autoscaling/manifests/scaler-endpoint.yaml"
