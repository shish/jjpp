import json
import logging
import re
import typing as t
from pathlib import Path

import httpx

from ... import exc
from ...utils import exec, git, jj
from ..base import CRListItem, Forge
from .client import PhabricatorClient

log = logging.getLogger(__name__)

PhRev = int
PhID = str


class Phabricator(Forge):
    def __init__(self, remote: str):
        super().__init__(remote)
        try:
            self.repo_config = json.loads(Path(".arcconfig").read_text())
            self.forge_url = httpx.URL(self.repo_config["phabricator.uri"])
            self.project_id = self.repo_config["repository.callsign"]
            self.merge_target = self.repo_config.get(
                "arc.land.onto.default", git.get_merge_target()
            )
            self.client = PhabricatorClient(self.forge_url)
        except Exception as e:
            raise exc.UserError(f"Error loading repo config from .arcconfig: {e}")

    def push_cr(
        self,
        ref: str | None,
        draft: bool = False,
        message: str | None = None,
    ) -> None:
        changes = jj.change_id(ref) if ref else jj.pushable_stack()
        log.info(f"Pushing {ref} ({changes})")
        for change_id in changes:
            self._push_one(change_id, draft=draft, message=message)

    def _push_one(
        self,
        change_id: str,
        draft: bool = False,
        message: str | None = None,
    ) -> None:
        log.info(f"Pushing {change_id}")
        rev = self._change_to_revision(change_id)
        if rev:
            log.info(f"Updating revision D{rev} for {change_id}")
        else:
            log.info(f"Creating new revision for {change_id}")

        # to-do list
        data: dict[str, t.Any] = {
            "transactions": [],
        }

        # Update an existing revision, if we have one
        # (if not we'll create a new one)
        if rev:
            data["objectIdentifier"] = self._revision_to_phid(rev)

        # Attach a diff
        diff_id = self.client.call(
            "differential.createrawdiff",
            diff=jj.run("diff", "--git", "-r", change_id),
            repositoryPHID=self._callsign_to_phid(self.project_id),
        )["phid"]
        data["transactions"].append({"type": "update", "value": diff_id})

        # Set parent diff if our parent commit contains a diff ID
        parents = jj.change_ids(f"{change_id}- & mutable()")
        parent_revs = [self._change_to_revision(p) for p in parents]
        parent_revs = [p for p in parent_revs if p is not None]
        parent_phids = [self._revision_to_phid(p) for p in parent_revs]
        if parent_phids:
            data["transactions"].append({"type": "parents.set", "value": parent_phids})

        # If we're creating a new rev, populate the metadata from the commit message
        if not rev:
            ts = self.client.call(
                "differential.parsecommitmessage",
                corpus=jj.description_of(change_id),
            )["transactions"]
            for r in {"title", "summary", "testPlan"}:
                for t in ts:
                    if t["type"] == r:
                        break
                else:
                    data["transactions"].append({"type": r, "value": "-"})
            data["transactions"].extend(ts)

        # If --draft, set that flag
        if draft:
            data["transactions"].append({"type": "draft", "value": "true"})

        # Submit the new revision
        revision_id = self.client.call(
            "differential.revision.edit",
            **data,
        )["object"]["id"]

        # TODO: add a message if -m is passed

        # If the Change didn't have a Revision already, attach it
        if not rev:
            jj.describe(
                r=change_id,
                m=(
                    jj.description_of(change_id)
                    + f"\n\nDifferential Revision: {self.forge_url}/D{revision_id}"
                ),
            )
            print(f"Created revision {self.forge_url}/D{revision_id} for {change_id}")
        else:
            print(f"Updated revision {self.forge_url}/D{revision_id} for {change_id}")

    def _change_to_revision(self, change_id: jj.ChangeID) -> PhRev | None:
        d = jj.description_of(change_id)
        if m := re.search(r"Differential Revision:.*D(\d+)", d):
            return int(m.group(1))
        return None

    def _revision_to_phid(self, revision: PhRev) -> PhID:
        result = self.client.call(
            "differential.revision.search",
            constraints={"ids": [revision]},
        )
        if not result["data"]:
            raise exc.UserError(f"Revision D{revision} not found")
        return result["data"][0]["phid"]

    def _callsign_to_phid(self, callsign: str) -> PhID:
        return self.client.call(
            "diffusion.repository.search",
            constraints={"callsigns": [callsign]},
        )["data"][0]["phid"]

    def checkout_cr(self, identifier: str) -> None:
        log.info(f"Checking out Phabricator diff {identifier}")
        exec.run(["arc", "patch", identifier], cap=False)

    def list_crs(self, all_projects: bool = False) -> list[CRListItem]:
        log.info(
            f"Listing diffs for {self.remote_url} ({'*' if all_projects else self.project_id})"
        )

        myPHID = self.client.call("user.whoami")["phid"]
        rev_constraints = {
            "authorPHIDs": [myPHID],
            "statuses": [
                "draft",
                "needs-review",
                "needs-revision",
                "accepted",
                "changes-planned",
            ],
        }
        if not all_projects:
            rev_constraints["repositoryPHIDs"] = [
                self._callsign_to_phid(self.project_id)
            ]
        revs = self.client.call(
            "differential.revision.search",
            constraints=rev_constraints,
        )["data"]

        return [
            CRListItem(
                forge_name="Phabricator",
                forge_url=self.forge_url,
                project_id=self.project_id,
                identifier=str(rev["id"]),
                title=rev["fields"]["title"],
                url=httpx.URL(rev["fields"]["uri"]),
                state=_colour_state(rev["fields"]["status"]["name"]),
                blockers="",
            )
            for rev in revs
        ]


def _colour_state(state: str) -> str:
    s2c = {
        "Draft": "cyan",
        "Changes Planned": "cyan",
        "Rejected": "red",
        "Needs Review": "yellow",
        "Accepted": "green",
    }
    c = s2c.get(state, "yellow")
    return f"[{c}]{state}[/{c}]"
