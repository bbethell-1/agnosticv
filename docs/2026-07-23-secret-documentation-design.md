# Mandatory Documentation for Encrypted Secrets

**Jira:** [GPTEINFRA-16176](https://redhat.atlassian.net/browse/GPTEINFRA-16176)
**Date:** 2026-07-23
**Author:** Guillaume Core

## Problem

The `includes/secrets/` directory contains ~150 vault-encrypted secret files. Most have no documentation — no owner, no description of what happens if the credential leaks, no expiration date, no instructions for rotation. When a secret needs to be rotated or investigated, the team has to reverse-engineer its purpose from variable names and `#include` references scattered across catalog items.

## Design

### Comment Format

Every vault-encrypted variable must have a `# @field: value` comment block immediately above it. Seven fields are mandatory per variable:

| Field | Format | Description |
|-------|--------|-------------|
| `@owner` | `Name <email>[, ...]` | Person(s) or team responsible. Comma-separated for multiple owners |
| `@purpose` | free text | What this credential does |
| `@impact` | `HIGH\|MEDIUM\|LOW - explanation` | What happens if it leaks |
| `@expiration` | `YYYY-MM-DD`, `never`, or `UNKNOWN` | When the credential expires |
| `@rotation` | free text | How to rotate or renew |
| `@source` | URL or description | Where the credential was created or can be regenerated |
| `@exposure` | free text | Where the decrypted value ends up at runtime |

### Impact Levels

- **HIGH** — Can access or destroy production resources, customer data, or external services with broad scope (e.g., cloud admin keys, org-level OAuth tokens).
- **MEDIUM** — Can access dev/staging environments or internal-only systems with limited blast radius (e.g., dev cluster tokens, internal API keys).
- **LOW** — Limited scope, easily revokable, no customer data exposure (e.g., test-only credentials, time-limited workshop tokens).

### UNKNOWN Placeholder

Any field value can be set to `UNKNOWN` (case-insensitive) when the person documenting a secret genuinely doesn't know the answer. This is better than making something up — it flags the field for future investigation while still satisfying CI. For `@impact` and `@expiration`, `UNKNOWN` bypasses format validation.

### Example: Single-Variable File

```yaml
---
# @owner: Guillaume Core <gucore@redhat.com>
# @purpose: OAuth token for Quay.io org-admin API access
# @impact: HIGH - leaked token grants full org admin on quay.io/rhpds, can delete repos and manage teams
# @expiration: 2027-01-15
# @rotation: Regenerate in quay.io org settings > Applications > rhpds-sandbox
# @source: https://quay.io/organization/rhpds?tab=applications
# @exposure: AgnosticD execution only, not persisted
quay_io_oauth_token: !vault |
  $ANSIBLE_VAULT;1.2;AES256;gpte-vault-0
  61336662393763353834613566326234373262...
```

### Example: Multi-Variable File

```yaml
---
# @owner: Guillaume Core <gucore@redhat.com>
# @purpose: AWS access key ID for ROSA provisioning (not secret on its own, identifies the account)
# @impact: LOW - read-only identifier, useless without the secret key
# @expiration: never
# @rotation: Regenerate in AWS IAM > Users > rosa-provisioner > Security credentials
# @source: https://console.aws.amazon.com/iam/home#/users/rosa-provisioner
# @exposure: injected as env vars during AgnosticD execution
rosa_aws_access_key_id: !vault |
  $ANSIBLE_VAULT;1.2;AES256;gpte-vault-0
  ...

# @owner: Guillaume Core <gucore@redhat.com>
# @purpose: AWS secret access key for ROSA provisioning
# @impact: HIGH - combined with the access key, grants full programmatic access to rhpds AWS account
# @expiration: never
# @rotation: Regenerate in AWS IAM > Users > rosa-provisioner > Security credentials
# @source: https://console.aws.amazon.com/iam/home#/users/rosa-provisioner
# @exposure: injected as env vars during AgnosticD execution
rosa_aws_secret_access_key: !vault |
  $ANSIBLE_VAULT;1.2;AES256;gpte-vault-0
  ...
```

### Placement Rules

- Each `!vault` variable must have its own `# @field:` block immediately above it.
- The block is associated with the next vault variable that follows — a blank line between `@` comments and the variable is allowed.
- Field order is not enforced but the recommended order is: owner, purpose, impact, expiration, rotation, source, exposure.
- Multi-line values are not supported — each field is a single `# @field: value` line.

## CI Enforcement

### Scope: Gradual Adoption

Any YAML file **touched in the current PR** is scanned for `!vault` variables. Each vault variable must have the required `@` comment block. Files not modified in the PR are not checked. This avoids a big-bang migration while ensuring all new or updated secrets are documented going forward.

### Implementation

A new validation script (`.tests/check_secret_docs.py`) called from `.tests/static-tests.sh`:

1. **Identify changed files:** Use the `$PR` environment variable (already available in the `all-checks-pr.yml` workflow) to get the list of files changed in the PR via GitHub API, or use `git diff` against the base branch.
2. **Filter to YAML:** Keep only files matching `*.yaml` or `*.yml`.
3. **Parse per-variable:** Walk lines top to bottom. Accumulate `# @key: value` lines (regex: `^# @(\w+):\s*(.+)$`) into a current block. When a `!vault` variable is encountered, validate the accumulated block against the 7 required fields, then reset the block.
4. **Validate field formats:**
   - `@impact` must start with `HIGH`, `MEDIUM`, or `LOW`.
   - `@expiration` must be a valid `YYYY-MM-DD` date or the literal `never`.
6. **Report:** On failure, print a clear error listing each file, variable name, and its missing/invalid fields. Exit non-zero to fail the PR check.

### Error Output Example

```
ERROR: includes/secrets/rosa-aws.yaml
  rosa_aws_access_key_id: missing @impact, @expiration, @rotation
  rosa_aws_secret_access_key: missing @owner, @purpose, @impact, @expiration, @rotation, @source
  
ERROR: includes/secrets/ocp4_token.yaml
  ocp4_token: invalid @impact (must start with HIGH, MEDIUM, or LOW)
              invalid @expiration ("next year" is not YYYY-MM-DD or "never")

3 undocumented secret(s) in 2 file(s).

Required fields: @owner, @purpose, @impact, @expiration, @rotation, @source, @exposure
See includes/secrets/TEMPLATE.yaml for the required format.
```

### Workflow Integration

The check runs as part of the existing `all-checks-pr.yml` workflow, inside the `static-tests.sh` script. No new workflow file needed.

## Out of Scope

- **Automated expiration alerts:** This spec only adds documentation. Alerting on approaching expiration dates is a future enhancement.
- **Validating `@source` URLs are reachable:** The source field is documentation, not a health check.
- **Enforcing `@owner` against a known team roster:** Any `Name <email>` format passes.
- **Backfilling all 150 existing secrets:** Gradual adoption. Existing files are documented when next modified.
- **Validating consumer references:** Who `#include`s a secret is discoverable via grep; no `@consumers` field needed.

## Implementation Summary

1. Create the validation script (shell or Python).
2. Wire it into `static-tests.sh`.
3. Add a template/example file at `includes/secrets/TEMPLATE.yaml` for contributors to copy.
4. Update `readme.adoc` with the new requirement.
