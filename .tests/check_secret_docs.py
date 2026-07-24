#!/usr/bin/env python3
"""Check that every vault-encrypted variable in secret files has mandatory
# @field: documentation comments immediately above it.

Usage:
    check_secret_docs.py FILE [FILE ...]
    check_secret_docs.py --from-stdin        # reads file paths from stdin, one per line

Exit codes:
    0  All vault variables are documented
    1  Argument error
    2  Documentation errors found
"""

import re
import sys
from datetime import datetime

REQUIRED_FIELDS = ('owner', 'purpose', 'impact', 'expiration', 'rotation', 'source', 'exposure')
VALID_IMPACT_LEVELS = ('HIGH', 'MEDIUM', 'LOW')
FIELD_RE = re.compile(r'^\s*#\s*@(\w+):\s*(.+)$')
VAULT_RE = re.compile(r'^\s*(\S+):\s*!vault\s*\|')


def parse_file(filepath):
    """Parse a secret file and return a list of (var_name, line_number, fields_dict)
    for each vault-encrypted variable found."""
    variables = []
    current_fields = {}

    try:
        with open(filepath) as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return variables

    for lineno, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip()

        field_match = FIELD_RE.match(line)
        if field_match:
            key = field_match.group(1).lower()
            value = field_match.group(2).strip()
            current_fields[key] = value
            continue

        vault_match = VAULT_RE.match(line)
        if vault_match:
            var_name = vault_match.group(1)
            variables.append((var_name, lineno, dict(current_fields)))
            current_fields = {}
            continue

        # Non-@ comment or blank line: keep accumulating (don't reset).
        # A YAML key that is NOT vault resets the block.
        stripped = line.lstrip()
        if stripped and not stripped.startswith('#') and not stripped.startswith('---'):
            current_fields = {}

    return variables


def is_unknown(value):
    """Return True if the value is the special UNKNOWN placeholder."""
    return value.strip().upper() == 'UNKNOWN'


def validate_expiration(value):
    """Return an error string if the expiration value is invalid, else None."""
    if value.lower() == 'never' or is_unknown(value):
        return None
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        return f'invalid @expiration: "{value}" (use YYYY-MM-DD or "never")'
    return None


def validate_impact(value):
    """Return an error string if the impact value is invalid, else None."""
    if is_unknown(value):
        return None
    for level in VALID_IMPACT_LEVELS:
        if value.startswith(level):
            return None
    return f'invalid @impact: must start with HIGH, MEDIUM, or LOW (or UNKNOWN)'


def check_variable(var_name, lineno, fields):
    """Return a list of error strings for this variable."""
    errors = []

    missing = [f for f in REQUIRED_FIELDS if f not in fields]
    if missing:
        errors.append(f'missing: @{", @".join(missing)}')
        # Don't validate format of fields that are missing
        fields_to_validate = {k: v for k, v in fields.items() if k in REQUIRED_FIELDS}
    else:
        fields_to_validate = fields

    if 'impact' in fields_to_validate:
        err = validate_impact(fields_to_validate['impact'])
        if err:
            errors.append(err)

    if 'expiration' in fields_to_validate:
        err = validate_expiration(fields_to_validate['expiration'])
        if err:
            errors.append(err)

    return errors


def check_files(filepaths):
    """Check all files and return (total_errors, output_lines)."""
    total_errors = 0
    output = []

    for filepath in filepaths:
        variables = parse_file(filepath)

        if not variables:
            continue

        file_errors = []
        for var_name, lineno, fields in variables:
            errors = check_variable(var_name, lineno, fields)
            if errors:
                file_errors.append((var_name, lineno, errors))

        if file_errors:
            output.append(f'ERROR: {filepath}')
            for var_name, lineno, errors in file_errors:
                for err in errors:
                    output.append(f'  {var_name} (line {lineno}): {err}')
            output.append('')
            total_errors += len(file_errors)

    return total_errors, output


def main():
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} FILE [FILE ...]\n'
              f'       {sys.argv[0]} --from-stdin', file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == '--from-stdin':
        filepaths = [line.strip() for line in sys.stdin if line.strip()]
    else:
        filepaths = sys.argv[1:]

    total_errors, output = check_files(filepaths)

    if total_errors > 0:
        for line in output:
            print(line)
        print(f'{total_errors} undocumented vault variable(s) found.\n')
        print(f'Required fields: @{", @".join(REQUIRED_FIELDS)}')
        print('See includes/secrets/TEMPLATE.yaml for the required format.')
        sys.exit(2)


if __name__ == '__main__':
    main()