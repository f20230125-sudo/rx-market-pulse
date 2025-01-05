import pytest

from rx.ingredients import first_name, ingredient_key


@pytest.mark.parametrize(
    "text, expected",
    [
        ("ATORVASTATIN CALCIUM", "ATORVASTATIN"),
        ("sitagliptin phosphate", "SITAGLIPTIN"),
        ("SITAGLIPTIN", "SITAGLIPTIN"),
        ("metformin hydrochloride; sitagliptin phosphate", "METFORMIN; SITAGLIPTIN"),
        ("sitagliptin and metformin hydrochloride", "METFORMIN; SITAGLIPTIN"),
        ("EZETIMIBE, SIMVASTATIN", "EZETIMIBE; SIMVASTATIN"),
        ("amoxicillin and clavulanate potassium", "AMOXICILLIN; CLAVULANATE"),
        ("AMLODIPINE BESYLATE", "AMLODIPINE"),
        ("insulin glargine (rDNA origin)", "INSULIN GLARGINE"),
        ("DIMETHYL FUMARATE", "DIMETHYL FUMARATE"),  # the 'salt' is the drug
        ("ERTUGLIFLOZIN PIDOLATE", "ERTUGLIFLOZIN"),
        ("PEMETREXED HEPTAHYDRATE", "PEMETREXED"),
        ("DOXYCYCLINE HYCLATE", "DOXYCYCLINE"),
        ("risankizumab-rzaa", "RISANKIZUMAB"),
        ("adalimumab-atto", "ADALIMUMAB"),
        ("SODIUM", "SODIUM"),  # stripping would leave nothing, so keep it
        ("POTASSIUM CHLORIDE", "POTASSIUM CHLORIDE"),
    ],
)
def test_ingredient_key(text, expected):
    assert ingredient_key(text) == expected


def test_combination_order_does_not_matter():
    assert ingredient_key("A and B") == ingredient_key("B; A")


@pytest.mark.parametrize("text", [None, "", "   "])
def test_ingredient_key_empty(text):
    assert ingredient_key(text) is None


@pytest.mark.parametrize(
    "name, expected",
    [
        ("HUMIRA PEN 40MG/0.4ML 2 PENS", "HUMIRA"),
        ("Biktarvy", "BIKTARVY"),
        ("STELARA 90MG/1.0ML - prefilled syringe", "STELARA"),
        ("TRIKAFTA (elexacaftor, tezacaftor, ivacaftor; ivacaftor)", "TRIKAFTA"),
        ("OZEMPIC 0.25MG/0.5MG 1X3ML", "OZEMPIC"),
        ("ENBREL (etanercept)", "ENBREL"),
        ("", None),
        (None, None),
    ],
)
def test_first_name(name, expected):
    assert first_name(name) == expected
