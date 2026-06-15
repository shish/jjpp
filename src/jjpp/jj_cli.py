#!/usr/bin/env python3
"""CLI for jj utilities using Typer."""

import logging

import typer

from jjpp.jj import closest_work, current_stack, revset_to_changeid

log = logging.getLogger(__name__)

app = typer.Typer(help="Utilities for working with jj (Jujutsu) version control")


@app.callback(invoke_without_command=False)
def globals(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)


@app.command(name="closest-work")
def closest_work_cmd():
    result = closest_work()
    typer.echo(result)


@app.command(name="current-stack")
def current_stack_cmd():
    result = current_stack()
    for changeid in result:
        typer.echo(changeid)


@app.command(name="revset-to-changeid")
def revset_to_changeid_cmd(
    revset: str = typer.Argument(..., help="The revset expression to convert"),
):
    result = revset_to_changeid(revset)
    typer.echo(result)


def main():
    app()


if __name__ == "__main__":
    main()
