"""Fair parking allocation: need first, then a transparent points score."""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass

NEEDS = ("standard", "accessible", "ev")
SPACE_TYPES = NEEDS


class DataError(ValueError):
    """Raised when an input file has a bad or missing value."""


@dataclass(frozen=True)
class Space:
    space_id: str
    type: str
    zone: str


@dataclass(frozen=True)
class Request:
    employee: str
    need: str
    carpool: bool
    weeks_waiting: int
    commute_miles: float


def score(req: Request) -> float:
    """Points: 2 per week waiting, 3 for carpooling, 1 per 10 commute miles (max 5)."""
    return 2 * req.weeks_waiting + (3 if req.carpool else 0) + min(req.commute_miles / 10, 5)


def _rows(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _need(row: dict, key: str, line: int) -> str:
    value = (row.get(key) or "").strip()
    if not value:
        raise DataError(f"line {line}: missing value for '{key}'")
    return value


def load_spaces(path: str) -> list[Space]:
    spaces, seen = [], set()
    for i, row in enumerate(_rows(path), start=2):
        sid = _need(row, "space_id", i)
        kind = _need(row, "type", i).lower()
        if kind not in SPACE_TYPES:
            raise DataError(f"line {i}: type '{kind}' is not one of {list(SPACE_TYPES)}")
        if sid in seen:
            raise DataError(f"line {i}: duplicate space_id '{sid}'")
        seen.add(sid)
        spaces.append(Space(sid, kind, _need(row, "zone", i)))
    return spaces


def load_requests(path: str) -> list[Request]:
    out, seen = [], set()
    for i, row in enumerate(_rows(path), start=2):
        name = _need(row, "employee", i)
        need = _need(row, "need", i).lower()
        if need not in NEEDS:
            raise DataError(f"line {i}: need '{need}' is not one of {list(NEEDS)}")
        carpool = _need(row, "carpool", i).lower()
        if carpool not in ("yes", "no"):
            raise DataError(f"line {i}: carpool must be yes or no, got '{carpool}'")
        try:
            weeks = int(_need(row, "weeks_waiting", i))
            miles = float(_need(row, "commute_miles", i))
        except ValueError as exc:
            raise DataError(f"line {i}: {exc}") from exc
        if weeks < 0 or miles < 0:
            raise DataError(f"line {i}: weeks_waiting and commute_miles cannot be negative")
        if name in seen:
            raise DataError(f"line {i}: duplicate employee '{name}'")
        seen.add(name)
        out.append(Request(name, need, carpool == "yes", weeks, miles))
    return out


def allocate(spaces: list[Space], requests: list[Request], seed: int = 0):
    """Return (assignments, waitlist).

    Accessible and EV requests get a space of their own type first. An EV
    request that finds no EV space falls back to a standard space; an
    accessible request never falls back. Within a group the highest score wins
    and exact ties are broken by a seeded shuffle, so a run can be repeated.
    """
    rng = random.Random(seed)
    order = list(requests)
    rng.shuffle(order)
    order.sort(key=score, reverse=True)  # stable: ties keep the shuffled order
    free = {t: sorted((s for s in spaces if s.type == t), key=lambda s: s.space_id) for t in SPACE_TYPES}
    assignments, waitlist = [], []
    for need in ("accessible", "ev", "standard"):
        for req in [r for r in order if r.need == need]:
            pool = free[need]
            if not pool and need == "ev":
                pool = free["standard"]
            if pool:
                assignments.append((req, pool.pop(0)))
            else:
                waitlist.append(req)
    waitlist.sort(key=score, reverse=True)
    return assignments, waitlist
