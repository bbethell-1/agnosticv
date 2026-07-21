# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Catalog Item: AgentOps Intel

This is an AgnosticV catalog item for the "AgentOps Intel" lab - an AgentOps in Production workshop using Intel Gaudi accelerated LLMs.

### Directory Structure

```
agd_v2/agentops-intel/
├── common.yaml              # Main catalog item configuration
├── dev.yaml                 # Development environment overrides
├── description.adoc         # Catalog item description (user-facing)
├── info-message-template.adoc  # User provisioning message template
└── CLAUDE.md                # This file
```

### Key Files

**common.yaml**
- Main configuration for the catalog item
- Defines workloads, collections, cluster configuration
- **Critical variables:**
  - `llm_model: qwen3-14b` - LLM model for testing (will change to gpt-oss-120b-gaudi when Intel backend is available)
  - `ocp4_workload_showroom_content_git_repo` - Showroom content repository
  - `ocp4_workload_gitops_bootstrap_repo_url: https://github.com/rhpds/agentops-in-prod-automation` - GitOps automation
  - `ocp4_workload_gitops_bootstrap_repo_revision: intel-with-configurable-storage` - Branch with Intel optimizations + storage class fix
  - `ocp4_workload_gitops_bootstrap_helm_values.storageClassName: "ocs-external-storagecluster-ceph-rbd"` - Storage class for CNV clusters (use `gp3-csi` for AWS)
  - `asset_uuid` - Unique identifier for this catalog item
  - `tag: main` - Collection version tag

**dev.yaml**
- Development environment overrides
- Typically includes purpose and any dev-specific settings

**description.adoc**
- AsciiDoc format catalog description
- Shown to users in RHDP catalog
- Contains lab overview, modules, and support information

**info-message-template.adoc**
- Template for user provisioning success message
- Contains credentials and access URLs

### Architecture

**Component Structure:**
- Base: CNV cluster (`agd_v2/ocp-cluster-cnv-pools`)
- Workloads deployed in order:
  1. Authentication (Keycloak)
  2. OpenShift GitOps (ArgoCD)
  3. LiteLLM Virtual Keys
  4. GitOps Bootstrap (from `rhpds/agentops-in-prod-automation`)
  5. OCP Console Embed
  6. Showroom

**GitOps Application Stack:**
- Bootstrapped via ArgoCD from `rhpds/agentops-in-prod-automation`
- Deploys mortgage-ai multi-agent application
- Deploys observability stack (Grafana, MLflow)

**Showroom Content:**
- Source: `https://github.com/rhpds/agentops-intel`
- Contains lab modules and instructions
- Embedded OCP console, terminal, and various application UIs

### Common Development Tasks

**Validate YAML syntax:**
```bash
yamllint agd_v2/agentops-intel/common.yaml
```

**Check include file references:**
```bash
grep "#include" agd_v2/agentops-intel/common.yaml
```

**Test variable interpolation:**
```bash
# Variables use Jinja2 syntax: {{ variable_name }}
grep -o "{{ [^}]* }}" agd_v2/agentops-intel/common.yaml
```

**Update LLM model:**
Edit `common.yaml` line ~139:
```yaml
llm_model: gpt-oss-120b-gaudi
```
This propagates to:
- `ocp4_workload_litellm_virtual_keys_models`
- `ocp4_workload_gitops_bootstrap_helm_values.remotellm.id`

**Update Showroom content repository:**
Edit `common.yaml` line ~175:
```yaml
ocp4_workload_showroom_content_git_repo: https://github.com/rhpds/agentops-intel
ocp4_workload_showroom_content_git_repo_ref: main
```

**Commit changes:**
```bash
git add agd_v2/agentops-intel/
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat: update agentops-intel"
```

### AgnosticV Conventions

**Include files:**
- Located in `/includes/` at repository root
- Provide reusable configuration snippets
- Examples:
  - `/includes/agd-v2-mapping.yaml` - AgnosticD v2 role mappings
  - `/includes/catalog-icon-openshift.yaml` - OpenShift icon
  - `/includes/parameters/litellm_metadata.yaml` - LiteLLM tracking

**Variable precedence:**
1. Environment-specific files (dev.yaml, prod.yaml)
2. common.yaml
3. Include files
4. Defaults

**Workloads:**
- Ansible roles from collections
- Format: `namespace.collection.role_name`
- Deployed in order listed in `workloads:` array
- Removed in order listed in `remove_workloads:` array (during teardown)

**Component structure:**
- Listed in `__meta__.components`
- Each component is a separate catalog item
- Provision data propagated via `propagate_provision_data`

### Related Repositories

- **GitOps automation:** `rhpds/agentops-in-prod-automation` - ArgoCD bootstrap manifests
- **Showroom content:** `rhpds/agentops-intel` - Lab instructions and modules
- **Core workloads:** `rhpds/core_workloads` - Reusable OpenShift workload roles
- **AI workloads:** `rhpds/ai_workloads` - AI-specific workload roles
- **Showroom collection:** `rhpds/showroom` - Showroom deployment role

### Troubleshooting

**Common issues:**

1. **YAML syntax errors** - Use `yamllint` to validate
2. **Include file not found** - Check path is relative to repo root
3. **Variable not defined** - Check variable is set in common.yaml or includes
4. **Workload deployment fails** - Check collection version compatibility
5. **Showroom content not loading** - Verify GitHub repo exists and is accessible

**Debugging workflow:**

1. Check YAML syntax
2. Verify all `#include` references exist
3. Validate variable interpolation
4. Check collection versions in `requirements_content`
5. Review workload order and dependencies
6. Test with `dev.yaml` environment first

### Testing

**Pre-deployment validation:**
```bash
# Syntax check
yamllint agd_v2/agentops-intel/*.yaml

# Include validation
for file in $(grep -h "#include" agd_v2/agentops-intel/*.yaml | awk '{print $2}'); do
  [ -f "$file" ] && echo "✓ $file" || echo "✗ $file MISSING"
done
```

**Post-deployment validation:**
- Verify catalog item appears in RHDP
- Provision on dev environment
- Check all workloads deployed successfully
- Verify Showroom content loads
- Test all Showroom tabs (Console, Terminal, MLflow, etc.)

### Future Enhancements

When this catalog item is stable:

1. **Create prod.yaml:**
   - Pin collection versions (replace `tag: main` with specific tags)
   - Pin Showroom content ref to release tag
   - Pin GitOps bootstrap revision

2. **Create event.yaml** (if needed for specific events)

3. **Version management:**
   - Create release tags in `rhpds/agentops-intel` showroom repo
   - Pin `ocp4_workload_showroom_content_git_repo_ref` to specific tag

### Support

For issues with this catalog item:
- Open RHDP support ticket: https://red.ht/rhdp-ticket
- Slack: #forum-demo-redhat-com
- Maintainer: Tony Kay (ankay@redhat.com)
