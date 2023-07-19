#!/usr/bin/env python

import os
import sys
import subprocess
import argparse
import requests
import time

import yaml

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    if v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False

    raise argparse.ArgumentTypeError('Boolean value expected.')


parser = argparse.ArgumentParser(
    description='Validate all catalog items against an OpenAPI schema.'
)

parser.add_argument('--agnosticv_cli',
                    type=str,
                    dest='agnosticv_cli',
                    help='Path of AgnosticV CLI',
                    default='agnosticv',
                    required=False,
                    )

parser.add_argument('--from_file',
                    type=str,
                    dest='from_file',
                    help='List of catalog items to check',
                    default='',
                    required=False,
                    )

parser.add_argument('--debug',
                    type=str2bool,
                    dest='debug',
                    nargs='?',
                    const=True,
                    default=False,
                    help="Activate debug mode.")

args = parser.parse_args()

process_all = subprocess.run(
    [str(args.agnosticv_cli), '--list'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    universal_newlines=True,
    check=True,
)

all_catalog_items = process_all.stdout.split()

if len(all_catalog_items) == 0:
    print("No catalog item found")
    sys.exit(2)

catalog_items = all_catalog_items

# Override if it's passed as a file
if args.from_file != '':
    with open(args.from_file) as x:
        catalog_items = x.readlines()

valid = []
invalid = []

def check_duplicate_directories(c, ci):
    '''Check for duplicate directories'''
    path = os.path.join(os.environ['GITHUB_WORKSPACE'], c.get('directory', ''))  # get the directory path from the catalog item contents
    if not path:
        raise ValueError('Missing "directory" field in catalog item')

    seen_dirs = {}
    duplicate_dirs = {}
    for root, dirs, files in os.walk(path):
        # Exclude directories containing .git, includes, and parameters in the path
        dirs[:] = [d for d in dirs if '.git' not in os.path.join(root, d) and 'includes' not in os.path.join(root, d) and 'parameters' not in os.path.join(root, d)]
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            if os.path.isdir(dir_path):
                if dir in seen_dirs:
                    seen_dir_path = seen_dirs[dir]
                    if dir in duplicate_dirs:
                        duplicate_dirs[dir].append(dir_path)
                    else:
                        duplicate_dirs[dir] = [seen_dir_path, dir_path]
                else:
                    seen_dirs[dir] = dir_path

    if duplicate_dirs:
        error_message = f"Found {len(duplicate_dirs)} duplicate directories in catalog item {ci}:\n"
        for dir, paths in duplicate_dirs.items():
            dir_paths = '\n                 '.join(paths)
            error_message += f"- {dir}:\n                 {dir_paths}\n"
        raise ValueError(error_message)
    return True


def check_double_booking(c,ci):
    '''Ensure catalog item doesn't double-book
    AWS sandboxes with both Babylon and admin host scripts'''

    if '__meta__' in c and 'agnosticv_meta' in c:
        if 'aws_sandboxed' in c['__meta__'] and 'sandboxed' in c['agnosticv_meta']:
            if (c['__meta__']['aws_sandboxed']
                and c['agnosticv_meta']['sandboxed']):
                raise ValueError(
                    '''__meta__.aws_sandboxed and agnosticv_meta.sandboxed can't be both true'''
                )

    return True

def check_name(c,ci):
    '''Ensure account and catalog item name
    should not greater than 52 character'''
    if len(ci) <= 52:
        return True

    ciAccNamStg=ci[0:ci.rfind(".")].replace("/", ".")
    if len(ciAccNamStg)>52:
        print("AgV Length is %d and AgV is %s" %(len(ciAccNamStg), ciAccNamStg))
        raise ValueError(
            '''Ensure catalog item name should not greater than 52 character'''
        )
    return True

def check_tag_var(c,ci):
    '''Ensure configuration is having no prefix for prod tagging'''

    ciAccNamStg=ci[0:ci.rfind(".")].replace("/", ".")
    if '__meta__' in c or 'agnosticv_meta' in c:
        if (ciAccNamStg.endswith(".prod") or ciAccNamStg.endswith(".ilt")):
            if 'agnosticd_git_tag_prefix' in c['agnosticv_meta']:
                raise ValueError(
                    '''agnosticd_git_ref should be used for prod/ilt, not agnosticd_git_tag_prefix.'''
                )
            if  'deploy_with' in c['agnosticv_meta'] and 'deployer' in c['__meta__']:
                deployer = c['__meta__']['deployer']
                if (c['agnosticv_meta']['deploy_with'] == "babylon" and 'git_tag_prefix' in deployer):
                    raise ValueError(
                        '''scm_ref should be used for prod/ilt, not git_tag_prefix.'''
                    )
    return True

virtualenv_check_result = {}
exeenv_check_result = {}
def check_virtualenv(c, ci):
    """
    Check that __meta__.deployer.virtualenv exists in GitHub upstream repo
    """
    if "__meta__" in c or "agnosticv_meta" in c:
        deployer = c.get("__meta__", {}).get("deployer", {})
        virtualenv = deployer.get("virtualenv") or c.get("agnosticv_meta", {}).get("virtualenv")
        if virtualenv:
            url = f"https://raw.githubusercontent.com/redhat-cop/agnosticd/development/tools/virtualenvs/{virtualenv}.txt"
            cached_result = virtualenv_check_result.get(url)
            if virtualenv == "babylon":
                return True
            elif cached_result:
                if cached_result != 200:
                    raise ValueError(f"Error accessing {url} or virtualenv doesn't exist. Status code: {cached_result} (cached)")
            else:
                headers = {"User-Agent": "Mozilla/5.0"}
                r = requests.get(url, headers=headers)
                result = r.status_code
                virtualenv_check_result[url] = r.status_code
                if r.status_code != 200:
                    raise ValueError(f"Error accessing {url} or virtualenv doesn't exist. Status code: {r.status_code}")
        else:
            exe_env = deployer.get("execution_environment")
            if exe_env:
                exe_env_image = exe_env.get("image")
                if exe_env_image:
                    url = f"http://{exe_env_image}"
                    cached_result = exeenv_check_result.get(url)
                    if cached_result:
                        if cached_result != 200:
                            raise ValueError(f"Error accessing {url} or virtualenv doesn't exist. Status code: {cached_result} (cached)")
                    else:
                        headers = {"User-Agent": "Mozilla/5.0"}
                        r = requests.get(url, headers=headers)
                        result = r.status_code
                        exeenv_check_result[url] = r.status_code
                        if r.status_code != 200:
                            raise ValueError(f"Error accessing {url} or virtualenv doesn't exist. Status code: {r.status_code}")
                else:
                  return True
            else:
                raise ValueError(f"No Execution Environment or virtualenv defined.")
    return True

def check_valid_agv_tag(c,ci):
    '''Ensure configuration is having a valid git tag agnosticv meta'''

    ciAccNamStg=ci[0:ci.rfind(".")].replace("/", ".")
    if '__meta__' in c or 'agnosticv_meta' in c:
        if (ciAccNamStg.endswith(".prod") or ciAccNamStg.endswith(".ilt")):
            agvRepo = "redhat-cop/agnosticd/git/matching-refs/tags/"
            # Getting tag value from agnosticv_meta section
            agvMetaTag = ''
            if 'agnosticd_git_ref' in c['agnosticv_meta']:
                agvMetaTag = c['agnosticv_meta']['agnosticd_git_ref']
            elif 'agnosticd_git_tag_prefix' in c['agnosticv_meta']:
                agvMetaTag = c['agnosticv_meta']['agnosticd_git_tag_prefix']
            # Call Github API and check git tag on agnosticd repo
            agvMetaResponse = requests.get("https://api.github.com/repos/"+agvRepo+agvMetaTag)
            if agvMetaResponse.status_code==200 and agvMetaResponse.json() is not None and len(agvMetaResponse.json())<1:
                raise ValueError(
                    '''No such git tag exist on agnosticd provided under agnosticv_meta: ''' + agvMetaTag
                )

    return True

def check_valid_babylon_tag(c,ci):
    '''Ensure configuration is having a valid git tag on babylon meta'''

    ciAccNamStg=ci[0:ci.rfind(".")].replace("/", ".")
    if '__meta__' in c or 'agnosticv_meta' in c:
        if (
            (ciAccNamStg.endswith(".prod") or ciAccNamStg.endswith(".ilt")) and
            (not ciAccNamStg.startswith("ansiblebu"))
        ):
            bMetaProdRepo = "redhat-cop/agnosticd"
            bMetaRepo = ''
            # Getting tag value from __meta__ section
            bMetaTag = ''
            if 'deployer' in c['__meta__']:
                deployer = c['__meta__']['deployer']
                if 'scm_ref' in deployer:
                    bMetaTag = deployer['scm_ref']
                elif 'git_tag_prefix' in deployer:
                    bMetaTag = deployer['git_tag_prefix']
                if 'scm_url' in deployer:
                    bMetaScmUrl = deployer['scm_url']
                    bMetaProdRepo = bMetaScmUrl.replace("https://github.com/","").replace(".git","")
                # Call Github API and check git tag on agnosticd repo
                bMetaRepo = bMetaProdRepo + "/git/matching-refs/tags/"
                bTagResponse = requests.get("https://api.github.com/repos/"+bMetaRepo+bMetaTag)
                if bTagResponse.status_code==200 and bTagResponse.json() is not None and len(bTagResponse.json())<1:
                    raise ValueError(
                        '''No such git tag exist on agnosticd provided under __meta__: ''' + bMetaTag
                    )

    return True

def check_anarchy_namespace(c,ci):
    '''Ensure catalog item have anarchy namespace'''

    if '__meta__' in c and 'agnosticv_meta' in c:
        if 'deploy_with' in c['agnosticv_meta'] and c['agnosticv_meta']['deploy_with'] == "babylon":
            if ('anarchy' in c['__meta__']):
                anarchyObj = c['__meta__']['anarchy']
                if ('namespace' in anarchyObj):
                    anarchynamespace = anarchyObj['namespace']
                    if not anarchynamespace:
                        raise ValueError(
                            '''__meta__.anarchy and __meta__.anarchy.namespace can't be blank'''
                        )
                else:
                    raise ValueError(
                        '''__meta__.anarchy and __meta__.anarchy.namespace can't be blank'''
                    )
            else:
                raise ValueError(
                    '''__meta__.anarchy can't be blank, plaese add __meta__.anarchy.namespace'''
                )
            # Checking for parameters
            if ('catalog' in c['__meta__']):
                catalogObj = c['__meta__']['catalog']
                if ('parameters' not in catalogObj):
                    raise ValueError(
                        '''__meta__.catalog and __meta__.catalog.parameters can't be blank'''
                    )
            else:
                raise ValueError(
                    '''__meta__.catalog can't be blank, plaese add __meta__.catalog.parameters'''
                )

    return True

for ci in catalog_items:
    ci = ci.strip()
    process_ci = subprocess.run(
        [str(args.agnosticv_cli), '--merge', ci],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=True,
    )

    ci_object = yaml.safe_load(process_ci.stdout)
    passed = True
    exceptions = {}
    for f in [check_double_booking,check_name,check_tag_var,check_valid_agv_tag,check_valid_babylon_tag,check_anarchy_namespace,check_virtualenv,check_duplicate_directories]:
        try:
            if not f(ci_object,ci):
                passed = False
                if str(f) in exceptions:
                    exceptions[str(f)].append("Did not pass test")
                else:
                    exceptions[str(f)] = ["Did not pass test"]

        except Exception as exc:
            passed = False
            if str(f) in exceptions:
                exceptions[str(f)].append(exc)
            else:
                exceptions[str(f)] = [exc]

    if not passed:
        invalid.append([ci, exceptions])
        if args.debug:
            print('F', end='', flush=True)
    else:
        valid.append(ci)
        if args.debug:
            print('.', end='', flush=True)

print()
print("Valid: %d" %(len(valid)))
print("Invalid: %d" %(len(invalid)))


for ci in invalid:
    print()
    print('#'*80)
    print()
    print(ci[0])
    for f_str in ci[1].keys():
        print()
        print('Failed passing babylon tests %s:' %(f_str))
        print()
        for exception in ci[1][f_str]:
            print(exception)

if len(invalid) > 0:
    sys.exit(2)

sys.exit(0)
