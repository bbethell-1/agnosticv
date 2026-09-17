# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## What This Is

The **tenant** half of the LB1815 Lightwell Sandbox API cluster/tenant pair — see `rh1-2027/lb1815-lightwell-cluster/AGENTS.md` for the cluster side and how the pair connects. This AgnosticV catalog item provisions a single per-user demo seat on the shared cluster: a Keycloak login, an isolated namespace, provisioned accounts in AAP2/GitLab/Artifactory (via a per-tenant ArgoCD Application, not an Ansible role), and a Showroom lab guide.

### What is Lightwell?

Red Hat + IBM's Lightwell is a trusted software supply chain initiative. It provides remediated, digitally signed open-source dependencies via **Lightwell Network** and coordinates vulnerability disclosure/patching via **Lightwell Clearinghouse**. Attendees use this tenant to detect, triage, and remediate CVEs in application dependencies using packages backed by the Lightwell Network.

## Layout

```
common.yaml                ← Tenant workloads, user config, Showroom tabs, __meta__ with sandboxes
dev.yaml                   ← Dev overrides (Antora dev mode, purpose cost-tag)
description.adoc           ← Catalog description (leads with the lab's full title)
info-message-template.adoc ← User-facing access info template
```

## How This Connects to the Cluster

1. `__meta__.sandboxes[].cloud_selector` (`cloud: cnv-dedicated-shared`, `lab: lb1815-lightwell`, `purpose: dev`) matches the cluster CI's registered `sandbox_host.annotations` to land on the shared cluster — see the cluster's AGENTS.md for the registration side.
2. The matched sandbox exposes `sandbox_openshift_api_url` and `openshift_cluster_admin_token` directly. This CI remaps them: `openshift_api_url: "{{ sandbox_openshift_api_url }}"` and `cluster_admin_agnosticd_sa_token: "{{ openshift_cluster_admin_token }}"`, because the `namespaced_workloads` roles and the Showroom role expect those specific variable names.
3. `ocp4_workload_gitops_bootstrap` creates a per-tenant ArgoCD Application (`lightwell-tenant-{{ guid }}`, `bootstrap-tenant` path in `rhpds/lightwell-automation-gitops`) that provisions the tenant's AAP2/GitLab/Artifactory accounts — this is GitOps, not an Ansible role.

## Key Conventions

### Variable Naming
- Workload vars are prefixed with the full role name: `ocp4_workload_tenant_namespace_use_cluster_quota`, `ocp4_workload_gitops_bootstrap_helm_values`
- `common_password` — generated password shared across this tenant's accounts (Keycloak, AAP, GitLab)
- `{{ guid }}` — the per-tenant identifier; namespaces, usernames, and the ArgoCD Application name are all suffixed with it

### Include Directives
`#include /path` lines at the top of YAML files merge content from `includes/` at the repo root. Standard set for Sandbox API tenant items:
```yaml
#include /includes/agd-v2-mapping.yaml
#include /includes/catalog-icon-openshift.yaml
#include /includes/terms-of-service.yaml
#include /includes/sandbox-api.yaml
#include /includes/parameters/purpose.yaml
```

### Stage Overrides
- `dev.yaml` — Antora dev mode for Showroom, cost-tag `purpose: development`
- `common.yaml` — the `cloud_selector` (`lab`, `purpose: dev`) is set here and applies to every stage; there's no dev/event split for this tenant

### __meta__ Block
- `asset_uuid` — must be unique per catalog item (generate a new one, don't reuse another CI's)
- `sandboxes[].cloud_selector` — must match the cluster's `sandbox_host.annotations` (see cluster AGENTS.md)
- `catalog.display_name` — what appears in the RHDP catalog
- `catalog.workshop_user_mode: none` — provision doesn't call `agnosticd_user_info` with `user` set, so `provision_data` won't report `users`; all data/messages go to the workshop seat directly
- `deployer.execution_environment.image` — use a current `ee-multicloud:chained-*` tag, kept in sync with the cluster CI's

### Resource Sizing
- `ocp4_workload_tenant_namespace_default_quota` — total ClusterResourceQuota pool for this tenant's namespaces, sized for a Jenkins/Maven build plus a running sample app
- `ocp4_workload_tenant_namespace_default_limit_range` — per-pod defaults for pods that don't specify requests/limits

### AsciiDoc Templates
- `description.adoc` — catalog-facing, plain AsciiDoc; leads with the full lab title ("Get Ready for Lightwell: Patch to Production at the Speed of AI")
- `info-message-template.adoc` — uses `ifdef`/`ifndef` guards and `{variable}` (single-brace AsciiDoc attributes, not Jinja2)

## Current Workloads

Deploys in order:

1. **ocp4_workload_tenant_keycloak_user** — per-tenant OpenShift login via the shared cluster's Keycloak SSO
2. **ocp4_workload_tenant_namespace** — isolated `{user}-enterprise` namespace with a ClusterResourceQuota
3. **ocp4_workload_gitops_bootstrap** — per-tenant ArgoCD Application provisioning AAP2/GitLab/Artifactory accounts
4. **ocp4_workload_showroom** — lab guide with embedded consoles for Jenkins, Artifactory, GitLab, the OpenShift console, Red Hat Quay, and AAP2

### Collections

- **namespaced_workloads** (`{{ tag }}` — `main` for dev) — Keycloak user, tenant namespace
- **core_workloads** (`{{ tag }}`) — GitOps bootstrap
- **showroom** (v1.6.11) — lab guide

## Validation

There is no local test suite. Validation is done by:
1. Deploying via RHDP (ordering the catalog item) against a cluster CI already provisioned with a matching `lab` annotation
2. Checking the AgnosticV operator processes the YAML correctly
3. Verifying the Showroom lab guide loads with working tabs and the tenant's Keycloak login works

To check YAML syntax locally: `python -c "import yaml; yaml.safe_load(open('common.yaml'))"` (note: `#include` directives will be treated as comments by plain YAML parsers, which is fine for syntax checking).
