# AgentOps Intel Catalog Item Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `agd_v2/agentops-intel/` catalog item for AgentOps in Production lab with Intel Gaudi acceleration

**Architecture:** Clone Summit 2026 AgentOps catalog item, update metadata/branding, switch LLM model to Intel Gaudi, fork Showroom content repository

**Tech Stack:** AgnosticV/AgnosticD, YAML, GitHub API, Python (for UUID generation)

## Global Constraints

- Source directory: `summit-2026/lb2144-agentops-ocp-cnv/`
- Target directory: `agd_v2/agentops-intel/`
- Only create `common.yaml`, `dev.yaml`, `description.adoc`, `info-message-template.adoc`, and `CLAUDE.md`
- Do NOT create `prod.yaml` or `event.yaml` (development catalog item only)
- LLM model must be: `gpt-oss-120b-gaudi`
- Showroom repo must be: `https://github.com/rhpds/agentops-intel`
- All commits must bypass pre-commit: `PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit`

---

### Task 1: Create Directory Structure and Copy Base Files

**Files:**
- Create: `agd_v2/agentops-intel/` (directory)
- Copy: `summit-2026/lb2144-agentops-ocp-cnv/common.yaml` → `agd_v2/agentops-intel/common.yaml`
- Copy: `summit-2026/lb2144-agentops-ocp-cnv/dev.yaml` → `agd_v2/agentops-intel/dev.yaml`
- Copy: `summit-2026/lb2144-agentops-ocp-cnv/description.adoc` → `agd_v2/agentops-intel/description.adoc`
- Copy: `summit-2026/lb2144-agentops-ocp-cnv/info-message-template.adoc` → `agd_v2/agentops-intel/info-message-template.adoc`

**Interfaces:**
- Consumes: Source files in `summit-2026/lb2144-agentops-ocp-cnv/`
- Produces: Base directory `agd_v2/agentops-intel/` with copied files

- [ ] **Step 1: Create target directory**

```bash
mkdir -p agd_v2/agentops-intel
```

Expected: Directory created

- [ ] **Step 2: Copy common.yaml**

```bash
cp summit-2026/lb2144-agentops-ocp-cnv/common.yaml agd_v2/agentops-intel/common.yaml
```

Expected: File copied

- [ ] **Step 3: Copy dev.yaml**

```bash
cp summit-2026/lb2144-agentops-ocp-cnv/dev.yaml agd_v2/agentops-intel/dev.yaml
```

Expected: File copied

- [ ] **Step 4: Copy description.adoc**

```bash
cp summit-2026/lb2144-agentops-ocp-cnv/description.adoc agd_v2/agentops-intel/description.adoc
```

Expected: File copied

- [ ] **Step 5: Copy info-message-template.adoc**

```bash
cp summit-2026/lb2144-agentops-ocp-cnv/info-message-template.adoc agd_v2/agentops-intel/info-message-template.adoc
```

Expected: File copied

- [ ] **Step 6: Verify files copied**

```bash
ls -la agd_v2/agentops-intel/
```

Expected output:
```
common.yaml
description.adoc
dev.yaml
info-message-template.adoc
```

- [ ] **Step 7: Commit base directory**

```bash
git add agd_v2/agentops-intel/
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat: create agentops-intel catalog item base"
```

Expected: Commit created

---

### Task 2: Update common.yaml Metadata and Identity

**Files:**
- Modify: `agd_v2/agentops-intel/common.yaml:1-296`

**Interfaces:**
- Consumes: Copied `common.yaml` from Task 1
- Produces: Updated `common.yaml` with new UUID, display name, keywords, and removed Summit-specific elements

- [ ] **Step 1: Generate new UUID**

```bash
python3 -c "import uuid; print(uuid.uuid4())"
```

Expected: New UUID printed (example: `a1b2c3d4-e5f6-7890-abcd-ef1234567890`)
Save this UUID for next step.

- [ ] **Step 2: Update asset_uuid in common.yaml**

Edit `agd_v2/agentops-intel/common.yaml`, find line with `asset_uuid:` (around line 220) and replace the UUID:

```yaml
__meta__:
  asset_uuid: <NEW_UUID_FROM_STEP_1>
```

- [ ] **Step 3: Update display_name**

Edit `agd_v2/agentops-intel/common.yaml`, find `display_name:` (around line 231) and update:

```yaml
catalog:
  display_name: "AgentOps Intel"
```

- [ ] **Step 4: Remove Summit-specific labels**

Edit `agd_v2/agentops-intel/common.yaml`, find the `labels:` section (around line 239) and remove the `Brand_Event` line:

```yaml
labels:
  Provider: RHDP
```

(Delete the `Brand_Event: Red_Hat_Summit_2026` line)

- [ ] **Step 5: Update keywords**

Edit `agd_v2/agentops-intel/common.yaml`, find `keywords:` (around line 234) and replace:

```yaml
keywords:
- agentops
- intel
- gaudi
- openshift-ai
- llama-stack
```

- [ ] **Step 6: Remove hardcoded email and catalog_item_name**

Edit `agd_v2/agentops-intel/common.yaml`, find and delete lines 22-23:

```yaml
### Hardcoded litellm metadata for summit
requester_email: summit-{{guid}}@demo.redhat.com
catalog_item_name: summit-2026.lb2144-agentops-ocp-cnv.event
```

(Delete these two lines completely, including the comment line 21)

- [ ] **Step 7: Verify changes**

```bash
grep -n "asset_uuid" agd_v2/agentops-intel/common.yaml
grep -n "display_name" agd_v2/agentops-intel/common.yaml
grep -n "summit" agd_v2/agentops-intel/common.yaml
```

Expected: New UUID shown, display_name is "AgentOps Intel", no "summit" references found

- [ ] **Step 8: Commit metadata updates**

```bash
git add agd_v2/agentops-intel/common.yaml
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat: update agentops-intel metadata and remove Summit branding"
```

Expected: Commit created

---

### Task 3: Update LLM Model to Intel Gaudi

**Files:**
- Modify: `agd_v2/agentops-intel/common.yaml:139`

**Interfaces:**
- Consumes: Updated `common.yaml` from Task 2
- Produces: `common.yaml` with `llm_model: gpt-oss-120b-gaudi`

- [ ] **Step 1: Update llm_model variable**

Edit `agd_v2/agentops-intel/common.yaml`, find line 139 with `llm_model:` and update:

```yaml
llm_model: gpt-oss-120b-gaudi
```

- [ ] **Step 2: Verify the change propagates**

```bash
grep -n "llm_model" agd_v2/agentops-intel/common.yaml
```

Expected output showing line 139:
```
139:llm_model: gpt-oss-120b-gaudi
141:ocp4_workload_litellm_virtual_keys_models:
142:- "{{ llm_model }}"
```

Also verify in the GitOps bootstrap section (around line 160):
```
160:    id: "{{ llm_model }}"
```

- [ ] **Step 3: Commit LLM model change**

```bash
git add agd_v2/agentops-intel/common.yaml
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat: switch to Intel Gaudi LLM model (gpt-oss-120b-gaudi)"
```

Expected: Commit created

---

### Task 4: Fork Showroom Repository on GitHub

**Files:**
- External: GitHub repository fork

**Interfaces:**
- Consumes: GitHub API, source repo `rhpds/agentops-in-prod-showroom`
- Produces: Forked repository `rhpds/agentops-intel`

- [ ] **Step 1: Check if gh CLI is available**

```bash
which gh
```

Expected: Path to gh binary (e.g., `/usr/local/bin/gh`)
If not found, user must install GitHub CLI first.

- [ ] **Step 2: Verify GitHub authentication**

```bash
gh auth status
```

Expected: Shows authenticated to github.com

- [ ] **Step 3: Fork the repository**

```bash
gh repo fork rhpds/agentops-in-prod-showroom --fork-name agentops-intel --org rhpds --clone=false
```

Expected output:
```
✓ Created fork rhpds/agentops-intel
```

**Note:** This requires permissions to create repos in the `rhpds` organization. User must approve or manually create the fork.

- [ ] **Step 4: Verify fork exists**

```bash
gh repo view rhpds/agentops-intel
```

Expected: Repository information displayed

- [ ] **Step 5: Document fork creation**

Create a note file:

```bash
echo "Showroom repository forked: rhpds/agentops-intel from rhpds/agentops-in-prod-showroom on $(date)" > agd_v2/agentops-intel/.fork-created
```

- [ ] **Step 6: Commit fork documentation**

```bash
git add agd_v2/agentops-intel/.fork-created
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "docs: record Showroom repository fork creation"
```

Expected: Commit created

---

### Task 5: Update Showroom Repository Reference

**Files:**
- Modify: `agd_v2/agentops-intel/common.yaml:175`

**Interfaces:**
- Consumes: Updated `common.yaml` from Task 3, forked repo from Task 4
- Produces: `common.yaml` pointing to `rhpds/agentops-intel`

- [ ] **Step 1: Update showroom content repo URL**

Edit `agd_v2/agentops-intel/common.yaml`, find line 175 with `ocp4_workload_showroom_content_git_repo:` and update:

```yaml
ocp4_workload_showroom_content_git_repo: https://github.com/rhpds/agentops-intel
```

- [ ] **Step 2: Verify the reference**

```bash
grep -n "ocp4_workload_showroom_content_git_repo" agd_v2/agentops-intel/common.yaml
```

Expected output:
```
175:ocp4_workload_showroom_content_git_repo: https://github.com/rhpds/agentops-intel
```

- [ ] **Step 3: Verify branch reference is still main**

```bash
grep -A1 "ocp4_workload_showroom_content_git_repo" agd_v2/agentops-intel/common.yaml
```

Expected output:
```
ocp4_workload_showroom_content_git_repo: https://github.com/rhpds/agentops-intel
ocp4_workload_showroom_content_git_repo_ref: main
```

- [ ] **Step 4: Commit showroom repo update**

```bash
git add agd_v2/agentops-intel/common.yaml
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "feat: update Showroom content repository to agentops-intel"
```

Expected: Commit created

---

### Task 6: Update description.adoc

**Files:**
- Modify: `agd_v2/agentops-intel/description.adoc:1-52`

**Interfaces:**
- Consumes: Copied `description.adoc` from Task 1
- Produces: Updated `description.adoc` without Summit disclaimers

- [ ] **Step 1: Remove developer warning**

Edit `agd_v2/agentops-intel/description.adoc`, delete lines 1-5:

```adoc
[WARNING]
====
Do not order this item unless you are a developer working on the CI.
Order the parent CI instead: link:https://catalog.demo.redhat.com/catalog?item=babylon-catalog-prod%2Fpublished.agentops-ocp.prod[AgentOps in Production^].
====
```

(Delete this entire WARNING block)

- [ ] **Step 2: Remove Summit disclaimer**

Edit `agd_v2/agentops-intel/description.adoc`, delete lines 11-14 (after previous deletion, these will be around line 6-9):

```adoc
[IMPORTANT]
====
This Red Hat Summit 2026 lab is being released as-is with little change from the version delivered in person at the event. There is limited support for these labs and only those with regular usage will be retained in the RHDP catalog. A 30 day advance notice will be posted for any labs that get scheduled for removal.
====
```

(Delete this entire IMPORTANT block)

- [ ] **Step 3: Verify remaining content**

```bash
head -20 agd_v2/agentops-intel/description.adoc
```

Expected: Should start with:
```
In this workshop, you take on the role of a senior engineer at a mortgage lending company...
```

- [ ] **Step 4: Commit description updates**

```bash
git add agd_v2/agentops-intel/description.adoc
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "docs: remove Summit-specific disclaimers from description"
```

Expected: Commit created

---

### Task 7: Create CLAUDE.md

**Files:**
- Create: `agd_v2/agentops-intel/CLAUDE.md`

**Interfaces:**
- Consumes: Completed catalog item structure from previous tasks
- Produces: `CLAUDE.md` file with development guidance

- [ ] **Step 1: Create CLAUDE.md**

Create file `agd_v2/agentops-intel/CLAUDE.md`:

```markdown
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
  - `llm_model: gpt-oss-120b-gaudi` - Intel Gaudi accelerated model
  - `ocp4_workload_showroom_content_git_repo: https://github.com/rhpds/agentops-intel` - Showroom content
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
```

- [ ] **Step 2: Verify CLAUDE.md created**

```bash
ls -la agd_v2/agentops-intel/CLAUDE.md
```

Expected: File exists

- [ ] **Step 3: Commit CLAUDE.md**

```bash
git add agd_v2/agentops-intel/CLAUDE.md
PRE_COMMIT_ALLOW_NO_CONFIG=1 git commit -m "docs: add CLAUDE.md development guidance"
```

Expected: Commit created

---

### Task 8: Validate Configuration and Create Draft PR

**Files:**
- Verify: All files in `agd_v2/agentops-intel/`
- Create: Draft pull request

**Interfaces:**
- Consumes: All files from previous tasks
- Produces: Draft PR on GitHub

- [ ] **Step 1: Validate YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('agd_v2/agentops-intel/common.yaml'))"
```

Expected: No output (valid YAML)

- [ ] **Step 2: Verify critical variables**

```bash
grep "llm_model: gpt-oss-120b-gaudi" agd_v2/agentops-intel/common.yaml
grep "agentops-intel" agd_v2/agentops-intel/common.yaml
grep "AgentOps Intel" agd_v2/agentops-intel/common.yaml
```

Expected: All three patterns found

- [ ] **Step 3: Verify no Summit references remain**

```bash
grep -i "summit" agd_v2/agentops-intel/common.yaml agd_v2/agentops-intel/description.adoc
```

Expected: No matches (exit code 1)

- [ ] **Step 4: List all files**

```bash
ls -la agd_v2/agentops-intel/
```

Expected files:
```
CLAUDE.md
common.yaml
description.adoc
dev.yaml
info-message-template.adoc
```

- [ ] **Step 5: Check git status**

```bash
git status
```

Expected: All files committed, working directory clean

- [ ] **Step 6: Push branch to remote**

```bash
git push -u origin ci/agentops-intel
```

Expected: Branch pushed to remote

- [ ] **Step 7: Create draft pull request**

```bash
gh pr create \
  --draft \
  --title "[WIP] AgentOps Intel catalog item" \
  --body "## Summary

Creates new AgentOps Intel catalog item in agd_v2/ based on Summit 2026 AgentOps lab.

## Changes

- Create agd_v2/agentops-intel/ catalog item
- Update metadata: new UUID, display name \"AgentOps Intel\"
- Remove Summit-specific branding and disclaimers
- Switch LLM model to gpt-oss-120b-gaudi (Intel Gaudi)
- Fork Showroom content to rhpds/agentops-intel
- Update Showroom repository reference
- Add CLAUDE.md development guidance

## Files

- agd_v2/agentops-intel/common.yaml
- agd_v2/agentops-intel/dev.yaml
- agd_v2/agentops-intel/description.adoc
- agd_v2/agentops-intel/info-message-template.adoc
- agd_v2/agentops-intel/CLAUDE.md

## Testing

- [ ] YAML syntax validated
- [ ] Include file references validated
- [ ] Variable interpolation checked
- [ ] Provision test on dev environment
- [ ] Showroom content loads from new repository

## References

- Design spec: docs/superpowers/specs/2026-07-20-agentops-intel-design.md
- Source: summit-2026/lb2144-agentops-ocp-cnv/
- Showroom fork: https://github.com/rhpds/agentops-intel
- GitOps automation: https://github.com/rhpds/agentops-in-prod-automation"
```

Expected: Draft PR created, URL returned

- [ ] **Step 8: Verify PR created**

```bash
gh pr view
```

Expected: PR details displayed, shows [WIP] prefix and draft status

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Task 1: Copy directory structure (spec section: File Structure)
- ✅ Task 2: Update metadata and identity (spec section: Identity & Metadata, Email & Tracking)
- ✅ Task 3: Update LLM model (spec section: LLM Model Configuration)
- ✅ Task 4: Fork Showroom repository (spec section: Showroom Content Repository)
- ✅ Task 5: Update Showroom reference (spec section: Showroom Content Repository)
- ✅ Task 6: Update description (spec section: Description Updates)
- ✅ Task 7: Create CLAUDE.md (spec section: Implementation Notes)
- ✅ Task 8: Validate and create PR (spec section: Testing Strategy, Implementation Notes)

**No placeholders:** All code, commands, and file paths are concrete and complete.

**Type consistency:** Variable names and file paths consistent across all tasks.

**All spec requirements covered:** No gaps identified.
