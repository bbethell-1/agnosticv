# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

`agd_v2/rh-ai-maas/` is an AgnosticV catalog item that deploys **OpenShift AI with Models-as-a-Service (MaaS)** on a CNV-based OpenShift 4.21 cluster. It provisions shared platform infrastructure (not per-user tenants) and is designed for registration with the OpenShift Sandbox API.

**Goal:** A minimal cluster CI — OpenShift + Keycloak auth + OpenShift AI 3.4. Phase A provides the base platform; Phase C will add the MaaS governance layer (Kuadrant, LWS, gateway, maas-api).

## MaaS Overview

MaaS (GA in OpenShift AI 3.4) is an enterprise AI inference gateway providing:
- Centralized OpenAI-compatible API endpoint at `https://maas.<cluster-domain>/`
- API key management (`sk-oai-*` prefix), subscription-based token rate limiting
- Governance via CRDs: `LLMInferenceService`, `MaaSModelRef`, `MaaSAuthPolicy`, `MaaSSubscription`, `ExternalModel`
- Architecture layers: Gateway (Kuadrant/Authorino/Limitador) → Token Management (maas-api + PostgreSQL) → Model Serving (vLLM/llm-d) → Governance CRDs

### Required Operators for MaaS

1. Red Hat OpenShift AI (RHOAI) — `stable-3.4` channel
2. Red Hat Connectivity Link (RHCL / Kuadrant)
3. cert-manager
4. Service Mesh (Istio)
5. Leader Worker Set (LWS)
6. Optional: NVIDIA GPU Operator + NFD (for GPU-served models)

### Key MaaS Enablement

MaaS is activated via the `DataScienceCluster` CR:
```yaml
spec.components.kserve.modelsAsService.managementState: Managed
```
And dashboard flag in `OdhDashboardConfig`:
```yaml
modelAsService: true
```

## AgnosticV Catalog Item Structure

### File Anatomy

| File | Purpose |
|------|---------|
| `common.yaml` | Main config — includes, workloads, variables, `__meta__` block |
| `dev.yaml` | Development stage — sets `scm_ref: main`, minimal overrides |
| `prod.yaml` | Production stage — pins `tag:` and `scm_ref:` to release tags |
| `event.yaml` | Event stage — pins to commit SHAs for reproducibility |
| `description.adoc` | Catalog UI description (AsciiDoc) |
| `info-message-template.adoc` | Post-provision info message (AsciiDoc with `{variable}` substitution) |
| `cluster-config-*.json` | Sandbox API placement config (max placements, resource thresholds) |

### Inheritance Chain

```
/common.yaml (repo root)           → global defaults, secrets, deployer SCM
  → agd_v2/account.yaml            → anarchy namespace, lifetime, controller assignment
    → agd_v2/rh-ai-maas/common.yaml → this CI's workloads, variables, __meta__
      → agd_v2/rh-ai-maas/dev.yaml  → dev stage overrides
```

### Key Patterns

- **`#include` directives** are processed by the AgnosticV operator, not standard YAML. Paths are repo-root-relative with leading `/`.
- **`config: openshift-workloads`** means this runs workloads on an existing cluster (not provisioning a new one).
- **`cloud_provider: none`** means the cluster comes from a pool via `__meta__.components`.
- **`__meta__.components`** references the OCP cluster pool item (`agd-v2/ocp-cluster-cnv-pools`) and maps provision data (API URL, tokens, bastion info) into this CI's variables.
- **YAML list replacement**: stage files that override `requirements_content.collections` must include the full list — YAML lists replace, they don't merge.
- **`tag:` variable**: used in `requirements_content` collection versions; set to `main` in dev, pinned to release tags in prod/event.

## Key `__meta__` Fields

- `asset_uuid` — unique identifier, must be regenerated for this new CI (use `uuidgen`)
- `components[].item` — references the cluster pool (`agd-v2/ocp-cluster-cnv-pools`)
- `components[].parameter_values.host_ocp4_installer_version` — target OCP version (set to `"4.21"`)
- `deployer.scm_url` — AgnosticD v2 repo (`https://github.com/rhpds/agnosticd-v2`)
- `deployer.execution_environment.image` — the Ansible EE image from `quay.io/agnosticd/ee-multicloud`

## Reference Resources

- **MaaS official docs**: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/govern_llm_access_with_models-as-a-service/index
- **MaaS setup guide repo** (bash + Kustomize, not Ansible): https://github.com/rh-aiservices-bu/rhoai-maas-guide.git
  - `manifests/01-prerequisites/` through `manifests/08-external-models/` — ordered deployment phases
  - `manifests/05-maas-models/simulator/` — CPU-only test model (no GPU needed)
  - `scripts/setup-maas.sh` — all-in-one idempotent setup script
  - `scripts/verify-maas.sh` — E2E verification
- **lb2645 reference CI** (the scaffold this was forked from): `summit-2026/lb2645-agentic-devops-cluster/`

## Validation

```bash
# Lint YAML syntax
python -c "import yaml; yaml.safe_load(open('agd_v2/rh-ai-maas/common.yaml'))"

# Validate catalog item structure (from repo root)
agnosticv --list  # list all catalog items
agnosticv --validate agd_v2/rh-ai-maas  # validate this CI

# Check that asset_uuid is unique across the repo
grep -r "$(grep asset_uuid agd_v2/rh-ai-maas/common.yaml | awk '{print $2}')" --include='*.yaml' .
```

## Current State

Phase A + C are implemented:
- `common.yaml` — 3 workloads (Keycloak auth + RHOAI 3.4 + MaaS governance), OCP 4.21 multinode CNV
- `dev.yaml` — minimal, just `scm_ref: main`
- `description.adoc` — MaaS platform description
- `info-message-template.adoc` — cluster console, RHOAI dashboard, MaaS API, bastion SSH
- `cluster-config-dev.json` — Sandbox API placement, 1 max for dev

The MaaS governance layer (`rhpds.openshift_ai_maas.ocp4_workload_openshift_ai_maas`) deploys:
1. Control-plane node scheduling (removes master NoSchedule taints)
2. cert-manager, Service Mesh, RHCL (Kuadrant), LWS operators
3. MaaS gateway (GatewayClass, Gateway, passthrough Route, ClusterIP service)
4. PostgreSQL + maas-api for token management
5. RHOAI DSC `kserve.modelsAsService: Managed` + dashboard `modelAsService: true`
6. Inference simulator (CPU-only `facebook/opt-125m`) for validation
7. Optional ExternalModel CRs for remote model providers

Reference: https://github.com/rh-aiservices-bu/rhoai-maas-guide.git
