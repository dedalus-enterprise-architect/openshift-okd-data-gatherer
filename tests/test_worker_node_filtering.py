import pytest
from data_gatherer.reporting.common import calculate_effective_replicas, will_run_on_worker

@pytest.mark.parametrize("kind,manifest,pod_spec,worker_node_count,expected", [
    # DaemonSet targeting infra node (should be excluded)
    ("DaemonSet", {"spec": {"template": {"spec": {"nodeSelector": {"node-role.kubernetes.io/infra": ""}}}}}, {"nodeSelector": {"node-role.kubernetes.io/infra": ""}}, 5, 0),
    # DaemonSet with no nodeSelector (should be included)
    ("DaemonSet", {"spec": {"template": {"spec": {}}}}, {}, 5, 5),
    # Deployment targeting master node (should be excluded)
    ("Deployment", {"spec": {"template": {"spec": {"nodeSelector": {"node-role.kubernetes.io/master": ""}}}}}, {"nodeSelector": {"node-role.kubernetes.io/master": ""}}, 5, 0),
    # Deployment with no nodeSelector (should be included)
    ("Deployment", {"spec": {"template": {"spec": {}}}}, {}, 5, 1),
])
def test_worker_node_filtering(kind, manifest, pod_spec, worker_node_count, expected):
    replicas = calculate_effective_replicas(kind, manifest, pod_spec, worker_node_count)
    if kind == "DaemonSet":
        # DaemonSet: replicas should be worker_node_count or 0
        assert replicas == expected
    else:
        # Deployment: always 1 unless nodeSelector disables worker scheduling
        # Filtering is handled by will_run_on_worker, not by replicas
        assert will_run_on_worker(pod_spec) == (expected == 1)
