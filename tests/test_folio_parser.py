"""
test_folio_parser.py — Tests unitarios para el parser de folios históricos.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.folio_parser import (
    parse_folios, folio_to_int, int_to_folio, format_folio,
    calculate_suggested_range
)


class MockRecord:
    def __init__(self, folios):
        self.folios = folios


def test_parse_range():
    result = parse_folios("002r-003v")
    assert result == (2, 'r', 3, 'v'), f"Expected (2, 'r', 3, 'v'), got {result}"


def test_parse_single_with_cara():
    result = parse_folios("0140r")
    assert result == (140, 'r', 140, 'r'), f"Expected (140, 'r', 140, 'r'), got {result}"


def test_parse_single_without_cara():
    result = parse_folios("140")
    assert result == (140, 'r', 140, 'r'), f"Expected (140, 'r', 140, 'r'), got {result}"


def test_parse_verso():
    result = parse_folios("002v")
    assert result == (2, 'v', 2, 'v'), f"Expected (2, 'v', 2, 'v'), got {result}"


def test_parse_invalid():
    result = parse_folios("abc")
    assert result is None, f"Expected None for invalid input, got {result}"


def test_parse_empty():
    assert parse_folios("") is None
    assert parse_folios(None) is None


def test_folio_to_int_recto():
    assert folio_to_int(1, 'r') == 1
    assert folio_to_int(2, 'r') == 3
    assert folio_to_int(100, 'r') == 199


def test_folio_to_int_verso():
    assert folio_to_int(1, 'v') == 2
    assert folio_to_int(2, 'v') == 4
    assert folio_to_int(100, 'v') == 200


def test_int_to_folio():
    assert int_to_folio(1) == (1, 'r')
    assert int_to_folio(2) == (1, 'v')
    assert int_to_folio(3) == (2, 'r')
    assert int_to_folio(4) == (2, 'v')


def test_format_folio():
    assert format_folio(1, 'r') == "001r"
    assert format_folio(42, 'v') == "042v"
    assert format_folio(100, 'r') == "100r"


def test_calculate_suggested_range():
    prev = MockRecord("006r-007v")
    curr = MockRecord("010r-011v")
    result = calculate_suggested_range(prev, curr)
    assert result is not None
    assert "008r" in result, f"Expected suggestion to start with 008r, got {result}"


def test_folio_int_roundtrip():
    for n in range(1, 100):
        num, cara = int_to_folio(n)
        back = folio_to_int(num, cara)
        assert back == n, f"Roundtrip failed for {n}: got {back}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
            print(f"  [OK] {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  [FAIL] {t.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed} passed, {failed} failed")
