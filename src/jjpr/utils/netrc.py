import logging
import netrc
from pathlib import Path

log = logging.getLogger(__name__)


def read(hostname: str) -> tuple[str, str] | None:
    try:
        rc = netrc.netrc()
    except (FileNotFoundError, netrc.NetrcParseError) as e:
        log.warning(f"Could not get creds from netrc file: {e}")
        return None

    auth = rc.authenticators(hostname)
    if not auth:
        log.warning(f"No credentials found in netrc for {hostname}")
        return None

    login, _, password = auth
    if not password:
        log.warning(f"Empty password in netrc for {hostname}")
        return None

    return (login, password)


def write(hostname: str, login: str, password: str) -> None:
    rc_path = Path.home() / ".netrc"
    # Append to existing file or create new one
    with rc_path.open("a") as f:
        f.write(f"machine {hostname}\nlogin {login}\npassword {password}\n")
    # Ensure proper permissions
    rc_path.chmod(0o600)
