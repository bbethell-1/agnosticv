#!/usr/bin/env bash


set -o pipefail

git config --local user.email "rhpds-bot@redhat.com"
git config --local user.name "rhpds-bot"

git checkout integration
git pull

set +e

# Merge master (sync)

if ! git merge \
    --no-edit \
    --squash \
    -X theirs \
    "origin/master"; then

    # Try to resolve conflicts

    # Delete files deleted in their branch
    git status --porcelain \
        | grep -E '^UD' \
        | cut -d' ' -f 1 --complement \
        | while read -r i; do
        git rm "${i}"
    done

    # Add files added in their branch

    git status --porcelain \
        | grep -E '^UA' \
        | cut -d' ' -f 1 --complement \
        | while read -r i; do
        git add "${i}"
    done

    git commit -m "Auto-merge #${PR} into integration"
fi

if [ $(git diff --cached | wc -c) != 0 ]; then
    git commit -m "Auto-merge master into integration"
fi
git push
