# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## What This Is

A **Sandbox API cluster/tenant catalog item pair** for the Red Hat Lightwell demo, targeting Summit Connect 2026. These are AgnosticV catalog items that define OpenShift cluster infrastructure and per-user tenant environments provisioned via RHDP (Red Hat Demo Platform).

### What is Lightwell?

Red Hat + IBM's Lightwell is a trusted software supply chain initiative. It provides remediated, digitally signed open-source dependencies via **Lightwell Network** and coordinates vulnerability disclosure/patching via **Lightwell Clearinghouse**. The demo showcases how enterprises integrate Lightwell with their build pipelines to detect, triage, and remediate CVEs in application dependencies.

Key technologies for the demo:
- **OpenShift 4.21** — target platform
- **Ansible Automation Platform (Controller)** — automation orchestration
- **Red Hat Trusted Application Pipelines (RHTAP)** — Tekton-based TSSC pipelines, RHTAS (signing), RHTPA (profile analysis)
- **GitLab** — source code management (replacing Gitea from LB2645)
- **JFrog Artifactory** — enterprise artifact proxy to Lightwell Network repositories
- **OpenShift GitOps (ArgoCD)** — app-of-apps Helm deployment pattern

Prior art references:
- `agd_v2/trusted-software-factory-cnv/` — existing TSSC demo CI with GitLab, Quay, ArgoCD, Konflux
- `NA-FSI-Services/lightwell-tssc-workshop` — 5-module Showroom workshop (RHLN, Maven integration, OSV triage, SBOM, pipeline enforcement)
- `cnuland/hello-chris-lightwell` — standalone Artifactory→RHLN proxy lab

## Architecture: Cluster/Tenant Split

This follows the **Sandbox API shared-cluster pattern**: one cluster CI installs cluster-wide infrastructure, then many tenant CIs are provisioned on top via the OpenShift Sandbox API.

```
lb1815-lightwell-cluster/     ← Cluster CI: cluster-scoped operators + shared services
  common.yaml                ← Workloads, collections, operator config, __meta__ with components + sandbox_host
  dev.yaml                   ← Dev stage overrides (deployer scm_ref, purpose: dev annotation)
  description.adoc           ← Catalog description
  info-message-template.adoc ← Admin access info template

lb1815-lightwell-tenant/      ← Tenant CI: per-user namespaces, apps, Showroom
  common.yaml                ← Tenant workloads, user config, Showroom tabs, __meta__ with sandboxes
  dev.yaml                   ← Dev overrides (Antora dev mode, purpose cost-tag)
  description.adoc           ← Catalog description
  info-message-template.adoc ← User-facing access info template
```

### How the Pair Connects

1. The cluster CI's `__meta__.components` requests a CNV cluster from `agd-v2/ocp-cluster-cnv-pools` and maps its outputs (API URL, tokens, bastion) via `propagate_provision_data`.
2. The cluster CI deploys cluster-scoped workloads (operators, shared services).
3. The cluster CI's `__meta__.sandbox_host` registers it with the Sandbox API — `annotations: {cloud, lab}` plus `max_placements`/`max_cpu_usage_percentage`/`max_memory_usage_percentage`. `dev.yaml` layers on `annotations.purpose: dev`.
4. The tenant CI's `__meta__.sandboxes[].cloud_selector` (`cloud` + `lab: lb1815-lightwell` + `purpose: dev`) matches the cluster's registered annotations to land on the right cluster.
5. The matched sandbox exposes `openshift_cluster_admin_token` directly; the tenant aliases it to `cluster_admin_agnosticd_sa_token` because that's the variable name `namespaced_workloads` roles expect.

### Workload Ordering Matters

Workloads deploy in list order. Dependencies must come first:
- Authentication → before anything that needs users
- Operators (GitOps, OCP Virt) → before workloads that create CRs
- Cluster infrastructure → before tenant-level workloads

## Key Conventions

### Variable Naming
- Workload vars are prefixed with the full role name: `ocp4_workload_gitlab_namespace`, `ocp4_workload_ansible_automation_platform_admin_password`
- `common_admin_password` / `common_password` — generated passwords shared across workloads
- `tag` variable controls collection versions; `main` for dev

### Include Directives
`#include /path` lines at the top of YAML files merge content from `includes/` at the repo root. Standard set for Sandbox API items:
```yaml
#include /includes/agd-v2-mapping.yaml
#include /includes/catalog-icon-openshift.yaml
#include /includes/terms-of-service.yaml
#include /includes/sandbox-api.yaml
#include /includes/parameters/purpose.yaml
```

### Stage Overrides
- `dev.yaml` — minimal overrides for development (deployer ref, `sandbox_host`/cost-tag `purpose: dev`)
- `common.yaml` — the top-level `purpose` cost-tag comes from the stage file or parameter include, never set it here

### __meta__ Block
- `asset_uuid` — must be unique per catalog item (generate a new one, don't reuse another CI's)
- `catalog.display_name` — what appears in the RHDP catalog
- `catalog.keywords` / `labels` — keep these specific to Lightwell
- `sandboxes[].cloud_selector` — must match the cluster's `sandbox_host.annotations`
- `deployer.execution_environment.image` — use a current `ee-multicloud:chained-*` tag

### sandbox_host (cluster registration)
- `annotations.lab` must match across the cluster's `sandbox_host.annotations.lab` and the tenant's `cloud_selector.lab`
  - Current value: `lb1815-lightwell`
- `max_placements` — number of concurrent tenants the cluster supports
- No separate JSON registration files or dev/event split — one `sandbox_host` block in `common.yaml`, with `dev.yaml` layering on `annotations.purpose: dev`
- The tenant reads the matched sandbox's `openshift_cluster_admin_token` directly (see "How the Pair Connects" above) — there's no `deployer_admin_sa_token_target_var` indirection

### AsciiDoc Templates
- `description.adoc` — catalog-facing, plain AsciiDoc
- `info-message-template.adoc` — uses `ifdef`/`ifndef` guards and `{variable}` (single-brace AsciiDoc attributes, not Jinja2)

## Current Workloads

The cluster CI deploys the following workloads in order:

1. **ocp4_workload_authentication** — Keycloak-based SSO for OpenShift console and workload auth
2. **ocp4_workload_openshift_gitops** — OpenShift GitOps operator (ArgoCD)
3. **ocp4_workload_gitops_bootstrap** — Bootstraps Lightwell infrastructure from GitOps repo
4. **ocp4_workload_ansible_automation_platform** — AAP Controller (currently commented out)
5. **ocp4_workload_ocp_console_embed** — OCP console iframe embedding support for Showroom

### GitOps Repository Architecture

The cluster uses a **GitOps bootstrap** pattern. The `ocp4_workload_gitops_bootstrap` workload points to:

- **Repo:** `https://github.com/rhpds/lightwell-automation-gitops.git`
- **Path:** `bootstrap-infra`
- **Application Name:** `lb1815-lightwell`

This GitOps repository (created in Task 1 of the implementation plan) contains Helm charts and ArgoCD Applications for:
- GitLab
- JFrog Artifactory
- RHTAP components (Tekton pipelines, signing services)
- Additional Lightwell demo infrastructure

The bootstrap workload passes environment-specific values (domain, passwords) via `ocp4_workload_gitops_bootstrap_helm_values`.

### Collections

The cluster CI pulls from these collections:

- **assisted_installer** (v0.0.9) — CNV cluster provisioning support
- **core_workloads** (`{{ tag }}` — `main` for dev) — authentication, GitOps, AAP workloads
- **showroom** (v1.6.11) — console embed support

## Validation

There is no local test suite. Validation is done by:
1. Deploying via RHDP (ordering the catalog item)
2. Checking the AgnosticV operator processes the YAML correctly
3. Verifying workloads deploy successfully on the target cluster

To check YAML syntax locally: `python -c "import yaml; yaml.safe_load(open('common.yaml'))"` (note: `#include` directives will be treated as comments by plain YAML parsers, which is fine for syntax checking).

If deploys get stuck, a trivial commit+push to the branch can unstick a stale AgnosticV operator sync.
