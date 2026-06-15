from typing import Optional


class GlobalOptions:
    def __init__(self, forge: Optional[str] = None, remote: str = "origin"):
        self.forge = forge
        self.remote = remote
