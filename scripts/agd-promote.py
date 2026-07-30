#!/usr/bin/env python3
"""AgnosticV Promotion Automation Tool.

Automates the process of promoting a catalog item to prod/event by:
1. Discovering repos from common.yaml
2. Finding the highest existing tag across all repos
3. Creating new tags on all tagged repos
4. Updating stage YAML files (tag + scm_ref + cloud_provider_version)
5. Updating pinned collection versions in common.yaml
"""

import argparse
import json
import os
import re
import subprocess
import sys

import yaml

# Known pinned collections that should be checked for updates
KNOWN_PINNED_URLS = {
    "https://github.com/rhpds/assisted_installer.git",
    "https://github.com/rhpds/showroom.git",
}


def parse_version(version_str):
    """Parse a version string like '1.2.3' or 'v1.2.3' into a tuple of ints."""
    v = version_str.lstrip("v")
    parts = v.split(".")
    if len(parts) == 2:
        parts.append("0")
    if len(parts) != 3:
        raise ValueError(f"Cannot parse version: {version_str}")
    return tuple(int(p) for p in parts)


def format_version(version_tuple):
    """Format a version tuple as 'x.y.z'."""
    return ".".join(str(p) for p in version_tuple)


def bump_version(version_tuple, bump_type):
    """Apply a version bump."""
    major, minor, patch = version_tuple
    if bump_type == "patch":
        return (major, minor, patch + 1)
    elif bump_type == "minor":
        return (major, minor + 1, 0)
    elif bump_type == "major":
        return (major + 1, 0, 0)
    else:
        raise ValueError(f"Unknown bump type: {bump_type}")


def parse_tag(tag_str):
    """Parse a tag like 'mcp-openshift-1.0.2' into (prefix, version_tuple).

    Returns (prefix, (major, minor, patch)).
    """
    match = re.match(r"^(.+)-(\d+\.\d+\.\d+)$", tag_str)
    if not match:
        # Try two-part version
        match = re.match(r"^(.+)-(\d+\.\d+)$", tag_str)
        if not match:
            raise ValueError(f"Cannot parse tag: {tag_str}")
    prefix = match.group(1)
    version = parse_version(match.group(2))
    return prefix, version


def repo_from_url(url):
    """Extract 'org/repo' from a git URL."""
    match = re.match(r"https://github\.com/([^/]+/[^/]+?)(?:\.git)?$", url)
    if not match:
        raise ValueError(f"Cannot parse GitHub URL: {url}")
    return match.group(1)


# --- GitHub CLI wrappers ---

def gh_check_auth():
    """Verify gh CLI is authenticated (interactive login or GH_TOKEN)."""
    if os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        return
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("ERROR: GitHub CLI is not authenticated.", file=sys.stderr)
        print("Run 'gh auth login' to authenticate, or set GH_TOKEN.", file=sys.stderr)
        sys.exit(1)


def gh_check_repo_access(repo):
    """Check if a repo is accessible."""
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}", "--silent"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def gh_get_matching_tags(repo, prefix):
    """Get all tags matching a prefix from a repo.

    Returns list of (version_tuple, tag_name) sorted ascending.
    """
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/git/matching-refs/tags/{prefix}-",
         "--paginate", "--jq", '.[].ref'],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []

    tags = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        tag_name = line.replace("refs/tags/", "")
        try:
            _, version = parse_tag(tag_name)
            tags.append((version, tag_name))
        except ValueError:
            continue
    return sorted(tags)


def gh_get_version_tags(repo):
    """Get all bare version tags (e.g., '1.2.3') from a repo.

    Returns list of (version_tuple, tag_name) sorted ascending.
    """
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/git/matching-refs/tags/",
         "--paginate", "--jq", '.[].ref'],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []

    tags = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        tag_name = line.replace("refs/tags/", "")
        # Match bare version tags like "1.2.3"
        if re.match(r"^\d+\.\d+\.\d+$", tag_name):
            try:
                version = parse_version(tag_name)
                tags.append((version, tag_name))
            except ValueError:
                continue
    return sorted(tags)


def gh_get_latest_tag(repo):
    """Get the latest semver tag from a repo.

    Returns (version_str, tag_name) or None.
    """
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/tags", "--paginate",
         "--jq", '.[].name'],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None

    best = None
    best_version = None
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            version = parse_version(line)
            if best_version is None or version > best_version:
                best_version = version
                best = line
        except ValueError:
            continue

    if best is None:
        return None
    return best, best_version


def gh_tag_exists(repo, tag):
    """Check if a tag exists on a repo."""
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/git/ref/tags/{tag}", "--silent"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def gh_get_default_branch_sha(repo):
    """Get the HEAD SHA of the default branch."""
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}", "--jq", ".default_branch"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    default_branch = result.stdout.strip()

    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/git/ref/heads/{default_branch}",
         "--jq", ".object.sha"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def gh_create_tag(repo, tag, sha):
    """Create a lightweight tag on a repo. Returns True on success."""
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/git/refs",
         "-f", f"ref=refs/tags/{tag}", "-f", f"sha={sha}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False, result.stderr
    # Verify tag exists
    if not gh_tag_exists(repo, tag):
        return False, "Tag creation succeeded but verification failed"
    return True, None


# --- Discovery ---

class _AnsibleSafeLoader(yaml.SafeLoader):
    """SafeLoader that accepts Ansible-specific YAML tags like !vault."""


_AnsibleSafeLoader.add_multi_constructor(
    "", lambda loader, suffix, node: loader.construct_scalar(node),
)


def load_common_yaml(item_path):
    """Load and parse common.yaml, returning raw dict."""
    path = os.path.join(item_path, "common.yaml")
    if not os.path.exists(path):
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return yaml.load(f, Loader=_AnsibleSafeLoader)


def discover_repos(common_data, item_path):
    """Discover all repo categories from common.yaml.

    Returns:
        tagged_repos: list of org/repo strings (Category A)
        pinned_collections: list of (org/repo, current_version, url) (Category B)
        cloud_provider_repo: org/repo string or None (Category C)
        deployer_repo: org/repo string
    """
    tagged_repos = []
    pinned_collections = []

    # Parse collections
    collections = (common_data.get("requirements_content", {})
                   .get("collections", []))
    for coll in collections:
        url = coll.get("name", "")
        version = str(coll.get("version", ""))

        if "{{ tag }}" in version:
            try:
                tagged_repos.append(repo_from_url(url))
            except ValueError as e:
                print(f"WARNING: {e}", file=sys.stderr)
        elif url in KNOWN_PINNED_URLS:
            try:
                pinned_collections.append((repo_from_url(url), version, url))
            except ValueError as e:
                print(f"WARNING: {e}", file=sys.stderr)

    # Deployer repo
    deployer_url = (common_data.get("__meta__", {})
                    .get("deployer", {})
                    .get("scm_url", ""))
    deployer_repo = None
    if deployer_url:
        try:
            deployer_repo = repo_from_url(deployer_url)
        except ValueError as e:
            print(f"WARNING: Cannot parse deployer URL: {e}", file=sys.stderr)

    # Cloud provider repo (Category C)
    cloud_provider_repo = None
    cloud_provider = common_data.get("cloud_provider", "none")
    cloud_provider_version = str(common_data.get("cloud_provider_version", ""))
    if cloud_provider != "none" and "{{ tag }}" in cloud_provider_version:
        cloud_provider_repo = f"agnosticd/cloud_provider_{cloud_provider}"

    return tagged_repos, pinned_collections, cloud_provider_repo, deployer_repo


def discover_showroom_repo(common_data):
    """Extract showroom content repo info from common.yaml.

    Returns (org/repo, current_ref) or (None, None).
    """
    url = common_data.get("ocp4_workload_showroom_content_git_repo", "")
    ref = str(common_data.get("ocp4_workload_showroom_content_git_repo_ref", ""))
    if not url:
        return None, None
    try:
        repo = repo_from_url(url)
    except ValueError:
        return None, None
    return repo, ref


def read_stage_file(item_path, stage):
    """Read a stage file and extract tag info.

    Returns (lines, tag_value, has_cloud_provider_version, cpv_value, scm_ref_value)
    or None if file missing.
    """
    path = os.path.join(item_path, f"{stage}.yaml")
    if not os.path.exists(path):
        return None

    with open(path) as f:
        lines = f.readlines()

    tag_value = None
    cpv_value = None
    has_cpv = False
    scm_ref_value = None

    for line in lines:
        tag_match = re.match(r"^tag:\s*(\S+)", line)
        if tag_match:
            tag_value = tag_match.group(1)

        cpv_match = re.match(r'^cloud_provider_version:\s*"?([^"\s]+)"?', line)
        if cpv_match:
            has_cpv = True
            cpv_value = cpv_match.group(1)

        scm_ref_match = re.match(r"\s+scm_ref:\s*(\S+)", line)
        if scm_ref_match:
            scm_ref_value = scm_ref_match.group(1)

    return lines, tag_value, has_cpv, cpv_value, scm_ref_value


def find_highest_version(tagged_repos, deployer_repo, prefix):
    """Query all repos for the highest version matching the prefix.

    Returns version_tuple of the highest found.
    """
    highest = None

    all_repos = list(tagged_repos)
    if deployer_repo:
        all_repos.append(deployer_repo)

    for repo in all_repos:
        tags = gh_get_matching_tags(repo, prefix)
        if tags:
            version, _ = tags[-1]  # sorted ascending, last is highest
            if highest is None or version > highest:
                highest = version

    return highest


def find_highest_cloud_provider_version(cloud_provider_repo):
    """Find the highest bare version tag on the cloud provider repo."""
    if not cloud_provider_repo:
        return None
    tags = gh_get_version_tags(cloud_provider_repo)
    if tags:
        return tags[-1][0]  # highest version tuple
    return None


def check_pinned_updates(pinned_collections):
    """Check each pinned collection for available updates.

    Returns list of (org/repo, current_version, latest_version, latest_tag_name, url).
    """
    results = []
    for repo, current, url in pinned_collections:
        latest = gh_get_latest_tag(repo)
        if latest is None:
            results.append((repo, current, None, None, url))
            continue
        latest_tag, latest_version = latest
        try:
            current_version = parse_version(current)
        except ValueError:
            results.append((repo, current, None, None, url))
            continue

        results.append((repo, current, format_version(latest_version),
                         latest_tag, url))
    return results


# --- YAML editing (line-based) ---

def update_stage_yaml(item_path, stage, new_tag, new_cpv=None,
                      has_tagged_repos=True):
    """Update tag, scm_ref, and optionally cloud_provider_version in a stage file.

    If has_tagged_repos=True and no tag: line exists, inserts one before __meta__.
    If has_tagged_repos=False, skips tag: handling entirely (only updates scm_ref).

    Returns True on success.
    """
    path = os.path.join(item_path, f"{stage}.yaml")
    if not os.path.exists(path):
        print(f"WARNING: {path} does not exist, skipping", file=sys.stderr)
        return False

    with open(path) as f:
        lines = f.readlines()

    tag_count = 0
    scm_ref_count = 0
    cpv_count = 0
    new_lines = []

    for i, line in enumerate(lines):
        # Replace tag:
        if has_tagged_repos and re.match(r"^tag:\s*\S+", line):
            new_lines.append(f"tag: {new_tag}\n")
            tag_count += 1
        # Replace scm_ref:
        elif re.match(r"(\s*)scm_ref:\s*\S+", line):
            indent = re.match(r"(\s*)", line).group(1)
            new_lines.append(f"{indent}scm_ref: {new_tag}\n")
            scm_ref_count += 1
        # Replace cloud_provider_version:
        elif new_cpv and re.match(r'^cloud_provider_version:\s*', line):
            new_lines.append(f'cloud_provider_version: "{new_cpv}"\n')
            cpv_count += 1
        else:
            # Insert tag: before __meta__: if needed and not yet found
            if (has_tagged_repos and tag_count == 0
                    and re.match(r"^__meta__:", line)):
                new_lines.append(f"tag: {new_tag}\n")
                tag_count += 1
            new_lines.append(line)

    # Validate replacements
    if has_tagged_repos and tag_count != 1:
        print(f"ERROR: Expected 1 tag: replacement in {path}, found {tag_count}",
              file=sys.stderr)
        return False
    if scm_ref_count != 1:
        print(f"ERROR: Expected 1 scm_ref: replacement in {path}, found {scm_ref_count}",
              file=sys.stderr)
        return False
    if new_cpv and cpv_count != 1:
        print(f"ERROR: Expected 1 cloud_provider_version: replacement in {path}, "
              f"found {cpv_count}", file=sys.stderr)
        return False

    with open(path, "w") as f:
        f.writelines(new_lines)
    return True


def update_common_yaml(item_path, pinned_updates):
    """Update pinned collection versions in common.yaml.

    pinned_updates: list of (org/repo, old_version, new_tag_name, url) where
    new_tag_name is the full tag (e.g., 'v0.0.10') and url is the collection URL
    used to anchor the replacement.
    """
    path = os.path.join(item_path, "common.yaml")
    with open(path) as f:
        lines = f.readlines()

    # Build a lookup from URL to (old_version, new_tag)
    updates_by_url = {}
    for _repo, old_version, new_tag, url in pinned_updates:
        if new_tag is not None:
            updates_by_url[url] = (old_version, new_tag)

    # Scan lines: when we see a `- name:` line matching a URL, replace the
    # next `version:` line within the following few lines.
    pending_url = None
    new_lines = []
    for line in lines:
        name_match = re.match(r"(\s*)-\s*name:\s*(\S+)", line)
        if name_match and name_match.group(2) in updates_by_url:
            pending_url = name_match.group(2)
            new_lines.append(line)
            continue

        if pending_url:
            ver_match = re.match(r"(\s*version:\s*)", line)
            if ver_match:
                old_version, new_tag = updates_by_url[pending_url]
                new_lines.append(f"{ver_match.group(1)}{new_tag}\n")
                pending_url = None
                continue
            # If we hit another `- name:` before finding version, stop looking
            if re.match(r"\s*-\s*name:", line):
                pending_url = None

        new_lines.append(line)

    with open(path, "w") as f:
        f.writelines(new_lines)


def update_showroom_ref_in_common(item_path):
    """Replace ocp4_workload_showroom_content_git_repo_ref value with {{ tag }}."""
    path = os.path.join(item_path, "common.yaml")
    with open(path) as f:
        lines = f.readlines()

    count = 0
    new_lines = []
    for line in lines:
        if re.match(r"^ocp4_workload_showroom_content_git_repo_ref:\s*", line):
            new_lines.append('ocp4_workload_showroom_content_git_repo_ref: "{{ tag }}"\n')
            count += 1
        else:
            new_lines.append(line)

    if count != 1:
        print(f"ERROR: Expected 1 showroom ref replacement in {path}, "
              f"found {count}", file=sys.stderr)
        return False

    with open(path, "w") as f:
        f.writelines(new_lines)
    return True


def ensure_dev_showroom_override(item_path):
    """Ensure dev.yaml has ocp4_workload_showroom_content_git_repo_ref: main."""
    path = os.path.join(item_path, "dev.yaml")
    if not os.path.exists(path):
        return False

    with open(path) as f:
        lines = f.readlines()

    for line in lines:
        if re.match(r"^ocp4_workload_showroom_content_git_repo_ref:\s*", line):
            return True

    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if not inserted and re.match(r"^tag:\s*", line):
            new_lines.append("\n")
            new_lines.append("ocp4_workload_showroom_content_git_repo_ref: main\n")
            inserted = True

    if not inserted:
        for i, line in enumerate(new_lines):
            if re.match(r"^__meta__:", line):
                new_lines.insert(i, "ocp4_workload_showroom_content_git_repo_ref: main\n")
                new_lines.insert(i + 1, "\n")
                inserted = True
                break

    if not inserted:
        new_lines.append("\nocp4_workload_showroom_content_git_repo_ref: main\n")

    with open(path, "w") as f:
        f.writelines(new_lines)
    return True


# --- Validation mode ---

def validate_pr(file_paths):
    """CI validation mode: check that tags in stage files exist on all repos."""
    all_passed = True

    for file_path in file_paths:
        if not os.path.exists(file_path):
            print(f"SKIP: {file_path} does not exist")
            continue

        # Determine item_path from file path
        item_path = os.path.dirname(file_path)
        stage = os.path.basename(file_path).replace(".yaml", "")

        print(f"\n--- Validating {file_path} ---")

        # Read stage file
        stage_data = read_stage_file(item_path, stage)
        if stage_data is None:
            print(f"  SKIP: Cannot read {file_path}")
            continue

        _, tag_value, has_cpv, cpv_value, scm_ref_value = stage_data

        # Use tag_value if available, otherwise fall back to scm_ref
        effective_tag = tag_value or scm_ref_value
        if not effective_tag:
            print(f"  SKIP: No tag: or scm_ref: found in {file_path}")
            continue

        print(f"  Tag: {effective_tag}")

        # Load common.yaml to discover repos
        common_data = load_common_yaml(item_path)
        tagged_repos, _, cloud_provider_repo, deployer_repo = discover_repos(
            common_data, item_path)

        # Check all tagged repos + deployer
        all_repos = list(tagged_repos)
        if deployer_repo:
            all_repos.append(deployer_repo)

        file_passed = True
        for repo in all_repos:
            if gh_tag_exists(repo, effective_tag):
                print(f"  PASS: {repo} has tag {effective_tag}")
            else:
                print(f"  FAIL: {repo} missing tag {effective_tag}")
                file_passed = False
                all_passed = False

        # Check cloud provider tag if applicable
        if cloud_provider_repo and has_cpv and cpv_value:
            if gh_tag_exists(cloud_provider_repo, cpv_value):
                print(f"  PASS: {cloud_provider_repo} has tag {cpv_value}")
            else:
                print(f"  FAIL: {cloud_provider_repo} missing tag {cpv_value}")
                file_passed = False
                all_passed = False

        # Check showroom content repo if ref uses {{ tag }}
        showroom_repo, showroom_ref = discover_showroom_repo(common_data)
        if showroom_repo and "{{ tag }}" in showroom_ref:
            if gh_tag_exists(showroom_repo, effective_tag):
                print(f"  PASS: {showroom_repo} has tag {effective_tag}")
            else:
                print(f"  FAIL: {showroom_repo} missing tag {effective_tag}")
                file_passed = False
                all_passed = False

        if file_passed:
            print(f"  Result: ALL TAGS PRESENT")
        else:
            print(f"  Result: MISSING TAGS")

    return 0 if all_passed else 1


# --- Interactive tag selection ---

def interactive_tag_selection(repos_to_tag, only_repos=None):
    """Present an interactive menu to toggle which repos get tagged.

    Args:
        repos_to_tag: list of (repo, tag) tuples
        only_repos: if set, only these repos start enabled

    Returns filtered list of (repo, tag) tuples, or None if aborted.
    """
    if not repos_to_tag:
        return []

    enabled = []
    if only_repos:
        repo_names = {repo for repo, _ in repos_to_tag}
        unknown = [r for r in only_repos if r not in repo_names]
        if unknown:
            print("ERROR: --only-repo specifies unknown repos:",
                  file=sys.stderr)
            for r in unknown:
                print(f"  - {r}", file=sys.stderr)
            sys.exit(1)
        enabled = [repo in only_repos for repo, _ in repos_to_tag]
    else:
        enabled = [True] * len(repos_to_tag)

    def render():
        print()
        print("=== Tag Selection ===")
        for i, (repo, tag) in enumerate(repos_to_tag):
            mark = "x" if enabled[i] else " "
            print(f"  [{i + 1}] [{mark}] {repo:<45s} {tag}")
        print()
        print("Toggle: enter number(s) to toggle (e.g. '1 3'), "
              "'a' to toggle all")
        print("Proceed: 'y' to continue, 'n' to abort")

    while True:
        render()
        try:
            answer = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return None

        if answer == "n":
            return None
        if answer == "y":
            selected = [(repo, tag) for (repo, tag), on
                        in zip(repos_to_tag, enabled) if on]
            if not selected:
                print("No repos selected. Aborting.")
                return None
            return selected
        if answer == "a":
            val = not all(enabled)
            enabled[:] = [val] * len(enabled)
            continue

        nums = answer.split()
        changed = False
        for tok in nums:
            try:
                idx = int(tok) - 1
                if 0 <= idx < len(enabled):
                    enabled[idx] = not enabled[idx]
                    changed = True
                else:
                    print(f"  Invalid number: {tok}")
            except ValueError:
                print(f"  Invalid input: {tok}")
        if not changed and nums:
            print("  No valid numbers entered. Try again.")


# --- Main orchestration ---

def main():
    parser = argparse.ArgumentParser(
        description="AgnosticV Promotion Automation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s agd_v2/mcp-with-openshift patch
  %(prog)s agd_v2/mcp-with-openshift minor --dry-run
  %(prog)s agd_v2/ocp-cluster-cnv-pools patch --cloud-provider-bump minor
  %(prog)s --validate-pr agd_v2/mcp-with-openshift/prod.yaml
""",
    )

    parser.add_argument("--validate-pr", nargs="+", metavar="FILE",
                        help="CI mode: validate tags in given stage files exist")
    parser.add_argument("item_path", nargs="?",
                        help="Path to catalog item dir")
    parser.add_argument("bump", nargs="?", choices=["patch", "minor", "major"],
                        help="Version bump type")
    parser.add_argument("--stage", default="prod,event",
                        help="Comma-separated stages to update (default: prod,event)")
    parser.add_argument("--cloud-provider-bump",
                        choices=["patch", "minor", "major"],
                        help="Separate bump for cloud_provider_version (default: same as main)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan only, no confirmation prompt")
    parser.add_argument("--skip-tagging", action="store_true",
                        help="Only update YAML files, skip git tag creation")
    parser.add_argument("--tag-prefix",
                        help="Override auto-detected tag prefix")
    parser.add_argument("--tag-showroom", action="store_true",
                        help="Include showroom content repo in tagging "
                             "and switch ref to {{ tag }}")
    parser.add_argument("--select-tags", action="store_true",
                        help="Interactively select which repos to tag")
    parser.add_argument("--only-repo", action="append", metavar="ORG/REPO",
                        help="Pre-select only this repo for tagging "
                             "(can be repeated, implies --select-tags)")

    args = parser.parse_args()

    # Validation mode
    if args.validate_pr:
        gh_check_auth()
        sys.exit(validate_pr(args.validate_pr))

    # Normal mode requires item_path and bump
    if not args.item_path or not args.bump:
        parser.error("item_path and bump are required (unless using --validate-pr)")

    item_path = args.item_path.rstrip("/")
    stages = [s.strip() for s in args.stage.split(",")]
    cloud_provider_bump = args.cloud_provider_bump or args.bump

    # Step 1: Discovery
    print("Discovering repos from common.yaml...")
    common_data = load_common_yaml(item_path)
    tagged_repos, pinned_collections, cloud_provider_repo, deployer_repo = (
        discover_repos(common_data, item_path))

    if not tagged_repos and not deployer_repo:
        print("ERROR: No tagged repos found in common.yaml", file=sys.stderr)
        sys.exit(1)

    # Showroom content repo discovery
    showroom_repo = None
    showroom_current_ref = None
    if args.tag_showroom:
        showroom_repo, showroom_current_ref = discover_showroom_repo(common_data)
        if showroom_repo:
            print(f"  Showroom content repo: {showroom_repo} "
                  f"(ref: {showroom_current_ref})")
        else:
            print("WARNING: --tag-showroom specified but no "
                  "ocp4_workload_showroom_content_git_repo found in common.yaml",
                  file=sys.stderr)

    # Step 2: Read tag from first available stage file
    tag_prefix = args.tag_prefix
    current_version = None
    primary_stage = None

    for stage in stages:
        stage_data = read_stage_file(item_path, stage)
        if stage_data is None:
            continue
        _, tag_value, _, _, scm_ref_value = stage_data
        if tag_value:
            primary_stage = stage
            if not tag_prefix:
                try:
                    prefix, version = parse_tag(tag_value)
                except ValueError:
                    print(
                        f"ERROR: 'tag: {tag_value}' in {stage}.yaml is not a"
                        f" versioned tag (expected format: <prefix>-X.Y.Z).\n"
                        f"  Set an initial versioned tag first, e.g.:\n"
                        f"    tag: {args.item_path}-0.1.0\n"
                        f"  Or use --tag-prefix to specify the prefix explicitly.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                tag_prefix = prefix
                current_version = version
            break
        elif scm_ref_value and not tag_prefix:
            try:
                prefix, version = parse_tag(scm_ref_value)
                tag_prefix = prefix
                current_version = version
                primary_stage = stage
                break
            except ValueError:
                continue

    if not tag_prefix:
        print("ERROR: Could not determine tag prefix from stage files.",
              file=sys.stderr)
        print("Ensure at least one stage file has a 'tag:' or 'scm_ref:' line, "
              "or use --tag-prefix.",
              file=sys.stderr)
        sys.exit(1)

    # Step 3: Pre-flight checks
    print("Running pre-flight checks...")
    gh_check_auth()

    # Check repo access
    all_tag_repos = list(tagged_repos)
    if deployer_repo:
        all_tag_repos.append(deployer_repo)

    inaccessible = []
    for repo in all_tag_repos:
        if not gh_check_repo_access(repo):
            inaccessible.append(repo)
    if cloud_provider_repo and not gh_check_repo_access(cloud_provider_repo):
        inaccessible.append(cloud_provider_repo)
    if showroom_repo and not gh_check_repo_access(showroom_repo):
        inaccessible.append(showroom_repo)
    for repo, _, _ in pinned_collections:
        if not gh_check_repo_access(repo):
            inaccessible.append(repo)

    if inaccessible:
        print("ERROR: Cannot access the following repos:", file=sys.stderr)
        for repo in inaccessible:
            print(f"  - {repo}", file=sys.stderr)
        sys.exit(1)

    # Step 2b: Find highest version across all repos
    print("Querying repos for highest existing tag...")
    highest = find_highest_version(tagged_repos, deployer_repo, tag_prefix)
    if highest is None:
        if current_version is None:
            highest = (0, 0, 0)
            print("  No existing tags found — initializing from 0.0.0")
        else:
            highest = current_version
            print(f"  No tags found on repos, using version from stage file: "
                  f"{format_version(highest)}")
    else:
        print(f"  Highest version found: {format_version(highest)}")

    # Step 2c: Check pinned collections
    print("Checking pinned collections for updates...")
    pinned_updates = check_pinned_updates(pinned_collections)

    # Cloud provider version
    current_cpv = None
    highest_cpv = None
    new_cpv = None
    if cloud_provider_repo:
        # Read current CPV from stage file
        for stage in stages:
            stage_data = read_stage_file(item_path, stage)
            if stage_data and stage_data[3]:
                current_cpv = parse_version(stage_data[3])
                break

        highest_cpv = find_highest_cloud_provider_version(cloud_provider_repo)
        if highest_cpv:
            print(f"  Cloud provider highest version: {format_version(highest_cpv)}")
        elif current_cpv:
            highest_cpv = current_cpv

    # Step 4: Compute new version
    new_version = bump_version(highest, args.bump)
    new_tag = f"{tag_prefix}-{format_version(new_version)}"

    if cloud_provider_repo and highest_cpv:
        new_cpv_version = bump_version(highest_cpv, cloud_provider_bump)
        new_cpv = format_version(new_cpv_version)

    # Step 5: Show plan
    print()
    print("=" * 50)
    print("=== Promotion Plan ===")
    print("=" * 50)
    print(f"Item:       {item_path}")
    print(f"Current:    {tag_prefix}-{format_version(highest)}  "
          f"(highest across all repos)")
    print(f"New:        {new_tag}")
    print()

    print("Tags to create:")
    for repo in tagged_repos:
        print(f"  {repo:<40s} {new_tag}")
    if deployer_repo:
        print(f"  {deployer_repo:<40s} {new_tag}")
    if cloud_provider_repo and new_cpv:
        print(f"  {cloud_provider_repo:<40s} {new_cpv}")
    if showroom_repo:
        print(f"  {showroom_repo:<40s} {new_tag}")
    print()

    if pinned_updates:
        print("Pinned collection updates (common.yaml):")
        pinned_to_apply = []
        for repo, current, latest_version, latest_tag, url in pinned_updates:
            if latest_version is None:
                print(f"  {repo:<40s} {current} (could not check)")
            elif parse_version(latest_tag) > parse_version(current):
                print(f"  {repo:<40s} {current} -> {latest_tag}  (latest available)")
                pinned_to_apply.append((repo, current, latest_tag, url))
            else:
                print(f"  {repo:<40s} {current} (already latest)")
        print()
    else:
        pinned_to_apply = []

    print("Files to update:")
    if pinned_to_apply:
        for repo, old_v, new_v, _url in pinned_to_apply:
            short_name = repo.split("/")[-1]
            print(f"  common.yaml: {short_name} version {old_v} -> {new_v}")
    if showroom_repo:
        print(f"  common.yaml: showroom ref {showroom_current_ref}"
              f' -> "{{{{ tag }}}}"')
        dev_path = os.path.join(item_path, "dev.yaml")
        if os.path.exists(dev_path):
            print(f"  dev.yaml:    ensure showroom ref override -> main")
    for stage in stages:
        stage_file = os.path.join(item_path, f"{stage}.yaml")
        if os.path.exists(stage_file):
            parts = [f"tag + scm_ref -> {new_tag}"] if tagged_repos else [f"scm_ref -> {new_tag}"]
            if cloud_provider_repo and new_cpv:
                stage_data = read_stage_file(item_path, stage)
                if stage_data and stage_data[2]:
                    parts.append(f"cloud_provider_version -> {new_cpv}")
            print(f"  {stage}.yaml:  {', '.join(parts)}")
        else:
            print(f"  {stage}.yaml:  (not found, skipping)")
    print()

    # Build the full list of repos to tag
    all_repos_to_tag = [(repo, new_tag) for repo in tagged_repos]
    if deployer_repo:
        all_repos_to_tag.append((deployer_repo, new_tag))
    if cloud_provider_repo and new_cpv:
        all_repos_to_tag.append((cloud_provider_repo, new_cpv))
    if showroom_repo:
        all_repos_to_tag.append((showroom_repo, new_tag))

    # Confirmation / interactive tag selection
    if args.skip_tagging:
        if args.dry_run:
            print("Dry run complete. No changes made.")
            return
        repos_to_tag = []
        try:
            answer = input("Proceed with YAML updates? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(1)
        if answer != "y":
            print("Aborted.")
            sys.exit(0)
    elif args.select_tags or args.only_repo:
        repos_to_tag = interactive_tag_selection(
            all_repos_to_tag, only_repos=args.only_repo)
        if repos_to_tag is None or args.dry_run:
            if args.dry_run:
                print("Dry run complete. No changes made.")
            else:
                print("Aborted.")
            sys.exit(0)
    else:
        if args.dry_run:
            print("Dry run complete. No changes made.")
            return
        try:
            answer = input("Proceed? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(1)
        if answer != "y":
            print("Aborted.")
            sys.exit(0)
        repos_to_tag = list(all_repos_to_tag)

    # Determine which repo categories were selected
    selected_repos = {repo for repo, _ in repos_to_tag}
    tagged_repos_selected = any(r in selected_repos for r in tagged_repos)
    deployer_selected = deployer_repo and deployer_repo in selected_repos
    cpv_selected = (cloud_provider_repo
                    and cloud_provider_repo in selected_repos)
    showroom_selected = showroom_repo and showroom_repo in selected_repos

    # Step 6: Create tags
    if repos_to_tag:
        print()
        print("Creating tags...")
        successes = []
        failures = []

        for repo, tag in repos_to_tag:
            if gh_tag_exists(repo, tag):
                print(f"  SKIP: {repo} already has tag {tag}")
                successes.append((repo, tag))
                continue

            sha = gh_get_default_branch_sha(repo)
            if not sha:
                print(f"  FAIL: {repo} - could not get HEAD SHA")
                failures.append((repo, tag, "could not get HEAD SHA"))
                continue

            ok, err = gh_create_tag(repo, tag, sha)
            if ok:
                print(f"  OK:   {repo} tagged {tag} (sha: {sha[:12]})")
                successes.append((repo, tag))
            else:
                print(f"  FAIL: {repo} - {err}")
                failures.append((repo, tag, err))

        if failures:
            print()
            print("ERROR: Some tags failed to create:", file=sys.stderr)
            for repo, tag, err in failures:
                print(f"  {repo}: {err}", file=sys.stderr)
            print()
            print("Cleanup commands for successfully created tags:")
            for repo, tag in successes:
                if not gh_tag_exists(repo, tag):
                    continue
                print(f"  gh api -X DELETE repos/{repo}/git/refs/tags/{tag}")
            print()
            print("YAML files NOT updated due to tagging failures.",
                  file=sys.stderr)
            sys.exit(1)

    # Step 7: Update YAML files
    print()
    print("Updating YAML files...")

    # Update common.yaml pinned versions
    if pinned_to_apply:
        update_common_yaml(item_path, pinned_to_apply)
        print(f"  Updated common.yaml with pinned collection versions")

    # Update showroom ref in common.yaml and ensure dev.yaml override
    if showroom_selected:
        if update_showroom_ref_in_common(item_path):
            print(f"  Updated common.yaml showroom ref to {{{{ tag }}}}")
        else:
            print(f"  FAIL: Could not update showroom ref in common.yaml",
                  file=sys.stderr)
        if ensure_dev_showroom_override(item_path):
            print(f"  Ensured dev.yaml has showroom ref override")

    # Update stage files only for selected tag categories
    update_tag_in_stages = tagged_repos_selected or deployer_selected
    if update_tag_in_stages or cpv_selected:
        for stage in stages:
            stage_data = read_stage_file(item_path, stage)
            if stage_data is None:
                print(f"  SKIP: {stage}.yaml not found")
                continue

            _, _, has_cpv, _, _ = stage_data
            cpv_to_set = (new_cpv if (cpv_selected and has_cpv and new_cpv)
                          else None)

            if update_stage_yaml(item_path, stage, new_tag, cpv_to_set,
                                 has_tagged_repos=update_tag_in_stages):
                print(f"  Updated {stage}.yaml")
            else:
                print(f"  FAIL: Could not update {stage}.yaml",
                      file=sys.stderr)

    print()
    print("Promotion complete!")
    print(f"New tag: {new_tag}")
    if new_cpv:
        print(f"New cloud_provider_version: {new_cpv}")
    print()
    print("Next steps:")
    print("  1. Review changes: git diff")
    print("  2. Commit and create a PR")


if __name__ == "__main__":
    main()
