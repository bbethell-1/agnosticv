#!/usr/bin/env bash

merge_squash() {
    if ! git merge \
        --no-edit \
        --squash \
        -X theirs \
        master; then

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

        git commit -m "Auto-merge master into integration"
    fi

    if [ $(git diff --cached | wc -c) != 0 ]; then
        git commit -m "Auto-merge master into integration"
    fi

}


set -o pipefail

git config --local user.email "rhpds-bot@redhat.com"
git config --local user.name "rhpds-bot"

git checkout integration
git pull

set +e

# Merge master (sync)

# Merge master into integration, prefer master
merge_squash

if [ "${FORCE_SYNC}" = "true" ]; then
    if [ "$(git diff master integration | wc -c)" != 0 ]; then

        # Merge integration into master but prefer master
        git checkout master
        git merge --no-edit -s ours integration

        # Merge master into integration, prefer master
        git checkout integration
        merge_squash
    fi
fi

# Push only integration
git push origin integration
