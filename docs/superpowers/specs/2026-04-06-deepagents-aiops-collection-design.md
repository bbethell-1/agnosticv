# deepagents-aiops Ansible Collection: RHEL VM Roles

**Date:** 2026-04-06
**Author:** Tony Kay
**Status:** Draft

## Summary

A minimal Ansible collection (`deepagents_aiops`) providing two roles to
deploy a RHEL VM on OpenShift Virtualization (KubeVirt). Replaces the
hummingbird collection for lb2645, removing the GitOps dependency and
all lb2865-specific workloads (RHTAS, Builds, Quay integration).

The VM is a simple Ansible target — SSH-accessible from within the
cluster (Showroom terminal, AAP2 controller).

## Collection Structure

```
deepagents_aiops/
  galaxy.yml
  roles/
    ocp4_workload_rhel_vm_infra/
      defaults/main.yml
      tasks/
        main.yml
        workload.yml
        remove_workload.yml
      templates/
        secret-s3.yaml.j2
        datavolume.yaml.j2
        datasource.yaml.j2
    ocp4_workload_rhel_vm_tenant/
      defaults/main.yml
      tasks/
        main.yml
        workload.yml
        remove_workload.yml
      templates/
        vm.yaml.j2
        cloudinit-userdata.yaml.j2
        service-ssh.yaml.j2
```

## Role: ocp4_workload_rhel_vm_infra

Downloads a RHEL qcow2 image and creates a DataVolume + DataSource in
`openshift-virtualization-os-images`. No GitOps/ArgoCD dependency.

### Tasks (workload.yml)

1. **Assert OpenShift Virtualization is installed** — check for
   HyperConverged CRD.
2. **Create S3 credentials secret** (conditional) — only when S3
   credentials are provided. Uses `no_log: true`.
3. **Create DataVolume** — downloads qcow2 image via HTTP or S3.
   Explicitly sets storage class to `-immediate` variant.
4. **Wait for DataVolume to reach Succeeded** — poll with configurable
   retries/delay.
5. **Create DataSource** — references the populated PVC.

### Default Variables

```yaml
# Image source
ocp4_workload_rhel_vm_infra_datavolume_source: ""
ocp4_workload_rhel_vm_infra_datavolume_name: rhel-base
ocp4_workload_rhel_vm_infra_datavolume_namespace: openshift-virtualization-os-images
ocp4_workload_rhel_vm_infra_datavolume_size: 10Gi
ocp4_workload_rhel_vm_infra_datavolume_storage_class: ocs-external-storagecluster-ceph-rbd-immediate

# S3 credentials (optional — omit for plain HTTP source)
ocp4_workload_rhel_vm_infra_datavolume_s3_access_key_id: ""
ocp4_workload_rhel_vm_infra_datavolume_s3_secret_access_key: ""

# Retry configuration
ocp4_workload_rhel_vm_infra_datavolume_retries: 60
ocp4_workload_rhel_vm_infra_datavolume_retry_delay: 10
```

### Templates

**secret-s3.yaml.j2** — Opaque secret with S3 `accessKeyId` and
`secretKey`. Only created when credentials are provided.

**datavolume.yaml.j2** — CDI DataVolume. Source is S3 when credentials
exist, otherwise HTTP. Explicitly sets `storageClassName` to avoid
falling back to the cluster default `WaitForFirstConsumer` class (which
causes the volume binding deadlock we hit).

**datasource.yaml.j2** — CDI DataSource referencing the DataVolume PVC.

## Role: ocp4_workload_rhel_vm_tenant

Creates a per-tenant RHEL VM with an SSH ClusterIP service. Exposes
connection details via `agnosticd_user_info`.

### Tasks (workload.yml)

1. **Create VM** — from DataSource clone, with cloud-init user setup.
2. **Create SSH service** — ClusterIP service on port 22.
3. **Wait for VM to be Ready** — poll VMI status with configurable
   retries/delay.
4. **Save user info** — register VM hostname, user, and password in
   `agnosticd_user_info`.

### Default Variables

```yaml
# VM configuration
ocp4_workload_rhel_vm_tenant_vm_name: rhel
ocp4_workload_rhel_vm_tenant_vm_namespace: "{{ ocp4_workload_username }}-rhel"
ocp4_workload_rhel_vm_tenant_vm_disksize: 10Gi
ocp4_workload_rhel_vm_tenant_vm_instancetype: u1.medium
ocp4_workload_rhel_vm_tenant_vm_preference: rhel.10

# DataSource reference (must match infra role output)
ocp4_workload_rhel_vm_tenant_vm_datasource_name: rhel-base
ocp4_workload_rhel_vm_tenant_vm_datasource_namespace: openshift-virtualization-os-images

# Storage class for the clone PVC (must use Immediate binding)
ocp4_workload_rhel_vm_tenant_vm_storage_class: ocs-external-storagecluster-ceph-rbd-immediate

# VM user
ocp4_workload_rhel_vm_tenant_vm_user: rhel
ocp4_workload_rhel_vm_tenant_vm_password: "{{ ocp4_workload_user_password | default(common_password) }}"
ocp4_workload_rhel_vm_tenant_vm_ssh_pwauth: true

# Cloud-init (optional)
ocp4_workload_rhel_vm_tenant_vm_init_script_url: ""

# Retry configuration
ocp4_workload_rhel_vm_tenant_vm_ready_retries: 60
ocp4_workload_rhel_vm_tenant_vm_ready_retry_delay: 10
```

### Templates

**vm.yaml.j2** — KubeVirt VirtualMachine. Uses `instancetype` and
`preference` (not inline resource specs). DataVolumeTemplate clones from
the DataSource. Cloud-init from `cloudinit-userdata.yaml.j2`. Explicitly
sets `storageClassName` on the DataVolumeTemplate to avoid the
`WaitForFirstConsumer` deadlock.

**cloudinit-userdata.yaml.j2** — Cloud-init userdata. Creates the VM
user with sudo, enables SSH password auth. Optionally runs an init
script URL if provided.

**service-ssh.yaml.j2** — ClusterIP service targeting port 22 on the
VM. Service name: `{{ ocp4_workload_rhel_vm_tenant_vm_name }}-ssh`.

### agnosticd_user_info Output

```yaml
rhel_vm_name: "{{ ocp4_workload_rhel_vm_tenant_vm_name }}"
rhel_vm_user: "{{ ocp4_workload_rhel_vm_tenant_vm_user }}"
rhel_vm_password: "{{ ocp4_workload_rhel_vm_tenant_vm_password }}"
rhel_vm_hostname: "{{ ocp4_workload_rhel_vm_tenant_vm_name }}-ssh.{{ ocp4_workload_rhel_vm_tenant_vm_namespace }}.svc.cluster.local"
```

This gives the showroom and AAP2 controller a DNS name to SSH to:
```
ssh rhel@rhel-ssh.user-GUID-rhel.svc.cluster.local
```

## What was dropped from hummingbird

| Hummingbird component | Disposition |
|---|---|
| GitOps/ArgoCD dependency | Removed — infra asserts OCP Virt, not ArgoCD |
| RHTAS ArgoCD application | Removed |
| Keycloak-RHTAS ArgoCD app | Removed |
| ClusterRole for Builds | Removed |
| ClusterRoleBinding for Builds | Removed |
| HTTP service (port 8080) | Replaced with SSH service (port 22) |
| OpenShift Route (edge TLS) | Removed — no HTTP exposure needed |
| 30Gi disk | Reduced to 10Gi |
| Satellite registration | Removed — not needed for basic Ansible target |

## Changes to lb2645 CIs

### Cluster CI

- Replace `hummingbird` collection with `deepagents_aiops`
- Replace `ocp4_workload_hummingbird_infra` with
  `ocp4_workload_rhel_vm_infra`
- Remove `ocp4_workload_openshift_gitops` (no longer required by VM
  infra — evaluate if needed for other purposes)
- Set `ocp4_workload_rhel_vm_infra_datavolume_source` to the S3 image
  URL
- Set vault-encrypted S3 credentials

### Tenant CI

- Replace `hummingbird` collection with `deepagents_aiops`
- Replace `ocp4_workload_hummingbird_tenant` with
  `ocp4_workload_rhel_vm_tenant`
- Update variable names from `ocp4_workload_hummingbird_tenant_*` to
  `ocp4_workload_rhel_vm_tenant_*`
- Set disk size to 10Gi

## Ansible Coding Standards

All code follows these rules:
- `register:` variables prefixed `r_` (e.g., `r_hyperconverged`)
- `when:` placed after `name:`, before module/block
- All `retries:`, `delay:` values are role variables with defaults
- All loops use `loop_control:` with `loop_var:`
- Fully qualified collection names for all modules
- Role variable prefix: `ocp4_workload_rhel_vm_infra_` / `ocp4_workload_rhel_vm_tenant_`
