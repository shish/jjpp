import logging
import shlex
import subprocess
import typing as t

log = logging.getLogger(__name__)


@t.overload
def run(cmd: list[str], cap: t.Literal[True]) -> str: ...


@t.overload
def run(cmd: list[str], cap: t.Literal[False]) -> None: ...


@t.overload
def run(cmd: list[str]) -> str: ...


def run(cmd: list[str], cap: bool = True) -> str | None:
    try:
        if not cap:
            log.debug(f"run({shlex.join(cmd)}) -> ...")
        result = subprocess.run(
            cmd,
            capture_output=cap,
            text=True,
            check=True,
        )
        if cap:
            rs = result.stdout.strip()
            if "\n" in rs:
                log.debug(f"run({shlex.join(cmd)}) -> \n{rs}")
            else:
                log.debug(f"run({shlex.join(cmd)}) -> {rs!r}")
            return rs
        else:
            return None
    except subprocess.CalledProcessError as e:
        log.info(f"run({shlex.join(cmd)}) failed")
        log.debug(f"Return code: {e.returncode}")
        if cap:
            log.debug(f"stdout: {e.stdout.strip()}")
            log.debug(f"stderr: {e.stderr.strip()}")
        raise
