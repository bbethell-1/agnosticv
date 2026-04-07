# deepagents-aiops Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a minimal Ansible collection with two roles that deploy a RHEL VM on OpenShift Virtualization, replacing hummingbird in lb2645.

**Architecture:** Two roles — `ocp4_workload_rhel_vm_infra` (cluster-level: downloads image, creates DataVolume/DataSource) and `ocp4_workload_rhel_vm_tenant` (tenant-level: creates VM, SSH service, exposes connection info). No GitOps dependency. Explicit `-immediate` storage class everywhere to avoid `WaitForFirstConsumer` deadlocks.

**Tech Stack:** Ansible, Jinja2 templates, KubeVirt/CDI APIs, `kubernetes.core` collection

**Spec:** `docs/superpowers/specs/2026-04-06-deepagents-aiops-collection-design.md`

**Ansible Standards:** Use the `ansible-best-practices` skill. Key rules: `r_` register prefix, `when:` at top, retries as role vars, `loop_control` on all loops, FQCN everywhere.

---

## Pre-requisites

The collection will live in a new GitHub repo. Before starting, you need:
- A GitHub repo created (e.g., `rhpds/deepagents-aiops` or similar)
- The repo cloned locally

All paths below are relative to the collection repo root.

---

## File Map

| File | Responsibility |
|---|---|
| `galaxy.yml` | Collection metadata, dependencies |
| `roles/ocp4_workload_rhel_vm_infra/defaults/main.yml` | Infra role default variables |
| `roles/ocp4_workload_rhel_vm_infra/tasks/main.yml` | Standard AgnosticD dispatcher |
| `roles/ocp4_workload_rhel_vm_infra/tasks/workload.yml` | Provision: assert OCP Virt, create DV/DS |
| `roles/ocp4_workload_rhel_vm_infra/tasks/remove_workload.yml` | Destroy: remove DataSource, DataVolume, secret |
| `roles/ocp4_workload_rhel_vm_infra/templates/secret-s3.yaml.j2` | S3 credentials secret |
| `roles/ocp4_workload_rhel_vm_infra/templates/datavolume.yaml.j2` | CDI DataVolume (HTTP or S3 source) |
| `roles/ocp4_workload_rhel_vm_infra/templates/datasource.yaml.j2` | CDI DataSource |
| `roles/ocp4_workload_rhel_vm_tenant/defaults/main.yml` | Tenant role default variables |
| `roles/ocp4_workload_rhel_vm_tenant/tasks/main.yml` | Standard AgnosticD dispatcher |
| `roles/ocp4_workload_rhel_vm_tenant/tasks/workload.yml` | Provision: create VM, SSH svc, save user_info |
| `roles/ocp4_workload_rhel_vm_tenant/tasks/remove_workload.yml` | Destroy: delete VM, service, namespace cleanup |
| `roles/ocp4_workload_rhel_vm_tenant/templates/vm.yaml.j2` | KubeVirt VirtualMachine manifest |
| `roles/ocp4_workload_rhel_vm_tenant/templates/cloudinit-userdata.yaml.j2` | Cloud-init user config |
| `roles/ocp4_workload_rhel_vm_tenant/templates/service-ssh.yaml.j2` | ClusterIP SSH service |

---

## Task 1: Collection scaffold and galaxy.yml

**Files:**
- Create: `galaxy.yml`

- [ ] **Step 1: Create galaxy.yml**

```yaml
---
namespace: rhpds
name: deepagents_aiops
version: 0.1.0
readme: README.md

authors:
  - Tony Kay <ankay@redhat.com>

description: >-
  Ansible workloads for the Deep Agents AIOps lab.
  Provides RHEL VM provisioning on OpenShift Virtualization.

license:
  - GPL-2.0-or-later

tags:
  - cloud
  - openshift
  - kubevirt

dependencies:
  kubernetes.core: ">=2.4.0"

repository: https://github.com/rhpds/deepagents-aiops
documentation: https://github.com/rhpds/deepagents-aiops
homepage: https://github.com/rhpds/deepagents-aiops
issues: https://github.com/rhpds/deepagents-aiops/issues

build_ignore: []
```

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p roles/ocp4_workload_rhel_vm_infra/{defaults,tasks,templates}
mkdir -p roles/ocp4_workload_rhel_vm_tenant/{defaults,tasks,templates}
```

- [ ] **Step 3: Commit**

```bash
git add galaxy.yml roles/
git commit -m "feat: scaffold deepagents_aiops collection structure"
```

---

## Task 2: Infra role — defaults and dispatcher

**Files:**
- Create: `roles/ocp4_workload_rhel_vm_infra/defaults/main.yml`
- Create: `roles/ocp4_workload_rhel_vm_infra/tasks/main.yml`

- [ ] **Step 1: Create defaults/main.yml**

```yaml
---
# ===================================================================
# Role: ocp4_workload_rhel_vm_infra
# Downloads a RHEL qcow2 image and creates a DataVolume + DataSource
# in openshift-virtualization-os-images.
# ===================================================================

# Image source URL (HTTP or S3)
ocp4_workload_rhel_vm_infra_datavolume_source: ""

# DataVolume identity
ocp4_workload_rhel_vm_infra_datavolume_name: rhel-base
ocp4_workload_rhel_vm_infra_datavolume_namespace: openshift-virtualization-os-images
ocp4_workload_rhel_vm_infra_datavolume_size: 10Gi

# Storage class — must use Immediate binding to avoid WaitForFirstConsumer deadlock
ocp4_workload_rhel_vm_infra_datavolume_storage_class: ocs-external-storagecluster-ceph-rbd-immediate

# S3 credentials (optional — leave empty for plain HTTP source)
ocp4_workload_rhel_vm_infra_datavolume_s3_access_key_id: ""
ocp4_workload_rhel_vm_infra_datavolume_s3_secret_access_key: ""
ocp4_workload_rhel_vm_infra_s3_secret_name: "{{ ocp4_workload_rhel_vm_infra_datavolume_name }}-s3-credentials"

# Retry configuration for DataVolume readiness
ocp4_workload_rhel_vm_infra_datavolume_retries: 60
ocp4_workload_rhel_vm_infra_datavolume_retry_delay: 10
```

- [ ] **Step 2: Create tasks/main.yml**

```yaml
---
# --------------------------------------------------
# Do not modify this file
# --------------------------------------------------
- name: Running workload provision tasks
  when: ACTION == "provision"
  ansible.builtin.include_tasks: workload.yml

- name: Running workload removal tasks
  when: ACTION == "destroy"
  ansible.builtin.include_tasks: remove_workload.yml
```

- [ ] **Step 3: Commit**

```bash
git add roles/ocp4_workload_rhel_vm_infra/
git commit -m "feat: add infra role defaults and dispatcher"
```

---

## Task 3: Infra role — templates

**Files:**
- Create: `roles/ocp4_workload_rhel_vm_infra/templates/secret-s3.yaml.j2`
- Create: `roles/ocp4_workload_rhel_vm_infra/templates/datavolume.yaml.j2`
- Create: `roles/ocp4_workload_rhel_vm_infra/templates/datasource.yaml.j2`

- [ ] **Step 1: Create secret-s3.yaml.j2**

```yaml
---
apiVersion: v1
kind: Secret
metadata:
  name: {{ ocp4_workload_rhel_vm_infra_s3_secret_name }}
  namespace: {{ ocp4_workload_rhel_vm_infra_datavolume_namespace }}
type: Opaque
stringData:
  accessKeyId: {{ ocp4_workload_rhel_vm_infra_datavolume_s3_access_key_id }}
  secretKey: {{ ocp4_workload_rhel_vm_infra_datavolume_s3_secret_access_key }}
```

- [ ] **Step 2: Create datavolume.yaml.j2**

```yaml
---
apiVersion: cdi.kubevirt.io/v1beta1
kind: DataVolume
metadata:
  name: {{ ocp4_workload_rhel_vm_infra_datavolume_name }}
  namespace: {{ ocp4_workload_rhel_vm_infra_datavolume_namespace }}
spec:
  source:
{% if ocp4_workload_rhel_vm_infra_datavolume_s3_access_key_id | default('') | length > 0 %}
    s3:
      url: {{ ocp4_workload_rhel_vm_infra_datavolume_source }}
      secretRef: {{ ocp4_workload_rhel_vm_infra_s3_secret_name }}
{% else %}
    http:
      url: {{ ocp4_workload_rhel_vm_infra_datavolume_source }}
{% endif %}
  storage:
    storageClassName: {{ ocp4_workload_rhel_vm_infra_datavolume_storage_class }}
    resources:
      requests:
        storage: {{ ocp4_workload_rhel_vm_infra_datavolume_size }}
```

- [ ] **Step 3: Create datasource.yaml.j2**

```yaml
---
apiVersion: cdi.kubevirt.io/v1beta1
kind: DataSource
metadata:
  name: {{ ocp4_workload_rhel_vm_infra_datavolume_name }}
  namespace: {{ ocp4_workload_rhel_vm_infra_datavolume_namespace }}
spec:
  source:
    pvc:
      name: {{ ocp4_workload_rhel_vm_infra_datavolume_name }}
      namespace: {{ ocp4_workload_rhel_vm_infra_datavolume_namespace }}
```

- [ ] **Step 4: Commit**

```bash
git add roles/ocp4_workload_rhel_vm_infra/templates/
git commit -m "feat: add infra role templates (DataVolume, DataSource, S3 secret)"
```

---

## Task 4: Infra role — workload and remove tasks

**Files:**
- Create: `roles/ocp4_workload_rhel_vm_infra/tasks/workload.yml`
- Create: `roles/ocp4_workload_rhel_vm_infra/tasks/remove_workload.yml`

- [ ] **Step 1: Create workload.yml**

```yaml
---
- name: Assert OpenShift Virtualization is installed
  kubernetes.core.k8s_info:
    api_version: hco.kubevirt.io/v1beta1
    kind: HyperConverged
    namespace: openshift-cnv
  register: r_hyperconverged

- name: Fail if OpenShift Virtualization is not installed
  ansible.builtin.assert:
    that:
      - r_hyperconverged.resources | length > 0
    fail_msg: >-
      OpenShift Virtualization (HyperConverged) is not installed.
      Deploy ocp4_workload_openshift_virtualization on the cluster first.

- name: Create S3 credentials secret
  when: ocp4_workload_rhel_vm_infra_datavolume_s3_access_key_id | default('') | length > 0
  kubernetes.core.k8s:
    state: present
    definition: "{{ lookup('ansible.builtin.template', 'secret-s3.yaml.j2') | from_yaml }}"
  no_log: true

- name: Create DataVolume for RHEL base image
  kubernetes.core.k8s:
    state: present
    definition: "{{ lookup('ansible.builtin.template', 'datavolume.yaml.j2') | from_yaml }}"

- name: Wait for DataVolume to reach Succeeded phase
  kubernetes.core.k8s_info:
    api_version: cdi.kubevirt.io/v1beta1
    kind: DataVolume
    name: "{{ ocp4_workload_rhel_vm_infra_datavolume_name }}"
    namespace: "{{ ocp4_workload_rhel_vm_infra_datavolume_namespace }}"
  register: r_datavolume
  retries: "{{ ocp4_workload_rhel_vm_infra_datavolume_retries }}"
  delay: "{{ ocp4_workload_rhel_vm_infra_datavolume_retry_delay }}"
  until:
    - r_datavolume.resources | length > 0
    - r_datavolume.resources[0].status.phase is defined
    - r_datavolume.resources[0].status.phase == "Succeeded"

- name: Create DataSource referencing the base image PVC
  kubernetes.core.k8s:
    state: present
    definition: "{{ lookup('ansible.builtin.template', 'datasource.yaml.j2') | from_yaml }}"
```

- [ ] **Step 2: Create remove_workload.yml**

```yaml
---
- name: Remove DataSource
  kubernetes.core.k8s:
    state: absent
    api_version: cdi.kubevirt.io/v1beta1
    kind: DataSource
    name: "{{ ocp4_workload_rhel_vm_infra_datavolume_name }}"
    namespace: "{{ ocp4_workload_rhel_vm_infra_datavolume_namespace }}"

- name: Remove DataVolume
  kubernetes.core.k8s:
    state: absent
    api_version: cdi.kubevirt.io/v1beta1
    kind: DataVolume
    name: "{{ ocp4_workload_rhel_vm_infra_datavolume_name }}"
    namespace: "{{ ocp4_workload_rhel_vm_infra_datavolume_namespace }}"

- name: Remove S3 credentials secret
  when: ocp4_workload_rhel_vm_infra_datavolume_s3_access_key_id | default('') | length > 0
  kubernetes.core.k8s:
    state: absent
    api_version: v1
    kind: Secret
    name: "{{ ocp4_workload_rhel_vm_infra_s3_secret_name }}"
    namespace: "{{ ocp4_workload_rhel_vm_infra_datavolume_namespace }}"
```

- [ ] **Step 3: Commit**

```bash
git add roles/ocp4_workload_rhel_vm_infra/tasks/
git commit -m "feat: add infra role provision and destroy tasks"
```

---

## Task 5: Tenant role — defaults and dispatcher

**Files:**
- Create: `roles/ocp4_workload_rhel_vm_tenant/defaults/main.yml`
- Create: `roles/ocp4_workload_rhel_vm_tenant/tasks/main.yml`

- [ ] **Step 1: Create defaults/main.yml**

```yaml
---
# ===================================================================
# Role: ocp4_workload_rhel_vm_tenant
# Creates a per-tenant RHEL VM with SSH service.
# ===================================================================

# VM identity
ocp4_workload_rhel_vm_tenant_vm_name: rhel
ocp4_workload_rhel_vm_tenant_vm_namespace: "{{ ocp4_workload_username }}-rhel"
ocp4_workload_rhel_vm_tenant_vm_disksize: 10Gi
ocp4_workload_rhel_vm_tenant_vm_instancetype: u1.medium
ocp4_workload_rhel_vm_tenant_vm_preference: rhel.10

# DataSource reference (must match infra role output)
ocp4_workload_rhel_vm_tenant_vm_datasource_name: rhel-base
ocp4_workload_rhel_vm_tenant_vm_datasource_namespace: openshift-virtualization-os-images

# Storage class for the clone PVC — must use Immediate binding
ocp4_workload_rhel_vm_tenant_vm_storage_class: ocs-external-storagecluster-ceph-rbd-immediate

# VM user credentials
ocp4_workload_rhel_vm_tenant_vm_user: rhel
ocp4_workload_rhel_vm_tenant_vm_password: "{{ ocp4_workload_user_password | default(common_password) }}"
ocp4_workload_rhel_vm_tenant_vm_ssh_pwauth: true

# Cloud-init init script (optional — leave empty to skip)
ocp4_workload_rhel_vm_tenant_vm_init_script_url: ""

# Retry configuration for VM readiness
ocp4_workload_rhel_vm_tenant_vm_ready_retries: 60
ocp4_workload_rhel_vm_tenant_vm_ready_retry_delay: 10

# SSH service name
ocp4_workload_rhel_vm_tenant_vm_ssh_service_name: "{{ ocp4_workload_rhel_vm_tenant_vm_name }}-ssh"
```

- [ ] **Step 2: Create tasks/main.yml**

```yaml
---
# --------------------------------------------------
# Do not modify this file
# --------------------------------------------------
- name: Running workload provision tasks
  when: ACTION == "provision"
  ansible.builtin.include_tasks: workload.yml

- name: Running workload removal tasks
  when: ACTION == "destroy"
  ansible.builtin.include_tasks: remove_workload.yml
```

- [ ] **Step 3: Commit**

```bash
git add roles/ocp4_workload_rhel_vm_tenant/
git commit -m "feat: add tenant role defaults and dispatcher"
```

---

## Task 6: Tenant role — templates

**Files:**
- Create: `roles/ocp4_workload_rhel_vm_tenant/templates/vm.yaml.j2`
- Create: `roles/ocp4_workload_rhel_vm_tenant/templates/cloudinit-userdata.yaml.j2`
- Create: `roles/ocp4_workload_rhel_vm_tenant/templates/service-ssh.yaml.j2`

- [ ] **Step 1: Create cloudinit-userdata.yaml.j2**

```yaml
#cloud-config
user: {{ ocp4_workload_rhel_vm_tenant_vm_user }}
password: {{ ocp4_workload_rhel_vm_tenant_vm_password }}
chpasswd:
  expire: false
ssh_pwauth: {{ ocp4_workload_rhel_vm_tenant_vm_ssh_pwauth | lower }}
users:
  - name: {{ ocp4_workload_rhel_vm_tenant_vm_user }}
    sudo: ALL=(ALL) NOPASSWD:ALL
    lock_passwd: false
    plain_text_passwd: {{ ocp4_workload_rhel_vm_tenant_vm_password }}
    shell: /bin/bash
{% if ocp4_workload_rhel_vm_tenant_vm_init_script_url | default('') | length > 0 %}
runcmd:
  - curl -sSL {{ ocp4_workload_rhel_vm_tenant_vm_init_script_url }} | bash
{% endif %}
```

- [ ] **Step 2: Create vm.yaml.j2**

```yaml
---
apiVersion: kubevirt.io/v1
kind: VirtualMachine
metadata:
  name: {{ ocp4_workload_rhel_vm_tenant_vm_name }}
  namespace: {{ ocp4_workload_rhel_vm_tenant_vm_namespace }}
  labels:
    app: {{ ocp4_workload_rhel_vm_tenant_vm_name }}
spec:
  running: true
  instancetype:
    name: {{ ocp4_workload_rhel_vm_tenant_vm_instancetype }}
    kind: VirtualMachineClusterInstancetype
  preference:
    name: {{ ocp4_workload_rhel_vm_tenant_vm_preference }}
    kind: VirtualMachineClusterPreference
  dataVolumeTemplates:
    - metadata:
        name: {{ ocp4_workload_rhel_vm_tenant_vm_name }}-volume
      spec:
        sourceRef:
          kind: DataSource
          name: {{ ocp4_workload_rhel_vm_tenant_vm_datasource_name }}
          namespace: {{ ocp4_workload_rhel_vm_tenant_vm_datasource_namespace }}
        storage:
          storageClassName: {{ ocp4_workload_rhel_vm_tenant_vm_storage_class }}
          resources:
            requests:
              storage: {{ ocp4_workload_rhel_vm_tenant_vm_disksize }}
  template:
    metadata:
      labels:
        app: {{ ocp4_workload_rhel_vm_tenant_vm_name }}
        kubevirt.io/domain: {{ ocp4_workload_rhel_vm_tenant_vm_name }}
    spec:
      domain:
        devices:
          disks:
            - name: rootdisk
              disk:
                bus: virtio
            - name: cloudinitdisk
              disk:
                bus: virtio
      volumes:
        - name: rootdisk
          dataVolume:
            name: {{ ocp4_workload_rhel_vm_tenant_vm_name }}-volume
        - name: cloudinitdisk
          cloudInitNoCloud:
            userData: |
              {{ lookup('ansible.builtin.template', 'cloudinit-userdata.yaml.j2') | indent(14) }}
```

- [ ] **Step 3: Create service-ssh.yaml.j2**

```yaml
---
apiVersion: v1
kind: Service
metadata:
  name: {{ ocp4_workload_rhel_vm_tenant_vm_ssh_service_name }}
  namespace: {{ ocp4_workload_rhel_vm_tenant_vm_namespace }}
spec:
  type: ClusterIP
  selector:
    app: {{ ocp4_workload_rhel_vm_tenant_vm_name }}
  ports:
    - name: ssh
      protocol: TCP
      port: 22
      targetPort: 22
```

- [ ] **Step 4: Commit**

```bash
git add roles/ocp4_workload_rhel_vm_tenant/templates/
git commit -m "feat: add tenant role templates (VM, cloud-init, SSH service)"
```

---

## Task 7: Tenant role — workload and remove tasks

**Files:**
- Create: `roles/ocp4_workload_rhel_vm_tenant/tasks/workload.yml`
- Create: `roles/ocp4_workload_rhel_vm_tenant/tasks/remove_workload.yml`

- [ ] **Step 1: Create workload.yml**

```yaml
---
- name: Create VirtualMachine
  kubernetes.core.k8s:
    state: present
    definition: "{{ lookup('ansible.builtin.template', 'vm.yaml.j2') | from_yaml }}"

- name: Create SSH ClusterIP service
  kubernetes.core.k8s:
    state: present
    definition: "{{ lookup('ansible.builtin.template', 'service-ssh.yaml.j2') | from_yaml }}"

- name: Wait for VirtualMachineInstance to be Ready
  kubernetes.core.k8s_info:
    api_version: kubevirt.io/v1
    kind: VirtualMachineInstance
    name: "{{ ocp4_workload_rhel_vm_tenant_vm_name }}"
    namespace: "{{ ocp4_workload_rhel_vm_tenant_vm_namespace }}"
  register: r_vmi
  retries: "{{ ocp4_workload_rhel_vm_tenant_vm_ready_retries }}"
  delay: "{{ ocp4_workload_rhel_vm_tenant_vm_ready_retry_delay }}"
  until:
    - r_vmi.resources | length > 0
    - r_vmi.resources[0].status is defined
    - r_vmi.resources[0].status.phase is defined
    - r_vmi.resources[0].status.phase == "Running"

- name: Save VM connection info to agnosticd_user_info
  agnosticd_user_info:
    data:
      rhel_vm_name: "{{ ocp4_workload_rhel_vm_tenant_vm_name }}"
      rhel_vm_user: "{{ ocp4_workload_rhel_vm_tenant_vm_user }}"
      rhel_vm_password: "{{ ocp4_workload_rhel_vm_tenant_vm_password }}"
      rhel_vm_hostname: >-
        {{ ocp4_workload_rhel_vm_tenant_vm_ssh_service_name }}.{{ ocp4_workload_rhel_vm_tenant_vm_namespace }}.svc.cluster.local
```

- [ ] **Step 2: Create remove_workload.yml**

```yaml
---
- name: Remove VirtualMachine
  kubernetes.core.k8s:
    state: absent
    api_version: kubevirt.io/v1
    kind: VirtualMachine
    name: "{{ ocp4_workload_rhel_vm_tenant_vm_name }}"
    namespace: "{{ ocp4_workload_rhel_vm_tenant_vm_namespace }}"

- name: Remove SSH service
  kubernetes.core.k8s:
    state: absent
    api_version: v1
    kind: Service
    name: "{{ ocp4_workload_rhel_vm_tenant_vm_ssh_service_name }}"
    namespace: "{{ ocp4_workload_rhel_vm_tenant_vm_namespace }}"
```

- [ ] **Step 3: Commit**

```bash
git add roles/ocp4_workload_rhel_vm_tenant/tasks/
git commit -m "feat: add tenant role provision and destroy tasks"
```

---

## Task 8: Update lb2645 cluster CI

**Files:**
- Modify: `summit-2026/lb2645-agentic-devops-cluster/common.yaml`

This task replaces hummingbird with deepagents_aiops in the cluster CI.

- [ ] **Step 1: Update collections**

In `requirements_content.collections`, replace the hummingbird entry:

```yaml
    # deepagents-aiops — RHEL VM workloads
    - name: https://github.com/rhpds/deepagents-aiops.git
      type: git
      version: "{{ tag }}"
```

Remove:
```yaml
    # Hummingbird - provides RHEL VM workloads
    - name: https://github.com/rhpds/hummingbird.git
      type: git
      version: "{{ tag }}"
```

- [ ] **Step 2: Update workloads list**

Replace `rhpds.hummingbird.ocp4_workload_hummingbird_infra` with:
```yaml
  - rhpds.deepagents_aiops.ocp4_workload_rhel_vm_infra
```

Remove `ocp4_workload_openshift_gitops` from the workloads list (no longer
needed for VM infra). Keep the config vars commented in case needed later.

- [ ] **Step 3: Replace hummingbird infra variables**

Remove the entire `ocp4_workload_hummingbird_infra` section and the
`ocp4_workload_openshift_virtualization` section.

Replace with:

```yaml
# ===================================================================
# Workload: ocp4_workload_openshift_virtualization
# ===================================================================
ocp4_workload_openshift_virtualization_channel: stable
ocp4_workload_openshift_virtualization_use_catalog_snapshot: false

# ===================================================================
# Workload: ocp4_workload_rhel_vm_infra
# ===================================================================
ocp4_workload_rhel_vm_infra_datavolume_source: https://s3.us-east-1.amazonaws.com/rhdp-images/lb2865.qcow2
ocp4_workload_rhel_vm_infra_datavolume_s3_access_key_id: !vault |
  $ANSIBLE_VAULT;1.2;AES256;gpte_vault_0
  35326433623865663635633430376463306633323233353931373362623735373466636531363030
  3633316565333935386162303264326562306131343338330a353436386331656138306662623330
  30376339336562323035653865663036383333336631343263626633393438383836396331666564
  6530373836616334370a343037383135313833343934613135616535303464353430613136323364
  32306535306166386664303033386437663930633431363566336262333931623733

ocp4_workload_rhel_vm_infra_datavolume_s3_secret_access_key: !vault |
  $ANSIBLE_VAULT;1.2;AES256;gpte_vault_0
  62333066613835656362666161656535653839303530323135386530663536396365376133373734
  3239616362383965613139313734613339353731383766640a643937356165356131326638643938
  34333439613834663631376233373736383934353236303737633038306461303065333666373433
  3038336462313539340a613566653432633237393835393366616139386261623734333230396364
  33336331326235303436613935373738636434363366636437663233346530636566613263343839
  3732386564393061373838633262383537343862323735386531
```

- [ ] **Step 4: Commit**

```bash
git add summit-2026/lb2645-agentic-devops-cluster/common.yaml
git commit -m "feat: replace hummingbird with deepagents_aiops in cluster CI"
```

---

## Task 9: Update lb2645 tenant CI

**Files:**
- Modify: `summit-2026/lb2645-agentic-devops-tenant/common.yaml`

- [ ] **Step 1: Update collections**

In `requirements_content.collections`, replace the hummingbird entry:

```yaml
    # deepagents-aiops — RHEL VM workloads
    - name: https://github.com/rhpds/deepagents-aiops.git
      type: git
      version: "{{ tag }}"
```

Remove:
```yaml
    # Hummingbird - provides RHEL VM workloads
    - name: https://github.com/rhpds/hummingbird.git
      type: git
      version: "{{ tag }}"
```

- [ ] **Step 2: Update workloads list**

Replace `rhpds.hummingbird.ocp4_workload_hummingbird_tenant` with:
```yaml
  - rhpds.deepagents_aiops.ocp4_workload_rhel_vm_tenant
```

- [ ] **Step 3: Replace hummingbird tenant variables**

Remove the entire `ocp4_workload_hummingbird_tenant` section.

Replace with:

```yaml
# -------------------------------------------------------------------
# Workload: ocp4_workload_rhel_vm_tenant
# -------------------------------------------------------------------
ocp4_workload_rhel_vm_tenant_vm_name: rhel
ocp4_workload_rhel_vm_tenant_vm_namespace: "{{ ocp4_workload_tenant_keycloak_username }}-rhel"
ocp4_workload_rhel_vm_tenant_vm_datasource_name: rhel-base
ocp4_workload_rhel_vm_tenant_vm_datasource_namespace: openshift-virtualization-os-images
ocp4_workload_rhel_vm_tenant_vm_user: rhel
ocp4_workload_rhel_vm_tenant_vm_password: "{{ common_password }}"
ocp4_workload_rhel_vm_tenant_vm_disksize: 10Gi
ocp4_workload_rhel_vm_tenant_vm_instancetype: u1.medium
```

- [ ] **Step 4: Commit**

```bash
git add summit-2026/lb2645-agentic-devops-tenant/common.yaml
git commit -m "feat: replace hummingbird with deepagents_aiops in tenant CI"
```

---

## Task 10: Push collection and test

- [ ] **Step 1: Push the collection repo to GitHub**

```bash
# In the collection repo
git push -u origin main
```

- [ ] **Step 2: Push lb2645 CI changes**

```bash
# In the agnosticv repo
git push
```

- [ ] **Step 3: Verify collection installs**

```bash
ansible-galaxy collection install git+https://github.com/rhpds/deepagents-aiops.git,main --force
ansible-galaxy collection list | grep deepagents
```

Expected: `rhpds.deepagents_aiops 0.1.0`

- [ ] **Step 4: Deploy and verify**

Trigger a cluster + tenant deployment via RHDP. Verify:
- DataVolume reaches `Succeeded` phase (no `WaitForFirstConsumer` deadlock)
- VM reaches `Running` state
- SSH service exists with port 22
- `agnosticd_user_info` contains `rhel_vm_hostname`
- SSH works: `ssh rhel@rhel-ssh.user-GUID-rhel.svc.cluster.local` from Showroom terminal
