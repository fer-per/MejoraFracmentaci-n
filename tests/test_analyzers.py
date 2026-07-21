"""
test_analyzers.py — Tests unitarios para los analizadores de calidad.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import InventoryRecord
from utils.analyzers import analizar_folios, analizar_topica, analizar_cronica


def _make_record(id, folios, titulo="", estado="", fecha_inicio="", registro=""):
    return InventoryRecord(
        id=id, fila=1, registro=registro or f"1891-{id.replace('#','')}",
        escribano="Test", protocolo="P-001",
        folios=folios, pg_pdf="", titulo=titulo, estado=estado,
        fecha_inicio=fecha_inicio,
    )


def test_folios_sequential_ok():
    records = [
        _make_record("#0001", "001r-002v"),
        _make_record("#0002", "003r-004v"),
        _make_record("#0003", "005r-006v"),
    ]
    result = analizar_folios(records)
    assert result.ok, f"Expected no errors, got {len(result.errores)}"


def test_folios_gap_detected():
    records = [
        _make_record("#0001", "001r-002v"),
        _make_record("#0002", "005r-006v"),  # gap: 003, 004
    ]
    result = analizar_folios(records)
    assert not result.ok
    assert any(e.tipo == "SALTO" for e in result.errores)


def test_folios_overlap_detected():
    records = [
        _make_record("#0001", "001r-004v"),
        _make_record("#0002", "003r-005v"),  # overlap
    ]
    result = analizar_folios(records)
    assert not result.ok
    assert any(e.tipo == "SOLAPAMIENTO" for e in result.errores)


def test_folios_format_error():
    records = [
        _make_record("#0001", "abc"),  # formato inválido
    ]
    result = analizar_folios(records)
    assert not result.ok
    assert any(e.tipo == "FORMATO" for e in result.errores)


def test_topica_empty_title():
    records = [_make_record("#0001", "001r-002v", titulo="")]
    result = analizar_topica(records)
    assert not result.ok


def test_topica_valid():
    records = [_make_record("#0001", "001r-002v", titulo="Escritura de compraventa")]
    result = analizar_topica(records)
    assert result.ok


def test_cronica_valid():
    records = [
        _make_record("#0001", "001r-002v", fecha_inicio="15/03/1891", registro="1891-001"),
        _make_record("#0002", "003r-004v", fecha_inicio="20/06/1892", registro="1892-001"),
    ]
    result = analizar_cronica(records)
    assert result.ok


def test_cronica_regression():
    records = [
        _make_record("#0001", "001r-002v", fecha_inicio="1892", registro="1892-001"),
        _make_record("#0002", "003r-004v", fecha_inicio="1891", registro="1891-001"),
    ]
    result = analizar_cronica(records)
    assert not result.ok


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
