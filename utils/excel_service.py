"""
excel_service.py — Servicio de carga y procesamiento de archivos Excel de inventario.
Extrae la lógica de WorkspaceView._process_excel_file para mantener separada la UI del negocio.
"""
import os
import re
import pandas as pd
from typing import Tuple, List, Optional

from utils.folio_engine import mapper_from_state, FolioMapper
from utils.folio_parser import calculate_suggested_range
from utils.analyzers import analizar_folios
from utils.hierarchy_builder import RomanToSigloArabic
from project_types import InventoryRecord, SugerenciaCorreccion


class ExcelLoadResult:
    """Resultado del procesamiento de un archivo Excel."""
    def __init__(self):
        self.records: List[InventoryRecord] = []
        self.suggestions: List[SugerenciaCorreccion] = []
        self.siglo_detectado: str = "XIX"
        self.acervo_detectado: str = "7"
        self.total_records: int = 0
        self.total_errors: int = 0
        self.error_messages: List[str] = []


def process_excel_file(path: str, app_state) -> ExcelLoadResult:
    """
    Procesa un archivo Excel de inventario y retorna el resultado.
    Actualiza app_state con records y suggestions generados.
    """
    result = ExcelLoadResult()

    # 1. Leer metadatos globales (filas 4 y 7)
    try:
        if not path.lower().endswith('.csv'):
            meta_df = pd.read_excel(path, nrows=7, header=None)
            if len(meta_df) >= 4:
                celda_siglo = str(meta_df.iloc[3, 0])
                match_s = re.search(r'secci[oó]n:\s*([A-Za-z0-9]+)', celda_siglo, re.IGNORECASE)
                if match_s:
                    result.siglo_detectado = match_s.group(1).upper()

            if len(meta_df) >= 7:
                celda_acervo = str(meta_df.iloc[6, 0])
                match_a = re.search(r'c[oó]digo\s+del\s+fondo:\s*[Nn]0*(\d+)', celda_acervo, re.IGNORECASE)
                if match_a:
                    result.acervo_detectado = match_a.group(1)
    except Exception as e:
        result.error_messages.append(f"No se pudieron extraer metadatos: {e}")

    # 2. Cargar DataFrame
    try:
        if path.lower().endswith('.csv'):
            df = pd.read_csv(path)
        else:
            df = pd.read_excel(path, skiprows=7)
    except Exception as e:
        result.error_messages.append(f"Fallo al abrir el archivo: {e}")
        return result

    df.columns = [str(c).strip() for c in df.columns]
    cols = [c for c in df.columns if not str(c).startswith("Unnamed:")]

    # 3. Mapeo de columnas
    col_map = {
        "registro": None, "escribano": None, "protocolo": None,
        "folios": None, "titulo": None, "fecha_inicio": None,
        "fecha_fin": None, "interesado1": None, "interesado2": None
    }

    for c in cols:
        c_clean = c.lower().replace("\n", " ").strip()
        if "n° de registro" in c_clean or "numero de registro" in c_clean:
            col_map["registro"] = c
        elif "escribano" in c_clean or "notario" in c_clean:
            col_map["escribano"] = c
        elif "n° de prot" in c_clean or "protocolo" in c_clean:
            col_map["protocolo"] = c
        elif "n° de folios" in c_clean or "folios" in c_clean:
            col_map["folios"] = c
        elif "titulo estandar" in c_clean or "titulo" in c_clean:
            col_map["titulo"] = c
        elif "interesado 1" in c_clean or "interesado1" in c_clean:
            col_map["interesado1"] = c
        elif "interesado 2" in c_clean or "interesado2" in c_clean:
            col_map["interesado2"] = c
        elif "fecha inicial" in c_clean or "data cronica 1" in c_clean or ("data cr" in c_clean and "1" in c_clean):
            col_map["fecha_inicio"] = c
        elif "fecha final" in c_clean or "data cronica 2" in c_clean or ("data cr" in c_clean and "2" in c_clean):
            col_map["fecha_fin"] = c

    for key, possible_names in [
        ("registro", ["registro", "id", "expediente"]),
        ("escribano", ["escribano", "notario"]),
        ("protocolo", ["prot", "protocolo", "tomo"]),
        ("folios", ["folios", "rango", "paginas"]),
        ("titulo", ["titulo", "asunto", "desc"]),
        ("fecha_inicio", ["inicial", "inicio", "fecha 1"]),
        ("fecha_fin", ["final", "fin", "fecha 2"]),
        ("interesado1", ["interesado 1", "interesado"]),
        ("interesado2", ["interesado 2"])
    ]:
        if col_map[key] is None:
            for c in cols:
                if any(pn in c.lower() for pn in possible_names):
                    col_map[key] = c
                    break

    if len(df.columns) >= 5:
        col_map["titulo"] = df.columns[4]
    if len(df.columns) >= 6:
        col_map["fecha_inicio"] = df.columns[5]

    # 4. Construir registros
    mapper = mapper_from_state(app_state)
    fila_inicio_idx = max(0, app_state.fila_inicio - 9)
    fila_fin_idx = min(len(df), app_state.fila_fin - 8)

    records_temp = []
    for i in range(fila_inicio_idx, fila_fin_idx):
        row_data = df.iloc[i]
        first_cell = str(row_data.iloc[0]).strip()

        if re.match(r'^\s*(protocolo|registro)\b', first_cell, re.IGNORECASE):
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

        if not reg and not esc and not fols:
            continue

        fila_excel_real = i + 9
        r_id = f"#{len(records_temp) + 1:04d}"
        pg_range = mapper.folio_str_to_pdf_range(fols) or "1"

        rec = InventoryRecord(
            id=r_id, fila=fila_excel_real,
            registro=reg if reg else f"REG-{r_id}",
            escribano=esc if esc else "Sin Escribano",
            protocolo=prot if prot else "S/P",
            folios=fols if fols else "001r",
            pg_pdf=pg_range,
            titulo=tit if tit else "Sin Título",
            estado="",
            fecha_inicio=f_ini,
            fecha_fin=f_fin,
            interesado1=int1,
            interesado2=int2,
        )
        records_temp.append(rec)

    result.records = records_temp
    result.total_records = len(records_temp)

    # 5. Ejecutar análisis de folios
    app_state.records = records_temp
    app_state.suggestions = []
    res_folios = analizar_folios(records_temp, app_state.exclusions)

    for err in res_folios.errores:
        for rec in app_state.records:
            if rec.id == err.record_id:
                rec.estado = "REVISAR"
                break

        curr_idx = next((idx for idx, r in enumerate(app_state.records) if r.id == err.record_id), None)
        prev_rec = app_state.records[curr_idx - 1] if curr_idx and curr_idx > 0 else None
        curr_rec = app_state.records[curr_idx] if curr_idx is not None else None

        sug_range = "001r-002v"
        if prev_rec and curr_rec:
            sug_range = calculate_suggested_range(prev_rec, curr_rec) or "001r-002v"

        sug = SugerenciaCorreccion(
            id=f"SUG-{len(app_state.suggestions)+1:03d}",
            registro_id=err.record_id,
            tipo_error=err.tipo,
            descripcion=err.descripcion,
            valor_actual=curr_rec.folios if curr_rec else "",
            valor_sugerido=sug_range,
            escribano=curr_rec.escribano if curr_rec else "",
            folios_original=curr_rec.folios if curr_rec else "",
            rango_sugerido=sug_range,
            paginas_pdf=curr_rec.pg_pdf if curr_rec else "",
            paginas_sugeridas=mapper.folio_str_to_pdf_range(sug_range) or "",
            fecha_original="",
            fecha_validada=""
        )
        app_state.suggestions.append(sug)

    result.suggestions = app_state.suggestions
    result.total_errors = len(res_folios.errores)

    return result
