
# RBAC

Dedicated directory for Role-Based Access Control assets used by the Data Gatherer.

## Files
- `data-gatherer-cluster-role.yaml` - Read-only ClusterRole
- `data-gatherer-cluster-role-binding.yaml` - ClusterRoleBinding linking service account
- `setup-rbac.sh` - Helper script to install RBAC and output config snippet

## Quick Setup
```bash
oc login https://your-cluster-api:6443
cd rbac/
./setup-rbac.sh
```
Copy the emitted YAML snippet into `config/config.yaml`.

## Manual Setup
```bash
oc apply -f data-gatherer-cluster-role.yaml
oc apply -f data-gatherer-cluster-role-binding.yaml
oc create serviceaccount data-gatherer -n openshift
oc create token data-gatherer -n openshift --duration=8760h
```

## Permissions Summary
Read-only (`get`, `list`, `watch`) for workloads (Deployments, StatefulSets, DaemonSets, Jobs, CronJobs, DeploymentConfigs, ReplicaSets), core & infra (Namespaces, Nodes, PVs, PVCs, Services, ConfigMaps, Secrets metadata, Pods), OpenShift resources (Routes, ImageStreams, Builds), scaling & policy objects (HPAs, NetworkPolicies, Ingresses, PodDisruptionBudgets, PriorityClasses), quotas/limits, EndpointSlices, CRDs, and non-resource discovery endpoints.

## Token Rotation
Regenerate annually:
```bash
oc create token data-gatherer -n openshift --duration=8760h
```

## Customization
Override namespace/service account:
```bash
NAMESPACE=my-ns SERVICE_ACCOUNT_NAME=my-gatherer ./setup-rbac.sh
```
Update `cluster-role-binding` subject + config token accordingly.

Refer to `config/README.md` for configuration details.
