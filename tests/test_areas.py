from pathlib import Path

import pytest

from rx.areas import area_for_class, area_for_name, load_name_rules, load_rules

RULES = load_rules(Path(__file__).resolve().parents[1] / "data" / "ref" / "therapeutic_area_rules.csv")


@pytest.mark.parametrize(
    "cls, area",
    [
        ("GLP-1 Receptor Agonist [EPC]", "Diabetes & obesity"),
        ("Dipeptidyl Peptidase 4 Inhibitor [EPC]", "Diabetes & obesity"),
        ("Insulin Analog [EPC]", "Diabetes & obesity"),
        ("Kinase Inhibitor [EPC]", "Oncology"),
        ("Programmed Death Receptor-1 Blocking Antibody [EPC]", "Oncology"),
        ("Interleukin-17A Antagonist [EPC]", "Immunology & inflammation"),
        ("Tumor Necrosis Factor Blocker [EPC]", "Immunology & inflammation"),
        ("Human Immunodeficiency Virus Nucleoside Analog Reverse Transcriptase Inhibitor [EPC]", "HIV"),
        ("Hepatitis B Virus Nucleoside Analog Reverse Transcriptase Inhibitor [EPC]", "Infectious disease (non-HIV)"),
        ("Atypical Antipsychotic [EPC]", "Neurology & psychiatry"),
        ("Factor Xa Inhibitor [EPC]", "Cardiovascular"),
        ("Opioid Antagonist [EPC]", "Pain, addiction & anesthesia"),
    ],
)
def test_known_classes(cls, area):
    assert area_for_class(cls, RULES)[0] == area


def test_specific_rule_beats_general_one():
    # JAK inhibitors are 'Kinase Inhibitor' too, but belong with immunology, not oncology.
    assert area_for_class("Janus Kinase Inhibitor [EPC]", RULES)[0] == "Immunology & inflammation"
    # IGF-1R is 'Insulin-like', but is not a diabetes drug.
    assert area_for_class("Insulin-like Growth Factor-1 Receptor Inhibitor [EPC]", RULES)[0] == "Rare & genetic disease"
    # 'Angiotensin Converting Enzyme Inhibitor' contains 'Enzyme' (rare disease rule) but is cardiovascular.
    assert area_for_class("Angiotensin Converting Enzyme Inhibitor [EPC]", RULES)[0] == "Cardiovascular"


def test_unknown_class_returns_none():
    assert area_for_class("Some Brand New Mechanism [EPC]", RULES) is None


NAME_RULES = load_name_rules(Path(__file__).resolve().parents[1] / "data" / "ref" / "name_area_rules.csv")


@pytest.mark.parametrize(
    "name, area",
    [
        ("ELEXACAFTOR; IVACAFTOR; TEZACAFTOR", "Rare & genetic disease"),
        ("EMICIZUMAB", "Hematology"),
        ("DEUTETRABENAZINE", "Neurology & psychiatry"),
        ("OZEMPIC", "Diabetes & obesity"),
        ("ERTUGLIFLOZIN", "Diabetes & obesity"),
        ("CABOTEGRAVIR; RILPIVIRINE", "HIV"),
        ("PANCRELIPASE AMYLASE; PANCRELIPASE LIPASE", "Gastroenterology"),
        ("BELZUTIFAN", "Oncology"),
        ("WATER", "Other (vitamins, fluids, diagnostics)"),
        ("FLOVENT", "Respiratory & allergy"),
    ],
)
def test_name_rules(name, area):
    assert area_for_name(name, NAME_RULES) == area


def test_name_rules_do_not_invent_areas():
    assert area_for_name("SOMETHING NOBODY HEARD OF", NAME_RULES) is None
    assert area_for_name(None, NAME_RULES) is None


def test_rules_are_sorted_and_patterns_compile():
    priorities = [r.priority for r in RULES]
    assert priorities == sorted(priorities)
    assert len(RULES) >= 15
