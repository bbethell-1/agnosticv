#!/usr/bin/env python

import sys
import subprocess
import argparse
import requests

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

catalog_items = process_all.stdout.split()

if len(catalog_items) == 0:
    print("No catalog item found")
    sys.exit(2)

valid = []
invalid = []

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

def check_valid_agv_tag(c,ci):
    '''Ensure configuration is having a valid git tag or branch'''

    ciAccNamStg=ci[0:ci.rfind(".")].replace("/", ".")
    if '__meta__' in c or 'agnosticv_meta' in c:
        if (ciAccNamStg.endswith(".prod") or ciAccNamStg.endswith(".ilt") or ciAccNamStg.endswith(".test")):
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

for ci in catalog_items:
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
    for f in [check_double_booking,check_name,check_tag_var,check_valid_agv_tag]:
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
