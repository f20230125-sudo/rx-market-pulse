import pytest

from rx.ndc import product_ndc9, to_ndc11


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("0002-1433-80", "00002143380"),  # 4-4-2 pads the labeler
        ("50242-040-01", "50242004001"),  # 5-3-2 pads the product
        ("12345-1234-1", "12345123401"),  # 5-4-1 pads the package
        ("12345-1234-12", "12345123412"),  # already 5-4-2
        ("00002143380", "00002143380"),  # already 11 digits
        (" 00002143380 ", "00002143380"),
    ],
)
def test_converts_every_layout(raw, expected):
    assert to_ndc11(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "1234567890", "0002-1433", "12-34-56", "abcde-fghi-jk", "00002-1433-800"])
def test_refuses_what_it_cannot_read_safely(raw):
    # A bare 10-digit string fits three layouts; guessing would create wrong join keys.
    assert to_ndc11(raw) is None


def test_the_front_padding_shortcut_is_wrong():
    # Stripping hyphens and padding the front would give 05024204001 for this 5-3-2 code.
    naive = "50242-040-01".replace("-", "").zfill(11)
    assert naive != to_ndc11("50242-040-01")


def test_product_ndc9():
    assert product_ndc9("00002143380") == "000021433"
    assert product_ndc9("1234") is None
    assert product_ndc9(None) is None
