#!/usr/bin/env bash
set -euo pipefail
# Authored local adaptation; no Docker Desktop or paid cloud dependency.
mkdir -p /opt/guruge-reproduction/bin
cd /opt/guruge-reproduction/bin
release='https://github.com/k3s-io/k3s/releases/download/v1.33.6%2Bk3s1'
curl -fL --retry 2 "$release/k3s" -o k3s
curl -fL --retry 2 "$release/sha256sum-amd64.txt" -o sha256sum-amd64.txt
awk '$2 == "k3s" {print}' sha256sum-amd64.txt > selected-sha.txt
test -s selected-sha.txt
sha256sum -c selected-sha.txt
chmod +x k3s
cat > /etc/systemd/system/guruge-k3s.service <<'EOF'
[Unit]
Description=Local Guruge reproduction K3s cluster
After=network-online.target
[Service]
Type=simple
ExecStart=/opt/guruge-reproduction/bin/k3s server --data-dir /opt/guruge-reproduction/data --node-name guruge-local --disable traefik --disable servicelb --write-kubeconfig /opt/guruge-reproduction/kubeconfig.yaml
Restart=on-failure
Delegate=yes
KillMode=process
LimitNOFILE=1048576
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
# Start for this experiment; intentionally do not enable automatic boot startup.
systemctl start guruge-k3s
