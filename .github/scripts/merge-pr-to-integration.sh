#!/usr/bin/env bash

set -o pipefail
git config --local user.email "rhpds-bot@redhat.com"
git config --local user.name "rhpds-bot"
git checkout integration
git pull
# Merge PR branch as a squashed merge commit
set +e
git merge \
    --no-edit \
    --squash \
    -X theirs \
    "origin/${GITHUB_HEAD_REF}" 2>&1 \
    | tee -a /tmp/merge.log

if [ $? != 0 ]; then

    # Try to resolve conflicts

    # Delete files deleted in their branch
    git status --porcelain \
        | grep -E '^UD' \
        | cut -d' ' -f 1 --complement \
        | while read -r i; do
        git rm "${i}"
    done

    # Add files updated in their branch which are deleted in ours
    git status --porcelain \
        | grep -E '^DU' \
        | cut -d' ' -f 1 --complement \
        | while read -r i; do
        git add "${i}"
    done

    # Add files added in their branch

    git status --porcelain \
        | grep -E '^UA' \
        | cut -d' ' -f 1 --complement \
        | while read -r i; do
        git add "${i}"
    done

    git commit -m "Auto-merge #${PR} into integration"

    if [ $? != 0 ]; then
        {
            echo 'Cannot merge `'${GITHUB_HEAD_REF}'` into `integration`:'
            echo
            echo '```'
            cat /tmp/merge.log
            echo '```'
        } > /tmp/comment.md
        gh pr comment ${PR} --body-file /tmp/comment.md
        exit 1
    fi
fi

if [ $(git diff --cached | wc -c) != 0 ]; then
    git commit -m "Auto-merge #${PR} into integration"
fi
git push
