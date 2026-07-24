#!/usr/bin/env bash
#
GITHUB_TOKEN="${RHPDS_BOT_REPO:-}"

set -uo pipefail

ORIG=$(cd $(dirname $0); pwd)

export PATH=$PWD:$PATH

json_escape () {
    printf '%s' "$1" | python -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

comment() {
    local data="$(json_escape "${1}")"
    body=$(mktemp)

    if [ -z "${GITHUB_TOKEN}" ]; then
        echo "GITHUB_TOKEN empty" >&2
        return
    fi

    cat > $body <<EOF
{"body": ${data}}
EOF

    curl -s \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        -X POST \
        --data @$body \
        "${GITHUB_API_URL}/repos/${GITHUB_REPOSITORY}/issues/${PULL_NO}/comments"

    rm $body
}

temp1=$(mktemp)
temp2=$(mktemp)
difftemp=$(mktemp)
errtemp=$(mktemp)
changed=$(mktemp)
errors=$(mktemp)
changed_git=$(mktemp)
changed_ci=$(mktemp)
changed_ci_uniq=$(mktemp)
deleted_files=$(mktemp)
schema_output=$(mktemp)
babylon_checks_output=$(mktemp)

_cleanup_on_exit() {
    local exit_status=${1:-$?}

    rm $temp1
    rm $temp2
    rm $difftemp
    rm $changed
    rm $changed_git
    rm $changed_ci
    rm $changed_ci_uniq
    rm $errtemp
    rm $errors
    rm $deleted_files
    rm $schema_output

    exit ${exit_status}
}

set -e

trap "_cleanup_on_exit" EXIT

PULL_REF=${GITHUB_SHA}
ORIG_REF=$( git show -s --pretty=format:"%H" remotes/origin/${GITHUB_BASE_REF})
PULL_NO=${GITHUB_REF##refs/pull/}
PULL_NO=${PULL_NO///merge}

git diff \
    --no-commit-id \
    --name-only \
    --diff-filter=AM \
    ${ORIG_REF}...${PULL_REF} \
    > ${changed_git}

# add related files
for f in $(cat ${changed_git}); do
    agnosticv --list --related $f >> ${changed_ci} 2>>$errors
done

sort ${changed_ci} | uniq > ${changed_ci_uniq}

git checkout $PULL_REF &>/dev/null

set +e

for i in $(cat ${changed_ci_uniq}); do
    git checkout $PULL_REF &>/dev/null
    if [ $? != 0 ]; then
        echo "ERROR git checkout  ${PULL_REF}" >> $errors
        continue
    fi

    agnosticv --git=false --merge $i | sed '/^#/d' > $temp1 2>$errtemp
    if [ $? != 0 ]; then
        # remove schema output as it's too verbose
        sed -i '/^Schema:/,/^Value:/d' $errtemp

        echo "ERROR merging $i" >> $errors
        cat $errtemp >> $errors
        continue
    fi

    git checkout $ORIG_REF &>/dev/null
    if [ $? != 0 ]; then
        echo "ERROR git checkout  $ORIG_REF" >> $errors
        continue
    fi

    if [ ! -e "$i" ]; then
        echo "$i (new)" >> $changed
        continue
    fi

    agnosticv --git=false --merge $i | sed '/^#/d' > $temp2
    if [ $? != 0 ]; then
        echo "ERROR merging $i in branch $ORIG_REF" >&2
        # assuming it changed
        echo $i >> $changed
        continue
    fi

    if ! diff -u $temp2 $temp1 > $difftemp; then
        echo "${i}" >> $changed
    fi
done

data=''

if [  $(wc -l < $changed) -gt 0 ]; then
    read -r -d '' data << EOF
Catalog items modified by this change:

\`\`\`
$(cat $changed)
\`\`\`
EOF
fi

if [  $(wc -l < $errors) -gt 0 ]; then
    read -r -d '' data << EOF
${data}

:warning: Errors:

\`\`\`
$(cat $errors)
\`\`\`
EOF

    RC=2
fi

git diff \
    --no-commit-id \
    --name-only \
    --diff-filter=D \
    ${ORIG_REF}...${PULL_REF} > $deleted_files

if [ $(wc -l < $deleted_files) -gt 0 ]; then
    read -r -d '' data << EOF
${data}

Deleted files:

\`\`\`
$(cat ${deleted_files})
\`\`\`
EOF
fi

git checkout $PULL_REF &>/dev/null

${ORIG}/babylon_checks.py --from_file ${changed_ci_uniq} > ${babylon_checks_output}

if [ $? != 0 ]; then
    RC=2
    sync

    read -r -d '' data << EOF
${data}

Some catalog items do not pass Babylon checks:

\`\`\`
$(cat ${babylon_checks_output})
\`\`\`
EOF
fi

# Check secret documentation for changed secret files
secret_docs_output=$(mktemp)
changed_secrets=$(grep '^includes/secrets/.*\.yaml$' ${changed_git} || true)

if [ -n "${changed_secrets}" ]; then
    echo "${changed_secrets}" | ${ORIG}/check_secret_docs.py --from-stdin > ${secret_docs_output} 2>&1

    if [ $? != 0 ]; then
        RC=2
        sync

        read -r -d '' data << EOF
${data}

:lock: Secret documentation errors:

\`\`\`
$(cat ${secret_docs_output})
\`\`\`
EOF
    fi
fi

rm -f ${secret_docs_output}

# ci-inspector validation (informational — never fails the pipeline)
if command -v ci-inspector &>/dev/null; then
    ci_inspector_output=$(mktemp)
    for i in $(cat ${changed_ci_uniq}); do
        ci_name=$(basename $(dirname "$i"))
        stage=$(basename "$i" | sed 's/\.ya\?ml$//')
        merged_yaml=$(agnosticv --git=false --merge "$i" 2>/dev/null | sed '/^#/d')
        if [ -z "$merged_yaml" ]; then
            continue
        fi
        echo "$merged_yaml" | ci-inspector validate-merged - \
            --ci-name "$ci_name" \
            --stage "$stage" \
            --format table >> ${ci_inspector_output} 2>/dev/null
        echo "" >> ${ci_inspector_output}
    done

    if [ -s "${ci_inspector_output}" ]; then
        read -r -d '' data << EOF
${data}

:mag: Infrastructure validation:

\`\`\`
$(cat ${ci_inspector_output})
\`\`\`
EOF
    fi
    rm -f ${ci_inspector_output}
fi

if [ ! -z "${data}" ]; then
    comment "$(head -c 65535 <<< "${data}")"
fi

exit ${RC:-0}
