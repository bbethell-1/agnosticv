# AgentOps Intel Catalog Item Design

**Date:** 2026-07-20  
**Author:** Tony Kay  
**Status:** Approved

## Overview

Create a new AgnosticV catalog item `agd_v2/agentops-intel/` based on the Summit 2026 AgentOps lab (`summit-2026/lb2144-agentops-ocp-cnv/`), adapted for general use with Intel Gaudi acceleration.

## Goals

1. Preserve the working AgentOps in Production lab configuration
2. Remove Summit-specific branding and constraints
3. Switch to Intel Gaudi accelerated LLM model
4. Create dedicated Showroom content repository
5. Establish clean agd_v2 catalog item structure

## Architecture

### Component Structure

**Base Infrastructure:**
- OpenShift cluster via `agd_v2/ocp-cluster-cnv-pools` component
- CNV (OpenShift Virtualization) multinode cluster
- OpenShift 4.20

**Workload Stack:**
1. `ocp4_workload_authentication` - Keycloak-based auth with admin + user accounts
2. `ocp4_workload_openshift_gitops` - ArgoCD with cluster admin setup
3. `ocp4_workload_litellm_virtual_keys` - LiteLLM API key management
4. `ocp4_workload_gitops_bootstrap` - Bootstrap from `rhpds/agentops-in-prod-automation`
5. `ocp4_workload_ocp_console_embed` - Embedded console for Showroom
6. `ocp4_workload_showroom` - Interactive lab content delivery

### Data Flow

```
User provisions catalog item
  ↓
CNV cluster provisioned (ocp-cluster-cnv-pools)
  ↓
Authentication configured (Keycloak)
  ↓
GitOps operator installed (ArgoCD)
  ↓
LiteLLM virtual key created (gpt-oss-120b-gaudi model)
  ↓
GitOps bootstrap deploys application stack
  ↓
Showroom content loads (agentops-intel repo)
  ↓
User accesses lab via Showroom UI
```

## Key Changes from Source

### 1. Identity & Metadata

**Change:**
- Generate new `asset_uuid` (replace `193d2575-de1e-4e7c-a80b-2a1e96aaac60`)
- Display name: `"AgentOps Intel"`
- Remove `Brand_Event: Red_Hat_Summit_2026` label
- Remove `summit-2026`, `lb2144` keywords
- Add `agentops`, `intel`, `gaudi` keywords
- Keep category as `Brand_Events` (can be changed later to appropriate category)

**Why:** Clean separation from Summit-specific instance, establish independent identity

**How to apply:** Generate UUID via Python, update `__meta__.catalog` section in `common.yaml`

### 2. Email & Tracking

**Change:**
- Remove hardcoded `requester_email: summit-{{guid}}@demo.redhat.com`
- Remove hardcoded `catalog_item_name: summit-2026.lb2144-agentops-ocp-cnv.event`
- Use standard includes: `#include /includes/parameters/litellm_metadata.yaml`

**Why:** The include provides proper dynamic email/catalog tracking without hardcoding

**How to apply:** Delete lines 22-23 in common.yaml, rely on the include already present at line 21

### 3. LLM Model Configuration

**Change:**
```yaml
# Before:
llm_model: gpt-oss-120b

# After:
llm_model: gpt-oss-120b-gaudi
```

**Why:** Target Intel Gaudi accelerator hardware for LLM inference

**How to apply:** Update line 139 in `common.yaml`. This value flows to:
- `ocp4_workload_litellm_virtual_keys_models` (line 141-142)
- `ocp4_workload_gitops_bootstrap_helm_values.remotellm.id` (line 160)

### 4. Showroom Content Repository

**Change:**
```yaml
# Before:
ocp4_workload_showroom_content_git_repo: https://github.com/rhpds/agentops-in-prod-showroom

# After:
ocp4_workload_showroom_content_git_repo: https://github.com/rhpds/agentops-intel
```

**Why:** Separate content repository allows Intel-specific customization without affecting Summit lab

**How to apply:** 
1. Fork `rhpds/agentops-in-prod-showroom` to `rhpds/agentops-intel` on GitHub
2. Update line 175 in `common.yaml`
3. Keep `main` branch reference (line 176)

### 5. Version Management

**Change:**
- Do not create `prod.yaml` or `event.yaml` initially
- Use `tag: main` from `common.yaml` for all collection versions

**Why:** This is a development catalog item; production configuration will be added later when stable

**How to apply:** Only copy `common.yaml` and `dev.yaml`, skip production files

### 6. Description Updates

**Change:**
- Remove "Do not order this item unless you are a developer" warning (lines 1-5)
- Remove "Red Hat Summit 2026 lab" disclaimer (lines 11-14)
- Keep technical content and learning objectives
- Update support section if needed

**Why:** This is a generally available catalog item, not a Summit-specific limited release

**How to apply:** Edit `description.adoc`, preserve technical content about the lab experience

## File Structure

```
agd_v2/agentops-intel/
├── common.yaml              # Main configuration (modified)
├── description.adoc         # Catalog description (modified)
├── dev.yaml                 # Dev environment config (copied)
├── info-message-template.adoc  # User provisioning message (copied)
└── CLAUDE.md                # Development guidance (new)
```

**Note:** No `prod.yaml` or `event.yaml` initially - this is a development catalog item.

## Testing Strategy

**Pre-deployment validation:**
1. YAML syntax validation
2. Include file reference validation
3. Variable interpolation check

**Post-deployment validation:**
1. Catalog item appears in appropriate namespace
2. Provision test on dev environment
3. Verify LiteLLM virtual key created with correct model
4. Verify GitOps bootstrap deploys successfully
5. Verify Showroom content loads from new repository
6. Verify all Showroom tabs work (OCP Console, Terminal, MLflow, etc.)

## Error Handling

**Potential issues:**

1. **Showroom repository not found** - Ensure fork created before first provision
2. **LiteLLM model not available** - Verify `gpt-oss-120b-gaudi` exists in LiteMaaS
3. **GitOps bootstrap timeout** - Check `agentops-in-prod-automation` repo accessibility
4. **Collection version mismatch** - Ensure `tag: main` resolves to compatible versions

## Migration Path

**From Summit lab to Intel lab:**
- Users can provision Intel version independently
- Summit lab remains unchanged in `summit-2026/` directory
- No migration of existing Summit deployments needed

**Future updates:**
- Pin specific collection versions in `prod.yaml` when stable
- Create release tags in showroom repo for production stability
- Consider moving from CNV to AWS if Intel hardware requirements change

## Success Criteria

1. ✅ New catalog item appears in RHDP catalog
2. ✅ Provisions successfully on CNV cluster
3. ✅ Uses `gpt-oss-120b-gaudi` LLM model
4. ✅ Loads content from `rhpds/agentops-intel` repository
5. ✅ All workloads deploy without errors
6. ✅ Showroom UI accessible with all tabs functional
7. ✅ User can complete lab modules end-to-end

## Open Questions

None - design approved for implementation.

## Implementation Notes

**Execution order:**
1. Copy directory structure
2. Modify YAML configurations
3. Create GitHub repository fork
4. Update repository references
5. Commit changes
6. Create draft PR for review
7. Write CLAUDE.md guidance

**GitHub fork creation:**
- Will require user approval for fork action
- Fork settings: public repository, copy main branch only
- Update README in fork to reflect Intel focus

## Appendix: Key Variables Reference

| Variable | Source Value | New Value | Impact |
|----------|--------------|-----------|--------|
| `asset_uuid` | `193d2575-de1e-4e7c-a80b-2a1e96aaac60` | New UUID | Catalog item identity |
| `display_name` | `LB2144: AI AgentOps OpenShift (CNV)` | `AgentOps Intel` | User-visible name |
| `llm_model` | `gpt-oss-120b` | `gpt-oss-120b-gaudi` | LLM inference hardware |
| `showroom_repo` | `agentops-in-prod-showroom` | `agentops-intel` | Lab content source |
| `tag` (prod) | `lb2144-agentops-1.0.3` | `main` | Collection versions |

## References

- Source: `summit-2026/lb2144-agentops-ocp-cnv/`
- GitOps automation: `https://github.com/rhpds/agentops-in-prod-automation`
- Showroom source: `https://github.com/rhpds/agentops-in-prod-showroom`
- Showroom fork: `https://github.com/rhpds/agentops-intel` (to be created)
