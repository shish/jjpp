import json
import logging
import re
from pathlib import Path
from typing import Any, List, Optional

import httpx

from .. import jj, utils
from .base import CRListItem, Forge

log = logging.getLogger(__name__)

PhRev = int
PhID = str


class PhabricatorClient(httpx.Client):
    """Custom httpx.Client for Phabricator.

    - Loads api.token from ~/.arcrc for the given base_url.
    - Adds api.token to POST request data.
    - Raises exceptions on HTTP errors
    """

    def __init__(self, base_url: httpx.URL):
        super().__init__(base_url=base_url.copy_with(path="/api/"))

        token = None
        arc_conf = Path.home() / ".arcrc"
        if arc_conf.exists():
            with open(arc_conf) as f:
                data = json.load(f)
            for url, config in data.get("hosts", {}).items():
                if httpx.URL(url).host == base_url.host:
                    token = config.get("token")
                    break
        if not token:
            raise utils.UserError(
                f"API token for {base_url.host} not found in ~/.arcrc"
            )
        self.token = token

    def request(self, *args, **kwargs) -> httpx.Response:
        response = super().request(*args, **kwargs)
        log.debug(
            f"{response.request.method}({response.request.url}) -> {response.text}"
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            e.add_note(e.response.text)
            raise
        js = response.json()
        if js.get("error_code"):
            raise Exception(
                f"Phabricator API error: {js['error_code']} - {js.get('error_info')}"
            )
        return response

    @staticmethod
    def _struct2http(base: Optional[str], formed_params: dict, params: dict) -> None:
        for key, value in params.items():
            if base:
                new_key = f"{base}[{key}]"
            else:
                new_key = key
            if isinstance(value, dict):
                PhabricatorClient._struct2http(new_key, formed_params, value)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    PhabricatorClient._struct2http(
                        new_key, formed_params, {str(i): item}
                    )
            else:
                formed_params[new_key] = value

    def post(
        self,
        url: str | httpx.URL,
        *args,
        data: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> httpx.Response:
        formed_params = {
            "api.token": self.token,
        }
        self._struct2http(None, formed_params, data or {})
        return super().post(url, data=formed_params, *args, **kwargs)


class Phabricator(Forge):
    def __init__(self, remote: str, remote_url: httpx.URL):
        super().__init__(remote, remote_url)
        self.client = PhabricatorClient(self.forge_url)

    @property
    def project_id(self) -> str:
        arcconfig_path = Path(".arcconfig")
        if arcconfig_path.exists():
            with open(arcconfig_path) as f:
                arcconfig = json.load(f)
            if callsign := arcconfig.get("repository.callsign"):
                return callsign
        raise utils.UserError(
            "Could not determine project ID. Ensure .arcconfig exists and has 'repository.callsign' set."
        )

    def push(
        self,
        ref: Optional[str],
        draft: bool = False,
        message: Optional[str] = None,
    ) -> None:
        changes = jj.specified_or_stack(ref, require_description=True)
        log.info(f"Pushing {ref} ({changes})")
        for change_id in changes:
            self._push_one(change_id, draft=draft, message=message)

    def _push_one(
        self,
        change_id: str,
        draft: bool = False,
        message: Optional[str] = None,
    ) -> None:
        log.info(f"Pushing {change_id}")
        rev = self._change_to_revision(change_id)
        if rev:
            log.info(f"Updating revision D{rev} for {change_id}")
        else:
            log.info(f"Creating new revision for {change_id}")

        parents = jj.change_ids(f"{change_id}- & mutable()")
        parent_revs = [self._change_to_revision(p) for p in parents]
        parent_revs = [p for p in parent_revs if p is not None]
        parent_phids = [self._revision_to_phid(p) for p in parent_revs]

        diff_id = self.client.post(
            "differential.createrawdiff",
            data={
                "diff": jj.run("diff", "--git", "-r", change_id),
                "repositoryPHID": self._callsign_to_phid(self.project_id),
            },
        ).json()["result"]["phid"]

        data: dict[str, Any] = {
            "transactions": [
                {"type": "update", "value": diff_id},
                {"type": "parents.set", "value": parent_phids},
            ],
        }

        if rev:
            data["objectIdentifier"] = self._revision_to_phid(rev)
        else:
            data["transactions"].extend(
                self.client.post(
                    "differential.parsecommitmessage",
                    data={"corpus": jj.description_of(change_id)},
                ).json()["result"]["transactions"]
            )

        if draft:
            data["transactions"].append({"type": "draft", "value": "true"})

        revision_id = self.client.post(
            "differential.revision.edit",
            data=data,
        ).json()["result"]["object"]["id"]

        # TODO: add a message if -m is passed
        if not rev:
            jj.describe(
                r=change_id,
                m=(
                    jj.description_of(change_id)
                    + f"\n\nDifferential Revision: {self.forge_url}/D{revision_id}"
                ),
            )

    def _change_to_revision(self, change_id: jj.ChangeID) -> Optional[PhRev]:
        d = jj.description_of(change_id)
        if m := re.search(r"Differential Revision:.*D(\d+)", d):
            return int(m.group(1))
        return None

    def _revision_to_phid(self, revision: PhRev) -> PhID:
        result = self.client.post(
            "differential.revision.search",
            params={"constraints": {"ids": [revision]}},
        ).json()["result"]
        if not result["data"]:
            raise utils.UserError(f"Revision D{revision} not found")
        return result["data"][0]["phid"]

    def _callsign_to_phid(self, callsign: str) -> PhID:
        return self.client.post(
            "diffusion.repository.search",
            params={"constraints": {"callsigns": [callsign]}},
        ).json()["result"]["data"][0]["phid"]

    def checkout(self, identifier: str) -> None:
        log.info(f"Checking out Phabricator diff {identifier}")
        utils.run(["arc", "patch", identifier], cap=False)

    def list(self, all_projects: bool = False) -> List[CRListItem]:
        log.info(
            f"Listing diffs for {self.remote_url} ({'*' if all_projects else self.project_id})"
        )

        myPHID = self.client.post("user.whoami").json()["result"]["phid"]
        rev_constraints = {
            "constraints": {
                "authorPHIDs": [myPHID],
                "statuses": [
                    "draft",
                    "needs-review",
                    "needs-revision",
                    "accepted",
                    "changes-planned",
                ],
            }
        }
        if not all_projects:
            rev_constraints["constraints"]["repositoryPHIDs"] = [
                self._callsign_to_phid(self.project_id)
            ]
        revs = self.client.post(
            "differential.revision.search",
            params=rev_constraints,
        ).json()["result"]["data"]

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
