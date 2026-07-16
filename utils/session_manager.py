"""
session_manager.py — Persistencia de sesión del Escritorio del Archivista.
Guarda y carga el estado de la aplicación en archivos JSON.
"""
import json
import os
from dataclasses import asdict, fields


def save_session(app_state, path: str = None) -> str:
    """
    Guarda el estado de la sesión actual en un archivo JSON.
    Retorna la ruta del archivo guardado.
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "session.json")

    data = {
        "excel_path": app_state.excel_path,
        "pdf_path": app_state.pdf_path,
        "fila_inicio": app_state.fila_inicio,
        "fila_fin": app_state.fila_fin,
        "folio_inicio": app_state.folio_inicio,
        "pag_pdf_inicio": app_state.pag_pdf_inicio,
        "acervo_num": app_state.acervo_num,
        "output_dir": app_state.output_dir,
        "segmentos": app_state.segmentos,
        "overrides": app_state.overrides,
        "records": [_record_to_dict(r) for r in app_state.records],
        "exclusions": [_exclusion_to_dict(e) for e in app_state.exclusions],
        "suggestions": [_suggestion_to_dict(s) for s in app_state.suggestions],
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return path


def load_session(app_state, path: str = None) -> bool:
    """
    Carga la sesión desde un archivo JSON en el AppState proporcionado.
    Retorna True si se cargó correctamente, False si no.
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "session.json")

    if not os.path.exists(path):
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return False

    app_state.excel_path = data.get("excel_path")

    # Si no hay Excel, limpiar datos derivados (no mostrar registros huérfanos)
    if not app_state.excel_path or not os.path.exists(app_state.excel_path):
        data["records"] = []
        data["exclusions"] = []
        data["suggestions"] = []
    app_state.pdf_path = data.get("pdf_path")
    app_state.fila_inicio = data.get("fila_inicio", 2)
    app_state.fila_fin = data.get("fila_fin", 500)
    app_state.folio_inicio = data.get("folio_inicio", 1)
    app_state.pag_pdf_inicio = data.get("pag_pdf_inicio", 1)
    app_state.acervo_num = data.get("acervo_num", "7")
    app_state.output_dir = data.get("output_dir")
    app_state.segmentos = data.get("segmentos", [])
    app_state.overrides = data.get("overrides", {})

    # Reconstruir records
    from project_types import InventoryRecord
    app_state.records = []
    for rd in data.get("records", []):
        r = InventoryRecord(
            id=rd["id"], fila=rd["fila"], registro=rd["registro"],
            escribano=rd["escribano"], protocolo=rd["protocolo"],
            folios=rd["folios"], pg_pdf=rd["pg_pdf"], titulo=rd["titulo"],
            estado=rd.get("estado", ""),
            fecha_inicio=rd.get("fecha_inicio", ""),
            fecha_fin=rd.get("fecha_fin", ""),
            interesado1=rd.get("interesado1", ""),
            interesado2=rd.get("interesado2", ""),
        )
        app_state.records.append(r)

    # Reconstruir exclusions
    from project_types import ExclusionRule
    app_state.exclusions = []
    for ed in data.get("exclusions", []):
        e = ExclusionRule(
            id=ed["id"], tipo=ed["tipo"],
            desde=ed["desde"], hasta=ed["hasta"],
            motivo=ed["motivo"],
            tipo_contenido=ed.get("tipo_contenido"),
        )
        app_state.exclusions.append(e)

    # Reconstruir suggestions
    from project_types import SugerenciaCorreccion
    app_state.suggestions = []
    for sd in data.get("suggestions", []):
        s = SugerenciaCorreccion(
            id=sd["id"], registro_id=sd["registro_id"],
            tipo_error=sd["tipo_error"], descripcion=sd["descripcion"],
            valor_actual=sd["valor_actual"], valor_sugerido=sd["valor_sugerido"],
            escribano=sd["escribano"], folios_original=sd["folios_original"],
            rango_sugerido=sd["rango_sugerido"],
            paginas_pdf=sd["paginas_pdf"], paginas_sugeridas=sd["paginas_sugeridas"],
            fecha_original=sd.get("fecha_original", ""),
            fecha_validada=sd.get("fecha_validada", ""),
        )
        app_state.suggestions.append(s)

    return True


def _record_to_dict(r) -> dict:
    return {
        "id": r.id, "fila": r.fila, "registro": r.registro,
        "escribano": r.escribano, "protocolo": r.protocolo,
        "folios": r.folios, "pg_pdf": r.pg_pdf, "titulo": r.titulo,
        "estado": r.estado,
        "fecha_inicio": getattr(r, "fecha_inicio", ""),
        "fecha_fin": getattr(r, "fecha_fin", ""),
        "interesado1": getattr(r, "interesado1", ""),
        "interesado2": getattr(r, "interesado2", ""),
    }


def _exclusion_to_dict(e) -> dict:
    return {
        "id": e.id, "tipo": e.tipo,
        "desde": e.desde, "hasta": e.hasta,
        "motivo": e.motivo,
        "tipo_contenido": e.tipo_contenido,
    }


def _suggestion_to_dict(s) -> dict:
    return {
        "id": s.id, "registro_id": s.registro_id,
        "tipo_error": s.tipo_error, "descripcion": s.descripcion,
        "valor_actual": s.valor_actual, "valor_sugerido": s.valor_sugerido,
        "escribano": s.escribano, "folios_original": s.folios_original,
        "rango_sugerido": s.rango_sugerido,
        "paginas_pdf": s.paginas_pdf, "paginas_sugeridas": s.paginas_sugeridas,
        "fecha_original": s.fecha_original, "fecha_validada": s.fecha_validada,
    }
