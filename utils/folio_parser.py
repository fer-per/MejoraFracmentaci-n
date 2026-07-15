"""
folio_parser.py — Intérprete y validador de secuencias de folios históricos.
Convierte strings de foliación en números planos para cálculos correlativos.
"""
import re
from typing import Optional, Tuple


FolioTuple = Tuple[int, str, int, str]  # (desde_num, desde_cara, hasta_num, hasta_cara)


def parse_folios(folio_str: str) -> Optional[FolioTuple]:
    """
    Interpreta un string de foliación histórica y lo convierte en una tupla numérica.

    Soporta:
    - Rangos: '002r-003v', '12r-14v', '100-120'
    - Únicos: '140', '140r', '002v'

    Returns:
        Tupla (desde_num, desde_cara, hasta_num, hasta_cara) o None si error.
    """
    if not folio_str or not isinstance(folio_str, str):
        return None

    folio_str = folio_str.strip().lower()

    # Expresión regular para rangos como '002r-003v'
    rango_match = re.match(r'(\d+)([rv])?-(\d+)([rv])?', folio_str)
    if rango_match:
        desde_num = int(rango_match.group(1))
        desde_cara = rango_match.group(2) if rango_match.group(2) else 'r'
        hasta_num = int(rango_match.group(3))
        hasta_cara = rango_match.group(4) if rango_match.group(4) else 'v'
        return desde_num, desde_cara, hasta_num, hasta_cara

    # Expresión regular para folios únicos como '140' o '140r'
    unico_match = re.match(r'(\d+)([rv])?$', folio_str)
    if unico_match:
        num = int(unico_match.group(1))
        cara = unico_match.group(2) if unico_match.group(2) else 'r'
        return num, cara, num, cara

    return None  # Error de formato


def folio_to_int(num: int, cara: str) -> int:
    """
    Convierte un folio con cara a un entero plano para cálculos secuenciales.
    recto (r) = num * 2 - 1
    verso (v) = num * 2
    """
    if cara == 'r':
        return num * 2 - 1
    else:
        return num * 2


def int_to_folio(n: int) -> Tuple[int, str]:
    """Convierte un entero plano de vuelta a (num_folio, cara)."""
    if n % 2 == 1:
        return (n + 1) // 2, 'r'
    else:
        return n // 2, 'v'


def format_folio(num: int, cara: str) -> str:
    """Formatea un folio como string estilizado (ej: '002r')."""
    return f"{num:03d}{cara}"


def detect_sequence_jump(
    records: list,
    exclusions: list = None
) -> list:
    """
    Recorre los registros secuencialmente y detecta saltos no justificados.

    Args:
        records: Lista de InventoryRecord
        exclusions: Lista de ExclusionRule (saltos aprobados)

    Returns:
        Lista de IDs de registros con saltos detectados.
    """
    if exclusions is None:
        exclusions = []

    errores = []
    expected_next_int = None

    for record in records:
        parsed = parse_folios(record.folios)
        if parsed is None:
            continue

        desde_num, desde_cara, hasta_num, hasta_cara = parsed
        desde_int = folio_to_int(desde_num, desde_cara)
        hasta_int = folio_to_int(hasta_num, hasta_cara)

        if expected_next_int is not None and desde_int != expected_next_int:
            # Verificar si el salto está cubierto por una regla de exclusión
            salto_aprobado = _check_exclusion(
                expected_next_int, desde_int, exclusions
            )
            if not salto_aprobado:
                errores.append(record.id)

        expected_next_int = hasta_int + 1

    return errores


def _check_exclusion(desde: int, hasta: int, exclusions: list) -> bool:
    """Verifica si un rango de salto está cubierto por alguna exclusión."""
    for excl in exclusions:
        excl_desde = folio_to_int(excl.desde, 'r')
        excl_hasta = folio_to_int(excl.hasta, 'v')
        if excl_desde <= desde and excl_hasta >= hasta:
            return True
    return False


def calculate_suggested_range(prev_record, current_record) -> Optional[str]:
    """
    Calcula el rango sugerido correcto para un registro con error de salto.
    """
    parsed_prev = parse_folios(prev_record.folios)
    if parsed_prev is None:
        return None

    _, _, hasta_num, hasta_cara = parsed_prev
    start_int = folio_to_int(hasta_num, hasta_cara) + 1

    parsed_current = parse_folios(current_record.folios)
    if parsed_current is None:
        return None

    desde_num, desde_cara, hasta_num_c, hasta_cara_c = parsed_current
    span = folio_to_int(hasta_num_c, hasta_cara_c) - folio_to_int(desde_num, desde_cara)

    end_int = start_int + span
    start_num, start_cara = int_to_folio(start_int)
    end_num, end_cara = int_to_folio(end_int)

    return f"{format_folio(start_num, start_cara)}-{format_folio(end_num, end_cara)}"
