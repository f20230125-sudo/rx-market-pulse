"""Therapeutic area from an FDA pharmacologic-class string.

The rules live in data/ref/therapeutic_area_rules.csv (priority, area, regex) so a reviewer can read and
change them without touching code. A class takes the area of the lowest-priority-number rule that
matches, which is how a specific rule ("Human Immunodeficiency Virus", 10) beats a general one
("Nucleoside Analog", 130).
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    priority: int
    area: str
    pattern: re.Pattern[str]


def load_rules(path: Path) -> list[Rule]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    rules = [Rule(int(r["priority"]), r["area"], re.compile(r["pattern"], re.IGNORECASE)) for r in rows]
    return sorted(rules, key=lambda r: r.priority)


def area_for_class(pharm_class: str, rules: list[Rule]) -> tuple[str, int] | None:
    """(area, priority) of the best matching rule, or None when no rule matches."""
    for rule in rules:  # already sorted, so the first hit is the best
        if rule.pattern.search(pharm_class):
            return rule.area, rule.priority
    return None


# ---------------------------------------------------------------- name rules (third step)
# For products with no pharmacologic class in the FDA directory, an editable list of ingredient and
# brand names. Order in the file is the priority; each row is "area, regex on the upper-case name".


@dataclass(frozen=True)
class NameRule:
    area: str
    pattern: re.Pattern[str]


def load_name_rules(path: Path) -> list[NameRule]:
    with open(path, newline="", encoding="utf-8") as f:
        return [NameRule(r["area"], re.compile(r["pattern"])) for r in csv.DictReader(f)]


def area_for_name(name: str | None, rules: list[NameRule]) -> str | None:
    """Area of the first rule matching an ingredient or brand name (upper-cased here)."""
    if not name:
        return None
    key = name.upper()
    for rule in rules:
        if rule.pattern.search(key):
            return rule.area
    return None
