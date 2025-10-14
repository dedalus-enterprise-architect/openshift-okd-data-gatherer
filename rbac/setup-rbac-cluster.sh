#!/bin/bash
# Setup cluster-scoped RBAC for data gatherer
# Usage: ./setup-rbac-cluster.sh
# This script is for CLUSTER-SCOPED RBAC only. For namespace-scoped RBAC, use setup-namespace-rbac-namespace.sh and namespace-scoped YAML files.
set -euo pipefail
SERVICE_ACCOUNT_NAMESPACE=${SERVICE_ACCOUNT_NAMESPACE:-openshift}
SERVICE_ACCOUNT_NAME=${SERVICE_ACCOUNT_NAME:-data-gatherer}

echo "Creating service account $SERVICE_ACCOUNT_NAME in $SERVICE_ACCOUNT_NAMESPACE"
oc create namespace "$SERVICE_ACCOUNT_NAMESPACE" --dry-run=client -o yaml | oc apply -f -
oc create serviceaccount "$SERVICE_ACCOUNT_NAME" -n "$SERVICE_ACCOUNT_NAMESPACE" --dry-run=client -o yaml | oc apply -f -

SCRIPT_DIR="$(dirname "$0")"

# Both ClusterRole and ClusterRoleBinding use YAML templates and sed substitution for variable injection
CLUSTERROLE_TMPL="$SCRIPT_DIR/data-gatherer-clusterrole.yaml"
CLUSTERROLEBINDING_TMPL="$SCRIPT_DIR/data-gatherer-clusterrolebinding.yaml"

# Apply ClusterRole using template and sed substitution
sed "s/TARGET_SERVICE_ACCOUNT_NAME/$SERVICE_ACCOUNT_NAME/g; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/$SERVICE_ACCOUNT_NAMESPACE/g" "$CLUSTERROLE_TMPL" | oc apply -f -
# Apply ClusterRoleBinding using template and sed substitution
sed "s/TARGET_SERVICE_ACCOUNT_NAME/$SERVICE_ACCOUNT_NAME/g; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/$SERVICE_ACCOUNT_NAMESPACE/g" "$CLUSTERROLEBINDING_TMPL" | oc apply -f -

echo "Creating token (1 year)"
TOKEN=$(oc create token "$SERVICE_ACCOUNT_NAME" -n "$SERVICE_ACCOUNT_NAMESPACE" --duration=8760h 2>/dev/null || oc create token "$SERVICE_ACCOUNT_NAME" -n "$SERVICE_ACCOUNT_NAMESPACE" 2>/dev/null || true)
API_URL=$(oc whoami --show-server)

cat <<YAML
# Add to config/config.yaml
clusters:
  - name: cluster-${RANDOM}
    namespace_scoped: false
    credentials:
      host: $API_URL
      token: "$TOKEN"
      verify_ssl: true
    include_kinds: [Deployment, StatefulSet, DaemonSet, CronJob, ConfigMap, Node, Namespace]
    parallelism: 4
YAML
