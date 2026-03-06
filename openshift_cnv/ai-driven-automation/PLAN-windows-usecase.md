# Plan: Add Windows Use Case to AI-Driven Ansible Automation Lab

## Context

The ai-driven-ansible-automation lab currently demonstrates AIOps with two use cases: Apache remediation (Linux) and OSPF network automation (Cisco routers). The user wants to add a third use case based on a demo showing Event-Driven Ansible detecting Windows events and creating AI-enriched tickets. This adds a "Part 3" to the workshop covering Windows automation with two scenarios:

1. **AD Account Creation**: EDA detects Windows Event ID 4722 (account enabled) -> creates a Mattermost ticket with event payload data
2. **Firewall Event + AI**: EDA detects Windows Firewall changes -> queries Granite LLM for analysis -> creates AI-enriched Mattermost ticket

## Design Decisions

- **Ticketing**: Use Mattermost (already deployed) instead of ServiceNow
- **Event flow**: Winlogbeat on Windows -> Kafka topic `windows-events` -> EDA (consistent with existing Filebeat -> Kafka -> EDA pattern)
- **AI**: Use existing LiteLLM/Granite setup (not ChatGPT)
- **Windows image**: `base-windows-ad-2022` with `e1000e` interface and PSRP connection (proven pattern from `openshift_cnv/ansible-super-lab/common.yaml`)
- **Scope**: All four repositories

## Changes by Repository

### 1. AgnosticV (`openshift_cnv/ai-driven-automation/common.yaml`)

#### Add Windows instance variables (after line 60, cisco_rootfs_size)
```yaml
windows_instance_image: base-windows-ad-2022
windows_rootfs_size: 60Gi
windows_admin_user: Administrator
windows_admin_password: "{{ common_password }}"
```

#### Add Windows VM instance (after cisco-rtr2, line 372)
Follow the pattern from `openshift_cnv/ansible-super-lab/common.yaml:494-521`:
- Image: `base-windows-ad-2022`, Memory: 16G, Cores: 4, Disk: 60Gi
- `interface_model: e1000e` (required for Windows on KubeVirt)
- AnsibleGroup: `windows`, ostype: `windows`
- Services: port 5986 (WinRM/PSRP), port 80 (HTTP), port 3389 (RDP)
- Network: `default`

#### Add Windows collections to `requirements_content` (line 377)
```yaml
- name: ansible.windows
  version: ">=2.0.0"
- name: microsoft.ad
  version: ">=1.0.0"
- name: community.windows
  version: ">=2.0.0"
```

#### Add Winlogbeat workload to `software_workloads` (line 411)
```yaml
windows:
  - lb2961.ai_driven_aap.winlogbeat
```

#### Add Windows credential to `controller_credentials` (after line 674)
```yaml
- name: "Windows"
  description: "Windows Server Credential"
  organization: "Default"
  credential_type: Machine
  inputs:
    username: "{{ windows_admin_user }}"
    password: "{{ windows_admin_password }}"
```

#### Add Windows inventory to `controller_inventories` (after line 702)
```yaml
- name: "windows-inventory"
  description: "Windows Server Inventory"
  organization: "Default"
  prevent_instance_group_fallback: false
  state: present
```

#### Add Windows host to `controller_hosts` (after line 731)
```yaml
- name: "windows"
  inventory: "windows-inventory"
  variables:
    ansible_host: "windows.lab.sandbox-{{ guid }}-ocp4-cluster.svc.cluster.local"
    ansible_connection: psrp
    ansible_psrp_auth: negotiate
    ansible_psrp_cert_validation: ignore
```

#### Add Windows job templates to `controller_templates` (after line 928)

4 new job templates:
1. **"Simulate AD Account Creation"** - Runs `playbooks/windows_create_ad_user.yml` against `windows-inventory` with `Windows` credential
2. **"Simulate Windows Firewall Toggle"** - Runs `playbooks/windows_toggle_firewall.yml` against `windows-inventory` with `Windows` credential
3. **"Windows: Create Mattermost Ticket"** - Runs `playbooks/windows_create_ticket.yml` on `Demo Inventory`, `ask_variables_on_launch: true`, passes mattermost URL/token
4. **"Windows AI: Analyze and Ticket"** - Runs `playbooks/windows_ai_analyze_and_ticket.yml` on `Demo Inventory`, `ask_variables_on_launch: true`, passes LiteLLM and Mattermost config

Plus 1 workflow creation template:
5. **"Create Windows Firewall AI Workflow"** - Runs `playbooks/create_windows_workflow.yml` with `AAP` credential

#### Add workflow launch job to `controller_launch_jobs` (line 929)
```yaml
- name: "Create Windows Firewall AI Workflow"
```

#### Add Windows EDA rulebook activation to `eda_rulebook_activations` (after line 989)
```yaml
- name: "Windows Events"
  description: "Detect Windows security and firewall events via Kafka"
  organization: Default
  project: "ai-eda"
  rulebook: "windows_events.yml"
  decision_environment: "{{ eda_decision_environment_name }}"
  restart_policy: "on-failure"
  enabled: true
  eda_credentials: "AAP"
  state: present
```

#### Add Windows host to `agnosticv_importdata` (line 1008)
```yaml
windows_host: "windows.lab.sandbox-{{ guid }}-ocp4-cluster.svc.cluster.local"
```

---

### 2. EDA Rulebooks & Playbooks (`~/work/src/aiops-summitlab`)

#### New file: `rulebooks/windows_events.yml`
Pattern follows existing `rulebooks/web_app.yml` (Kafka source on `service1:9092`, topic `windows-events`).

Two rules:
- **AD account enabled** (condition: `event.body.winlog.event_id == 4722`) -> `run_job_template` "Windows: Create Mattermost Ticket" with extra_vars from event payload (target account, source account, event description)
- **Firewall change** (condition: event_id in 4946, 4950, 2004, 2005) -> `run_job_template` "Windows AI: Analyze and Ticket" with extra_vars (event_id, message, raw payload)

#### New file: `playbooks/windows_create_ad_user.yml`
"Break" playbook that creates a test AD user using `microsoft.ad.user` module to trigger Event ID 4722.

#### New file: `playbooks/windows_toggle_firewall.yml`
"Break" playbook that toggles Windows Firewall Domain profile (disable then re-enable) using `ansible.windows.win_shell` with PowerShell `Set-NetFirewallProfile`.

#### New file: `playbooks/windows_create_ticket.yml`
Creates a Mattermost notification from Windows event data. Pattern follows existing `playbooks/mattermost_first_message.yml`. Uses `community.general.mattermost` with structured attachments showing Event ID, target account, initiated by, description, and ticket status.

#### New file: `playbooks/windows_ai_analyze_and_ticket.yml`
Combined playbook that:
1. Sends the Windows event to LiteLLM via `ansible.builtin.uri` (pattern from `playbooks/rhelai_inference_survey.yml`) asking "What does this Windows Event mean and what are recommended actions?"
2. Creates a Mattermost ticket with the AI analysis embedded (color-coded, fields for Event ID, type, AI analysis)

#### New file: `playbooks/create_windows_workflow.yml`
Creates the "Windows Firewall AI Analysis" workflow template in AAP using `ansible.controller.workflow_job_template`. Two nodes: AI analyze -> create ticket. Pattern follows the existing `playbooks/create_network_aiops_workflow.yml`.

---

### 3. Workload Collection (`~/work/src/lb2961.ai_driven_aap`)

#### New role: `roles/winlogbeat/`
Pattern follows existing `roles/filebeat/` role.

Structure:
```
roles/winlogbeat/
  defaults/main.yml    # kafka broker, topic, event IDs to filter
  tasks/main.yml       # Download, extract, configure, install, start Winlogbeat
  templates/winlogbeat.j2  # Winlogbeat config: Security + Firewall event logs -> Kafka output
  meta/main.yml        # Role metadata
```

Key details:
- Uses `ansible.windows.win_get_url`, `community.windows.win_unzip`, `ansible.windows.win_template`, `ansible.windows.win_service` modules
- Starts with `ansible.builtin.wait_for_connection` to handle slow Windows boot
- Winlogbeat config filters Security log for Event IDs 4722, 4720 and Firewall log for all events
- Outputs to Kafka broker `service1:9092` topic `windows-events`

#### Update Kafka role for additional topic
Add `kafka_additional_topics` variable support to `roles/kafka/defaults/main.yml` and a loop task in `roles/kafka/tasks/main.yml` to create the `windows-events` topic alongside the existing `httpd-error-logs` topic.

---

### 4. Showroom (`~/work/src/ai-driven-automation-showroom`)

#### New file: `content/modules/ROOT/pages/module-06.adoc`
"Part 3: AIOps with Windows Automation" covering:
- Introduction: Windows event-driven automation with AI enrichment
- Scenario 1 walkthrough: Simulate AD account creation, observe EDA, view Mattermost ticket
- Scenario 2 walkthrough: Toggle firewall, observe AI analysis workflow, view enriched ticket
- Include screenshots (to be added to `assets/images/`)

#### Update: `content/modules/ROOT/nav.adoc`
Add Part 3 section before the Summary:
```
* Part 3: AIOps with Windows Automation
** xref:module-06.adoc[6. Windows Events and AI-Driven Ticketing]
* xref:module-05.adoc[7. Summary and Call to Actions]
```

#### Update: `content/modules/ROOT/pages/module-05.adoc`
Add Part 3 accomplishments to the summary section.

#### Update: `content/modules/ROOT/pages/index.adoc`
Add Part 3 to the workshop agenda and lab topology description.

---

## Key Reference Files

| File | Purpose |
|------|---------|
| `openshift_cnv/ai-driven-automation/common.yaml` | Primary config to modify |
| `openshift_cnv/ansible-super-lab/common.yaml:494-521` | Windows VM on CNV pattern |
| `~/work/src/aiops-summitlab/rulebooks/web_app.yml` | EDA rulebook pattern (Kafka source) |
| `~/work/src/aiops-summitlab/playbooks/mattermost_first_message.yml` | Mattermost notification pattern |
| `~/work/src/aiops-summitlab/playbooks/rhelai_inference_survey.yml` | LiteLLM API call pattern |
| `~/work/src/lb2961.ai_driven_aap/roles/filebeat/` | Log shipper role pattern for Winlogbeat |

## Verification

1. Deploy the lab in dev mode and confirm the Windows VM boots and is accessible via PSRP
2. Verify Winlogbeat is running and forwarding events to the `windows-events` Kafka topic
3. Confirm the EDA "Windows Events" rulebook activation is running
4. Run the "Simulate AD Account Creation" job template and verify:
   - EDA picks up Event ID 4722
   - Mattermost ticket is created with correct event data
5. Run the "Simulate Windows Firewall Toggle" job template and verify:
   - EDA picks up firewall event
   - LiteLLM returns AI analysis
   - Mattermost ticket contains AI-enriched description
6. Review showroom module-06 renders correctly in the Showroom UI
