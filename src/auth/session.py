"""Minimal session token registry used by the Busleyden Guard proof."""


class SessionRegistry:
    def __init__(self) -> None:
        self._used_tokens: set[str] = set()

    def accept(self, token: str) -> bool:
        self._used_tokens.add(token)
        return True