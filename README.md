# JJ Forge Integration

Because I'm regularly using github, gerrit, and phabricator, and I don't like any of their standard `git` workflows (and then I go ahead and use `jj`, which has *much* better client-side UX, but the forge integrations are even less-well-supported...)

I really just want `jj pr pull` to bring me up to date with remote changes, and `jj pr push` to push my local changes for review - automatically Doing The Right Thing (eg updating existing reviews vs creating new ones), working consistently across forges.

## Features

* `jj pr pull` - pull remote trunk and rebase current stack on top of it
  * `jj pr pull --all` - pull trunk and rebase all local stacks
* `jj pr push` - push current stack to the forge
  * updates existing PR/CRs/Diffs if they exist
  * creates new ones if not
  * gerrit & phabricator create a review for each commit in the stack
  * github will create a new `pr/XYZ` branch, send that branch for review, and update that branch on subsequent pushes
  * `jj pr push <change id>` - push an individual commit
* `jj pr list` - list open PRs/CRs/Diffs for the current project
  * `jj pr list --all-projects` - list open CRs/Diffs for all projects on the forge 
* `jj pr pre-commit` - run pre-commit hooks on all commits in the current stack
  * `jj pr pre-commit <change id>` - run pre-commit hooks on a specific change
* `jj pr checkout <pr/cr/diff>` - pull a specific PR/CR/Diff from the forge

## Workflow

* `jj pr pull --all` - start the day by pulling remote changes and rebasing all my local stacks on top of them
* `jj pr list` - check for any reviews which need attention

### If I want to work on a new feature

* `jj new 'trunk()'` - create a new branch off of trunk (ie, `main` or `master`)
* `vim ...` - make some changes
* `jj commit` - commit the first unit of work
* `vim ...` - make more changes
* `jj commit` - commit the next unit of work
* `jj pr push` - push the two commits for review

### If any of my code needs to be changed based on feedback

* `jj edit <change id>` - switch to the change that needs to be updated
* `vim ...` - make the changes
* `jj pr push -m 'fixed the bugs'` - push an updated version of the commit for review, with a comment listing what changed since last time

#### If I want to test somebody else's code

* `jj pr checkout <pr/cr/diff>` - pull a specific PR/CR/Diff from the forge

## Backend Notes

* `github` - requires `gh` CLI to be installed and configured
* `gerrit` - requires an API token to be set in `~/.netrc`
* `phabricator` - requires `arc` CLI to be installed and configured

## Install

```sh
git clone https://github.com/shish/jj-pr
cd jj-pr
uv sync
jj config set --user aliases.pr "['util', 'exec', '--', '$(pwd)/.venv/bin/jj-pr']"

# if you want to be hacking on jj-pr itself
uv run prek install
```
