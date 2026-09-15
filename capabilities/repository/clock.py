
from datetime import datetime


class Clock:
    """Injected clock. Returns a fixed `as_of` time so cases are deterministic
    and never depend on the real wall clock (no datetime.now())."""

    def __init__(self, as_of: datetime):
        self._as_of = as_of

    def now(self) -> datetime:
        return self._as_of
