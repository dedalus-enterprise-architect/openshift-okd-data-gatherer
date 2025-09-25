#!/bin/bash
# OpenShift Resource Analyzer - RBAC Setup Script (moved from config/ to rbac/)
# This script creates the necessary ServiceAccount, ClusterRole, and ClusterRoleBinding

set -e

NAMESPACE=${NAMESPACE:-openshift}
SERVICE_ACCOUNT_NAME=${SERVICE_ACCOUNT_NAME:-data-gatherer}

echo "Setting up OpenShift Resource Analyzer RBAC..."
echo "Namespace: $NAMESPACE"
echo "Service Account: $SERVICE_ACCOUNT_NAME"

# Create the namespace if it doesn't exist (though 'openshift' should already exist)
echo "Ensuring namespace exists..."
oc create namespace "$NAMESPACE" --dry-run=client -o yaml | oc apply -f -

# Create the ServiceAccount
echo "Creating ServiceAccount..."
cat <<EOF | oc apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: $SERVICE_ACCOUNT_NAME
  namespace: $NAMESPACE
    labels:
        app: data-gatherer
    purpose: workload-analysis
EOF

# Apply the ClusterRole
echo "Creating ClusterRole..."
oc apply -f "$(dirname "$0")/data-gatherer-cluster-role.yaml"

# Apply the ClusterRoleBinding
echo "Creating ClusterRoleBinding..."
oc apply -f "$(dirname "$0")/data-gatherer-cluster-role-binding.yaml"

# Get the service account token
echo "Retrieving ServiceAccount token..."

# Check if any token secrets exist (older OpenShift versions)
TOKEN_SECRETS=$(oc get serviceaccount "$SERVICE_ACCOUNT_NAME" -n "$NAMESPACE" -o jsonpath='{.secrets[*].name}' 2>/dev/null || echo "")
TOKEN_SECRET=""

# Look for a token secret (not dockercfg)
for secret in $TOKEN_SECRETS; do
    if [[ "$secret" == *"token"* ]] && [[ "$secret" != *"dockercfg"* ]]; then
        TOKEN_SECRET="$secret"
        break
    fi
done

if [ -n "$TOKEN_SECRET" ]; then
    # For older versions, extract from secret
    echo "Extracting token from secret (older OpenShift): $TOKEN_SECRET"
    TOKEN=$(oc get secret "$TOKEN_SECRET" -n "$NAMESPACE" -o jsonpath='{.data.token}' | base64 -d)
else
    # For newer OpenShift versions, create a token manually
    echo "Creating token for ServiceAccount (OpenShift 4.11+)..."
    TOKEN=$(oc create token "$SERVICE_ACCOUNT_NAME" -n "$NAMESPACE" --duration=8760h 2>/dev/null)  # 1 year
    if [ -z "$TOKEN" ]; then
        echo "Failed to create token with duration, trying without duration..."
        TOKEN=$(oc create token "$SERVICE_ACCOUNT_NAME" -n "$NAMESPACE" 2>/dev/null)
    fi
fi

# Get cluster API URL
API_URL=$(oc whoami --show-server)

echo ""
echo "✅ Setup complete!"
echo ""
echo "Add this configuration to your config/config.yaml:"
echo ""
# Extract cluster name from API URL
CLUSTER_NAME=""
CLUSTER_NAME=$(echo "$API_URL" | sed -n 's|https\?://api\.\([^.]*\)\..*|\1|p')
if [ -z "$CLUSTER_NAME" ]; then
    CLUSTER_NAME=$(echo "$API_URL" | sed -n 's|https\?://\([^-]*\)-api\..*|\1|p')
fi
if [ -z "$CLUSTER_NAME" ]; then
    HOSTNAME=$(echo "$API_URL" | sed -n 's|https\?://\([^:]*\):.*|\1|p')
    CLUSTER_NAME=$(echo "$HOSTNAME" | sed 's/^api\.//' | sed 's/\..*$//' | sed 's/-api$//')
fi
CLUSTER_NAME=${CLUSTER_NAME_OVERRIDE:-$CLUSTER_NAME}
if [ -z "$CLUSTER_NAME" ]; then
    echo "Could not automatically determine cluster name from: $API_URL"
    echo "Please set CLUSTER_NAME_OVERRIDE environment variable or edit the output manually."
    CLUSTER_NAME="my-cluster"
fi

cat <<YAML
clusters:
  - name: $CLUSTER_NAME
    credentials:
      host: $API_URL
      token: "$TOKEN"
      verify_ssl: false
    include_kinds: [Deployment, StatefulSet, DaemonSet, CronJob, DeploymentConfig]
    ignore_system_namespaces: true
    exclude_namespaces: []
    parallelism: 4
YAML

echo ""
echo "🔑 Token expires in 1 year. To refresh:"
echo "   oc create token $SERVICE_ACCOUNT_NAME -n $NAMESPACE --duration=8760h"
echo ""
echo "💡 To override cluster name detection:"
echo "   CLUSTER_NAME_OVERRIDE=your-cluster-name ./setup-rbac.sh"
