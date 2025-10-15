#!/bin/bash
# Setup namespace-scoped RBAC for data gatherer
# Usage: ./setup-namespace-rbac-namespace.sh <namespace1> [namespace2] ...
# This script is for NAMESPACE-SCOPED RBAC only. For cluster-wide RBAC, use setup-rbac-cluster.sh and cluster-scoped YAML files.
set -euo pipefail
NAMESPACES=()
DELETE_MODE=false
DRY_RUN=false
CONFIRM=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --namespace)
      if [[ -n ${2:-} ]]; then
        NAMESPACES+=("$2")
        shift 2
      else
        echo "Error: --namespace requires a value" >&2
        exit 1
      fi
      ;;
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
      echo "Usage: $0 --namespace <namespace1> [--namespace <namespace2> ...] [--delete] [--dry-run] [--confirm yes]" >&2
      echo "  Example: $0 --namespace team-a --namespace team-b" >&2
      echo "  Example: $0 --namespace team-a --namespace team-b --delete" >&2
      echo "  Example: $0 --namespace team-a --namespace team-b --delete --confirm yes" >&2
      echo "  Example: $0 --namespace team-a --namespace team-b --dry-run" >&2
      exit 1
      ;;
  esac
done
if [ ${#NAMESPACES[@]} -eq 0 ]; then
  echo "Usage: $0 --namespace <namespace1> [--namespace <namespace2> ...] [--delete] [--dry-run] [--confirm yes]" >&2
  echo "  Example: $0 --namespace team-a --namespace team-b" >&2
  echo "  Example: $0 --namespace team-a --namespace team-b --delete" >&2
  echo "  Example: $0 --namespace team-a --namespace team-b --delete --confirm yes" >&2
  echo "  Example: $0 --namespace team-a --namespace team-b --dry-run" >&2
  exit 1
fi

# Use the first namespace as the service account namespace (unless overridden)
SERVICE_ACCOUNT_NAMESPACE=${SERVICE_ACCOUNT_NAMESPACE:-${NAMESPACES[0]}}
SERVICE_ACCOUNT_NAME=${SERVICE_ACCOUNT_NAME:-data-gatherer}

SCRIPT_DIR="$(dirname "$0")"

# Both Role and RoleBinding use YAML templates and sed substitution for variable injection
ROLE_TMPL="$SCRIPT_DIR/data-gatherer-role-namespace.yaml"
ROLEBINDING_TMPL="$SCRIPT_DIR/data-gatherer-rolebinding-namespace.yaml"

if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN MODE] - No changes will be applied"
fi

if [ "$DELETE_MODE" = true ]; then
  echo "Deleting RBAC resources for namespaces: ${NAMESPACES[*]}"
  echo "This will delete:"
  echo "  - Role 'data-gatherer' from namespaces: ${NAMESPACES[*]}"
  echo "  - RoleBinding 'data-gatherer' from namespaces: ${NAMESPACES[*]}"
  echo "  - ServiceAccount '$SERVICE_ACCOUNT_NAME' from namespace: $SERVICE_ACCOUNT_NAMESPACE"
  echo ""
  
  if [ "$DRY_RUN" = false ] && [ "$CONFIRM" = false ]; then
    read -p "Are you sure you want to proceed? (y/yes/no): " response
    if [[ ! "$response" =~ ^([Yy]|[Yy][Ee][Ss])$ ]]; then
      echo "Deletion cancelled.";
      exit 0;
    fi
  fi
  
  for ns in "${NAMESPACES[@]}"; do
    echo "Removing RBAC from namespace: $ns"
    if [ "$DRY_RUN" = true ]; then
      echo "[DRY RUN] Would delete: role data-gatherer -n $ns"
      echo "[DRY RUN] Would delete: rolebinding data-gatherer -n $ns"
    else
      oc delete role data-gatherer -n "$ns" --ignore-not-found=true
      oc delete rolebinding data-gatherer -n "$ns" --ignore-not-found=true
    fi
  done
  
  echo "Deleting service account $SERVICE_ACCOUNT_NAME from $SERVICE_ACCOUNT_NAMESPACE"
  if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Would delete: serviceaccount $SERVICE_ACCOUNT_NAME -n $SERVICE_ACCOUNT_NAMESPACE"
  else
    oc delete serviceaccount "$SERVICE_ACCOUNT_NAME" -n "$SERVICE_ACCOUNT_NAMESPACE" --ignore-not-found=true
  fi
  
  echo "RBAC cleanup complete."
  exit 0
fi

# Verify that all namespaces exist before proceeding
echo "Verifying namespaces exist..."
for ns in "${NAMESPACES[@]}"; do
  if [ "$DRY_RUN" = false ]; then
    if ! oc get namespace "$ns" &>/dev/null; then
      echo "Error: Namespace '$ns' does not exist. Please create it first." >&2
      exit 1
    fi
  fi
done

# Verify service account namespace exists (or will be the first namespace)
if [ "$DRY_RUN" = false ]; then
  if ! oc get namespace "$SERVICE_ACCOUNT_NAMESPACE" &>/dev/null; then
    echo "Error: Service account namespace '$SERVICE_ACCOUNT_NAMESPACE' does not exist. Please create it first." >&2
    exit 1
  fi
fi

echo "Creating service account $SERVICE_ACCOUNT_NAME in $SERVICE_ACCOUNT_NAMESPACE"
if [ "$DRY_RUN" = true ]; then
  echo "[DRY RUN] Would create serviceaccount: $SERVICE_ACCOUNT_NAME -n $SERVICE_ACCOUNT_NAMESPACE"
else
  oc create serviceaccount "$SERVICE_ACCOUNT_NAME" -n "$SERVICE_ACCOUNT_NAMESPACE" --dry-run=client -o yaml | oc apply -f -
fi

for ns in "${NAMESPACES[@]}"; do
  echo "Configuring namespace: $ns"
  if [ "$DRY_RUN" = true ]; then
    echo "[DRY RUN] Would apply Role in namespace: $ns"
    echo "[DRY RUN] Would apply RoleBinding in namespace: $ns"
    # Show what would be created
  sed "s/TARGET_NAMESPACE/$ns/g; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/$SERVICE_ACCOUNT_NAMESPACE/g; s/TARGET_SERVICE_ACCOUNT_NAME/$SERVICE_ACCOUNT_NAME/g" "$ROLE_TMPL"
    echo "---"
  sed "s/TARGET_NAMESPACE/$ns/g; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/$SERVICE_ACCOUNT_NAMESPACE/g; s/TARGET_SERVICE_ACCOUNT_NAME/$SERVICE_ACCOUNT_NAME/g" "$ROLEBINDING_TMPL"
    echo "---"
  else
    # Apply Role using template and sed substitution
  sed "s/TARGET_NAMESPACE/$ns/g; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/$SERVICE_ACCOUNT_NAMESPACE/g; s/TARGET_SERVICE_ACCOUNT_NAME/$SERVICE_ACCOUNT_NAME/g" "$ROLE_TMPL" | oc apply -f -
    # Apply RoleBinding using template and sed substitution
  sed "s/TARGET_NAMESPACE/$ns/g; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/$SERVICE_ACCOUNT_NAMESPACE/g; s/TARGET_SERVICE_ACCOUNT_NAME/$SERVICE_ACCOUNT_NAME/g" "$ROLEBINDING_TMPL" | oc apply -f -
  fi
done

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
  - name: namespaced-${RANDOM}
    namespace_scoped: true
    include_namespaces:
$(for ns in "${NAMESPACES[@]}"; do echo "      - $ns"; done)
    credentials:
      host: $API_URL
      token: "$TOKEN"
      verify_ssl: true
    include_kinds: [Deployment, DeploymentConfig, StatefulSet, DaemonSet, CronJob, ConfigMap]
    parallelism: 4
YAML
