"""Application errors."""


class UnresolvedPendingError(RuntimeError):
    """Raised where a rule depends on an open item (P-N in AGENTS.md) not decided yet."""

    def __init__(self, item: str, what: str) -> None:
        self.item = item
        super().__init__(f"{item} is unresolved: {what}. See the open items in AGENTS.md.")
