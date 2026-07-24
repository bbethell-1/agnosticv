#!/usr/bin/env python3
"""Tests for check_secret_docs.py — uses fixture files in fixtures/secrets/."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from check_secret_docs import parse_file, check_variable, check_files, validate_expiration, validate_impact, is_unknown

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures', 'secrets')


def fixture(name):
    return os.path.join(FIXTURES, name)


# ---------------------------------------------------------------------------
# Fixture-based integration tests: files that should PASS
# ---------------------------------------------------------------------------

class TestOKFixtures(unittest.TestCase):

    def _assert_clean(self, filename):
        total_errors, output = check_files([fixture(filename)])
        self.assertEqual(total_errors, 0, f'{filename} should pass:\n' + '\n'.join(output))

    def test_single_var(self):
        self._assert_clean('ok_single_var.yaml')

    def test_multi_var(self):
        self._assert_clean('ok_multi_var.yaml')

    def test_with_regular_comments(self):
        self._assert_clean('ok_with_regular_comments.yaml')

    def test_multiple_owners(self):
        self._assert_clean('ok_multiple_owners.yaml')

    def test_expiration_never(self):
        self._assert_clean('ok_expiration_never.yaml')

    def test_no_vault_vars_is_clean(self):
        self._assert_clean('no_vault_vars.yaml')

    def test_unknown_all_fields(self):
        self._assert_clean('ok_unknown_fields.yaml')

    def test_unknown_mixed_with_real_values(self):
        self._assert_clean('ok_unknown_mixed.yaml')

    def test_indented_vault_documented(self):
        self._assert_clean('ok_indented_vault.yaml')


# ---------------------------------------------------------------------------
# Fixture-based integration tests: files that should FAIL
# ---------------------------------------------------------------------------

class TestFailFixtures(unittest.TestCase):

    def _assert_fails(self, filename, expected_errors=None, expected_substring=None):
        total_errors, output = check_files([fixture(filename)])
        self.assertGreater(total_errors, 0, f'{filename} should fail but passed')
        if expected_errors is not None:
            self.assertEqual(total_errors, expected_errors,
                             f'{filename}: expected {expected_errors} errors, got {total_errors}:\n' + '\n'.join(output))
        if expected_substring is not None:
            joined = '\n'.join(output)
            self.assertIn(expected_substring, joined,
                          f'{filename}: expected "{expected_substring}" in output:\n{joined}')

    def test_no_docs(self):
        self._assert_fails('fail_no_docs.yaml', expected_errors=1, expected_substring='@owner')

    def test_missing_fields(self):
        self._assert_fails('fail_missing_fields.yaml', expected_errors=1, expected_substring='@impact')

    def test_bad_impact(self):
        self._assert_fails('fail_bad_impact.yaml', expected_errors=1, expected_substring='@impact')

    def test_bad_expiration(self):
        self._assert_fails('fail_bad_expiration.yaml', expected_errors=1, expected_substring='@expiration')

    def test_second_var_undocumented(self):
        self._assert_fails('fail_second_var_undocumented.yaml', expected_errors=1, expected_substring='secret_key')

    def test_docs_reset_by_plain_var(self):
        self._assert_fails('fail_docs_reset_by_plain_var.yaml', expected_errors=1, expected_substring='my_token')

    def test_indented_vault_no_docs(self):
        self._assert_fails('fail_indented_no_docs.yaml', expected_errors=1, expected_substring='ssh_key_data')


# ---------------------------------------------------------------------------
# Multiple files at once
# ---------------------------------------------------------------------------

class TestMultipleFiles(unittest.TestCase):

    def test_mixed_good_and_bad(self):
        total_errors, output = check_files([
            fixture('ok_single_var.yaml'),
            fixture('fail_no_docs.yaml'),
            fixture('ok_multi_var.yaml'),
        ])
        self.assertEqual(total_errors, 1)

    def test_all_good(self):
        good_files = [fixture(f) for f in os.listdir(FIXTURES) if f.startswith('ok_')]
        total_errors, output = check_files(good_files)
        self.assertEqual(total_errors, 0, 'All ok_ fixtures should pass:\n' + '\n'.join(output))

    def test_all_bad(self):
        bad_files = [fixture(f) for f in sorted(os.listdir(FIXTURES)) if f.startswith('fail_')]
        total_errors, output = check_files(bad_files)
        self.assertEqual(total_errors, len(bad_files),
                         f'Expected {len(bad_files)} errors:\n' + '\n'.join(output))

    def test_nonexistent_file_is_silent(self):
        total_errors, output = check_files(['/nonexistent/path.yaml'])
        self.assertEqual(total_errors, 0)


# ---------------------------------------------------------------------------
# Unit tests for validators
# ---------------------------------------------------------------------------

class TestValidateImpact(unittest.TestCase):

    def test_high(self):
        self.assertIsNone(validate_impact('HIGH - full access'))

    def test_medium(self):
        self.assertIsNone(validate_impact('MEDIUM - dev only'))

    def test_low(self):
        self.assertIsNone(validate_impact('LOW - test credentials'))

    def test_invalid_word(self):
        self.assertIsNotNone(validate_impact('critical - something'))

    def test_lowercase_rejected(self):
        self.assertIsNotNone(validate_impact('high - something'))

    def test_unknown(self):
        self.assertIsNone(validate_impact('UNKNOWN'))

    def test_unknown_case_insensitive(self):
        self.assertIsNone(validate_impact('Unknown'))


class TestValidateExpiration(unittest.TestCase):

    def test_valid_date(self):
        self.assertIsNone(validate_expiration('2027-01-15'))

    def test_never(self):
        self.assertIsNone(validate_expiration('never'))

    def test_never_case_insensitive(self):
        self.assertIsNone(validate_expiration('Never'))

    def test_freeform_text_rejected(self):
        self.assertIsNotNone(validate_expiration('next year'))

    def test_invalid_month(self):
        self.assertIsNotNone(validate_expiration('2027-13-01'))

    def test_unknown(self):
        self.assertIsNone(validate_expiration('UNKNOWN'))

    def test_unknown_case_insensitive(self):
        self.assertIsNone(validate_expiration('Unknown'))


# ---------------------------------------------------------------------------
# UNKNOWN placeholder
# ---------------------------------------------------------------------------

class TestUnknownPlaceholder(unittest.TestCase):

    def test_is_unknown_uppercase(self):
        self.assertTrue(is_unknown('UNKNOWN'))

    def test_is_unknown_lowercase(self):
        self.assertTrue(is_unknown('unknown'))

    def test_is_unknown_mixed_case(self):
        self.assertTrue(is_unknown('Unknown'))

    def test_is_unknown_with_whitespace(self):
        self.assertTrue(is_unknown('  UNKNOWN  '))

    def test_is_unknown_rejects_other(self):
        self.assertFalse(is_unknown('not known'))

    def test_all_unknown_fields_pass_validation(self):
        fields = {f: 'UNKNOWN' for f in ('owner', 'purpose', 'impact', 'expiration', 'rotation', 'source', 'exposure')}
        errors = check_variable('my_token', 10, fields)
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# Parser edge cases
# ---------------------------------------------------------------------------

class TestParserEdgeCases(unittest.TestCase):

    def test_fields_are_parsed_from_ok_single_var(self):
        variables = parse_file(fixture('ok_single_var.yaml'))
        self.assertEqual(len(variables), 1)
        name, lineno, fields = variables[0]
        self.assertEqual(name, 'quay_io_oauth_token')
        self.assertEqual(fields['owner'], 'Alice <alice@example.com>')
        self.assertEqual(fields['impact'], 'HIGH - leaked token grants full org admin on quay.io/rhpds')
        self.assertEqual(fields['expiration'], '2027-01-15')

    def test_multi_var_parses_independently(self):
        variables = parse_file(fixture('ok_multi_var.yaml'))
        self.assertEqual(len(variables), 2)
        self.assertEqual(variables[0][0], 'rosa_aws_access_key_id')
        self.assertEqual(variables[0][2]['impact'], 'LOW - read-only identifier, useless without the secret key')
        self.assertEqual(variables[1][0], 'rosa_aws_secret_access_key')
        self.assertEqual(variables[1][2]['impact'], 'HIGH - combined with the access key, grants full programmatic access')

    def test_regular_comments_dont_clobber_at_fields(self):
        variables = parse_file(fixture('ok_with_regular_comments.yaml'))
        self.assertEqual(len(variables), 1)
        self.assertEqual(variables[0][2]['owner'], 'Kevin Lewis <klewis@redhat.com>')
        self.assertEqual(len(variables[0][2]), 7)

    def test_plain_var_resets_accumulated_fields(self):
        variables = parse_file(fixture('fail_docs_reset_by_plain_var.yaml'))
        self.assertEqual(len(variables), 1)
        self.assertEqual(variables[0][2], {})

    def test_no_vault_vars_returns_empty(self):
        variables = parse_file(fixture('no_vault_vars.yaml'))
        self.assertEqual(variables, [])


if __name__ == '__main__':
    unittest.main()