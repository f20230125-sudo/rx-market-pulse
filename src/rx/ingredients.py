"""Ingredient and product-name harmonisation.

The same molecule is written many ways across the sources: "SITAGLIPTIN", "SITAGLIPTIN PHOSPHATE",
"sitagliptin and metformin hydrochloride". Analyses by molecule need one key per active moiety, so:

* salt and hydrate words are removed ("ATORVASTATIN CALCIUM" -> "ATORVASTATIN");
* combinations become a sorted, "; "-joined key, so "METFORMIN; SITAGLIPTIN" is the same product
  whichever way round the source lists it;
* a few names are protected because the "salt" word is the active part ("DIMETHYL FUMARATE");
* biologic suffixes are dropped ("RISANKIZUMAB-RZAA" -> "RISANKIZUMAB").

This is a deliberate approximation, documented, tested, and its coverage is reported in the scorecard.
"""

from __future__ import annotations

import re

_SALTS = (
    "HYDROCHLORIDE|HCL|DIHYDROCHLORIDE|HYDROBROMIDE|BROMIDE|CHLORIDE|SODIUM|POTASSIUM|CALCIUM|MAGNESIUM|"
    "DISODIUM|SULFATE|SULPHATE|PHOSPHATE|MALEATE|MESYLATE|BESYLATE|TARTRATE|SUCCINATE|FUMARATE|ACETATE|"
    "CITRATE|NITRATE|OXALATE|LACTATE|MONOHYDRATE|DIHYDRATE|TRIHYDRATE|HEMIHYDRATE|HEPTAHYDRATE|ANHYDROUS|"
    "HYDRATE|TROMETHAMINE|MEGLUMINE|PALMITATE|DECANOATE|PAMOATE|DIPROPIONATE|PROPIONATE|VALERATE|BITARTRATE|"
    "PIDOLATE|HYCLATE|MALATE|TOSYLATE|ESYLATE|NAPSYLATE|MONOSODIUM|HEMIFUMARATE"
)
_SALT_RE = re.compile(rf"\b(?:{_SALTS})\b")
_SPLIT_RE = re.compile(r"\s*(?:;|,|\||/|\bAND\b|\bWITH\b)\s*")
_NOISE_RE = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_BIOLOGIC_SUFFIX = re.compile(r"^([A-Z]+(?:MAB|CEPT|ALFA|TIDE|STIM|POETIN|ASE|GRASTIM)(?: [A-Z]+)*)-[A-Z]{4}$")

# Names where the word that looks like a salt is the active part, so stripping it would change the drug.
_PROTECTED = {
    "DIMETHYL FUMARATE", "MONOMETHYL FUMARATE", "DIROXIMEL FUMARATE", "FERROUS FUMARATE", "FERROUS SULFATE",
    "FERROUS GLUCONATE", "MAGNESIUM SULFATE", "ZINC SULFATE", "POTASSIUM CHLORIDE", "SODIUM CHLORIDE",
    "CALCIUM CHLORIDE", "CALCIUM CARBONATE", "SODIUM BICARBONATE", "CALCIUM ACETATE", "POTASSIUM CITRATE",
    "SODIUM PHOSPHATE", "POTASSIUM PHOSPHATE", "LITHIUM CARBONATE", "SODIUM FLUORIDE", "FERRIC CITRATE",
}


def ingredient_key(text: str | None) -> str | None:
    """Sorted, salt-free, '; '-joined key for one or several active ingredients."""
    if not text:
        return None
    parts: set[str] = set()
    for raw in _SPLIT_RE.split(_NOISE_RE.sub(" ", text.upper())):
        raw = re.sub(r"\s+", " ", raw).strip(" -.")
        if not raw:
            continue
        if raw in _PROTECTED:
            parts.add(raw)
            continue
        name = re.sub(r"\s+", " ", _SALT_RE.sub(" ", raw)).strip(" -.")
        m = _BIOLOGIC_SUFFIX.match(name)
        if m:
            name = m.group(1)
        parts.add(name or raw)  # if stripping leaves nothing (e.g. "SODIUM"), keep the original
    return "; ".join(sorted(parts)) or None


_STRENGTH_START = re.compile(r"[\s\-(]*\d")
_EXTRA = re.compile(r"[^A-Z0-9 \-]")


def first_name(product_name: str | None) -> str | None:
    """First word of a free-text product name: 'HUMIRA PEN 40MG/0.4ML 2 PENS' -> 'HUMIRA'.

    Used only as a fallback when a product cannot be matched to the FDA directory.
    """
    if not product_name:
        return None
    s = _EXTRA.sub(" ", product_name.upper()).strip()
    m = _STRENGTH_START.search(s)
    if m:
        s = s[: m.start()].strip()
    first = s.split(" ")[0] if s else ""
    return first or None
