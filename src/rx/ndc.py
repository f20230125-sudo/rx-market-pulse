"""National Drug Code (NDC) handling.

Every source in this project names a product by NDC, and each writes it differently:

* Medicaid files: 11 digits, no hyphens, "00002143380" (labeler 5, product 4, package 2).
* openFDA: hyphenated, 10 digits in one of three layouts: 4-4-2, 5-3-2 or 5-4-1.
  "0002-1433-80", "50242-040-01", "12345-1234-1".

A 10-digit NDC cannot be turned into the 11-digit form by looking at the digits alone: the hyphens say
which segment is short, and the short segment is padded with one leading zero. Dropping the hyphens
first and padding the front (a common shortcut) silently makes wrong keys and loses joins.
"""

from __future__ import annotations

import re

_HYPHENATED = re.compile(r"^(\d{4,5})-(\d{3,4})(?:-(\d{1,2}))?$")
_DIGITS_11 = re.compile(r"^\d{11}$")


def to_ndc11(value: str | None) -> str | None:
    """Return the 11-digit, no-hyphen NDC, or None when the value cannot be read safely.

    Accepts an 11-digit string as is, and the three hyphenated 10-digit layouts. A bare 10-digit string
    is ambiguous (three layouts fit) so it returns None rather than guess.
    """
    if value is None:
        return None
    s = str(value).strip()
    if _DIGITS_11.match(s):
        return s
    m = _HYPHENATED.match(s)
    if not m:
        return None
    labeler, product, package = m.group(1), m.group(2), m.group(3)
    if package is None:
        return None  # a product code alone has no package segment
    shape = (len(labeler), len(product), len(package))
    if shape == (4, 4, 2):
        labeler = labeler.zfill(5)
    elif shape == (5, 3, 2):
        product = product.zfill(4)
    elif shape == (5, 4, 1):
        package = package.zfill(2)
    elif shape != (5, 4, 2):
        return None
    return labeler + product + package


def product_ndc9(ndc11: str | None) -> str | None:
    """Labeler + product segments (first nine digits): the 'drug', ignoring pack size."""
    if ndc11 is None or not _DIGITS_11.match(ndc11):
        return None
    return ndc11[:9]
