#!/usr/bin/env python

import os
import sys
import shutil
import subprocess
import argparse

import yaml
import openapi_schema_validator

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
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

parser.add_argument('--schema_dir',
                    type=os.walk,
                    dest='schema_dir',
                    help='Directory containing openAPI v3.0 schema, in YAML format, used for data validation',
                    default='.schemas',
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

schemas = {}
for root, dirs, files in args.schema_dir:
    for name in files:
        try:
            schema = yaml.safe_load(open(os.path.join(root, name)).read())
            if name in schemas:
                print("Schema names must be unique, %s" %(name))
                sys.exit(2)

            schemas[name] = schema
            print("schema '%s' loaded" %(os.path.join(root, name)))
        except Exception as exc:
            print("Error loading schema %s" %(name))

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
for ci in catalog_items:
    try:
        process_ci = subprocess.run(
            [str(args.agnosticv_cli), '--merge', ci],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print()
        print("Error with %s" %(ci))
        print("%s" %(e))
        if e.stdout:
            print('<STDOUT>')
            print("%s" %(e.stdout), end='</STDOUT>\n')
        if e.stderr:
            print('<STDERR>')
            print("%s" %(e.stderr), end='</STDERR>\n')
        sys.exit(2)

    ci_object = yaml.safe_load(process_ci.stdout)
    failed = False
    exceptions = {}
    for schema in schemas:
        try:
            openapi_schema_validator.validate(ci_object, schemas[schema])
        except Exception as exc:
            failed = True
            if schema in exceptions:
                exceptions[schema].append(exc)
            else:
                exceptions[schema] = [exc]
    if failed:
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
    for schema in ci[1].keys():
        print()
        print('Failed passing schema %s:' %(schema))
        print()
        for exception in ci[1][schema]:
            print(exception)

if len(invalid) > 0:
    sys.exit(2)

sys.exit(0)
