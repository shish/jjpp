from abc import ABC, abstractmethod
from typing import Optional


class ForgeException(Exception):
    """Base exception for forge-related errors."""

    pass


class Forge(ABC):
    def __init__(self, remote_url: str):
        self.remote_url = remote_url

    @abstractmethod
    def push(self, ref: str) -> None:
        """Push changes to the forge."""
        pass

    @abstractmethod
    def pull(self, identifier: Optional[str] = None) -> None:
        """Pull changes from the forge."""
        pass

    @abstractmethod
    def list(self) -> None:
        """List items on the forge."""
        pass

    def pre_commit(self, ref: str) -> None:
        """Run pre-commit hooks."""
        pass
