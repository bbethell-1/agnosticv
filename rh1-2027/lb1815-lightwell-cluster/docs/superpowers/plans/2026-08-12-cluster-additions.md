# RHTPA Completion, OpenShift AI, and Lightweight TSSC Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: all 11 tasks executed and live-verified (2026-08-13).** This file is the historical execution record — it shows what was attempted and in what order, but several YAML snippets below (Task 2's `KC_HOST`/credentials, Task 3's entire CR, Task 5's `kserve` block, Tasks 8-9) were wrong as written and got corrected by post-hoc fix commits during live-cluster testing, *after* this plan's task loop and review passes had already approved them (the review process validated "matches the plan," not "matches reality" — the plan's own guesses were wrong in ways no reviewer without cluster access could catch). **Do not copy YAML from this plan as ground truth.** The design spec's "Post-Implementation Corrections" section (`../specs/2026-08-12-cluster-additions-design.md`) has the corrected, live-verified shape for everything. Summary of what changed post-plan:
> - Task 2: `KC_HOST` was `keycloak-keycloak.<domain>`, corrected to `sso.<domain>`; `ADMIN_USER`/`ADMIN_PASS` were `admin`/`.Values.admin.password`, corrected to a runtime lookup of the real `keycloak-initial-admin` secret (new RBAC added); a confidential `walker` OIDC client was added alongside the original `trustify-ui` client.
> - Task 3: the entire CR was wrong (`apiVersion`, `oidc`, `storage`, `db`, `hostname` didn't match the real `rhtpa.io/v1` schema) — rewritten, and a whole new Postgres deployment was added (not in this plan at all) since RHTPA has no embedded-database mode.
> - Task 5: `kserve.managementState: Managed` was changed to `Removed` — it requires OpenShift Serverless + Service Mesh operators this plan doesn't install.
> - Tasks 8-9: built as written, then deleted post-review — the pipeline's SBOM-submit step had nothing upstream generating an SBOM. Tracked as separate follow-up work in the design spec.

**Goal:** Add three components to the `bootstrap-infra` Helm chart in the `rhpds/lightwell-automation-gitops` repo: finish the RHTPA analyzer (it currently only installs the operator), add OpenShift AI (operator + default `DataScienceCluster`), and add a lightweight Tekton pipeline that builds, signs (RHTAS), scans (RHTPA), and pushes (Quay) — without pulling in the full upstream Konflux platform.

**Architecture:** Every addition is a set of raw Kubernetes manifests under `bootstrap-infra/templates/<component>/`, templated with Helm `{{ .Values.* }}` references and ordered by `argocd.argoproj.io/sync-wave` annotations, exactly like the existing `gitlab/`, `artifactory/`, `quay/`, and `rhads/` directories in this chart. ArgoCD (already running on the cluster via `ocp4_workload_gitops_bootstrap`) syncs this chart on every commit to `main`.

**Tech Stack:** Helm 3 (raw manifests, no sub-templates/helpers), ArgoCD sync-waves, OLM Subscriptions/OperatorGroups, Tekton Pipelines/Tasks, Keycloak Admin REST API (realm/client bootstrap job).

**Design spec:** `docs/superpowers/specs/2026-08-12-cluster-additions-design.md` (same directory as this plan).

## Global Constraints

- All file changes happen in the `rhpds/lightwell-automation-gitops` repo, checked out locally at `/tmp/lightwell-automation-gitops` (branch `main`, no PR process — this repo is synced directly by ArgoCD). If that checkout doesn't exist, clone it first: `gh repo clone rhpds/lightwell-automation-gitops /tmp/lightwell-automation-gitops`.
- Every task's file changes live under `/tmp/lightwell-automation-gitops/bootstrap-infra/`.
- **Do not `git push` without explicit user confirmation first** — this repo is watched live by ArgoCD on a real cluster; a push triggers an immediate sync. Commit locally after each task; push only at the end, once, after the user confirms.
- Sync-wave convention (confirmed from the existing chart, do not deviate): `-2` Namespace, `-1` RBAC/OperatorGroup, `0` Subscription/Secrets, `1` Routes/Services/PVCs/Tasks, `2` CR instance/Deployment, `3` init Jobs.
- Validate every task with `helm lint bootstrap-infra/` and `helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass` run from `/tmp/lightwell-automation-gitops`. There is no other test framework for this chart — rendered-output assertions via `grep` on `helm template` output are this plan's substitute for unit tests.
- ~~RHTPA CR field names (`oidc`, `storage`, `db`, `hostname`) are taken from the upstream `trustify-operator` CRD...~~ **Resolved, and wrong as originally written.** The real installed operator uses `apiVersion: rhtpa.io/v1` with a completely different field structure (`appDomain`, `oidc.issuerUrl`/`clients.{frontend,walker}`, flat `storage`, `database`/`createDatabase`/`migrateDatabase`). See the design spec's Component 1 for the corrected, live-verified shape.
- RHOAI subscription channel: `stable` — confirmed correct live, installed `rhods-operator.2.25.8`.
- OpenShift Pipelines subscription channel: `pipelines-1.21` (current latest as of August 2026, confirmed via Red Hat OpenShift Pipelines 1.21 release announcement).

---

### Task 1: Add values.yaml keys for RHTPA completion, RHOAI, and Tekton

**Files:**
- Modify: `/tmp/lightwell-automation-gitops/bootstrap-infra/values.yaml`

**Interfaces:**
- Produces: `.Values.tpa.keycloakRealm`, `.Values.tpa.storageSize`, `.Values.tpa.dbStorageSize`, `.Values.tpa.uiClientId`, `.Values.rhoai.namespace`, `.Values.rhoai.channel`, `.Values.tekton.namespace`, `.Values.tekton.channel` — every later task in this plan consumes these.

- [ ] **Step 1: Write the failing assertion**

From `/tmp/lightwell-automation-gitops`, run:

```bash
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -c "trustify.apps.example.com"
```

Expected: `0` (no template references this value yet — the key doesn't exist).

- [ ] **Step 2: Add the new values**

Edit `bootstrap-infra/values.yaml`. Find the existing `tpa:` block:

```yaml
tpa:
  namespace: lightwell-tpa
  channel: stable-v1.1
```

Replace it with:

```yaml
tpa:
  namespace: lightwell-tpa
  channel: stable-v1.1
  keycloakRealm: trusted-profile-analyzer
  uiClientId: trustify-ui
  storageSize: 20Gi
  dbStorageSize: 5Gi
```

Then, after the existing `aap:` block (before the final `jobAnsibleImage:` line), add two new top-level blocks:

```yaml
rhoai:
  namespace: redhat-ods-operator
  channel: stable

tekton:
  namespace: lightwell-tssc
  channel: pipelines-1.21
```

- [ ] **Step 3: Run helm lint to confirm valid YAML**

```bash
helm lint bootstrap-infra/
```

Expected: `0 chart(s) linted, 0 chart(s) failed`.

- [ ] **Step 4: Commit**

```bash
cd /tmp/lightwell-automation-gitops
git add bootstrap-infra/values.yaml
git commit -m "feat: add values for RHTPA realm, RHOAI, and Tekton pipeline"
```

---

### Task 2: RHTPA Keycloak realm/client bootstrap Job

**Files:**
- Create: `/tmp/lightwell-automation-gitops/bootstrap-infra/templates/rhads/sa-rbac-tpa-keycloak.yaml`
- Create: `/tmp/lightwell-automation-gitops/bootstrap-infra/templates/rhads/job-create-keycloak-realm.yaml`

**Interfaces:**
- Consumes: `.Values.tpa.keycloakRealm`, `.Values.tpa.uiClientId`, `.Values.tpa.namespace`, `.Values.deployer.domain`, `.Values.admin.password`, `.Values.jobAnsibleImage` (all already defined — `jobAnsibleImage` exists in `values.yaml` today).
- Produces: a Keycloak realm named `{{ .Values.tpa.keycloakRealm }}` with a public client `{{ .Values.tpa.uiClientId }}`, which Task 3's CR depends on for its `oidc.external.serverUrl`.

RHTAS's existing `Securesign` CR (`rhads/securesign-cr.yaml`) already assumes a `trusted-artifact-signer` Keycloak realm exists, but nothing in this chart creates it — that's a pre-existing gap outside this plan's scope. This task creates RHTPA's realm explicitly so the new CR in Task 3 isn't relying on the same unaddressed gap.

- [ ] **Step 1: Write the failing assertion**

```bash
cd /tmp/lightwell-automation-gitops
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -c "kind: Job"
```

Note the count (should reflect only the existing GitLab/Artifactory jobs — no Keycloak realm job yet).

- [ ] **Step 2: Create the ServiceAccount/RBAC**

Create `bootstrap-infra/templates/rhads/sa-rbac-tpa-keycloak.yaml`:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: tpa-keycloak-init
  namespace: {{ .Values.tpa.namespace }}
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
```

- [ ] **Step 3: Create the Job**

Create `bootstrap-infra/templates/rhads/job-create-keycloak-realm.yaml`, modeled on the existing `artifactory/job-init-repos.yaml` idempotent-curl pattern:

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: create-tpa-keycloak-realm
  namespace: {{ .Values.tpa.namespace }}
  annotations:
    argocd.argoproj.io/sync-wave: "1"
    argocd.argoproj.io/hook: Sync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  backoffLimit: 10
  template:
    spec:
      serviceAccountName: tpa-keycloak-init
      restartPolicy: OnFailure
      containers:
        - name: create-realm
          image: {{ .Values.jobAnsibleImage }}
          command:
            - /bin/bash
            - -c
            - |
              set -e
              KC_HOST="keycloak-keycloak.{{ .Values.deployer.domain }}"
              ADMIN_USER="admin"
              ADMIN_PASS="{{ .Values.admin.password }}"
              REALM="{{ .Values.tpa.keycloakRealm }}"
              CLIENT_ID="{{ .Values.tpa.uiClientId }}"
              REDIRECT_URI="https://trustify.{{ .Values.deployer.domain }}/*"

              echo "Waiting for Keycloak admin API..."
              for i in $(seq 1 60); do
                STATUS=$(curl -sk -o /dev/null -w '%{http_code}' "https://${KC_HOST}/realms/master" 2>/dev/null || true)
                if [ "${STATUS}" = "200" ]; then
                  echo "Keycloak API is ready"
                  break
                fi
                echo "Attempt $i/60 - API returned ${STATUS} (10s)..."
                sleep 10
              done
              if [ "${STATUS}" != "200" ]; then
                echo "ERROR: Keycloak API not ready after 10 minutes"
                exit 1
              fi

              TOKEN=$(curl -sk -X POST "https://${KC_HOST}/realms/master/protocol/openid-connect/token" \
                -d "client_id=admin-cli" -d "username=${ADMIN_USER}" -d "password=${ADMIN_PASS}" \
                -d "grant_type=password" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')
              if [ -z "${TOKEN}" ]; then
                echo "ERROR: failed to obtain Keycloak admin token"
                exit 1
              fi

              REALM_CODE=$(curl -sk -o /tmp/realm_resp.json -w '%{http_code}' \
                -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
                -X POST "https://${KC_HOST}/admin/realms" \
                -d "{\"realm\":\"${REALM}\",\"enabled\":true}")
              if [ "${REALM_CODE}" = "201" ] || [ "${REALM_CODE}" = "409" ]; then
                echo "Realm ${REALM} ready (HTTP ${REALM_CODE})"
              else
                echo "ERROR: failed to create realm (HTTP ${REALM_CODE})"
                cat /tmp/realm_resp.json
                exit 1
              fi

              CLIENT_CODE=$(curl -sk -o /tmp/client_resp.json -w '%{http_code}' \
                -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
                -X POST "https://${KC_HOST}/admin/realms/${REALM}/clients" \
                -d "{\"clientId\":\"${CLIENT_ID}\",\"publicClient\":true,\"redirectUris\":[\"${REDIRECT_URI}\"],\"webOrigins\":[\"*\"]}")
              if [ "${CLIENT_CODE}" = "201" ] || [ "${CLIENT_CODE}" = "409" ]; then
                echo "Client ${CLIENT_ID} ready (HTTP ${CLIENT_CODE})"
              else
                echo "ERROR: failed to create client (HTTP ${CLIENT_CODE})"
                cat /tmp/client_resp.json
                exit 1
              fi
```

- [ ] **Step 4: Run the assertion again to confirm it passes**

```bash
cd /tmp/lightwell-automation-gitops
helm lint bootstrap-infra/
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep "create-tpa-keycloak-realm"
```

Expected: `helm lint` passes, and the grep finds the Job name.

- [ ] **Step 5: Commit**

```bash
git add bootstrap-infra/templates/rhads/sa-rbac-tpa-keycloak.yaml bootstrap-infra/templates/rhads/job-create-keycloak-realm.yaml
git commit -m "feat: bootstrap Keycloak realm/client for RHTPA OIDC"
```

---

### Task 3: RHTPA TrustedProfileAnalyzer CR

**Files:**
- Create: `/tmp/lightwell-automation-gitops/bootstrap-infra/templates/rhads/trustedprofileanalyzer-cr.yaml`

**Interfaces:**
- Consumes: `.Values.tpa.namespace`, `.Values.tpa.keycloakRealm`, `.Values.tpa.uiClientId`, `.Values.tpa.storageSize`, `.Values.tpa.dbStorageSize`, `.Values.deployer.domain` (from Task 1).
- Consumes (implicitly, by ordering): the realm/client created in Task 2 must exist before this CR's OIDC config is usable — this CR is wave `2`, the Keycloak job is wave `1`, so ArgoCD applies them in the right order.

- [ ] **Step 1: Write the failing assertion**

```bash
cd /tmp/lightwell-automation-gitops
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -c "kind: TrustedProfileAnalyzer"
```

Expected: `0`.

- [ ] **Step 2: Create the CR**

Create `bootstrap-infra/templates/rhads/trustedprofileanalyzer-cr.yaml`:

```yaml
apiVersion: rhtpa.redhat.com/v1alpha1
kind: TrustedProfileAnalyzer
metadata:
  name: trustedprofileanalyzer-sample
  namespace: {{ .Values.tpa.namespace }}
  annotations:
    argocd.argoproj.io/sync-wave: "2"
    argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true
spec:
  hostname:
    hostname: "trustify.{{ .Values.deployer.domain }}"
  oidc:
    enabled: true
    externalServer: true
    external:
      serverUrl: "https://keycloak-keycloak.{{ .Values.deployer.domain }}/realms/{{ .Values.tpa.keycloakRealm }}"
      uiClientId: "{{ .Values.tpa.uiClientId }}"
  storage:
    type: FILESYSTEM
    filesystem:
      pvcSize: "{{ .Values.tpa.storageSize }}"
  db:
    externalDatabase: false
    embedded:
      pvcSize: "{{ .Values.tpa.dbStorageSize }}"
```

- [ ] **Step 3: Run the assertion again to confirm it passes**

```bash
cd /tmp/lightwell-automation-gitops
helm lint bootstrap-infra/
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -A3 "kind: TrustedProfileAnalyzer"
```

Expected: `helm lint` passes, and the grep shows the CR with `name: trustedprofileanalyzer-sample`.

- [ ] **Step 4: Commit**

```bash
git add bootstrap-infra/templates/rhads/trustedprofileanalyzer-cr.yaml
git commit -m "feat: add TrustedProfileAnalyzer CR to finish RHTPA install"
```

- [ ] **Step 5: On-cluster verification (do this once deployed to a dev cluster, not before)**

```bash
oc explain trustedprofileanalyzer.spec
oc get trustedprofileanalyzer -n lightwell-tpa
```

If `oc explain` shows different field names than `oidc`/`storage`/`db`/`hostname`, update `trustedprofileanalyzer-cr.yaml` to match the real schema and re-commit as a follow-up fix — do not guess further from this plan alone.

---

### Task 4: OpenShift AI operator install

**Files:**
- Create: `/tmp/lightwell-automation-gitops/bootstrap-infra/templates/rhoai/namespace.yaml`
- Create: `/tmp/lightwell-automation-gitops/bootstrap-infra/templates/rhoai/operatorgroup.yaml`
- Create: `/tmp/lightwell-automation-gitops/bootstrap-infra/templates/rhoai/subscription.yaml`

**Interfaces:**
- Consumes: `.Values.rhoai.namespace`, `.Values.rhoai.channel` (from Task 1).
- Produces: the `rhods-operator` installed in `{{ .Values.rhoai.namespace }}`, which Task 5's `DataScienceCluster` CR depends on.

- [ ] **Step 1: Write the failing assertion**

```bash
cd /tmp/lightwell-automation-gitops
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -c "redhat-ods-operator"
```

Expected: `0`.

- [ ] **Step 2: Create the namespace**

Create `bootstrap-infra/templates/rhoai/namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: {{ .Values.rhoai.namespace }}
  annotations:
    argocd.argoproj.io/sync-wave: "-2"
```

- [ ] **Step 3: Create the OperatorGroup (all-namespaces mode)**

Create `bootstrap-infra/templates/rhoai/operatorgroup.yaml`:

```yaml
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: rhoai-operator-group
  namespace: {{ .Values.rhoai.namespace }}
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
spec: {}
```

(`spec: {}` with no `targetNamespaces` means all-namespaces mode, which RHOAI requires.)

- [ ] **Step 4: Create the Subscription**

Create `bootstrap-infra/templates/rhoai/subscription.yaml`:

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: rhods-operator
  namespace: {{ .Values.rhoai.namespace }}
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  channel: {{ .Values.rhoai.channel }}
  installPlanApproval: Automatic
  name: rhods-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
```

- [ ] **Step 5: Run the assertion again to confirm it passes**

```bash
cd /tmp/lightwell-automation-gitops
helm lint bootstrap-infra/
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep "redhat-ods-operator\|rhods-operator"
```

Expected: `helm lint` passes; grep shows the namespace, OperatorGroup, and Subscription all referencing `redhat-ods-operator`/`rhods-operator`.

- [ ] **Step 6: Commit**

```bash
git add bootstrap-infra/templates/rhoai/
git commit -m "feat: install OpenShift AI operator"
```

---

### Task 5: OpenShift AI DataScienceCluster CR

**Files:**
- Create: `/tmp/lightwell-automation-gitops/bootstrap-infra/templates/rhoai/datasciencecluster-cr.yaml`

**Interfaces:**
- Consumes: nothing new from `values.yaml` — this CR's component list is fixed per the design spec (no per-environment override needed).
- Consumes (implicitly, by ordering): the `rhods-operator` from Task 4 must be installed and have registered its CRDs before this CR applies — this CR is wave `2`, well after the wave `0` Subscription.

- [ ] **Step 1: Write the failing assertion**

```bash
cd /tmp/lightwell-automation-gitops
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -c "kind: DataScienceCluster"
```

Expected: `0`.

- [ ] **Step 2: Create the CR**

Create `bootstrap-infra/templates/rhoai/datasciencecluster-cr.yaml`:

```yaml
apiVersion: datasciencecluster.opendatahub.io/v1
kind: DataScienceCluster
metadata:
  name: default-dsc
  annotations:
    argocd.argoproj.io/sync-wave: "2"
    argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true
spec:
  components:
    dashboard:
      managementState: Managed
    workbenches:
      managementState: Managed
    datasciencepipelines:
      managementState: Managed
    kserve:
      managementState: Managed
      serving:
        managementState: Managed
        name: knative-serving
        ingressGateway:
          certificate:
            type: OpenshiftDefaultIngress
```

(`DataScienceCluster` is cluster-scoped — no `namespace` field.)

- [ ] **Step 3: Run the assertion again to confirm it passes**

```bash
cd /tmp/lightwell-automation-gitops
helm lint bootstrap-infra/
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -A2 "kind: DataScienceCluster"
```

Expected: `helm lint` passes; grep shows `name: default-dsc`.

- [ ] **Step 4: Commit**

```bash
git add bootstrap-infra/templates/rhoai/datasciencecluster-cr.yaml
git commit -m "feat: add default DataScienceCluster for OpenShift AI"
```

- [ ] **Step 5: On-cluster verification (once deployed)**

```bash
oc get packagemanifest rhods-operator -n openshift-marketplace -o jsonpath='{.status.channels[*].name}'
oc get datasciencecluster default-dsc -o jsonpath='{.status.phase}'
```

If the first command doesn't list `stable`, update `.Values.rhoai.channel` in `values.yaml` to match a real channel name and re-commit as a follow-up fix.

---

### Task 6: OpenShift Pipelines operator install

**Files:**
- Create: `/tmp/lightwell-automation-gitops/bootstrap-infra/templates/tekton/subscription.yaml`

**Interfaces:**
- Consumes: `.Values.tekton.channel` (from Task 1).
- Produces: OpenShift Pipelines installed cluster-wide, which Tasks 8 and 9 depend on for the `Task`/`Pipeline` CRDs to exist.

- [ ] **Step 1: Write the failing assertion**

```bash
cd /tmp/lightwell-automation-gitops
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -c "openshift-pipelines-operator-rh"
```

Expected: `0`.

- [ ] **Step 2: Create the Subscription**

Create `bootstrap-infra/templates/tekton/subscription.yaml`. This operator installs into the existing `openshift-operators` namespace (same pattern as `rhads/subscription-rhtas.yaml`) — no dedicated namespace or OperatorGroup needed:

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: openshift-pipelines-operator-rh
  namespace: openshift-operators
  annotations:
    argocd.argoproj.io/sync-wave: "0"
spec:
  channel: {{ .Values.tekton.channel }}
  installPlanApproval: Automatic
  name: openshift-pipelines-operator-rh
  source: redhat-operators
  sourceNamespace: openshift-marketplace
```

- [ ] **Step 3: Run the assertion again to confirm it passes**

```bash
cd /tmp/lightwell-automation-gitops
helm lint bootstrap-infra/
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep "openshift-pipelines-operator-rh"
```

Expected: `helm lint` passes; grep shows the Subscription with `channel: pipelines-1.21`.

- [ ] **Step 4: Commit**

```bash
git add bootstrap-infra/templates/tekton/subscription.yaml
git commit -m "feat: install OpenShift Pipelines operator"
```

---

### Task 7: Tekton demo namespace + ServiceAccount/RBAC

**Files:**
- Create: `/tmp/lightwell-automation-gitops/bootstrap-infra/templates/tekton/namespace.yaml`
- Create: `/tmp/lightwell-automation-gitops/bootstrap-infra/templates/tekton/sa-rbac.yaml`

**Interfaces:**
- Consumes: `.Values.tekton.namespace` (from Task 1).
- Produces: ServiceAccount `pipeline-runner` in `{{ .Values.tekton.namespace }}`, which Tasks 8 and 9's `Task`/`Pipeline`/future `PipelineRun`s reference to authenticate to Quay.

- [ ] **Step 1: Write the failing assertion**

```bash
cd /tmp/lightwell-automation-gitops
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -c "lightwell-tssc"
```

Expected: `0`.

- [ ] **Step 2: Create the namespace**

Create `bootstrap-infra/templates/tekton/namespace.yaml`:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: {{ .Values.tekton.namespace }}
  annotations:
    argocd.argoproj.io/sync-wave: "-2"
```

- [ ] **Step 3: Create the ServiceAccount and RBAC**

Create `bootstrap-infra/templates/tekton/sa-rbac.yaml`. The pipeline's `buildah` Task needs to push to Quay using a registry credentials secret named `quay-push-secret` in this same namespace — creating that secret is out of scope for this plan (per the design's non-goals, it's a future tenant-provisioning concern), but the ServiceAccount that will reference it is in scope:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: pipeline-runner
  namespace: {{ .Values.tekton.namespace }}
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: pipeline-runner-edit
  namespace: {{ .Values.tekton.namespace }}
  annotations:
    argocd.argoproj.io/sync-wave: "-1"
subjects:
  - kind: ServiceAccount
    name: pipeline-runner
    namespace: {{ .Values.tekton.namespace }}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: edit
```

- [ ] **Step 4: Run the assertion again to confirm it passes**

```bash
cd /tmp/lightwell-automation-gitops
helm lint bootstrap-infra/
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep "lightwell-tssc\|pipeline-runner"
```

Expected: `helm lint` passes; grep shows the namespace and ServiceAccount.

- [ ] **Step 5: Commit**

```bash
git add bootstrap-infra/templates/tekton/namespace.yaml bootstrap-infra/templates/tekton/sa-rbac.yaml
git commit -m "feat: add Tekton demo namespace and pipeline ServiceAccount"
```

---

### Task 8: Custom Task — submit SBOM to RHTPA

**Files:**
- Create: `/tmp/lightwell-automation-gitops/bootstrap-infra/templates/tekton/task-submit-sbom.yaml`

**Interfaces:**
- Consumes: `.Values.tekton.namespace` (from Task 1), `.Values.deployer.domain` (existing), `.Values.tpa.namespace` (existing/Task 1).
- Produces: a `Task` named `submit-sbom-to-rhtpa` with params `sbom-path` (string) and `product-name` (string) — Task 9's `Pipeline` references this exact name and these exact param names.

This is the one pipeline step with no Tekton Hub equivalent — it's a plain `curl` upload of a CycloneDX/SPDX file to the RHTPA API's SBOM ingestion endpoint.

- [ ] **Step 1: Write the failing assertion**

```bash
cd /tmp/lightwell-automation-gitops
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -c "submit-sbom-to-rhtpa"
```

Expected: `0`.

- [ ] **Step 2: Create the Task**

Create `bootstrap-infra/templates/tekton/task-submit-sbom.yaml`:

```yaml
apiVersion: tekton.dev/v1
kind: Task
metadata:
  name: submit-sbom-to-rhtpa
  namespace: {{ .Values.tekton.namespace }}
  annotations:
    argocd.argoproj.io/sync-wave: "1"
spec:
  params:
    - name: sbom-path
      type: string
      description: Path to the generated SBOM file (CycloneDX JSON) inside the workspace.
    - name: product-name
      type: string
      description: Name to label this SBOM upload with in RHTPA.
  workspaces:
    - name: source
  steps:
    - name: submit
      image: registry.access.redhat.com/ubi9/ubi-minimal:latest
      workingDir: $(workspaces.source.path)
      script: |
        #!/usr/bin/env bash
        set -e
        microdnf install -y curl >/dev/null
        TPA_HOST="trustify.{{ .Values.deployer.domain }}"
        CODE=$(curl -sk -o /tmp/sbom_resp.json -w '%{http_code}' \
          -X POST "https://${TPA_HOST}/api/v2/sbom?labels.product=$(params.product-name)" \
          -H "Content-Type: application/json" \
          --data-binary "@$(params.sbom-path)")
        if [ "${CODE}" = "200" ] || [ "${CODE}" = "201" ]; then
          echo "SBOM submitted to RHTPA (HTTP ${CODE})"
        else
          echo "ERROR: SBOM submission failed (HTTP ${CODE})"
          cat /tmp/sbom_resp.json
          exit 1
        fi
```

- [ ] **Step 3: Run the assertion again to confirm it passes**

```bash
cd /tmp/lightwell-automation-gitops
helm lint bootstrap-infra/
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -A2 "submit-sbom-to-rhtpa"
```

Expected: `helm lint` passes; grep shows `kind: Task` / `name: submit-sbom-to-rhtpa`.

- [ ] **Step 4: Commit**

```bash
git add bootstrap-infra/templates/tekton/task-submit-sbom.yaml
git commit -m "feat: add custom Tekton Task to submit SBOMs to RHTPA"
```

---

### Task 9: Reusable Pipeline — build, sign, scan, push

**Files:**
- Create: `/tmp/lightwell-automation-gitops/bootstrap-infra/templates/tekton/pipeline.yaml`

**Interfaces:**
- Consumes: `.Values.tekton.namespace` (Task 1), `submit-sbom-to-rhtpa` Task with params `sbom-path`/`product-name` (Task 8's exact interface).
- Produces: a `Pipeline` named `build-sign-scan-push`. No `PipelineRun` is created by this chart — triggering is out of scope per the design's non-goals (deferred to `bootstrap-tenant`).

This `Pipeline` references three Tekton Hub `Task`s by name (`git-clone`, `buildah`, `cosign-sign`) — those aren't created by this chart; they're resolved at runtime via the cluster's Tekton Hub resolver (already available once the OpenShift Pipelines operator from Task 6 is installed, since it ships with the `hub` resolver enabled by default).

- [ ] **Step 1: Write the failing assertion**

```bash
cd /tmp/lightwell-automation-gitops
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -c "build-sign-scan-push"
```

Expected: `0`.

- [ ] **Step 2: Create the Pipeline**

Create `bootstrap-infra/templates/tekton/pipeline.yaml`:

```yaml
apiVersion: tekton.dev/v1
kind: Pipeline
metadata:
  name: build-sign-scan-push
  namespace: {{ .Values.tekton.namespace }}
  annotations:
    argocd.argoproj.io/sync-wave: "1"
spec:
  params:
    - name: git-url
      type: string
    - name: git-revision
      type: string
      default: main
    - name: image-ref
      type: string
      description: Full Quay image reference to push, e.g. quay-registry.example.com/lightwell/app:latest
    - name: product-name
      type: string
  workspaces:
    - name: shared-workspace
  tasks:
    - name: fetch-source
      taskRef:
        resolver: hub
        params:
          - name: kind
            value: task
          - name: name
            value: git-clone
          - name: version
            value: "0.9"
      workspaces:
        - name: output
          workspace: shared-workspace
      params:
        - name: url
          value: $(params.git-url)
        - name: revision
          value: $(params.git-revision)
    - name: build-image
      runAfter: ["fetch-source"]
      taskRef:
        resolver: hub
        params:
          - name: kind
            value: task
          - name: name
            value: buildah
          - name: version
            value: "0.6"
      workspaces:
        - name: source
          workspace: shared-workspace
      params:
        - name: IMAGE
          value: $(params.image-ref)
    - name: sign-image
      runAfter: ["build-image"]
      taskRef:
        resolver: hub
        params:
          - name: kind
            value: task
          - name: name
            value: cosign-sign
          - name: version
            value: "0.1"
      params:
        - name: image
          value: $(params.image-ref)
    - name: submit-sbom
      runAfter: ["build-image"]
      taskRef:
        name: submit-sbom-to-rhtpa
      workspaces:
        - name: source
          workspace: shared-workspace
      params:
        - name: sbom-path
          value: sbom.json
        - name: product-name
          value: $(params.product-name)
```

- [ ] **Step 3: Run the assertion again to confirm it passes**

```bash
cd /tmp/lightwell-automation-gitops
helm lint bootstrap-infra/
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass 2>&1 | grep -A2 "build-sign-scan-push"
```

Expected: `helm lint` passes; grep shows `kind: Pipeline` / `name: build-sign-scan-push`.

- [ ] **Step 4: Commit**

```bash
git add bootstrap-infra/templates/tekton/pipeline.yaml
git commit -m "feat: add build/sign/scan/push Tekton Pipeline"
```

- [ ] **Step 5: On-cluster verification (once deployed) — manual pipeline run**

```bash
tkn pipeline start build-sign-scan-push \
  -n lightwell-tssc \
  --param git-url=https://gitlab.<cluster-domain>/tsf/sample-component-golang.git \
  --param image-ref=quay-registry.<cluster-domain>/lightwell/sample:latest \
  --param product-name=sample-component \
  --workspace name=shared-workspace,volumeClaimTemplateFile=- <<'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: 1Gi
EOF
```

Confirm all four `Task`s (`fetch-source`, `build-image`, `sign-image`, `submit-sbom`) reach `Succeeded` via `tkn pipelinerun logs -f -n lightwell-tssc`. If `cosign-sign`'s default Hub Task doesn't already point at our RHTAS Fulcio/Rekor endpoints, this run will surface that as a concrete failure to fix — don't assume it works from this plan alone.

---

### Task 10: Chart metadata updates

**Files:**
- Modify: `/tmp/lightwell-automation-gitops/bootstrap-infra/Chart.yaml`
- Modify: `/tmp/lightwell-automation-gitops/README.md`

**Interfaces:**
- None — this is documentation/metadata only, no other task depends on it.

- [ ] **Step 1: Update Chart.yaml description**

In `bootstrap-infra/Chart.yaml`, change:

```yaml
description: Lightwell demo cluster infrastructure - GitLab, RHADS, Artifactory, Jenkins
```

to:

```yaml
description: Lightwell demo cluster infrastructure - GitLab, RHADS, Artifactory, Jenkins, OpenShift AI, Tekton
```

- [ ] **Step 2: Update README.md repository structure tree**

In `README.md`, in the `Repository Structure` code block, after the `rhads/` line add:

```
    rhoai/                OpenShift AI (operator + DataScienceCluster)
    tekton/               OpenShift Pipelines (build/sign/scan/push demo pipeline)
```

- [ ] **Step 3: Update README.md Components table**

Add two rows to the `## Components` table:

```markdown
| **OpenShift AI** | Data science dashboard, workbenches, pipelines, model serving | `redhat-ods-operator` / `redhat-ods-applications` |
| **OpenShift Pipelines** | Tekton-based build/sign/scan/push demo pipeline | `lightwell-tssc` |
```

- [ ] **Step 4: Commit**

```bash
cd /tmp/lightwell-automation-gitops
git add bootstrap-infra/Chart.yaml README.md
git commit -m "docs: update chart metadata for OpenShift AI and Tekton additions"
```

---

### Task 11: Full-chart validation and push

**Files:** none (validation-only task).

- [ ] **Step 1: Full chart lint and render**

```bash
cd /tmp/lightwell-automation-gitops
helm lint bootstrap-infra/
helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass > /tmp/rendered-full.yaml
```

Expected: `helm lint` passes with `0 chart(s) failed`; `/tmp/rendered-full.yaml` is non-empty.

- [ ] **Step 2: Confirm every new resource is present in the full render**

```bash
for r in "kind: TrustedProfileAnalyzer" "kind: DataScienceCluster" "kind: Pipeline" "kind: Task" "openshift-pipelines-operator-rh" "rhods-operator" "create-tpa-keycloak-realm"; do
  echo -n "$r: "; grep -c "$r" /tmp/rendered-full.yaml
done
```

Expected: every count is `>= 1`.

- [ ] **Step 3: Confirm sync-wave ordering is internally consistent**

```bash
grep -B5 "kind: TrustedProfileAnalyzer" /tmp/rendered-full.yaml | grep sync-wave
grep -B5 "kind: DataScienceCluster" /tmp/rendered-full.yaml | grep sync-wave
grep -B5 "kind: Pipeline" /tmp/rendered-full.yaml | grep sync-wave
```

Expected: `"2"`, `"2"`, `"1"` respectively, matching the convention in Global Constraints.

- [ ] **Step 4: Push — only after explicit user confirmation**

Ask the user to confirm before running this — ArgoCD will sync these changes to the live cluster immediately on push.

```bash
cd /tmp/lightwell-automation-gitops
git push origin main
```

- [ ] **Step 5: Watch the ArgoCD sync**

```bash
oc get application lb1815-lightwell -n openshift-gitops -o jsonpath='{.status.sync.status} {.status.health.status}{"\n"}'
oc get subscription,operatorgroup -n redhat-ods-operator
oc get subscription -n openshift-operators | grep pipelines
oc get trustedprofileanalyzer -n lightwell-tpa
oc get datasciencecluster default-dsc
```

Expected: `Synced Healthy` (allow several minutes for operators to install and CRs to reconcile), and each `oc get` returns a resource. Any failures here are real bugs to fix, not something this plan can pre-verify without a live cluster.
