import typing as t
from dataclasses import asdict, dataclass, field
from io import StringIO

import httpx
from rich.console import Console
from rich.markup import escape

if t.TYPE_CHECKING:  # pragma: no cover
    from .base import Forge


@dataclass
class Title:
    text: str
    url: httpx.URL | None = None

    def __str__(self) -> str:
        return self.text

    def __rich__(self) -> str:
        t = escape(self.text)
        if self.url:
            t = f"[link={self.url}]{t}[/link]"
        return t


@dataclass
class Blocker:
    name: str
    color: str | None = None
    url: httpx.URL | None = None

    def __rich__(self) -> str:
        t = escape(self.name)
        if self.color:
            t = f"[{self.color}]{t}[/{self.color}]"
        if self.url:
            t = f"[link={self.url}]{t}[/link]"
        return t


@dataclass
class State:
    name: str
    color: str | None = None
    url: httpx.URL | None = None

    def __rich__(self) -> str:
        t = escape(self.name)
        if self.color:
            t = f"[{self.color}]{t}[/{self.color}]"
        if self.url:
            t = f"[link={self.url}]{t}[/link]"
        return t

    def __str__(self) -> str:
        buffer = StringIO()
        console = Console(file=buffer, force_terminal=True, color_system="truecolor")

        console.print(self, end="")

        return buffer.getvalue()


@dataclass
class CodeReview:
    forge: "Forge"
    cr_id: str
    title: Title
    state: State
    blockers: list[Blocker]
    extra: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "forge": self.forge.asdict(),
            "cr_id": self.cr_id,
            "title": asdict(self.title),
            "state": asdict(self.state),
            "blockers": [str(b) for b in self.blockers],
            "extra": {k: str(v) for k, v in self.extra.items()},
        }
