"""
use_cases/analyzer_use_case.py — Caso de uso: Ejecutar analisis y generar sugerencias.

Centraliza la logica de: ejecutar analizadores -> detectar errores ->
generar SugerenciaCorreccion. Antes estaba duplicada en 4 vistas.
"""
from typing import List, Optional

from domain.models import (
    AppState,
    InventoryRecord,
    SugerenciaCorreccion,
    AnalysisResult,
    EstadoRecord,
)
from domain.registry import resolve


def execute_analysis(
    analyzer_key: str,
    app_state: AppState,
) -> AnalysisResult:
    """
    Ejecuta un analizador especifico y retorna el resultado.

    Args:
        analyzer_key: Clave del analizador ('folios', 'topica', 'cronica', 'coverage').
        app_state: Estado actual de la aplicacion.

    Returns:
        AnalysisResult con errores y advertencias detectados.
    """
    ANALYZER_MAP = {
        "folios": lambda records, exclusions, mapper, state: resolve("analizar_folios")(records, exclusions),
        "topica": lambda records, exclusions, mapper, state: resolve("analizar_topica")(records),
        "cronica": lambda records, exclusions, mapper, state: resolve("analizar_cronica")(records),
        "coverage": lambda records, exclusions, mapper, state: resolve("analizar_coverage")(
            records, state.pdf_total_pages, mapper
        ),
    }

    analyzer_fn = ANALYZER_MAP.get(analyzer_key)
    if analyzer_fn is None:
        return AnalysisResult(
            nombre=analyzer_key,
            total_revisados=0,
            info_extra={"error": f"Analizador '{analyzer_key}' no encontrado"},
        )

    mapper = resolve("mapper_from_state")(app_state)
    return analyzer_fn(app_state.records, app_state.exclusions, mapper, app_state)


def generate_suggestions_for_errors(
    analysis_result: AnalysisResult,
    app_state: AppState,
    error_type_label: str = "",
) -> List[SugerenciaCorreccion]:
    """
    Genera SugerenciaCorreccion para cada error detectado.

    Antes esta logica estaba duplicada en WorkspaceView, ExclusionsView,
    ExpandedAnalyzerView (3 lugares diferentes).

    Args:
        analysis_result: Resultado del analizador.
        app_state: Estado de la aplicacion (se modifican records.estado).
        error_type_label: Etiqueta para tipo_error en sugerencias no-folio.

    Returns:
        Lista de sugerencias generadas.
    """
    mapper = resolve("mapper_from_state")(app_state)
    suggestions = []

    for err in analysis_result.errores:
        _mark_record_as_review(err.record_id, app_state)
        suggestion = _build_suggestion(err, app_state, mapper, error_type_label)
        if suggestion:
            suggestions.append(suggestion)
            app_state.suggestions.append(suggestion)

    return suggestions


def reanalyze_with_exclusions(app_state: AppState) -> AnalysisResult:
    """
    Re-ejecuta el analisis de folios tras cambiar exclusiones.
    Resetia estados REVISAR y regenera sugerencias.

    Antes estaba en ExclusionsView._run_analysis_and_refresh().
    """
    result = resolve("analizar_folios")(app_state.records, app_state.exclusions)

    for rec in app_state.records:
        if rec.estado == EstadoRecord.REVISAR:
            rec.estado = ""

    _clear_folio_suggestions(app_state)

    for err in result.errores:
        _mark_record_as_review(err.record_id, app_state)

    suggestions = generate_suggestions_for_errors(result, app_state)
    app_state.suggestions.extend(suggestions)

    return result


def _mark_record_as_review(record_id: str, app_state: AppState) -> None:
    """Marca un registro como REVISAR."""
    for rec in app_state.records:
        if rec.id == record_id:
            rec.estado = EstadoRecord.REVISAR
            break


def _clear_folio_suggestions(app_state: AppState) -> None:
    """Elimina sugerencias de tipo folio/salto/formato."""
    folio_types = {"folios", "SALTO DE FOLIO", "SALTO", "FORMATO", "SOLAPAMIENTO", "REPETIDO"}
    app_state.suggestions = [
        s for s in app_state.suggestions if s.tipo_error not in folio_types
    ]


def _build_suggestion(
    err,
    app_state: AppState,
    mapper,
    error_type_label: str = "",
) -> Optional[SugerenciaCorreccion]:
    """Construye una SugerenciaCorreccion para un error dado."""
    curr_idx = next(
        (idx for idx, r in enumerate(app_state.records) if r.id == err.record_id),
        None,
    )
    if curr_idx is None:
        return None

    prev_rec = app_state.records[curr_idx - 1] if curr_idx > 0 else None
    curr_rec = app_state.records[curr_idx]

    sug_range = "001r-002v"
    if prev_rec and curr_rec:
        sug_range = resolve("calculate_suggested_range")(prev_rec, curr_rec) or "001r-002v"

    tipo = error_type_label if error_type_label else err.tipo

    return SugerenciaCorreccion(
        id=f"SUG-{len(app_state.suggestions) + 1:03d}",
        registro_id=err.record_id,
        tipo_error=tipo,
        descripcion=err.descripcion,
        valor_actual=curr_rec.folios,
        valor_sugerido=sug_range,
        escribano=curr_rec.escribano,
        folios_original=curr_rec.folios,
        rango_sugerido=sug_range,
        paginas_pdf=curr_rec.pg_pdf,
        paginas_sugeridas=mapper.folio_str_to_pdf_range(sug_range) or "",
        fecha_original="",
        fecha_validada="",
    )
