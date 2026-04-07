# LB2645: Add RHEL VM to Tenant

**Date:** 2026-04-06
**Author:** Tony Kay
**Status:** Approved

## Summary

Add a per-tenant RHEL VM to the LB2645 Agentic DevOps lab using the
hummingbird workloads from lb2865. The VM serves as a simple Ansible
target for basic tasks (ping, add user) — not deep work.

## Changes

### Cluster CI (`lb2645-agentic-devops-cluster/common.yaml`)

1. **Add `hummingbird` collection** to `requirements_content`.
2. **Add `ocp4_workload_openshift_virtualization`** workload and config
   (operator channel `stable`, no catalog snapshot).
3. **Add `ocp4_workload_hummingbird_infra`** workload with S3 DataVolume
   source URL and vault-encrypted credentials (copied from lb2865).

### Tenant CI (`lb2645-agentic-devops-tenant/common.yaml`)

1. **Add `hummingbird` collection** to `requirements_content`.
2. **Add `rhel` namespace suffix** to
   `ocp4_workload_tenant_namespace_suffixes`.
3. **Add `ocp4_workload_hummingbird_tenant`** workload (after gitea user,
   before showroom).
4. **Add VM config**: datasource `hummingbird` from
   `openshift-virtualization-os-images`, instancetype `u1.medium`, 30Gi
   disk, init script from hummingbird-showroom, VM user `rhel` with
   `common_password`.

### No changes

- AAP2, Gitea, LiteLLM, Showroom config, and all other workloads are
  untouched.
