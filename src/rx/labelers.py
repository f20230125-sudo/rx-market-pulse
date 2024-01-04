"""Manufacturer (labeler) name harmonisation.

The Medicaid product list names the company behind each NDC as free text: 1,315 distinct spellings,
235 labeler codes with more than one name, and the same company in different capitalisations
("Takeda Pharmaceuticals America, Inc." and "TAKEDA PHARMACEUTICALS AMERICA, INC."). Two steps:

1. normalise: upper-case, drop punctuation and legal/corporate filler, so spelling variants collapse;
2. parent: known corporate ownership, applied by ordered patterns (first match wins).

Parent company is *current ownership* (as of October 2026) applied to every year, so a deal such as
Celgene -> Bristol Myers Squibb (2019) shows the combined business across the whole period. Only
acquisitions that are completed and well documented are listed; anything else keeps its own name.
"""

from __future__ import annotations

import re

# Words that carry no identity. "PHARMACEUTICALS" and friends are dropped so "SUN PHARMA" and
# "SUN PHARMACEUTICAL INDUSTRIES, INC." meet; the parent table below handles the risky cases.
_FILLER = {
    "INC", "LLC", "LP", "LTD", "LIMITED", "CORP", "CORPORATION", "CO", "COMPANY", "AND", "THE", "OF",
    "USA", "US", "U", "S", "AMERICA", "AMERICAS", "NORTH", "NA", "PLC", "AG", "GMBH", "SA", "SAS", "BV", "NV",
    "PHARMACEUTICALS", "PHARMACEUTICAL", "PHARMA", "LABORATORIES", "LABORATORY", "LABS", "HEALTHCARE",
    "THERAPEUTICS", "INDUSTRIES", "HOLDINGS", "GROUP", "DIV", "DIVISION", "PRIVATE", "PVT",
}

# (key prefixes, parent company). Order matters: first match wins. A prefix must end at a word boundary,
# so "SUN" does not catch "SUNOVION" and "BAYER" does not catch "BAYERN".
PARENTS: list[tuple[tuple[str, ...], str]] = [
    (("MERCK SHARP", "MERCK", "SCHERING"), "Merck (MSD)"),
    (("ORGANON",), "Organon"),
    (("ABBVIE", "ALLERGAN", "PHARMACYCLICS"), "AbbVie"),
    (("JANSSEN", "ACTELION", "JOHNSON"), "Johnson & Johnson"),
    (("NOVARTIS",), "Novartis"),
    (("SANDOZ",), "Sandoz"),
    (("GENENTECH", "ROCHE"), "Roche"),
    (("SANOFI", "GENZYME", "BIOVERATIV", "AVENTIS"), "Sanofi"),
    (("SQUIBB", "BRISTOL", "CELGENE", "E R SQUIBB"), "Bristol Myers Squibb"),
    (("ASTRAZENECA", "ALEXION", "MEDIMMUNE"), "AstraZeneca"),
    (("GLAXOSMITHKLINE", "GSK", "VIIV"), "GSK (incl. ViiV)"),
    (("AMGEN", "IMMUNEX", "HORIZON"), "Amgen"),
    (("PFIZER", "PHARMACIA", "WYETH", "HOSPIRA", "SEAGEN", "PARKE DAVIS"), "Pfizer"),
    (("TAKEDA", "SHIRE"), "Takeda"),
    (("TEVA", "ACTAVIS", "BARR"), "Teva"),
    (("MYLAN", "VIATRIS", "UPJOHN", "GREENSTONE"), "Viatris"),
    (("ASEGUA", "GILEAD", "KITE"), "Gilead"),
    (("ELI LILLY", "LILLY"), "Eli Lilly"),
    (("NOVO NORDISK",), "Novo Nordisk"),
    (("BOEHRINGER",), "Boehringer Ingelheim"),
    (("SALIX", "BAUSCH HEALTH", "VALEANT"), "Bausch Health"),
    (("AUROBINDO", "EUGIA"), "Aurobindo"),
    (("DR REDDYS",), "Dr. Reddy's"),
    (("SUN",), "Sun Pharma"),
    (("ZYDUS",), "Zydus"),
    (("HIKMA",), "Hikma"),
    (("FRESENIUS KABI",), "Fresenius Kabi"),
    (("CSL",), "CSL"),
    (("AMNEAL",), "Amneal"),
    (("CAMBER",), "Camber (Hetero)"),
    (("OTSUKA",), "Otsuka"),
    (("BAYER",), "Bayer"),
]
_PARENTS = [(re.compile(r"^(?:" + "|".join(prefixes) + r")\b"), name) for prefixes, name in PARENTS]

# Names that start like Merck & Co. but are other companies (Merck KGaA trades in the US as EMD Serono).
_NOT_MSD = re.compile(r"\b(KGAA|SERONO|EMD)\b")


def normalise_labeler(name: str | None) -> str | None:
    """Spelling-insensitive key: upper case, punctuation to spaces, filler words removed."""
    if name is None:
        return None
    s = re.sub(r"[^A-Z0-9 ]+", " ", name.upper().replace("&", " AND ").replace("'", ""))
    tokens = [t for t in s.split() if t not in _FILLER]
    return " ".join(tokens) or None


def parent_company(name: str | None) -> str | None:
    """Parent company for a labeler name; falls back to the normalised, title-cased name."""
    key = normalise_labeler(name)
    if key is None:
        return None
    for pattern, parent in _PARENTS:
        if pattern.search(key):
            if parent == "Merck (MSD)" and _NOT_MSD.search(key):
                break
            return parent
    return key.title()
