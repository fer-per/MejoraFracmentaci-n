"""
use_cases/excel_processing_use_case.py — Caso de uso: Carga y procesamiento de Excel.

Extrae TODA la logica de negocio que estaba en WorkspaceView._process_excel_file()
(256 lineas God Method) y lacentraliza aqui. La vista solo llama a esta funcion.
"""
import os
import re
from typing import Optional

from domain.models import AppState, InventoryRecord, SugerenciaCorreccion, EXCEL_HEADER_OFFSET, DEFAULT_SKIPROWS
from domain.registry import resolve
from use_cases.analyzer_use_case import execute_analysis, generate_suggestions_for_errors


def process_excel(path: str, app_state: AppState, auto_detect: bool = True) -> dict:
    """
    Procesa un archivo Excel de inventario completo.

    Retorna un dict con:
        - records: Lista de InventoryRecord
        - siglo_detectado: str
        - acervo_detectado: str
        - total_records: int
        - total_errors: int
        - messages: list of (tipo, mensaje)
    """
    pd = resolve("pandas")
    messages = []
    result = {
        "records": [],
        "siglo_detectado": "XIX",
        "acervo_detectado": "7",
        "total_records": 0,
        "total_errors": 0,
        "messages": messages,
    }

    siglo_detectado, acervo_detectado = _extract_global_metadata(path, pd)
    result["siglo_detectado"] = siglo_detectado
    result["acervo_detectado"] = acervo_detectado
    app_state.acervo_num = acervo_detectado

    siglo_arabigo = resolve("RomanToSigloArabic")(siglo_detectado)
    messages.append((
        "SUCCESS",
        f"Metadatos extraidos: Acervo N{acervo_detectado}, "
        f"Siglo Romano '{siglo_detectado}' (Arabigo {siglo_arabigo}).",
    ))

    df = _load_dataframe(path, pd)
    if df is None:
        messages.append(("ERR", "No se pudo cargar el archivo Excel."))
        return result

    if auto_detect:
        _auto_detect_rows(df, app_state, messages)

    col_map = _build_column_mapping(df)

    mapper = resolve("mapper_from_state")(app_state)
    records = _build_records(df, col_map, app_state, mapper, pd)
    result["records"] = records
    result["total_records"] = len(records)

    app_state.records = records
    app_state.suggestions = []

    analysis = execute_analysis("folios", app_state)
    suggestions = generate_suggestions_for_errors(analysis, app_state)
    result["total_errors"] = len(analysis.errores)

    if analysis.errores:
        messages.append((
            "WARN",
            f"Se detectaron {len(analysis.errores)} alertas en la foliacion.",
        ))

    return result


def _extract_global_metadata(path: str, pd) -> tuple:
    """Extrae siglo y acervo de las filas 4 y 7 del Excel."""
    siglo = "XIX"
    acervo = "7"

    if path.lower().endswith(".csv"):
        return siglo, acervo

    try:
        meta_df = pd.read_excel(path, nrows=7, header=None)

        if len(meta_df) >= 4:
            celda_siglo = str(meta_df.iloc[3, 0])
            match_s = re.search(
                r"secci[oó]n:\s*([A-Za-z0-9]+)", celda_siglo, re.IGNORECASE
            )
            if match_s:
                siglo = match_s.group(1).upper()

        if len(meta_df) >= 7:
            celda_acervo = str(meta_df.iloc[6, 0])
            match_a = re.search(
                r"c[oó]digo\s+del\s+fondo:\s*[Nn]0*(\d+)",
                celda_acervo,
                re.IGNORECASE,
            )
            if match_a:
                acervo = match_a.group(1)
    except Exception:
        pass

    return siglo, acervo


def _load_dataframe(path: str, pd) -> Optional["pd.DataFrame"]:
    """Carga el DataFrame desde Excel o CSV."""
    try:
        if path.lower().endswith(".csv"):
            return pd.read_csv(path)
        return pd.read_excel(path, skiprows=DEFAULT_SKIPROWS)
    except Exception:
        return None


def _auto_detect_rows(
    df, app_state: AppState, messages: list
) -> None:
    """Auto-detecta filas de inicio y fin con datos reales."""
    if df.empty:
        return

    last_idx = df.last_valid_index()
    if last_idx is not None:
        app_state.fila_fin = last_idx + EXCEL_HEADER_OFFSET
        messages.append((
            "INFO",
            f"Filas detectadas: {app_state.fila_inicio} a {app_state.fila_fin}",
        ))

    for idx in range(len(df)):
        row_data = df.iloc[idx]
        first_cell = str(row_data.iloc[0]).strip()
        if re.match(r"^\s*(protocolo|registro)\b", first_cell, re.IGNORECASE):
            continue
        if any(str(row_data.iloc[c]).strip() for c in range(min(3, len(df.columns)))):
            app_state.fila_inicio = idx + EXCEL_HEADER_OFFSET
            break


def _build_column_mapping(df) -> dict:
    """Mapea columnas del DataFrame a campos del dominio."""
    cols = [c for c in df.columns if not str(c).startswith("Unnamed:")]

    col_map = {
        "registro": None, "escribano": None, "protocolo": None,
        "folios": None, "titulo": None, "fecha_inicio": None,
        "fecha_fin": None, "interesado1": None, "interesado2": None,
    }

    for c in cols:
        c_clean = c.lower().replace("\n", " ").strip()
        if "n de registro" in c_clean or "numero de registro" in c_clean:
            col_map["registro"] = c
        elif "escribano" in c_clean or "notario" in c_clean:
            col_map["escribano"] = c
        elif "n de prot" in c_clean or "protocolo" in c_clean:
            col_map["protocolo"] = c
        elif "n de folios" in c_clean or "folios" in c_clean:
            col_map["folios"] = c
        elif "titulo estandar" in c_clean or "titulo" in c_clean:
            col_map["titulo"] = c
        elif "interesado 1" in c_clean or "interesado1" in c_clean:
            col_map["interesado1"] = c
        elif "interesado 2" in c_clean or "interesado2" in c_clean:
            col_map["interesado2"] = c
        elif "fecha inicial" in c_clean or "data cronica 1" in c_clean or (
            "data cr" in c_clean and "1" in c_clean
        ):
            col_map["fecha_inicio"] = c
        elif "fecha final" in c_clean or "data cronica 2" in c_clean or (
            "data cr" in c_clean and "2" in c_clean
        ):
            col_map["fecha_fin"] = c

    fallbacks = [
        ("registro", ["registro", "id", "expediente"]),
        ("escribano", ["escribano", "notario"]),
        ("protocolo", ["prot", "protocolo", "tomo"]),
        ("folios", ["folios", "rango", "paginas"]),
        ("titulo", ["titulo", "asunto", "desc"]),
        ("fecha_inicio", ["inicial", "inicio", "fecha 1"]),
        ("fecha_fin", ["final", "fin", "fecha 2"]),
        ("interesado1", ["interesado 1", "interesado"]),
        ("interesado2", ["interesado 2"]),
    ]
    for key, possible_names in fallbacks:
        if col_map[key] is None:
            for c in cols:
                if any(pn in c.lower() for pn in possible_names):
                    col_map[key] = c
                    break

    if len(df.columns) >= 5:
        col_map["titulo"] = df.columns[4]
    if len(df.columns) >= 6:
        col_map["fecha_inicio"] = df.columns[5]

    return col_map


def _build_records(
    df,
    col_map: dict,
    app_state: AppState,
    mapper,
    pd,
) -> list:
    """Construye la lista de InventoryRecord desde el DataFrame."""
    fila_inicio_idx = max(0, app_state.fila_inicio - EXCEL_HEADER_OFFSET)
    fila_fin_idx = min(len(df), app_state.fila_fin - (EXCEL_HEADER_OFFSET - 1))

    records = []
    for i in range(fila_inicio_idx, fila_fin_idx):
        row_data = df.iloc[i]
        first_cell = str(row_data.iloc[0]).strip()

        if re.match(r"^\s*(protocolo|registro)\b", first_cell, re.IGNORECASE):
            continue

        def get_val(key):
            val = row_data.get(col_map[key])
            if pd.isna(val) or str(val).strip().lower() in ["nan", "nat"]:
                return ""
            return str(val).strip()

        reg = get_val("registro")
        esc = get_val("escribano")
        prot = get_val("protocolo")
        fols = get_val("folios")
        tit = get_val("titulo")
        f_ini = get_val("fecha_inicio")
        f_fin = get_val("fecha_fin")
        int1 = get_val("interesado1")
        int2 = get_val("interesado2")

        if prot:
            try:
                prot_float = float(prot)
                if prot_float == int(prot_float):
                    prot = str(int(prot_float))
            except (ValueError, TypeError):
                pass

        if not reg and not esc and not fols:
            continue

        fila_excel_real = i + EXCEL_HEADER_OFFSET
        r_id = f"#{len(records) + 1:04d}"
        pg_range = mapper.folio_str_to_pdf_range(fols) or "1"

        rec = InventoryRecord(
            id=r_id,
            fila=fila_excel_real,
            registro=reg if reg else f"REG-{r_id}",
            escribano=esc if esc else "Sin Escribano",
            protocolo=prot if prot else "S/P",
            folios=fols if fols else "001r",
            pg_pdf=pg_range,
            titulo=tit if tit else "Sin Titulo",
            estado="",
            fecha_inicio=f_ini,
            fecha_fin=f_fin,
            interesado1=int1,
            interesado2=int2,
        )
        records.append(rec)

    return records
