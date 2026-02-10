
# CommitV Claude Skill

## Overview

CommitV is a Claude skill that generates conventional commit messages.

## Basic Usage

```bash
claude -p "/commitv" --output-format text
```

## MacOS with Clipboard Copy/Paste

Copy the generated commit message and prepare a git commit command:

```bash
commitv='output=$(claude -p "/commitv" --output-format text); printf "%s\n" "$output"; printf "%s" "git commit -m \"$output\"" | pbcopy'
```

Run the alias and paste into your terminal:

```bash
$commitv
```

The commit message will be copied to your clipboard for easy use with `git commit`.
