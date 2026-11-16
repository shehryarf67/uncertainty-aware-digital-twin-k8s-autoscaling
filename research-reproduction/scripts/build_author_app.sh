#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
apt-get update -qq
apt-get install -y maven openjdk-21-jdk-headless > "$ROOT/logs/java-maven-install.log" 2>&1
cd "$ROOT/kubernetes-autoscaling/author-app"
# WSL JDK dynamic attach failed; explicit premain agent runs the original test.
mvn -B "-DargLine=-javaagent:/root/.m2/repository/org/mockito/mockito-core/5.14.2/mockito-core-5.14.2.jar" package > "$ROOT/logs/author-app-build-agent.log" 2>&1
python3 - "$ROOT" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
path=root/'kubernetes-autoscaling/manifests/stack.yaml'
text=path.read_text()
text=text.replace('pasanbhanu/springboot-sample-api-with-prometheus:latest','eclipse-temurin:21-jre-alpine')
text=text.replace('        ports: [{containerPort: 8080}]','        command: [java, -Xmx256m, -jar, /opt/app.jar]\n        volumeMounts: [{name: author-jar, mountPath: /opt/app.jar, readOnly: true}]\n        ports: [{containerPort: 8080}]',1)
text=text.replace('---\napiVersion: v1\nkind: Service\nmetadata:\n  name: sample-api',f'      volumes:\n      - name: author-jar\n        hostPath:\n          path: {root}/kubernetes-autoscaling/author-app/target/springbootapi.jar\n          type: File\n---\napiVersion: v1\nkind: Service\nmetadata:\n  name: sample-api',1)
(root/'kubernetes-autoscaling/manifests/stack-built-app.yaml').write_text(text)
PY
/opt/guruge-reproduction/bin/k3s kubectl --kubeconfig /opt/guruge-reproduction/kubeconfig.yaml apply -f "$ROOT/kubernetes-autoscaling/manifests/stack-built-app.yaml"
/opt/guruge-reproduction/bin/k3s kubectl --kubeconfig /opt/guruge-reproduction/kubeconfig.yaml rollout status deployment/sample-api -n guruge-repro --timeout=180s
