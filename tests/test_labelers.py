import pytest

from rx.labelers import normalise_labeler, parent_company


def test_case_and_punctuation_variants_collapse():
    a = normalise_labeler("Takeda Pharmaceuticals America, Inc.")
    b = normalise_labeler("TAKEDA PHARMACEUTICALS AMERICA, INC.")
    c = normalise_labeler("TAKEDA PHARMACEUTICALS AMERICA INC")
    assert a == b == c == "TAKEDA"


def test_sanofi_spellings_meet():
    assert normalise_labeler("SANOFI-AVENTIS, US LLC") == normalise_labeler("SANOFI-AVENTIS U.S.LLC")


@pytest.mark.parametrize(
    "name, parent",
    [
        ("MERCK SHARP & DOHME LLC", "Merck (MSD)"),
        ("Merck Sharp & Dohme Corp.", "Merck (MSD)"),
        ("SCHERING CORPORATION", "Merck (MSD)"),
        ("ALLERGAN, INC.", "AbbVie"),
        ("ALLERGAN INC", "AbbVie"),
        ("JANSSEN BIOTECH, INC", "Johnson & Johnson"),
        ("ACTELION PHARMACEUTICALS U.S., INC.", "Johnson & Johnson"),
        ("IMMUNEX CORPORATION", "Amgen"),
        ("HORIZON THERAPEUTICS USA, INC.", "Amgen"),
        ("SEAGEN INC.", "Pfizer"),
        ("Pfizer Laboratories Div Pfizer Inc", "Pfizer"),
        ("E.R. SQUIBB & SONS, LLC.", "Bristol Myers Squibb"),
        ("CELGENE CORPORATION", "Bristol Myers Squibb"),
        ("ASEGUA THERAPEUTICS LLC", "Gilead"),
        ("VIIV HEALTHCARE COMPANY", "GSK (incl. ViiV)"),
        ("MYLAN PHARMACEUTICALS, INC.", "Viatris"),
        ("ACTAVIS PHARMA, INC.", "Teva"),
    ],
)
def test_known_parents(name, parent):
    assert parent_company(name) == parent


@pytest.mark.parametrize(
    "name",
    ["ORGANON LLC", "SANDOZ", "EMD SERONO, INC.", "MERCK KGAA"],
)
def test_spin_offs_and_namesakes_are_not_folded_into_msd(name):
    # Organon was spun out of Merck in 2021; Sandoz out of Novartis in 2023; EMD Serono is Merck KGaA, not MSD.
    assert parent_company(name) != "Merck (MSD)"
    assert parent_company("ORGANON LLC") == "Organon"
    assert parent_company("SANDOZ") == "Sandoz"


def test_unknown_company_keeps_its_own_name():
    assert parent_company("Krystal Biotech, Inc.") == "Krystal Biotech"


def test_prefix_matches_stop_at_a_word_boundary():
    assert parent_company("SUNOVION PHARMACEUTICALS INC.") != "Sun Pharma"
    assert parent_company("Sun Pharmaceutical Industries, Inc.") == "Sun Pharma"
    assert parent_company("SUN PHARMACEUTICALS INDUSTRIES, INC.") == "Sun Pharma"


def test_none_and_empty():
    assert normalise_labeler(None) is None
    assert parent_company(None) is None
    assert normalise_labeler("INC.") is None
