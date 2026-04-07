# LB2645: Move AAP2 Workload from Tenant to Cluster

**Date:** 2026-04-03
**Author:** Tony Kay
**Status:** Approved

## Summary

Move the AAP2 (Ansible Automation Platform) workload from the tenant CI
(`summit-2026/lb2645-agentic-devops-tenant`) to the cluster CI
(`summit-2026/lb2645-agentic-devops-cluster`) so that AAP2 is installed
cluster-wide rather than per-tenant. The AAP Console tab remains in
Showroom. A future change will add per-tenant AAP2 user setup.

## Motivation

AAP2 is a cluster-scoped service — installing it per-tenant is
unnecessary overhead. Moving it to the cluster CI makes the deployment
model cleaner and sets up a future feature where tenants are onboarded as
users on the shared AAP2 instance.

## Changes

### Cluster CI (`lb2645-agentic-devops-cluster/common.yaml`)

1. **Update `core_workloads` collection version** from `{{ tag }}` to
   `aap2-scalars-to-vars`. Add a TODO comment to revert to `{{ tag }}`
   once the branch is merged to main.

2. **Add AAP2 workload** to the workloads list:
   `agnosticd.core_workloads.ocp4_workload_ansible_automation_platform`

3. **Add AAP2 configuration variables** (moved from tenant):
   - `ocp4_workload_ansible_automation_platform_admin_password`
   - `ocp4_workload_ansible_automation_platform_disable_controller: false`
   - `ocp4_workload_ansible_automation_platform_disable_eda: true`
   - `ocp4_workload_ansible_automation_platform_disable_hub: true`
   - `ocp4_workload_ansible_automation_platform_disable_lightspeed: true`
   - `ocp4_workload_ansible_automation_platform_inject_manifest: true`
   - `ocp4_workload_ansible_automation_platform_manifest` (CloudFront URL)
   - `ocp4_workload_ansible_automation_platform_create_eda_rolebinding: true`
   - `ocp4_workload_ansible_automation_platform_operator_channel: stable-2.6`
   - `ocp4_workload_ansible_automation_platform_catalog_snapshot_image_tag`
   - `ocp4_workload_ansible_automation_platform_ocp_cluster_role: cluster-reader`
   - `ocp4_workload_ansible_automation_platform_hub_file_storage_file_class`
   - `ocp4_workload_ansible_automation_platform_hub_file_storage_access_mode`

   The admin password will use `common_admin_password` (the cluster's
   existing password variable) instead of the tenant's `common_password`.

### Tenant CI (`lb2645-agentic-devops-tenant/common.yaml`)

1. **Remove AAP2 workload** from the workloads list.

2. **Remove all `ocp4_workload_ansible_automation_platform_*` variables**
   (the entire configuration block).

3. **Remove `core_workloads` collection** from `requirements_content` —
   no remaining tenant workloads depend on it.

### No changes

- Showroom config: the AAP tab (`https://aap-aap.{{ domain }}`) stays as-is
  since the cluster-wide AAP2 serves the same route.
- Tenant namespace, Keycloak, Gitea user, LiteLLM — all untouched.
- Cluster worker sizing, OpenShift AI, auth, Gitea operator — untouched.

## Future work

- Add per-tenant AAP2 user provisioning (tenant workload that creates a
  user on the cluster-wide AAP2 instance).
