#!/bin/bash
# Setup cluster-scoped RBAC for data gatherer
# Usage: ./setup-rbac-cluster.sh
# This script is for CLUSTER-SCOPED RBAC only. For namespace-scoped RBAC, use setup-namespace-rbac-namespace.sh and namespace-scoped YAML files.
set -euo pipefail

DELETE_MODE=false
DRY_RUN=false
CONFIRM=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --delete)
      DELETE_MODE=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --confirm)
      if [[ ${2:-} == "yes" ]]; then
        CONFIRM=true
        shift 2
      else
        echo "Error: --confirm requires 'yes' as value" >&2
        exit 1
      fi
      ;;
    *)
      echo "Usage: $0 [--delete] [--dry-run] [--confirm yes]" >&2
      echo "  Example: $0" >&2
      echo "  Example: $0 --delete" >&2
      echo "  Example: $0 --delete --confirm yes" >&2
      echo "  Example: $0 --dry-run" >&2
      exit 1
      ;;
  esac
done

SERVICE_ACCOUNT_NAMESPACE=${SERVICE_ACCOUNT_NAMESPACE:-openshift}
SERVICE_ACCOUNT_NAME=${SERVICE_ACCOUNT_NAME:-data-gatherer}

SCRIPT_DIR="$(dirname "$0")"

# Both ClusterRole and ClusterRoleBinding use YAML templates and sed substitution for variable injection
CLUSTERROLE_TMPL="$SCRIPT_DIR/data-gatherer-clusterrole.yaml"
CLUSTERROLEBINDING_TMPL="$SCRIPT_DIR/data-gatherer-clusterrolebinding.yaml"

if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN MODE] - No changes will be applied"
fi

if [ "$DELETE_MODE" = true ]; then
  echo "Deleting cluster-scoped RBAC resources"
  echo "This will delete:"
  echo "  - ClusterRole 'data-gatherer'"
  echo "  - ClusterRoleBinding 'data-gatherer'"
  echo "  - ServiceAccount '$SERVICE_ACCOUNT_NAME' from namespace: $SERVICE_ACCOUNT_NAMESPACE"
  echo ""
  
  if [ "$DRY_RUN" = false ] && [ "$CONFIRM" = false ]; then
    read -p "Are you sure you want to proceed? (y/yes/no): " response
    if [[ ! "$response" =~ ^([Yy]|[Yy][Ee][Ss])$ ]]; then
      echo "Deletion cancelled.";
      exit 0;
    fi
  fi
  
  echo "Removing cluster-scoped RBAC"
  if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Would delete: clusterrole data-gatherer"
    echo "[DRY RUN] Would delete: clusterrolebinding data-gatherer"
    echo "[DRY RUN] Would delete: serviceaccount $SERVICE_ACCOUNT_NAME -n $SERVICE_ACCOUNT_NAMESPACE"
  else
    oc delete clusterrole data-gatherer --ignore-not-found=true
    oc delete clusterrolebinding data-gatherer --ignore-not-found=true
    oc delete serviceaccount "$SERVICE_ACCOUNT_NAME" -n "$SERVICE_ACCOUNT_NAMESPACE" --ignore-not-found=true
  fi
  
  echo "RBAC cleanup complete."
  exit 0
fi

# Verify service account namespace exists before proceeding
if [ "$DRY_RUN" = false ]; then
  if ! oc get namespace "$SERVICE_ACCOUNT_NAMESPACE" &>/dev/null; then
    echo "Error: Service account namespace '$SERVICE_ACCOUNT_NAMESPACE' does not exist. Please create it first." >&2
    exit 1
  fi
fi

echo "Creating service account $SERVICE_ACCOUNT_NAME in $SERVICE_ACCOUNT_NAMESPACE"
echo "Creating service account $SERVICE_ACCOUNT_NAME in $SERVICE_ACCOUNT_NAMESPACE"
if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN] Would create serviceaccount: $SERVICE_ACCOUNT_NAME -n $SERVICE_ACCOUNT_NAMESPACE"
else
  oc create serviceaccount "$SERVICE_ACCOUNT_NAME" -n "$SERVICE_ACCOUNT_NAMESPACE" --dry-run=client -o yaml | oc apply -f -
fi

echo "Configuring cluster-scoped RBAC"
if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN] Would apply ClusterRole"
  echo "[DRY RUN] Would apply ClusterRoleBinding"
  # Show what would be created
  sed "s/TARGET_SERVICE_ACCOUNT_NAME/$SERVICE_ACCOUNT_NAME/g; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/$SERVICE_ACCOUNT_NAMESPACE/g" "$CLUSTERROLE_TMPL"
  echo "---"
  sed "s/TARGET_SERVICE_ACCOUNT_NAME/$SERVICE_ACCOUNT_NAME/g; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/$SERVICE_ACCOUNT_NAMESPACE/g" "$CLUSTERROLEBINDING_TMPL"
  echo "---"
else
  # Apply ClusterRole using template and sed substitution
  sed "s/TARGET_SERVICE_ACCOUNT_NAME/$SERVICE_ACCOUNT_NAME/g; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/$SERVICE_ACCOUNT_NAMESPACE/g" "$CLUSTERROLE_TMPL" | oc apply -f -
  # Apply ClusterRoleBinding using template and sed substitution
  sed "s/TARGET_SERVICE_ACCOUNT_NAME/$SERVICE_ACCOUNT_NAME/g; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/$SERVICE_ACCOUNT_NAMESPACE/g" "$CLUSTERROLEBINDING_TMPL" | oc apply -f -
fi

echo "Creating token (1 year)"
if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN] Would create token for: $SERVICE_ACCOUNT_NAME -n $SERVICE_ACCOUNT_NAMESPACE"
  TOKEN="<token-would-be-generated-here>"
  API_URL="<api-url-would-be-fetched-here>"
else
  TOKEN=$(oc create token "$SERVICE_ACCOUNT_NAME" -n "$SERVICE_ACCOUNT_NAMESPACE" --duration=8760h 2>/dev/null || oc create token "$SERVICE_ACCOUNT_NAME" -n "$SERVICE_ACCOUNT_NAMESPACE" 2>/dev/null || true)
  API_URL=$(oc whoami --show-server)
fi

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
