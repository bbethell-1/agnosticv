# Cluster Additions: RHTPA Completion, OpenShift AI, Lightweight TSSC Pipeline

> **Status: implemented and live-verified on `cluster-24wzh` (2026-08-13).** This doc was written before implementation; several sections below described assumptions that turned out to be wrong once tested against a real cluster. Sections are updated in place to reflect what actually shipped, with the original assumption kept alongside for context. See "Post-Implementation Corrections" at the end for the full list and why each one was wrong.

## Goal

Add three components to the `bootstrap-infra` Helm chart (in the `lightwell-automation-gitops` repo, checked out locally at `/tmp/lightwell-automation-gitops` at design time) that the ArgoCD-managed cluster CI (`rh1-2027/lb1815-lightwell-cluster`) deploys:

1. Finish RHTPA — it currently only installs the operator, with no running analyzer instance.
2. Add OpenShift AI (RHOAI) — operator + a default `DataScienceCluster`.
3. Install the OpenShift Pipelines operator, scaffolded for a future lightweight Tekton pipeline (build → sign (RHTAS) → SBOM scan (RHTPA) → push (Quay)) reusing infrastructure already deployed by this chart. No separate Konflux platform, UI, or build service — and, as it turned out during implementation, no actual pipeline content in this round either (see Component 3).

All three follow the chart's existing pattern: raw Helm templates ordered by `argocd.argoproj.io/sync-wave` annotations, values sourced from `bootstrap-infra/values.yaml` with runtime overrides injected from the AgnosticV cluster CI's Ansible workload (`ocp4_workload_gitops_bootstrap_helm_values`).

## Non-Goals

- No full upstream Konflux install (its own UI, build service, multi-tenant model, or GitLab/Quay-alternative source integration). Explicitly rejected as out of scope — would duplicate the GitLab/Quay this chart already deploys and is an order of magnitude larger than the rest of this chart.
- No `EventListener`/`Trigger` wiring so a GitLab push auto-fires a `PipelineRun`. That's a per-tenant concern; it belongs in `lb1815-lightwell-tenant` / `bootstrap-tenant` as follow-up work.
- **Added during implementation:** no `Pipeline`/`Task` content at all in this round (see Component 3) — descoped to operator-install-only after review found the drafted pipeline couldn't actually complete.
- No custom RHOAI notebook images, model-serving wiring, or integration with the Lightwell CVE narrative. Operator + default `DataScienceCluster` only, per explicit scoping decision. **Added during implementation:** `kserve` specifically is `Removed` (not just unconfigured), since enabling it needs operators this design doesn't install.
- No changes to `lb1815-lightwell-tenant` in this design.

## Existing Conventions (confirmed from the current chart)

Sync-wave ordering used consistently across `gitlab/`, `artifactory/`, `quay/`, `jenkins/`, `sonarqube/`, `rhads/`:

| Wave | Purpose |
|------|---------|
| `-2` | Namespace |
| `-1` | RBAC / OperatorGroup |
| `0`  | Subscription / Secrets |
| `1`  | Routes / Services / PVCs |
| `2`  | CR instance / Deployment |
| `3`  | Init Jobs |

New templates in this design follow the same waves.

## Component 1: Finish RHTPA (`templates/rhads/`)

**As shipped, this component turned out to need four pieces, not one.** The `rhads/` directory already had `namespace-tpa.yaml` and `subscription-tpa.yaml` (OperatorGroup + Subscription). This design added:

- `rhads/sa-rbac-tpa-keycloak.yaml` — a `tpa-keycloak-init` ServiceAccount plus a Role/RoleBinding granting it `get` on one secret (`keycloak-initial-admin`) in the `keycloak` namespace, cross-namespace.
- `rhads/job-create-keycloak-realm.yaml` — a sync-wave-`1` hook Job that creates the `{{ .Values.tpa.keycloakRealm }}` realm plus two OIDC clients (public `{{ .Values.tpa.uiClientId }}` for the frontend, confidential `walker` for the backend) via the Keycloak Admin REST API. **Verified working against a live cluster.**
- `rhads/postgresql-tpa.yaml` — a dedicated Postgres Deployment/Service/PVC for RHTPA (wave `0`/`1`). **Not in the original design** — see corrections below.
- `rhads/trustedprofileanalyzer-cr.yaml` — the `TrustedProfileAnalyzer` CR itself, wave `2`, `apiVersion: rhtpa.io/v1` (confirmed live, not `rhtpa.redhat.com/v1alpha1` as originally guessed). Real shape, confirmed against the installed operator's own JSON schema and reconciler errors, and cross-checked against a working reference implementation (`rhpds/lightwell-tssc-workshop`):

```yaml
spec:
  partOf: trustify
  replicas: 1
  appDomain: "-{{ .Values.tpa.namespace }}.{{ .Values.deployer.domain }}"
  tracing: { enabled: false }
  metrics: { enabled: false }
  storage:
    type: filesystem
    size: "{{ .Values.tpa.storageSize }}"
  oidc:
    issuerUrl: "https://sso.{{ .Values.deployer.domain }}/realms/{{ .Values.tpa.keycloakRealm }}"
    clients:
      frontend:
        clientId: "{{ .Values.tpa.uiClientId }}"
      walker:
        clientId: walker
        clientSecret: "{{ .Values.admin.password }}"
  database: &db
    host: tpa-postgresql.{{ .Values.tpa.namespace }}.svc.cluster.local
    name: tpa
    username: tpa
    password: "{{ .Values.admin.password }}"
    port: "5432"
  createDatabase: *db
  migrateDatabase: *db
  modules:
    createDatabase: { enabled: true }
    migrateDatabase: { enabled: true }
    createImporters: { enabled: false }
```

Notable field-level gotchas, each confirmed live and worth remembering for any future RHTPA work:
- `database` has no embedded/self-managed mode — it always requires a real Postgres connection. `createDatabase`/`migrateDatabase` must be repeated as full top-level blocks (same connection details as `database`) even though `modules.createDatabase.enabled`/`modules.migrateDatabase.enabled` look like they should be sufficient toggles — the operator's internal chart `deepCopy`s these values unconditionally and crashes on a nil block.
- `appDomain` is a suffix, not the bare cluster domain — the operator's internal chart builds the route hostname as `"server" + appDomain` with no separator, so it must be `-<namespace>.<domain>` (leading dash) to produce a valid `server-<namespace>.<domain>` route.
- The OIDC client key for a confidential backend client is `walker`, not `cli` — the reference repo's chart targets operator channel `stable-v3` (a newer major version) whose schema uses `cli`; the `stable-v1.1` operator this chart installs (channel `{{ .Values.tpa.channel }}`) uses `walker`. Don't copy client-key names from a reference chart without checking which operator channel it targets.

### values.yaml additions
```yaml
tpa:
  namespace: lightwell-tpa      # existing
  channel: stable-v1.1          # existing, confirmed correct live
  keycloakRealm: trusted-profile-analyzer   # new
  uiClientId: trustify-ui                    # new
  storageSize: 20Gi              # new
  dbStorageSize: 5Gi              # new
  postgresImage: docker.io/library/postgres:16-alpine   # new
```

## Component 2: OpenShift AI (`templates/rhoai/` — new directory)

Standard operator + CR pattern:

- `rhoai/namespace.yaml` — `redhat-ods-operator` (fixed by product convention), wave `-2`.
- `rhoai/operatorgroup.yaml` — wave `-1`.
- `rhoai/subscription.yaml` — `rhods-operator` subscription, channel `{{ .Values.rhoai.channel }}`, wave `0`.
- `rhoai/datasciencecluster-cr.yaml` — `DataScienceCluster` (`datasciencecluster.opendatahub.io/v1`), name `default-dsc`, wave `2` (after the operator has had time to establish CRDs), with core components set `Managed`: `dashboard`, `workbenches`, `datasciencepipelines`. All other components left at operator defaults (no explicit override) to keep this minimal.

**Correction — `kserve` is `Removed`, not `Managed`.** The original design set `kserve.managementState: Managed` with `serving.name: knative-serving`. Live testing showed `kserve`'s serving mode requires the OpenShift Serverless and OpenShift Service Mesh operators, neither of which this chart (or the cluster CI) installs — the `DataScienceCluster` would never reach `Ready` with `kserve` enabled. Set to `Removed`; the rest of the DSC (`dashboard`, `workbenches`, `datasciencepipelines`) reaches `Ready` cleanly this way. **Confirmed live: `oc get datasciencecluster default-dsc` → `Ready`.**

Channel confirmed correct on the first deploy: `stable` (channel names shift between OpenShift AI releases, but this one resolved cleanly — installed `rhods-operator.2.25.8`).

### values.yaml additions
```yaml
rhoai:
  namespace: redhat-ods-operator # new (fixed by product)
  channel: stable                 # new — confirmed correct live (installed 2.25.8)
```

## Component 3: Tekton Operator Install (`templates/tekton/` — new directory)

**Descoped from the original design.** The original plan for this section was a full lightweight pipeline (`git-clone` → `buildah` → `cosign sign` → custom SBOM-submit-to-RHTPA Task → push to Quay). Two of those pieces (`tekton/tasks.yaml` and `tekton/pipeline.yaml`) were built, then pulled back out after review: the `submit-sbom` step reads an `sbom.json` file that nothing in the pipeline actually generates (`git-clone`/`buildah` don't produce one), so the pipeline would always fail at its last step. On reflection, a working build/sign/scan pipeline is itself real "demo lab content," not cluster infrastructure — the same category of thing as GitLab repo content or Jenkins job definitions, neither of which this chart seeds either. It's tracked as separate follow-up work once the actual SBOM-generation step is designed (see Follow-up Work).

What shipped in this design, scoped down to match every other component's shape (operator install + minimal scaffold, no pipeline content):

- `tekton/subscription.yaml` — OpenShift Pipelines operator (`openshift-pipelines-operator-rh`), cluster-wide install (standard OLM pattern, target namespace `openshift-operators`), channel `{{ .Values.tekton.channel }}`, wave `0`. No dedicated namespace/OperatorGroup template needed — this operator installs cluster-scoped by convention. **Confirmed live: `pipelines-1.21` channel installed `openshift-pipelines-operator-rh.v1.21.3` successfully.**
- `tekton/namespace.yaml` — `{{ .Values.tekton.namespace }}` (`lightwell-tssc`) to hold future pipeline resources, wave `-2`.
- `tekton/sa-rbac.yaml` — a `pipeline-runner` ServiceAccount with `edit` RoleBinding in that namespace, scaffolded for whichever future pipeline lands there.

### values.yaml additions
```yaml
tekton:
  namespace: lightwell-tssc     # new
  channel: pipelines-1.21       # new — confirmed correct live (installed 1.21.3)
```

## Chart Metadata Updates

- `Chart.yaml` `description` currently reads "Lightwell demo cluster infrastructure - GitLab, RHADS, Artifactory, Jenkins" — update to mention RHOAI and the TSSC pipeline.
- `README.md` — update the components table (add RHOAI, Tekton/Pipelines rows) and the repo structure tree (add `rhoai/`, `tekton/` under `bootstrap-infra/templates/`).

## Testing / Validation

No local test suite for this chart beyond `helm lint` and `helm template` (per repo convention). As executed:

1. `helm lint bootstrap-infra/` and `helm template lb1815-lightwell bootstrap-infra/ --set deployer.domain=apps.example.com --set admin.password=testpass` — run after every commit, always clean.
2. Deployed to a real cluster (`cluster-24wzh.dynamic2.redhatworkshops.io`) via direct `git push` to the GitOps repo's `main` (ArgoCD auto-syncs). **All items below confirmed live, not just planned:**
   - `oc get trustedprofileanalyzer -n lightwell-tpa` → condition `Deployed: True, reason: InstallSuccessful`; `server`/`importer` pods `Running`, `create-db`/`migrate-db` Jobs `Completed`; route returns HTTP 200.
   - `oc get datasciencecluster default-dsc` → `Ready`.
   - `oc get subscription openshift-pipelines-operator-rh -n openshift-operators`, `oc get subscription rhods-operator -n redhat-ods-operator`, `oc get subscription rhtpa-operator -n lightwell-tpa` → all `Succeeded`.
   - Full ArgoCD Application sync: `Healthy`, `Synced` except the pre-existing, unrelated `AnsibleAutomationPlatform` drift (known operator-managed drift, not introduced by this work).
3. No `Pipeline`/`Task` shipped in this round (see Component 3), so no pipeline run to verify yet.

**Validation methodology note for future similar work:** none of the bugs below were caught by `helm lint`/`helm template` — both only check that the chart renders valid YAML, not that the rendered CRs match what their operators actually expect. The only way any of this was caught was applying to a real cluster and reading the operator's own reconciler logs/status conditions. Treat "renders cleanly" and "operator accepts it" as two separate, both-required checks for any CR whose schema isn't already proven elsewhere in this chart.

## Follow-up Work (explicitly deferred, not part of this design)

- Per-tenant `Trigger`/`EventListener` wiring so tenant GitLab pushes auto-fire a pipeline (belongs in `bootstrap-tenant`/`lb1815-lightwell-tenant`).
- **The actual Tekton pipeline content** (build → sign → scan → push): needs an SBOM-generation step (e.g. a `syft` Hub Task) between build and the RHTPA submit step that this round's draft was missing. Design and add as a follow-up once the demo's actual build/sign/scan narrative is worked out — do not just re-add the draft `pipeline.yaml`/`task-submit-sbom.yaml` as-is; the taskRef/param wiring was fine, only the missing SBOM step needs solving.
- Decision on how much upstream Konflux (if any) gets layered on top of the eventual pipeline.
- RHOAI integration into the Lightwell CVE/SBOM demo narrative (notebook images, model serving, dependency scanning tie-in) — deferred per explicit scoping decision. Note `kserve` is currently `Removed`; re-enabling model serving later requires first adding OpenShift Serverless + Service Mesh operator installs.

## Post-Implementation Corrections (found via live testing, 2026-08-13)

Six real bugs were found only by deploying to a real cluster and reading operator logs/status — none were visible from `helm lint`/`helm template` or from the docs consulted during design. In order found:

1. **Keycloak hostname was invented, not verified.** The design assumed `keycloak-keycloak.{{ .Values.deployer.domain }}`. The real route (from `ocp4_workload_authentication`) is `sso.{{ .Values.deployer.domain }}`. This was wrong in three places: the new Keycloak-realm Job, the new RHTPA CR, and the **pre-existing** RHTAS `Securesign` CR (not part of this design, but the same wrong assumption — fixed alongside since the evidence was already in hand).
2. **Keycloak admin credentials were assumed, not looked up.** The design's realm-bootstrap Job assumed `.Values.admin.password` (this chart's shared app password) was also the Keycloak master-realm admin password. The Keycloak Operator actually generates its own random admin login in a `keycloak-initial-admin` secret (username `temp-admin`) in the `keycloak` namespace. Fixed by granting the Job's ServiceAccount cross-namespace read access to that one secret and fetching it at runtime.
3. **The `TrustedProfileAnalyzer` CR schema was entirely wrong** — see Component 1 above for the full corrected shape. The design's "Open verification item" correctly flagged this as unverified, but the actual verification (pulling the operator's own bundled `values.schema.json` off the running pod, and reading its reconciler's structured validation errors) revealed a completely different field structure than the upstream community operator this design's guess was based on.
4. **RHTPA has no embedded-database mode.** Not anticipated at all in the original design — it was assumed the CR would offer the same embedded-vs-external toggle the upstream `trustify-operator` community CRD has. The Red Hat-branded `rhtpa.io/v1` schema always requires a real Postgres connection. Added a dedicated Postgres Deployment, matching the pattern already used for GitLab/Artifactory/SonarQube.
5. **The operator's internal Helm chart needs `createDatabase`/`migrateDatabase` as full top-level blocks**, not just `modules.createDatabase.enabled`/`modules.migrateDatabase.enabled` toggles — an internal template `deepCopy`s these unconditionally and panics on a nil value if only the toggle is set.
6. **`appDomain` needed a namespace-scoped dash-prefixed suffix**, not the bare cluster domain — confirmed by the operator generating an invalid route hostname (`serverapps.<domain>`, missing separator) until corrected to `-{{ .Values.tpa.namespace }}.{{ .Values.deployer.domain }}`.

Two scoping corrections (not bugs) also happened post-review, both covered above: the Tekton pipeline content was pulled back to operator-install-only, and RHOAI's `kserve` was set to `Removed`.
