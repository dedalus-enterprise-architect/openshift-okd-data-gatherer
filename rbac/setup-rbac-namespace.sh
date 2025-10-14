#!/bin/bash
# Setup namespace-scoped RBAC for data gatherer
# Usage: ./setup-namespace-rbac-namespace.sh <namespace1> [namespace2] ...
# This script is for NAMESPACE-SCOPED RBAC only. For cluster-wide RBAC, use setup-rbac-cluster.sh and cluster-scoped YAML files.
set -euo pipefail
if [ $# -eq 0 ]; then
  echo "Usage: $0 <namespace1> [namespace2] ..." >&2
  exit 1
fi
SERVICE_ACCOUNT_NAMESPACE=${SERVICE_ACCOUNT_NAMESPACE:-openshift}
SERVICE_ACCOUNT_NAME=${SERVICE_ACCOUNT_NAME:-data-gatherer}

echo "Creating service account $SERVICE_ACCOUNT_NAME in $SERVICE_ACCOUNT_NAMESPACE"
oc create namespace "$SERVICE_ACCOUNT_NAMESPACE" --dry-run=client -o yaml | oc apply -f -
oc create serviceaccount "$SERVICE_ACCOUNT_NAME" -n "$SERVICE_ACCOUNT_NAMESPACE" --dry-run=client -o yaml | oc apply -f -

SCRIPT_DIR="$(dirname "$0")"

# Both Role and RoleBinding use YAML templates and sed substitution for variable injection
ROLE_TMPL="$SCRIPT_DIR/data-gatherer-role-namespace.yaml"
ROLEBINDING_TMPL="$SCRIPT_DIR/data-gatherer-rolebinding-namespace.yaml"

for ns in "$@"; do
  echo "Configuring namespace: $ns"
  oc create namespace "$ns" --dry-run=client -o yaml | oc apply -f -
  # Apply Role using template and sed substitution
  sed "s/TARGET_NAMESPACE/$ns/g; s/TARGET_SERVICE_ACCOUNT_NAME/$SERVICE_ACCOUNT_NAME/g; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/$SERVICE_ACCOUNT_NAMESPACE/g" "$ROLE_TMPL" | oc apply -f -
  # Apply RoleBinding using template and sed substitution
  sed "s/TARGET_NAMESPACE/$ns/g; s/TARGET_SERVICE_ACCOUNT_NAME/$SERVICE_ACCOUNT_NAME/g; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/$SERVICE_ACCOUNT_NAMESPACE/g" "$ROLEBINDING_TMPL" | oc apply -f -
done

echo "Creating token (1 year)"
TOKEN=$(oc create token "$SERVICE_ACCOUNT_NAME" -n "$SERVICE_ACCOUNT_NAMESPACE" --duration=8760h 2>/dev/null || oc create token "$SERVICE_ACCOUNT_NAME" -n "$SERVICE_ACCOUNT_NAMESPACE" 2>/dev/null || true)
API_URL=$(oc whoami --show-server)

cat <<YAML
# Add to config/config.yaml
clusters:
  - name: namespaced-${RANDOM}
    namespace_scoped: true
    include_namespaces:
$(for ns in "$@"; do echo "      - $ns"; done)
    credentials:
      host: $API_URL
      token: "$TOKEN"
      verify_ssl: true
    include_kinds: [Deployment, StatefulSet, DaemonSet, CronJob, ConfigMap]
    parallelism: 4
YAML
