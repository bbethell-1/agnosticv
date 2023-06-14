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

    agnosticv --merge $i > $temp1 2>$errtemp
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

    agnosticv --merge $i > $temp2
    if [ $? != 0 ]; then
        echo "ERROR merging $i in branch $ORIG_REF" >&2
        # assuming it changed
        echo $i >> $changed
        continue
    fi

    if ! diff -u $temp2 $temp1 > $difftemp; then
        echo $i >> $changed
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

if [ ! -z "${data}" ]; then
    comment "${data}"
fi

exit ${RC:-0}
