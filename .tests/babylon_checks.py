#!/usr/bin/env python

import os
import sys
import subprocess
import argparse
import re
import requests
import time
import yaml
import uuid

github_token = os.environ.get('GITHUB_TOKEN')

def github_api_request(path, headers={}):
    headers = {**headers}
    url = f"https://api.github.com{path}"
    if github_token:
        headers['Authorization'] = f"Bearer {github_token}"
    return requests.get(url, headers=headers)

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    if v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False

    raise argparse.ArgumentTypeError('Boolean value expected.')

def validate_sandboxes_request(sandboxes_request):
    """
    Validate the sandboxes request __meta__.sandboxes

    This function should be also used in agnosticV validation tests

    returns: String
        'OK' if the request is valid
        The error message if the request is invalid
    """

    main_found = {}
    target_vars = {}

    if len(sandboxes_request) == 0:
        return "ERROR: At least one sandbox is required in the sandboxes request"

    for req in sandboxes_request:
        if 'kind' not in req:
            return "ERROR: Sandbox kind is required in the sandboxes request"

        kind = req['kind']

        if kind not in main_found:
            main_found[kind] = False

        var = req.get('var', False)
        if var:
            if var in target_vars:
                return "ERROR: Variable '" + var + "' is duplicated"
            target_vars[var] = True
        else:
            if main_found.get(kind, False):
                return "ERROR: missing 'var' key for second sandbox of kind " + kind

            main_found[kind] = True

        # Ensure annotations is a dict of string
        if 'annotations' in req:
            if not isinstance(req['annotations'], dict):
                return "ERROR: Annotations should be a dict for sandbox of kind " + kind

            for key in req['annotations']:
                if not isinstance(req['annotations'][key], str):
                    return "ERROR: Annotations values should be strings for sandbox of kind " + kind

        # Ensure cloud_selector is a dict of string
        if 'cloud_selector' in req:
            if not isinstance(req['cloud_selector'], dict):
                return "ERROR: cloud_selector should be a dict for sandbox of kind " + kind

            for key in req['cloud_selector']:
                if not isinstance(req['cloud_selector'][key], str):
                    return "ERROR: cloud_selector values should be strings for sandbox of kind " + kind

    if len(main_found) == 0:
        return "ERROR: At least one main sandbox is required in the sandboxes request"

    for kind in main_found:
        if not main_found[kind]:
            return "ERROR: Main sandbox is missing for kind " + kind

    return "OK"

class AgnosticVSafeLoader(yaml.SafeLoader):
    def ignore_vault(self, node):
        return None
AgnosticVSafeLoader.add_constructor(u'!vault', AgnosticVSafeLoader.ignore_vault)

class BabylonComponent:
    def __init__(self, definition, path):
        self.definition = definition
        self.errors = []
        self.name = re.sub(
            r'\.(yaml|yml|json)$', '', path.lower().replace("/", ".").replace('_', '-')
        )
        self.path = path
        (self.account, self.short_name, self.stage) = self.name.split('.')

    def __str__(self):
        return self.path

    @property
    def deploy_with_babylon(self):
        if self.definition.get('__meta__', {}).get('deployer', {}).get('type'):
            return True

        return False

    @property
    def is_prod(self):
        return self.stage in ('prod', 'ilt')


class BabylonChecker:

    def __init__(self, agnosticv_cli, debug, from_file, paths):
        self.agnosticv_cli = agnosticv_cli
        self.debug = debug
        self.failed_components = []
        self.from_file = from_file
        self.components = []
        self.component_paths = paths
        self.scm_check_cache = {}
        self.virtualenv_check_cache = {}
        # --- NEW: Attributes for git refs ---
        self.git_base_ref = None
        self.git_head_ref = None
        self._discover_git_refs()

    # --- NEW: Function to auto-discover git refs from CI environment ---
    def _discover_git_refs(self):
        """
        Automatically determine git base and head refs from CI environment variables.
        """
        # GitHub Actions is the primary target
        if os.environ.get('GITHUB_ACTIONS'):
            # GITHUB_BASE_REF is the name of the target branch (e.g., 'main')
            base_ref_name = os.environ.get('GITHUB_BASE_REF')
            # GITHUB_SHA is the merge commit SHA for the PR
            head_ref_sha = os.environ.get('GITHUB_SHA')
            
            if base_ref_name and head_ref_sha:
                # We need the full ref name for git diff (e.g., 'origin/main')
                self.git_base_ref = f"origin/{base_ref_name}"
                self.git_head_ref = head_ref_sha
                if self.debug:
                    print(f"Detected GitHub Actions environment: base={self.git_base_ref}, head={self.git_head_ref}")

    def check(self):
        self.load_components()
        self.check_global()
        self.check_components()

    def check_global(self):
        '''Global checks which always run against component all paths'''
        for check in (
            'asset_uuids',
            'short_names',
            'forbidden_files',
            'new_folder_naming_convention', # New check added
        ):
            if self.debug:
                print(f"Checking {check}: ", end='', flush=True)
            try:
                getattr(self, f"check_global_{check}")()
            except Exception as exception:
                print(f"\n\nFailed global check '{check}': {exception}")
                sys.exit(2)
            if self.debug:
                print(' PASSED')

    def check_global_forbidden_files(self):
        '''Check for forbidden 'description.html' files in the entire repository.'''
        
        # Use git ls-files to list all tracked files in the repository.
        git_ls_files_command = ['git', 'ls-files']
        
        result = subprocess.run(git_ls_files_command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Git ls-files failed: {result.stderr}")

        all_files = result.stdout.strip().split('\n')
        # Only find files that are exactly named 'description.html'
        html_files = [f for f in all_files if f and os.path.basename(f) == 'description.html']

        if html_files:
            error_message = (
                "Found 'description.html' files in the repository. This is not permitted. "
                "Please use 'description.adoc' for catalog item descriptions.\n"
                "Forbidden files found:\n" + "\n".join(f"- {f}" for f in html_files)
            )
            raise ValueError(error_message)

    def check_global_asset_uuids(self):
        '''Check for duplicate asset uuids'''
        common_yamls = set()
        for component_path in self.all_component_paths:
            common_yamls.add(
                re.sub(
                    r'/[^/]+\.(yaml|yml|json)$', '/common.yaml', component_path
                )
            )
        uuid_to_path = {}
        for common_yaml in common_yamls:
            with open(common_yaml) as fh:
                common = yaml.load(fh, Loader=AgnosticVSafeLoader)
                assetuuid = common.get('__meta__', {}).get('asset_uuid')
                try:
                    uuid.UUID(assetuuid)
                except (ValueError, TypeError):
                    raise ValueError(
                        f"{assetuuid} is not in valid uuid format in {common_yaml}"
                    )
                if assetuuid:
                    duplicate = uuid_to_path.get(assetuuid)
                    if duplicate:
                        raise ValueError(
                            f"{assetuuid} duplicated in {duplicate} and {common_yaml}"
                        )
                    uuid_to_path[assetuuid] = common_yaml
                    if self.debug:
                        print('.', end='', flush=True)

    def check_global_short_names(self):
        '''Check for duplicate short names.'''
        component_dirs = set()
        for component_path in self.all_component_paths:
            component_dirs.add(os.path.dirname(component_path))

        short_name_to_dir = {}
        for component_dir in component_dirs:
            short_name = os.path.split(component_dir)[1].lower().replace('_', '-')
            duplicate = short_name_to_dir.get(short_name)
            if duplicate:
                raise ValueError(
                    f"{short_name} duplicated in {duplicate} and {component_dir}"
                )
            short_name_to_dir[short_name] = component_dir
            if self.debug:
                print('.', end='', flush=True)

    def check_global_new_folder_naming_convention(self):
        '''Check that new subfolders use hyphens (-) instead of underscores (_).'''
        if not self.git_base_ref or not self.git_head_ref:
            if self.debug:
                print("SKIPPED (Git refs not found for PR context)")
            return

        # Get set of directories that already exist in the base branch
        existing_dirs_cmd = ['git', 'ls-tree', '-r', '-d', '--name-only', self.git_base_ref]
        result = subprocess.run(existing_dirs_cmd, capture_output=True, text=True)
        if result.returncode != 0:
             # Fallback for shallow clones: try to fetch the base branch
            if 'not a valid object name' in result.stderr:
                if self.debug:
                    print(f"\nWARN: Initial git ls-tree failed. Attempting to fetch base ref '{self.git_base_ref}'.")
                base_branch_name = self.git_base_ref.split('/')[-1]
                subprocess.run(['git', 'fetch', 'origin', base_branch_name, '--depth=1'], check=False, capture_output=True)
                result = subprocess.run(existing_dirs_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"Git ls-tree command failed to get existing directories: {result.stderr}")
        
        existing_dirs = set(result.stdout.strip().split('\n'))

        # Get the list of directories containing newly added files in the PR
        new_files_cmd = [
            'git', 'diff', '--name-only', '--diff-filter=A',
            f"{self.git_base_ref}...{self.git_head_ref}"
        ]
        result = subprocess.run(new_files_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Git diff command failed to find new files: {result.stderr}")

        new_files = result.stdout.strip().split('\n')
        
        # Find directories that are genuinely new
        newly_created_dirs = set()
        for file_path in new_files:
            if not file_path:
                continue
            
            dir_path = os.path.dirname(file_path)
            if dir_path and dir_path not in existing_dirs:
                newly_created_dirs.add(dir_path)

        # Check only the newly created directories for underscores
        invalid_folders = set()
        for new_dir in newly_created_dirs:
            if '_' in new_dir:
                # Check if a parent directory already existed to avoid flagging valid cases
                parent = os.path.dirname(new_dir)
                if parent not in existing_dirs and parent != '':
                     # This logic can be complex, so we simplify:
                     # Check the final component of the new path.
                     if '_' in os.path.basename(new_dir):
                        invalid_folders.add(new_dir)
                elif '_' in os.path.basename(new_dir):
                    invalid_folders.add(new_dir)

        if invalid_folders:
            sorted_folders = sorted(list(invalid_folders))
            error_message = (
                "Found new folders using underscores ('_'). Please use hyphens ('-') for all new folder names.\n"
                "Invalid folder paths found:\n" +
                "\n".join(f"- {folder}" for folder in sorted_folders)
            )
            raise ValueError(error_message)

    def check_component(self, component):
        '''Check AgnosticV component'''
        for check in (
            'anarchy',
            'aws_sandbox',
            'catalog',
            'deployer_scm',
            'deployer_virtualenv',
            'execution_environment',
            'name',
            'sandboxes',
        ):
            try:
                getattr(self, f"check_component_{check}")(component)
            except Exception as exception:
                component.errors.append(str(exception))
                if component not in self.failed_components:
                    self.failed_components.append(component)

        if self.debug:
            if component.errors:
                print('F', end='', flush=True)
            else:
                print('.', end='', flush=True)

    def check_component_anarchy(self, component):
        if not component.definition.get('__meta__', {}).get('anarchy', {}).get('namespace'):
            raise ValueError("__meta__.anarchy.namespace must be set")

    def check_component_aws_sandbox(self, component):
        meta = component.definition['__meta__']
        sandbox_request = meta.get('sandbox')
        if not sandbox_request:
            return
        for secret in meta.get('secrets', []):
            if secret.get('name') == 'sandbox-api':
                break
        else:
            raise ValueError(
                "__meta__.aws_sandboxed requires sandbox-api secret\n"
                "Please add the following to the component:\n"
                "#include /includes/aws-sandbox-meta.yaml"
            )

    def check_component_catalog(self, component):
        if 'parameters' not in component.definition.get('__meta__', {}).get('catalog'):
            raise ValueError("__meta__.catalog.parameters must be provided")

    def check_component_name(self, component):
        '''Ensure account and catalog item name
        should not greater than 52 character'''
    
        name_len = len(component.name)
        if name_len > 52:
            raise ValueError(
                f"Component name length must not be greater than 52 characters, "
                f"name length is {name_len}"
            )

    def check_component_deployer_scm(self, component):
        '''Ensure configuration is having no prefix for prod tagging'''
        deployer_meta = component.definition.get('__meta__', {}).get('deployer')
        if not deployer_meta or not deployer_meta.get('type'):
            return

        if 'git_tag_prefix' in deployer_meta:
            if component.is_prod:
                raise ValueError(
                    "Stage prod/ilt must use __meta__.deployer.scm_ref "
                    "rather than __meta__.deployer.git_tag_prefix"
                )
            self.check_component_git_tag_prefix(component)
        else:
            self.check_component_scm_ref(component)

    def check_component_deployer_virtualenv(self, component):
        virtualenv = component.definition.get('__meta__', {}).get('deployer', {}).get('virtualenv')
        if not virtualenv:
            return

        url = f"https://raw.githubusercontent.com/redhat-cop/agnosticd/development/tools/virtualenvs/{virtualenv}.txt"
        if virtualenv in self.virtualenv_check_cache:
            status_code = self.virtualenv_check_cache[virtualenv]
        else:
            response = requests.head(url, timeout=2)
            status_code = response.status_code
            self.virtualenv_check_cache[virtualenv] = status_code

        if status_code != 200:
            raise ValueError(f"Error accessing {url} or virtualenv doesn't exist. Status code: {status_code}")

    def check_component_execution_environment(self, component):
        ee_image = component.definition.get('__meta__', {}).get('deployer', {}).get('execution_environment', {}).get('image')
        if not ee_image:
            return
        # FIXME - use skopeo to check that image exists. Old check did not work.
        # Need to have skopeo available to check.

    def check_component_git_tag_prefix(self, component):
        deployer_meta = component.definition['__meta__']['deployer']
        prefix = deployer_meta['git_tag_prefix']
        scm_url = deployer_meta['scm_url']

        match = re.match(r'(?:https://|git@)github\.com/([^/]+)/([^/]+?)(?:\.git)?$', scm_url)
        if match:
            self.check_github_tag_prefix(
                org=match.group(1),
                repo=match.group(2),
                prefix=prefix,
            )

    def check_component_sandboxes(self, component):
        sandboxes = component.definition.get('__meta__', {}).get('sandboxes')
        if not sandboxes:
            return
        result = validate_sandboxes_request(sandboxes)
        if "OK" != result:
            raise ValueError(result)

    def check_component_scm_ref(self, component):
        deployer_meta = component.definition['__meta__']['deployer']
        scm_ref = deployer_meta['scm_ref']
        scm_url = deployer_meta['scm_url']

        match = re.match(r'(?:https://|git@)github\.com/([^/]+)/([^/]+?)(?:\.git)?$', scm_url)
        if match:
            self.check_github_ref(
                allow_branch=(not component.is_prod or 'hotfix' in scm_ref.lower()),
                org=match.group(1),
                repo=match.group(2),
                ref=scm_ref,
            )
    def check_component_secrets(self, component):
        """Ensure that secrets are not added under __meta__."""
        # Debug print to inspect the structure
        print(f"Component definition: {component.definition}")

        # Extract secrets from the __meta__ key
        secrets = component.definition.get('__meta__', {}).get('secrets', [])

        # Debug print to check secrets
        print(f"Extracted secrets from __meta__: {secrets}")

        if secrets:
            raise ValueError(
                f"Secrets should not be defined under __meta__ in component {component.name}. "
                "Please move them to the correct location. Use vaulted secret using include file."
            )

    def check_components(self):
        if self.debug:
            print("Checking components: ", end='', flush=True)
        for component in self.components:
            if component.deploy_with_babylon:
                self.check_component(component)
        if not self.failed_components:
            if self.debug:
                print(" PASSED")
            return

        if self.debug:
            print(" FAILED\n\n")
        for component in self.failed_components:
            print(f"Failed babylon checks: {component}")
            for error in component.errors:
                print(f"- {error}")

        sys.exit(2)

    def check_github_cache(self, org, repo, ref=None, regex=None):
        refs = self.scm_check_cache.get((org, repo))
        if not refs:
            return False
        if ref:
            return ref in refs
        if regex:
            for ref in refs:
                if regex.match(ref):
                    return True
        return False

    def check_github_ref(self, allow_branch, org, repo, ref):
        """
        Check if ref is a valid tag or branch name.
        """
        tag_ref = f"refs/tags/{ref}"
        branch_ref = f"refs/heads/{ref}"

        if self.check_github_cache(org, repo, tag_ref):
            return
        if allow_branch and self.check_github_cache(org, repo, ref=branch_ref):
            return

        self.fetch_github_tag(org=org, repo=repo, value=ref)
        if self.check_github_cache(org, repo, ref=tag_ref):
            return

        if not allow_branch:
            raise ValueError(
                f"Tag {ref} not found for https://github.com/{org}/{repo}"
            )

        self.fetch_github_branch(org=org, repo=repo, value=ref)
        if not self.check_github_cache(org, repo, ref=branch_ref):
            raise ValueError(
                f"Reference {ref} did not match a tag or branch for https://github.com/{org}/{repo}"
            )

    def check_github_tag_prefix(self, org, repo, prefix):
        """
        Check if tag prefix matches a tag in target repository.
        """
        tag_regex = re.compile(r'refs/tags/{}-?[0-9.]+$'.format(re.escape(prefix)))

        if self.check_github_cache(org, repo, regex=tag_regex):
            return
        self.fetch_github_tag(org=org, repo=repo, value=prefix)
        if not self.check_github_cache(org, repo, regex=tag_regex):
            raise ValueError(
                f"Tag prefix {prefix} did not match a tag for https://github.com/{org}/{repo}"
            )

    def fetch_github_branch(self, org, repo, value):
        response = github_api_request(f"/repos/{org}/{repo}/git/refs/heads/{value}")
        if response.status_code == 200:
            data = response.json()
            if not isinstance(data, list):
                data = [data]
            for item in data:
                self.scm_check_cache.setdefault((org, repo), set()).add(item['ref'])

    def fetch_github_tag(self, org, repo, value):
        for attempt in range(10):
            response = github_api_request(f"/repos/{org}/{repo}/git/matching-refs/tags/{value}")
            response.raise_for_status
            data = response.json()
            if not isinstance(data, list):
                if 'message' in data:
                    if data['message'].startswith('API rate limit exceeded'):
                        if self.debug:
                            print(f"Retrying after rate limit exceeded")
                        time.sleep(60)
                        continue
                    elif data['message'] == 'Not Found':
                        return
                data = [data]
            break
        else:
            raise Exception(f"Error communicating with GitHub api")
        for item in data:
            if 'ref' not in item:
                print(f"{url} {item}")
            self.scm_check_cache.setdefault((org, repo), set()).add(item['ref'])

    def get_all_component_paths(self):
        agnosticv_list = subprocess.run(
            [str(self.agnosticv_cli), '--list'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        )
        return agnosticv_list.stdout.split()

    def get_component_definition(self, component_path):
        agnosticv_merge = subprocess.run(
            [str(self.agnosticv_cli), '--merge', component_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        )
        return yaml.safe_load(agnosticv_merge.stdout)

    def load_components(self):
        """
        Load components paths either from file or list all.
        """
        if self.debug:
            print("Loading components: ", end='', flush=True)
        self.all_component_paths = self.get_all_component_paths()

        if len(self.all_component_paths) == 0:
            print("No components found")
            sys.exit(2)

        if not self.component_paths:
            if self.from_file != '':
                with open(self.from_file) as fh:
                    self.component_paths = fh.readlines()
            else:
                self.component_paths = self.all_component_paths

        for component_path in self.all_component_paths:
            if component_path in self.component_paths:
                self.components.append(
                    BabylonComponent(
                        definition = self.get_component_definition(component_path),
                        path = component_path,
                    )
                )
                if self.debug:
                    print('.', end='', flush=True)
        if self.debug:
            print()

def main():
    argparser = argparse.ArgumentParser(
        description='Validate babylon properties of all components.'
    )

    argparser.add_argument('--agnosticv_cli',
        type=str,
        dest='agnosticv_cli',
        help='Path of AgnosticV CLI',
        default='agnosticv',
        required=False,
    )

    argparser.add_argument('--from_file',
        type=str,
        dest='from_file',
        help='List of components to check',
        default='',
        required=False,
    )

    argparser.add_argument('--debug',
        type=str2bool,
        dest='debug',
        nargs='?',
        const=True,
        default=False,
        help="Activate debug mode."
    )

    argparser.add_argument('paths',
        metavar='PATH', 
        type=str,
        nargs='*',
        help="Restrict validation to listed component paths"
    )

    args = argparser.parse_args()

    if args.paths and args.from_file:
        raise argparse.ArgumentError("Cannot specify paths with --from_file")

    checker = BabylonChecker(
        agnosticv_cli = args.agnosticv_cli,
        debug = args.debug,
        from_file = args.from_file,
        paths = args.paths,
    )
    checker.check()

if __name__ == '__main__':
    main()
