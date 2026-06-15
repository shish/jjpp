```
uv sync
uv run pre-commit install
```

* `jjpp pre-commit` - run pre-commit hooks on all changes in the current stack
* `jjpp pre-commit abcd` - run pre-commit hooks on a specific change
* `jjpp list` - list my open PR/CR/Diffs
* `jjpp pull <pr/cr/diff>` - pull a specific PR/CR/Diff from the forge
* `jjpp push` - push current stack to the forge, updating existing PR/CRs/Diffs if they exist, or creating new ones if not
* `jjpp sync` - pull remote trunk and rebase local stacks on top of it
