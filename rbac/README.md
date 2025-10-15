
# RBAC

Dedicated directory for Role-Based Access Control assets used by the Data Gatherer.

## Files
Cluster-scoped (grants read across entire cluster):

Namespace-scoped (restricts to explicit namespaces only):
 `data-gatherer-role-namespace.yaml` - Role applied per target namespace
 `data-gatherer-rolebinding-namespace.yaml` - RoleBinding applied per target namespace
 `setup-rbac-namespace.sh` - Helper script to install namespace-scoped RBAC for one or more namespaces

Legacy / compatibility (will be removed in a future release):

## Script Features (Current)
Both `setup-rbac-cluster.sh` and `setup-rbac-namespace.sh` support:
- `--namespace <ns>`: Specify target namespace(s) (namespace-scoped only)
- `--delete`: Remove RBAC objects instead of creating
- `--dry-run`: Preview changes without applying
- `--confirm yes`: Skip confirmation prompt (for automation)
Confirmation prompt accepts `y` or `yes`.

## Quick Setup (Cluster-Scoped)
```bash
oc login https://your-cluster-api:6443
cd rbac/
./setup-rbac-cluster.sh
```
Copy the emitted YAML snippet into `config/config.yaml`.

### Script Usage (Cluster-Scoped)
```bash
./setup-rbac-cluster.sh [--delete] [--dry-run] [--confirm yes] [--service-account <name>] [--namespace <ns>]
```
Default service account: `data-gatherer` in `openshift` namespace. Override with env vars or flags.

## Manual Setup
```bash
oc apply -f data-gatherer-clusterrole.yaml
oc apply -f data-gatherer-clusterrolebinding.yaml
oc create serviceaccount data-gatherer -n openshift
oc create token data-gatherer -n openshift --duration=8760h
```

## Quick Setup (Namespace-Scoped)
```bash
oc login https://your-cluster-api:6443
cd rbac/
./setup-rbac-namespace.sh --namespace team-a --namespace team-b
```
Or:
```bash
./setup-rbac-namespace.sh team-a team-b
```
Supports `--delete`, `--dry-run`, and `--confirm yes` as above.
Copy the emitted YAML snippet into `config/config.yaml`.

## Permissions Summary
Read-only (`get`, `list`, `watch`) for workloads (Deployments, StatefulSets, DaemonSets, Jobs, CronJobs, DeploymentConfigs, ReplicaSets), core & infra (Namespaces, Nodes, PVs, PVCs, Services, ConfigMaps, Secrets metadata, Pods), OpenShift resources (Routes, ImageStreams, Builds), scaling & policy objects (HPAs, NetworkPolicies, Ingresses, PodDisruptionBudgets, PriorityClasses), quotas/limits, EndpointSlices, CRDs, and non-resource discovery endpoints.

## Token Rotation
Regenerate annually:
```bash
oc create token data-gatherer -n openshift --duration=8760h
```

For namespace-scoped, use the correct namespace:
```bash
oc create token data-gatherer -n <namespace> --duration=8760h
```

## Customization
Override namespace/service account (cluster-scoped example):
```bash
SERVICE_ACCOUNT_NAMESPACE=my-ns SERVICE_ACCOUNT_NAME=my-gatherer ./setup-rbac-cluster.sh
```

Namespace-scoped example:
```bash
SERVICE_ACCOUNT_NAMESPACE=automation SERVICE_ACCOUNT_NAME=dg ./setup-rbac-namespace.sh team-a team-b
```
Produces config snippet with `namespace_scoped: true` and `include_namespaces` entries.

### Script Flags (Namespace-Scoped)
```bash
./setup-rbac-namespace.sh --namespace team-a --namespace team-b --service-account dg --delete --dry-run --confirm yes
```

Manual namespace-scoped setup (example for namespaces team-a and team-b):
```bash
for ns in team-a team-b; do
	oc create namespace "$ns" --dry-run=client -o yaml | oc apply -f -
	sed "s/TARGET_NAMESPACE/$ns/" data-gatherer-role-namespace.yaml | oc apply -f -
	sed "s/TARGET_NAMESPACE/$ns/" data-gatherer-rolebinding-namespace.yaml \
		| sed "s/TARGET_SERVICE_ACCOUNT_NAME/data-gatherer/; s/TARGET_SERVICE_ACCOUNT_NAMESPACE/openshift/" \
		| oc apply -f -
done
```

### Deletion Example
To remove RBAC objects:
```bash
./setup-rbac-namespace.sh --namespace team-a --delete
```

Refer to `config/README.md` for configuration details.
