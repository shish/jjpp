import json
import logging
from pathlib import Path
from typing import Any, List, Optional

import requests
from rich.pretty import pretty_repr

from .. import jj, utils
from .base import CRListItem, Forge

log = logging.getLogger(__name__)


class PhabricatorSession(requests.Session):
    """HTTPAdapter that automatically adds api.token to POST request data."""

    def __init__(self, token: str, *args, **kwargs):
        self.token = token
        super().__init__(*args, **kwargs)

    @staticmethod
    def _flatten_params(base: Optional[str], formed_params: dict, params: dict) -> None:
        for key, value in params.items():
            if base:
                new_key = f"{base}[{key}]"
            else:
                new_key = key
            if isinstance(value, dict):
                PhabricatorSession._flatten_params(new_key, formed_params, value)
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    PhabricatorSession._flatten_params(
                        new_key, formed_params, {str(i): item}
                    )
            else:
                formed_params[new_key] = value

    def post(
        self,
        url: str,
        *args,
        data: Optional[dict[str, Any]] = None,
        **kwargs,
    ) -> requests.Response:
        formed_params = {
            "api.token": self.token,
        }
        self._flatten_params(None, formed_params, data or {})
        return super().post(url, data=formed_params, *args, **kwargs)


class Phabricator(Forge):
    @property
    def session(self) -> requests.Session:
        token = None
        arc_conf = Path.home() / ".arcrc"
        if arc_conf.exists():
            with open(arc_conf) as f:
                data = json.load(f)
            token = data.get("hosts", {}).get(self.forge_url, {}).get("token")
        if not token:
            raise utils.UserError(
                "Phabricator API token not found. Configure it in ~/.arcrc"
            )
        return PhabricatorSession(token)

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

    def _request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{self.forge_url}/api/{endpoint}"
        log.debug(f"Making request to {url}:\n{pretty_repr(params)}")
        response = self.session.post(url, data=params)
        response.raise_for_status()
        result = response.json()
        log.debug(f"Response from {url}:\n{pretty_repr(result)}")
        if result.get("error_code"):
            raise utils.UserError(
                f"Phabricator API error: {result['error_code']} - {result.get('error_info')}"
            )
        return result["result"]

    def push(
        self,
        ref: Optional[str],
        draft: bool = False,
        message: Optional[str] = None,
    ) -> None:
        changes = (
            [jj.revset_to_changeid(ref)]
            if ref
            else jj.current_stack(require_description=True)
        )
        for change_id in changes:
            with jj.with_new(change_id):
                log.info(f"Pushing {change_id}")
                args = ["arc", "diff", "HEAD^"]
                if draft:
                    args.append("--draft")
                if message:
                    args.extend(["--message", message])
                utils.run(args, cap=False)

    def checkout(self, identifier: str) -> None:
        log.info(f"Checking out Phabricator diff {identifier}")
        utils.run(["arc", "patch", identifier], cap=False)

    def list(self, all_projects: bool = False) -> List[CRListItem]:
        log.info(
            f"Listing diffs for {self.remote_url} ({'*' if all_projects else self.project_id})"
        )

        myPHID = self._request("user.whoami")["phid"]
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
                self._request(
                    "diffusion.repository.search",
                    params={"constraints": {"callsigns": [self.project_id]}},
                )["data"][0]["phid"]
            ]
        revs = self._request(
            "differential.revision.search",
            params=rev_constraints,
        )["data"]

        return [
            CRListItem(
                forge_name="Phabricator",
                forge_url=self.forge_url,
                project_id=self.project_id,
                identifier=str(rev["id"]),
                title=rev["fields"]["title"],
                url=rev["fields"]["uri"],
                state=self._colour_state(rev["fields"]["status"]["name"]),
                blockers="",
            )
            for rev in revs
        ]

    def _colour_state(self, state: str) -> str:
        s2c = {
            "Draft": "cyan",
            "Changes Planned": "cyan",
            "Rejected": "red",
            "Needs Review": "yellow",
            "Accepted": "green",
        }
        c = s2c.get(state, "yellow")
        return f"[{c}]{state}[/{c}]"
