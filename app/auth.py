"""Demo users. Hard-coded on purpose: this is a practice app, not a real system."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    username: str
    display_name: str
    role: str  # "trader" or "viewer"

    @property
    def can_trade(self) -> bool:
        return self.role == "trader"


_USERS = {
    "trader1": ("trader1pass", User("trader1", "Alex Rivera", "trader")),
    "trader2": ("trader2pass", User("trader2", "Jordan Lee", "trader")),
    "viewer1": ("viewer1pass", User("viewer1", "Sam Patel", "viewer")),
}


def authenticate(username: str, password: str) -> User | None:
    entry = _USERS.get(username.strip().lower())
    if entry and entry[0] == password:
        return entry[1]
    return None


def get_user(username: str) -> User | None:
    entry = _USERS.get(username)
    return entry[1] if entry else None
