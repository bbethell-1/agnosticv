#!/usr/bin/env bash
set -uo pipefail

if [ "$TRAVIS_PULL_REQUEST" = "false" ] ; then
    echo "Not a pull request."
    exit 0
fi

export PATH=$PWD:$PATH

json_escape () {
    printf '%s' "$1" | python -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

comment() {
    local data="$(json_escape "${1}")"
    body=$(mktemp)

    cat > $body <<EOF
{"body": ${data}}
EOF

    curl -s \
        -H "Authorization: token ${GITHUB_TOKEN}" \
        -X POST \
        --data @$body \
        "https://api.github.com/repos/${TRAVIS_REPO_SLUG}/issues/${TRAVIS_PULL_REQUEST}/comments"

    rm $body
}

temp1=$(mktemp)
temp2=$(mktemp)
difftemp=$(mktemp)
errtemp=$(mktemp)
changed=$(mktemp)
errors=$(mktemp)
changed_git=$(mktemp)
deleted_files=$(mktemp)

_cleanup_on_exit() {
    local exit_status=${1:-$?}

    rm $temp1
    rm $temp2
    rm $difftemp
    rm $changed
    rm $changed_git
    rm $errtemp
    rm $errors
    rm $deleted_files

    exit ${exit_status}
}

trap "_cleanup_on_exit" EXIT

git diff \
    --no-commit-id \
    --name-only \
    --diff-filter=AM \
    ${TRAVIS_BRANCH}...${TRAVIS_PULL_REQUEST_SHA} \
    | perl -pe 's/(account|common).ya?ml$//' \
    > ${changed_git}

git checkout $TRAVIS_PULL_REQUEST_SHA &>/dev/null

for i in $(agnosticv --list|grep -f ${changed_git}|grep -v '.travis.yml'); do
    git checkout $TRAVIS_PULL_REQUEST_SHA &>/dev/null
    if [ $? != 0 ]; then
        echo "ERROR git checkout  $TRAVIS_PULL_REQUEST_SHA" >> $errors
        continue
    fi

    agnosticv --merge $i > $temp1 2>$errtemp
    if [ $? != 0 ]; then
        echo "ERROR merging $i" >> $errors
        cat $errtemp >> $errors
        continue
    fi

    git checkout $TRAVIS_BRANCH &>/dev/null
    if [ $? != 0 ]; then
        echo "ERROR git checkout  $TRAVIS_BRANCH" >> $errors
        continue
    fi

    if [ ! -e "$i" ]; then
        echo "$i (new)" >> $changed
        continue
    fi

    agnosticv --merge $i > $temp2
    if [ $? != 0 ]; then
        echo "ERROR merging $i in branch $TRAVIS_BRANCH" >&2
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
    ${TRAVIS_BRANCH}...${TRAVIS_PULL_REQUEST_SHA} > $deleted_files

if [ $(wc -l < $deleted_files) -gt 0 ]; then
    read -r -d '' data << EOF
${data}

Deleted files:

\`\`\`
$(cat ${deleted_files})
\`\`\`
EOF
fi

if [ ! -z "${data}" ]; then
    comment "${data}"
fi

exit ${RC:-0}
