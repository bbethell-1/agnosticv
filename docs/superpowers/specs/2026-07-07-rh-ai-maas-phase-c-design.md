# rh-ai-maas Phase C: MaaS Platform Layer Design

**Date:** 2026-07-07
**Author:** Tony Kay
**Status:** Draft

## Summary

New Ansible collection `rhpds.openshift_ai_maas` with a single role
`ocp4_workload_openshift_ai_maas` that enables the RHOAI 3.4
Models-as-a-Service (MaaS) governance layer on an existing OpenShift
cluster where RHOAI is already installed (Phase A).

The role installs prerequisite operators (Kuadrant, cert-manager, LWS),
configures the MaaS gateway, deploys PostgreSQL for the maas-api backend,
patches the DataScienceCluster and dashboard to enable MaaS, deploys a
CPU-only simulator model, and optionally configures ExternalModel CRs for
remote inference providers.

**Reference implementation:**
https://github.com/rh-aiservices-bu/rhoai-maas-guide.git

## Scope

### In scope

- New GitHub repo `rhpds/openshift_ai_maas` with Ansible collection structure
- Role `ocp4_workload_openshift_ai_maas` with 7 deployment phases
- Idempotent operator installs (Kuadrant, cert-manager, LWS) with skip-if-present detection
- MaaS gateway with passthrough route at `maas.<cluster-domain>`
- PostgreSQL 16 single-pod deployment for maas-api backend
- DSC patch: `kserve.modelsAsService.managementState: Managed`
- OdhDashboardConfig patch: `modelAsService: true`, `maasAuthPolicies: true`
- CPU-only simulator model (llm-d-inference-sim) always deployed
- Optional ExternalModel CRs driven by a list variable
- Catalog item update: add collection + workload to `agd_v2/rh-ai-maas/common.yaml`

### Out of scope

- GPU-served local models (vLLM/llm-d on GPU nodes)
- Observability stack (Tempo, OpenTelemetry, COO)
- MetalLB (CNV pool clusters use standard ingress)
- HA PostgreSQL (simple deployment is sufficient for demo/lab)
- Modifying the upstream `ocp4_workload_openshift_ai` role

## Collection Structure

```
openshift_ai_maas/
  galaxy.yml                    # rhpds.openshift_ai_maas, version 1.0.0
  README.md
  roles/
    ocp4_workload_openshift_ai_maas/
      defaults/main.yml         # All configurable variables with defaults
      tasks/
        main.yml                # Action router (provision/remove)
        workload.yml            # Orchestrates all phases
        remove_workload.yml     # Teardown
        pre_workload.yml        # Validation / pre-flight
      templates/
        # Phase 1: Operators
        subscription-kuadrant.yaml.j2
        subscription-cert-manager.yaml.j2
        subscription-lws.yaml.j2
        # Phase 2: Platform config
        kuadrant-cr.yaml.j2
        gatewayclass.yaml.j2
        gateway.yaml.j2
        route-passthrough.yaml.j2
        configmap-uwm.yaml.j2
        configmap-gateway-options.yaml.j2
        # Phase 3: PostgreSQL
        secret-postgres-creds.yaml.j2
        secret-maas-db-config.yaml.j2
        deployment-postgres.yaml.j2
        service-postgres.yaml.j2
        pvc-postgres.yaml.j2
        # Phase 5: Simulator model
        namespace-llm.yaml.j2
        llminferenceservice-simulator.yaml.j2
        maasmodelref-simulator.yaml.j2
        maasauthpolicy-simulator.yaml.j2
        maassubscription-simulator.yaml.j2
        # Phase 6: External models
        namespace-external-models.yaml.j2
        externalmodel.yaml.j2
        secret-external-model.yaml.j2
        maasmodelref-external.yaml.j2
        maasauthpolicy-external.yaml.j2
        maassubscription-external.yaml.j2
      meta/main.yml
```

## Role Phases

### Phase 1: Operator Installation

Install three operators with idempotent detection. For each operator:
1. Check if Subscription already exists in target namespace
2. If not, create Subscription from template
3. Wait for ClusterServiceVersion phase `Succeeded`

| Operator | Subscription namespace | Package |
|----------|----------------------|---------|
| Red Hat Connectivity Link (Kuadrant) | `openshift-operators` | `openshift-connectivity-link-operator` |
| cert-manager for Red Hat OpenShift | `cert-manager-operator` | `openshift-cert-manager-operator` |
| LeaderWorkerSet | `openshift-lws-operator` | `lws-operator` |

Kuadrant uses `installPlanApproval: Manual` in its Subscription (same as
the reference guide). The role:
1. Creates the Subscription with `installPlanApproval: Manual`
2. Waits for an InstallPlan to appear in the namespace
3. Patches the InstallPlan's `spec.approved: true`
4. Waits for the CSV phase `Succeeded`

cert-manager and LWS use `installPlanApproval: Automatic`.

**Variables:**
- `ocp4_workload_openshift_ai_maas_install_operators: true` — set false to skip if operators are pre-installed

### Phase 2: Platform Configuration

Create the MaaS gateway infrastructure. Cluster domain is auto-detected
from the cluster's ingress config
(`oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}'`).

Resources created:
1. **Kuadrant CR** in `kuadrant-system` namespace
2. Authorino TLS patching — listener cert and CA bundle environment
   variables on the Authorino deployment
3. **User Workload Monitoring** ConfigMap in `openshift-monitoring`
   (enables `enableUserWorkload: true`)
4. **GatewayClass** `openshift-default` (cluster-scoped, controller:
   `istio.io/gateway-controller`)
5. **Gateway** `maas-default-gateway` in `openshift-ingress` — HTTPS
   listener on `maas.<cluster-domain>`, namespace selector requires label
   `maas.opendatahub.io/gateway-access: "true"`
6. **ConfigMap** `maas-gateway-options` in `openshift-ingress` — sets
   istio-proxy memory limit to 2Gi
7. **Passthrough Route** `maas-default-gateway-https` in
   `openshift-ingress` — targets service
   `maas-default-gateway-openshift-default` on HTTPS

**Variables:**
- `ocp4_workload_openshift_ai_maas_gateway_memory_limit: 2Gi`

### Phase 3: PostgreSQL Deployment

Deploy a single-pod PostgreSQL 16 instance in `redhat-ods-applications`
for the maas-api backend.

Resources created:
1. **Secret** `postgres-creds` — POSTGRES_USER=maas, POSTGRES_DB=maas,
   POSTGRES_PASSWORD=<random 24-char>
2. **Secret** `maas-db-config` — DB_CONNECTION_URL constructed from above
3. **PVC** `postgres-data` — 10Gi, default StorageClass
4. **Deployment** `postgres` — `registry.redhat.io/rhel9/postgresql-16:latest`,
   mounts PVC at `/var/lib/pgsql/data`
5. **Service** `postgres` — port 5432

**Variables:**
- `ocp4_workload_openshift_ai_maas_postgres_image: registry.redhat.io/rhel9/postgresql-16:latest`
- `ocp4_workload_openshift_ai_maas_postgres_storage: 10Gi`

### Phase 4: RHOAI MaaS Configuration

Patch existing RHOAI resources to enable MaaS.

1. **Patch DataScienceCluster** `default-dsc` — add
   `spec.components.kserve.modelsAsService.managementState: Managed`
2. **Patch OdhDashboardConfig** — set `modelAsService: true`,
   `maasAuthPolicies: true`
3. **Wait** for DSC conditions:
   - `KserveReady: True`
   - `ModelControllerReady: True`
4. **Wait** for CRD `maasmodelrefs.maas.opendatahub.io` to exist
5. **Wait** for `maas-api` Deployment rollout in `redhat-ods-applications`
6. **Wait** for Tenant `default-tenant` status `Ready` in
   `models-as-a-service` namespace
7. **Health check** — `uri` module against
   `https://maas.<cluster-domain>/maas-api/health`

**Variables:**
- `ocp4_workload_openshift_ai_maas_wait_retries: 60`
- `ocp4_workload_openshift_ai_maas_wait_delay: 10`

### Phase 5: Simulator Model

Deploy the CPU-only simulator for smoke testing. No GPU required.

Namespaces:
- `llm` — LLMInferenceService runs here, labeled with
  `maas.opendatahub.io/gateway-access: "true"`,
  `opendatahub.io/generated-namespace: "true"`,
  `opendatahub.io/dashboard: "true"`
- `models-as-a-service` — governance CRs (MaaSModelRef, MaaSAuthPolicy,
  MaaSSubscription) go here

Resources:
1. **Namespace** `llm` with required labels
2. **LLMInferenceService** `simulated` in `llm` — image
   `ghcr.io/llm-d/llm-d-inference-sim:v0.7.1`, model
   `facebook/opt-125m`, CPU-only (100m-500m CPU, 256-512Mi memory),
   references `maas-default-gateway` in `openshift-ingress`
3. **MaaSModelRef** `simulated` in `models-as-a-service` — references the
   LLMInferenceService
4. **MaaSAuthPolicy** `simulated` in `models-as-a-service` — default auth
   policy
5. **MaaSSubscription** `simulated` in `models-as-a-service` — default
   subscription

**Variables:**
- `ocp4_workload_openshift_ai_maas_simulator_image: ghcr.io/llm-d/llm-d-inference-sim:v0.7.1`
- `ocp4_workload_openshift_ai_maas_simulator_model: facebook/opt-125m`
- `ocp4_workload_openshift_ai_maas_deploy_simulator: true`

### Phase 6: External Models (Optional)

Loop over a list variable and create ExternalModel + governance CRs for
each entry. Empty by default — catalog items or the RHOAI dashboard UI
can add models.

Namespace `external-models` is created with the gateway-access label.

Each list item creates:
1. **Secret** with the provider's API key (labeled
   `inference.networking.k8s.io/bbr-managed: "true"`)
2. **ExternalModel** CR in `external-models` — provider, targetModel,
   endpoint, credentialRef
3. **MaaSModelRef** in `models-as-a-service`
4. **MaaSAuthPolicy** in `models-as-a-service`
5. **MaaSSubscription** in `models-as-a-service`

**Variables:**
```yaml
ocp4_workload_openshift_ai_maas_external_models: []
# Example:
# - name: gpt-4o
#   provider: openai
#   target_model: gpt-4o
#   endpoint: https://api.openai.com/v1
#   api_key: sk-...
# - name: claude-sonnet
#   provider: anthropic
#   target_model: claude-sonnet-4-20250514
#   endpoint: https://api.anthropic.com/v1
#   api_key: sk-ant-...
```

Models added manually via the RHOAI dashboard UI coexist with
Ansible-managed ones — the role does not delete unmanaged models.

## Catalog Item Changes

`agd_v2/rh-ai-maas/common.yaml` additions:

```yaml
# Add to requirements_content.collections:
- name: https://github.com/rhpds/openshift_ai_maas.git
  type: git
  version: "{{ tag }}"

# Add to workloads (after openshift_ai):
- rhpds.openshift_ai_maas.ocp4_workload_openshift_ai_maas
```

No external model secrets needed for the default configuration — the
simulator runs without any API keys.

## Role Variables Summary

| Variable | Default | Description |
|----------|---------|-------------|
| `ocp4_workload_openshift_ai_maas_install_operators` | `true` | Install Kuadrant/cert-manager/LWS operators |
| `ocp4_workload_openshift_ai_maas_gateway_memory_limit` | `2Gi` | Istio-proxy memory limit for gateway |
| `ocp4_workload_openshift_ai_maas_postgres_image` | `registry.redhat.io/rhel9/postgresql-16:latest` | PostgreSQL image |
| `ocp4_workload_openshift_ai_maas_postgres_storage` | `10Gi` | PostgreSQL PVC size |
| `ocp4_workload_openshift_ai_maas_wait_retries` | `60` | Max retries for wait conditions |
| `ocp4_workload_openshift_ai_maas_wait_delay` | `10` | Seconds between retry attempts |
| `ocp4_workload_openshift_ai_maas_simulator_image` | `ghcr.io/llm-d/llm-d-inference-sim:v0.7.1` | Simulator container image |
| `ocp4_workload_openshift_ai_maas_simulator_model` | `facebook/opt-125m` | Simulator model name |
| `ocp4_workload_openshift_ai_maas_deploy_simulator` | `true` | Deploy CPU-only simulator model |
| `ocp4_workload_openshift_ai_maas_external_models` | `[]` | List of external model configs |

## Action Router Pattern

```yaml
# tasks/main.yml
- name: Run action {{ ACTION }}
  ansible.builtin.include_tasks: "{{ ACTION }}.yml"
  vars:
    ACTION: >-
      {{ action | default(
           (ACTION | default('provision'))
           | regex_replace('^workload$', 'provision')
         ) }}
```

Supports `provision` (workload.yml), `remove` (remove_workload.yml).

## Remove Workload

Teardown in reverse order:
1. Delete external model namespaces and governance CRs
2. Delete simulator namespace and governance CRs
3. Remove DSC modelsAsService patch (set to Removed)
4. Revert OdhDashboardConfig
5. Delete PostgreSQL resources
6. Delete gateway infrastructure
7. Delete Kuadrant CR
8. Optionally delete operator Subscriptions + CSVs

## Testing

After deployment, verify:
1. `maas-api` health: `curl https://maas.<domain>/maas-api/health`
2. Simulator model is Ready: `oc get llminferenceservice simulated -n llm`
3. MaaS tenant is Ready: `oc get tenant default-tenant -n models-as-a-service`
4. Dashboard shows MaaS tab with registered models
5. Can create API key and call simulator via OpenAI-compatible API

## Dependencies

- Phase A must be deployed first (RHOAI 3.4 + Keycloak auth)
- Service Mesh 3.x (auto-installed by RHOAI as KServe dependency)
- Cluster domain must be resolvable (wildcard DNS)
