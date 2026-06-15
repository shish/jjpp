# JJ Push / Puller

Because I'm regularly using github, gerrit, and phabricator, and I don't like any of their standard `git` workflows (and then I go ahead and use `jj`, which has *much* better client-side UX, but the forge integrations are even less-well-supported...)

I really just want `jj pull` to bring me up to date with remote changes, and `jj push` to push my local changes for review - automatically Doing The Right Thing (eg updating existing reviews vs creating new ones), working consistently across forges.


## Features

* `jjpp push` - push current stack to the forge
  * updates existing PR/CRs/Diffs if they exist
  * creates new ones if not
  * gerrit & phabricator create a review for each commit in the stack
  * github will create a new `pr/XYZ` branch, send that branch for review, and update that branch on subsequent pushes
  * `jjpp push <change id>` - push an individual commit
* `jjpp pull` - pull remote trunk and rebase local stack on top of it
  * `jjpp pull --all` - pull trunk and rebase all local stacks
* `jjpp list` - list my open PR/CR/Diffs
* `jjpp pre-commit` - run pre-commit hooks on all commits in the current stack
  * `jjpp pre-commit <change id>` - run pre-commit hooks on a specific change
* `jjpp checkout <pr/cr/diff>` - pull a specific PR/CR/Diff from the forge


## Workflow

For convenience I have aliases in my `jj` config file so that eg `jj push`
will call `jjpp push`, etc. From there, my workflow is usually:

* `jj pull --all` - start the day by pulling remote changes and rebasing all my local stacks on top of them
* `jj list` - check for any reviews which need attention
* If any of my code needs to be changed based on feedback
  * `jj edit <change id>` - switch to the change that needs to be updated
  * `vim ...` - make the changes
  * `jj push` - push an updated version of the commit for review
* If I want to work on a new feature
  * `jj new <base>` - create a new branch for the feature ("base" is usually `main` or `master`)
  * `vim ...` - make the changes
  * `jj describe` - set commit title and description
  * `jj push` - push the new branch for review
* If I want to test somebody else's code
  * `jj checkout <pr/cr/diff>` - pull a specific PR/CR/Diff from the forge


## Backend Notes

* `github` - requires `gh` CLI to be installed and configured
* `gerrit` - requires an API token to be set
* `phabricator` - requires `arc` CLI to be installed and configured


## Install

```sh
git clone https://github.com/shish/jjpp
cd jjpp
uv sync
ln -s $(pwd)/.venv/bin/jjpp ~/.local/bin/jjpp  # or somewhere in your $PATH
uv run pre-commit install                      # if you want to be editing jjpp itself
```

`~/.config/jj/config.toml`:
```toml
[aliases]
push       = ["util", "exec", "--", "jjpp", "push"]
pull       = ["util", "exec", "--", "jjpp", "pull"]
list       = ["util", "exec", "--", "jjpp", "list"]
pre-commit = ["util", "exec", "--", "jjpp", "pre-commit"]
checkout   = ["util", "exec", "--", "jjpp", "checkout"]
```
