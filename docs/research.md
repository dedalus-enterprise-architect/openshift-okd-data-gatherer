# OpenShift and Kubernetes Resource Management and Scheduling

This document summarizes best practices and key concepts for managing OpenShift and Kubernetes clusters, focusing on cluster sizing, resource management, and scheduler logic.

## OpenShift Cluster Sizing

Properly sizing an OpenShift cluster is crucial for performance and stability. Red Hat does not provide one-size-fits-all guidance, as the ideal size depends on multiple factors.

### Tested Maximums

OpenShift Container Platform is tested against certain maximums. Exceeding these might lead to performance degradation. These are not absolute limits, but guidelines.

- **Nodes per cluster:** 2,000
- **Pods per cluster:** 150,000
- **Pods per node:** 250 (default), tested up to 2,500 with `OVNKubernetes` and custom configuration. `OpenShiftSDN` is tested up to 500 pods per node.
- **Namespaces:** 10,000
- **Services:** 10,000

### Key Sizing Factors

The following factors significantly impact cluster scale:

- **Number and size of pods and containers.**
- **Rate of API calls (cluster churn):** High rates of pod creation/deletion can impact performance.
- **Resource usage:** CPU, memory, and storage consumption.
- **Network plugin:** `OVNKubernetes` scales differently than `OpenShiftSDN`.
- **Object counts:** Number of namespaces, secrets, config maps, routes, etc.


### How OpenShift computes allocated resources
An allocated amount of a resource is computed based on the following formula:

[Allocatable] = [Node Capacity] - [system-reserved] - [Hard-Eviction-Thresholds]

The withholding of Hard-Eviction-Thresholds from Allocatable improves system reliability because the value for Allocatable is enforced for pods at the node level.

If Allocatable is negative, it is set to 0.

Each node reports the system resources that are used by the container runtime and kubelet. To simplify configuring the system-reserved parameter, view the resource use for the node by using the node summary API. The node summary is available at /api/v1/nodes/<node>/proxy/stats/summary.


### Planning Your Environment

To plan your cluster size:

1.  **Estimate application requirements:** Determine the CPU, memory, and storage needs for your applications.
2.  **Calculate required nodes:**
    `required pods per cluster / pods per node = total number of nodes needed`
3.  **Consider overcommitment:** Nodes are often overcommitted. Java applications and those using huge pages are not good candidates for overcommitment. A 30% overcommitment ratio is common.

## Pod Resource Requests and Limits

Setting resource requests and limits for containers is a fundamental practice for resource management in Kubernetes and OpenShift.

-   **`requests`**: The amount of resources the scheduler guarantees for a container. The scheduler uses this value to place pods on nodes.
-   **`limits`**: The maximum amount of a resource a container can use.

### CPU (Compressible Resource)

-   Measured in CPU units (1 CPU unit = 1 physical/virtual core).
-   Can be specified in fractional values (e.g., `500m` for half a core).
-   **Enforcement:** CPU is a "compressible" resource. If a container starts to exceed its CPU limit, the kernel will throttle it, slowing it down. The container will **not** be terminated for excessive CPU usage.
-   **Best Practice:** It is often recommended to **avoid setting CPU limits** and only set CPU requests. This prevents unexpected throttling that can degrade application performance. If a limit is set, it should be based on careful performance testing.

### Memory (Incompressible Resource)

-   Measured in bytes. Can be specified with suffixes like `M`, `G`, `Mi`, `Gi`.
-   **Enforcement:** Memory is an "incompressible" resource. If a container tries to use more memory than its limit, it will be terminated by the kernel with an Out of Memory (OOM) kill.
-   If a container exceeds its memory request and the node runs out of memory, the pod is likely to be evicted.

### Quality of Service (QoS) Classes

Kubernetes assigns a QoS class to each pod based on its resource requests and limits. This class determines how the pod is treated during resource contention and eviction.

-   **Guaranteed:** Pods where every container has both a memory request and a memory limit, and they are equal. CPU requests and limits must also be equal. These are the highest priority pods and are the last to be killed.
-   **Burstable:** Pods where at least one container has a memory or CPU request, but they don't meet the criteria for the Guaranteed class (e.g., limits are higher than requests). These pods can use more resources than requested if available.
-   **BestEffort:** Pods with no memory or CPU requests or limits set. These are the lowest priority pods and are the first to be killed if the node runs out of resources.

### Resource Handling for Init Containers

Init containers run before the main application containers and can have their own resource requests and limits. The pod's overall resource calculation is adjusted to account for them:

-   The **effective init resource request/limit** for a pod is the *highest* request/limit defined on any of its init containers.
-   The pod's total resource request for scheduling is the *higher* of:
    1.  The sum of all app container requests.
    2.  The effective init resource request.
-   This allows init containers to reserve resources needed for startup tasks, which may be higher than the steady-state resource needs of the application containers.

### General Best Practices

-   **Always set memory requests and limits** to prevent OOM kills and ensure stability.
-   **Always set CPU requests** for predictable scheduling.
-   Monitor your application's resource usage to fine-tune requests and limits.
-   If you only specify a limit, Kubernetes sets the request equal to the limit.

Example of setting resources for a container:
```yaml
resources:
  requests:
    memory: "64Mi"
    cpu: "250m"
  limits:
    memory: "128Mi"
    cpu: "500m"
```

## Tools and Strategies for Resource Management

Beyond setting per-container requests and limits, OpenShift and Kubernetes provide several tools for managing resources at a broader level.

### Namespace-level Controls

-   **`ResourceQuota`**: Provides namespace-wide constraints on resource usage. It can limit the total amount of CPU and memory requested or limited by all pods in a namespace. It can also limit the number of objects that can be created (e.g., pods, services, secrets).
-   **`LimitRange`**: Sets default resource requests and limits for containers in a namespace. If a container is created without its own resource specifications, the `LimitRange` defaults are applied. It can also enforce minimum and maximum resource values.

### Autoscaling

-   **Vertical Pod Autoscaler (VPA):** Monitors the historical and current resource usage of pods and provides recommendations for CPU and memory requests.
    -   **Recommendation Mode (`Off`):** This is the most common and recommended way to use VPA. It provides recommended values without automatically applying them, allowing administrators to make informed decisions.
    -   **Auto Mode:** VPA can automatically update the resource requests on pods, which requires a pod restart.
-   **Horizontal Pod Autoscaler (HPA):** Automatically scales the number of pod replicas in a deployment or statefulset based on observed metrics like CPU utilization or custom metrics.
-   **Cluster Autoscaler:** Automatically adjusts the number of nodes in a cluster. It adds nodes when pods are pending due to insufficient resources and removes underutilized nodes to save costs.

### Cluster-wide Overrides

-   **ClusterResourceOverride (CRO) Operator:** An OpenShift-specific operator that can apply default resource limits and requests cluster-wide. It can be configured to apply a ratio to a container's specified resources, ensuring a baseline level of overcommitment.

## OpenShift and Kubernetes Pod Scheduler Logic

The scheduler is responsible for assigning newly created pods to nodes. This is a two-step process:

1.  **Filtering (Predicates):** The scheduler filters out nodes that do not meet the pod's requirements. A node must satisfy all filter criteria to be considered. Examples of filters include:
    -   **PodFitsResources:** Checks if the node has enough available resources (CPU, memory) for the pod's requests.
    -   **PodToleratesNodeTaints:** Checks if the pod can tolerate the taints on a node.
    -   **PodFitsHostPorts:** Checks if the requested host port is available on the node.
    -   **MatchNodeSelector:** Checks if the node's labels match the pod's node selector.

2.  **Scoring (Priorities):** After filtering, the scheduler scores the remaining feasible nodes to find the best fit. The node with the highest score is chosen. If multiple nodes have the same highest score, one is chosen randomly. Examples of scoring functions include:
    -   **LeastRequestedPriority:** Favors nodes with more available resources.
    -   **BalancedResourceAllocation:** Favors nodes where resource usage is balanced between CPU and memory.
    -   **ImageLocalityPriority:** Favors nodes that already have the container images required by the pod.
    -   **NodeAffinityPriority:** Scores nodes based on preferred node affinity rules.
    -   **TaintTolerationPriority:** Gives priority to nodes that do not require the pod to tolerate taints.

### Influencing Scheduling Decisions

You can influence the scheduler's decisions using various mechanisms:

-   **Node Selectors and Node Affinity/Anti-Affinity:** To constrain pods to run on specific nodes.
-   **Pod Affinity and Anti-Affinity:** To co-locate or spread pods relative to other pods.
-   **Taints and Tolerations:** To prevent pods from being scheduled on certain nodes unless they have a matching toleration.
-   **Pod Topology Spread Constraints:** To control how pods are spread across failure-domains such as regions, zones, and nodes.
-   **PriorityClass:** A cluster-level object that defines a priority for pods. Higher-priority pods can preempt (evict) lower-priority pods to make room for themselves if the cluster is out of resources. This is critical for ensuring important system and application pods can run.
-   **Descheduler:** A tool that runs in the cluster and evicts pods that are violating scheduling policies, helping to rebalance the cluster over time. For example, it can evict pods that are violating anti-affinity rules or are running on nodes that have been newly tainted.
-   **Scheduler Profiles:** OpenShift allows configuring different scheduler profiles (`LowNodeUtilization`, `HighNodeUtilization`, `NoScoring`) to influence scheduling goals, such as spreading pods for high availability or packing them onto fewer nodes to save costs.

A pod remains in the `Pending` state if the scheduler cannot find a suitable node for it. You can inspect the pod's events using `kubectl describe pod <pod-name>` to understand why it's not being scheduled.

## Special Considerations for Java Applications

Running Java applications in containers requires special attention to memory configuration to ensure they respect the container's memory limits and use resources efficiently.

### Container Awareness: The Evolution

-   **Legacy Java (before JDK 8u191):** Older JVMs were not "container-aware." They would inspect the host system's memory and CPU resources, not the container's cgroup limits. This could lead the JVM to allocate a heap size larger than the container's memory limit, causing the container to be terminated with an Out of Memory (OOM) kill.
-   **Modern Java (JDK 8u191+, JDK 10+):** Modern JVMs are container-aware. The `UseContainerSupport` option is enabled by default, allowing the JVM to automatically detect memory and CPU limits set by the container's cgroup.
-   **Cgroup v2 Support (JDK 8u372+, JDK 11+):** With the adoption of cgroup v2 in modern Linux distributions and OpenShift 4.12+, it became crucial for the JVM to support it. OpenJDK 8u372 (April 2023) and later versions backported this support, ensuring that the JVM can correctly read resource limits on newer systems. Older versions that only support cgroup v1 will fail to detect limits on a cgroup v2 host.

### From `-Xmx` to Percentage-Based Tuning: A Shift in Best Practice

The best practice for memory tuning in containers has shifted from manually setting the heap size to letting the JVM calculate it based on the container's limit.

-   **Old Method (`-Xmx`):** Manually setting the maximum heap size (e.g., `-Xmx2g`). This is now considered an anti-pattern in containers because it decouples the JVM's memory from the container's memory limit. If the container limit changes, the `-Xmx` value must also be updated, otherwise it can lead to OOM kills (if `-Xmx` is too high) or resource underutilization (if `-Xmx` is too low).
-   **New Method (`-XX:MaxRAMPercentage`):** This flag tells the JVM to calculate the maximum heap size as a percentage of the container's memory limit. This keeps the heap size coupled to the container's resources, making configurations more portable and robust.

### Sizing Heap vs. Container Memory: The Importance of Off-Heap

It is critical to understand that the JVM heap is only one part of the total memory a Java process consumes. The container's memory limit must be large enough to accommodate both the heap and all other "off-heap" memory allocations. If the total memory usage exceeds the container's limit, the pod will be OOMKilled by the kernel.

Off-heap memory includes:
- **Metaspace:** For class metadata.
- **Thread Stacks:** Each thread has its own stack.
- **Code Cache:** For JIT-compiled native code.
- **Garbage Collection:** The GC itself requires memory for its data structures.
- **Native Memory:** Used by the JVM internally and by JNI/JNA libraries.
- **Other Processes:** Other processes in the same container (e.g., the WebLogic Node Manager) also consume memory.

A common and safe practice is to allocate **75-80%** of the container's memory to the JVM heap via `MaxRAMPercentage`, leaving the remaining 20-25% for off-heap needs.

### Key JVM Memory Flags for Containers

-   **`-XX:MaxRAMPercentage`**: Sets the maximum heap size as a percentage of the container's memory limit. This is the most important flag for preventing OOM kills.
-   **`-XX:InitialRAMPercentage`**: Sets the initial heap size as a percentage of the container's memory limit.
-   **`-XX:MinRAMPercentage`**: Sets the minimum heap size, which can be useful for applications with small memory footprints.

### Applying Configuration in Practice

These JVM flags are typically passed to the Java process via environment variables defined in the pod specification. The specific variable name depends on the base image and its startup scripts.

-   **Red Hat UBI Images:** The `run-java.sh` script uses the `JAVA_OPTS_APPEND` variable. It also respects `JAVA_MAX_MEM_RATIO` (e.g., `JAVA_MAX_MEM_RATIO=80.0`) to automatically configure `-XX:MaxRAMPercentage`.
    - **Default Heap Percentage:** The standard OpenJDK default is **25%**. Red Hat's older UBI8 images defaulted to **50%**, while newer images default to **80%** for better out-of-the-box utilization.
-   **Oracle WebLogic Images:** The WebLogic Kubernetes Operator uses the `USER_MEM_ARGS` environment variable in the Domain resource to pass arguments to the WebLogic Server JVM.

**Example for a generic Pod:**
```yaml
#...
spec:
  containers:
  - name: my-java-app
    image: my-java-image
    env:
    - name: JAVA_OPTS
      value: "-XX:MaxRAMPercentage=80.0"
    resources:
      requests:
        memory: "1Gi"
      limits:
        memory: "2Gi"
#...
```

By using modern, container-aware Java versions and correctly configuring the heap size relative to the container's memory limit, you can ensure that your Java applications run reliably and efficiently within their resource constraints on OpenShift and Kubernetes.
