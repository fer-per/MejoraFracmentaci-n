"""
analyzers.py — Los 4 Analizadores de Consistencia y Calidad de Datos.

Implementa la lógica pura descrita en la sección 3.C del documento del proyecto:
  - Sucesión de Folios: saltos, solapamientos, repetidos.
  - Data Tópica: caracteres geográficos válidos.
  - Data Crónica: progresión temporal.
  - Cobertura PDF: rango requerido vs tamaño real.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import List, Optional

from utils.folio_parser import parse_folios, folio_to_int


# ── Resultado de análisis ────────────────────────────────────────────────────

@dataclass
class AnalysisError:
    """Un error individual detectado por un analizador."""
    record_id: str
    fila: int
    tipo: str           # 'SALTO' | 'SOLAPAMIENTO' | 'REPETIDO' | 'FORMATO' | 'TOPICA' | 'CRONICA' | 'COVERAGE'
    descripcion: str
    valor_actual: str
    valor_esperado: str = ""


@dataclass
class AnalysisResult:
    """Resultado completo de un analizador."""
    nombre: str
    total_revisados: int
    errores: List[AnalysisError] = field(default_factory=list)
    advertencias: List[AnalysisError] = field(default_factory=list)
    info_extra: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return len(self.errores) == 0

    @property
    def resumen(self) -> str:
        if self.ok:
            return f"✅ {self.nombre}: {self.total_revisados} registros validados sin incidencias."
        return (
            f"⚠️ {self.nombre}: {len(self.errores)} error(es) en {self.total_revisados} registros."
        )


# ── A. Sucesión de Folios ────────────────────────────────────────────────────

def analizar_folios(records: list, exclusions: list = None) -> AnalysisResult:
    """
    Valida la integridad secuencial de la foliación histórica.
    Detecta:
      - Saltos no justificados entre registros.
      - Solapamientos (dos registros que comparten folios).
      - Folios repetidos (mismo inicio en distintas filas).
      - Errores de formato (folio no parseable).
    """
    exclusions = exclusions or []
    errores: List[AnalysisError] = []
    advertencias: List[AnalysisError] = []

    # Mapa de folios inicio ya vistos (para detectar repetidos)
    folios_vistos: dict = {}

    expected_next_int: Optional[int] = None
    prev_hasta_int: Optional[int] = None

    for i, r in enumerate(records):
        parsed = parse_folios(r.folios)

        # Validar formato
        if parsed is None:
            errores.append(AnalysisError(
                record_id=r.id, fila=r.fila,
                tipo="FORMATO",
                descripcion=f"El folio '{r.folios}' no tiene formato válido (esperado: '001r', '001r-002v', etc.).",
                valor_actual=r.folios,
                valor_esperado="NNNr o NNNr-NNNv",
            ))
            continue

        desde_num, desde_cara, hasta_num, hasta_cara = parsed
        desde_int = folio_to_int(desde_num, desde_cara)
        hasta_int = folio_to_int(hasta_num, hasta_cara)

        # Verificar repetidos
        key = desde_int
        if key in folios_vistos:
            errores.append(AnalysisError(
                record_id=r.id, fila=r.fila,
                tipo="REPETIDO",
                descripcion=(
                    f"El folio de inicio '{r.folios[:6]}' ya fue declarado en la fila "
                    f"{folios_vistos[key]} del inventario."
                ),
                valor_actual=r.folios,
                valor_esperado="Folio de inicio único",
            ))
        folios_vistos[key] = r.fila

        # Verificar solapamiento con registro anterior
        if prev_hasta_int is not None and desde_int <= prev_hasta_int:
            errores.append(AnalysisError(
                record_id=r.id, fila=r.fila,
                tipo="SOLAPAMIENTO",
                descripcion=(
                    f"El rango '{r.folios}' se solapa con el registro anterior "
                    f"(que termina en folio plano {prev_hasta_int})."
                ),
                valor_actual=r.folios,
                valor_esperado=f"Debe iniciar desde folio plano {prev_hasta_int + 1}",
            ))

        # Verificar salto
        if expected_next_int is not None and desde_int != expected_next_int:
            if not _salto_aprobado(expected_next_int, desde_int, exclusions):
                delta = abs(desde_int - expected_next_int)
                num_e, cara_e = _int_to_folio_str(expected_next_int)
                errores.append(AnalysisError(
                    record_id=r.id, fila=r.fila,
                    tipo="SALTO",
                    descripcion=(
                        f"Salto de {delta} unidad(es) detectado. "
                        f"Se esperaba '{num_e:03d}{cara_e}', se encontró '{r.folios[:6]}'."
                    ),
                    valor_actual=r.folios,
                    valor_esperado=f"{num_e:03d}{cara_e}",
                ))

        expected_next_int = hasta_int + 1
        prev_hasta_int = hasta_int

    return AnalysisResult(
        nombre="Sucesión de Folios",
        total_revisados=len(records),
        errores=errores,
        advertencias=advertencias,
        info_extra={
            "validados": sum(1 for r in records if r.estado == "VALIDADO"),
            "revisar": len(errores),
        }
    )


# ── B. Data Tópica ────────────────────────────────────────────────────────────

def analizar_topica(records: list) -> AnalysisResult:
    """
    Valida que los títulos/topónimos tengan caracteres alfabéticos válidos.
    Detecta: campos vacíos, caracteres numéricos donde solo debería haber texto,
    caracteres inválidos para nombres geográficos.
    """
    errores: List[AnalysisError] = []

    for r in records:
        titulo = r.titulo.strip() if r.titulo else ""

        if not titulo:
            errores.append(AnalysisError(
                record_id=r.id, fila=r.fila,
                tipo="TOPICA",
                descripcion="El campo 'Título/Tipo de escritura' está vacío.",
                valor_actual="(vacío)",
                valor_esperado="Texto descriptivo del acto jurídico",
            ))
            continue

        # Detectar si el título contiene solo dígitos (probable error de campo)
        if re.match(r'^\d+$', titulo):
            errores.append(AnalysisError(
                record_id=r.id, fila=r.fila,
                tipo="TOPICA",
                descripcion=f"El título '{titulo}' contiene solo dígitos. Posible confusión de columna.",
                valor_actual=titulo,
                valor_esperado="Descripción textual del acto",
            ))

        # Detectar caracteres de control o símbolos extraños
        if re.search(r'[<>{}[\]\\|^`~]', titulo):
            errores.append(AnalysisError(
                record_id=r.id, fila=r.fila,
                tipo="TOPICA",
                descripcion=f"El título '{titulo[:40]}' contiene caracteres inválidos para nombres de archivos/carpetas.",
                valor_actual=titulo,
                valor_esperado="Solo letras, números, espacios y puntuación estándar",
            ))

    return AnalysisResult(
        nombre="Data Tópica",
        total_revisados=len(records),
        errores=errores,
        info_extra={"campos_validados": len(records) - len(errores)},
    )


# ── C. Data Crónica ───────────────────────────────────────────────────────────

def analizar_cronica(records: list) -> AnalysisResult:
    """
    Valida la progresión temporal de la data crónica.
    Detecta: fechas inválidas en el campo 'fecha_inicio' (columna 6/F) o 'registro', regresiones cronológicas.
    """
    errores: List[AnalysisError] = []
    prev_anio: Optional[int] = None

    for r in records:
        # Intentar extraer del campo fecha_inicio primero, luego de registro
        anio = _extraer_anio(getattr(r, "fecha_inicio", ""))
        val_act = getattr(r, "fecha_inicio", "")
        if anio is None:
            anio = _extraer_anio(r.registro)
            val_act = r.registro

        if anio is None:
            errores.append(AnalysisError(
                record_id=r.id, fila=r.fila,
                tipo="CRONICA",
                descripcion=f"No se pudo extraer el año del campo Fecha/Registro '{val_act}'.",
                valor_actual=val_act,
                valor_esperado="Año de 4 dígitos (ej: 1891 o 15/03/1891)",
            ))
            continue

        if anio < 1500 or anio > 2100:
            errores.append(AnalysisError(
                record_id=r.id, fila=r.fila,
                tipo="CRONICA",
                descripcion=f"El año {anio} está fuera del rango histórico esperado (1500-2100).",
                valor_actual=str(anio),
                valor_esperado="Entre 1500 y 2100",
            ))

        if prev_anio is not None and anio < prev_anio:
            errores.append(AnalysisError(
                record_id=r.id, fila=r.fila,
                tipo="CRONICA",
                descripcion=(
                    f"Regresión cronológica: el registro es de {anio} pero el anterior era de {prev_anio}. "
                    f"Los registros deben tener avance temporal progresivo."
                ),
                valor_actual=str(anio),
                valor_esperado=f">= {prev_anio}",
            ))

        prev_anio = anio

    # Helper para min/max
    anios_validos = []
    for r in records:
        a = _extraer_anio(getattr(r, "fecha_inicio", "")) or _extraer_anio(r.registro)
        if a is not None:
            anios_validos.append(a)

    return AnalysisResult(
        nombre="Data Crónica",
        total_revisados=len(records),
        errores=errores,
        info_extra={
            "anio_min": min(anios_validos, default=0),
            "anio_max": max(anios_validos, default=0)
        },
    )


# ── D. Cobertura del PDF ──────────────────────────────────────────────────────

def analizar_coverage(records: list, total_pdf_pages: int, mapper=None) -> AnalysisResult:
    """
    Compara el máximo número de página requerida por el Excel contra el PDF cargado.
    Si mapper es None, usa el campo pg_pdf como referencia estática.
    """
    errores: List[AnalysisError] = []

    max_requerido = 0

    for r in records:
        if mapper:
            pages = mapper.folio_str_to_pdf_pages(r.folios)
            if pages:
                max_requerido = max(max_requerido, pages[-1])
        else:
            # Fallback: parsear pg_pdf estático
            pg = r.pg_pdf
            if pg:
                try:
                    parts = str(pg).split('-')
                    max_requerido = max(max_requerido, int(parts[-1]))
                except (ValueError, IndexError):
                    pass

    diferencia = total_pdf_pages - max_requerido

    if diferencia < 0:
        errores.append(AnalysisError(
            record_id="COVERAGE",
            fila=0,
            tipo="COVERAGE",
            descripcion=(
                f"El PDF tiene {total_pdf_pages} páginas pero el inventario requiere "
                f"{max_requerido} páginas. Faltan {abs(diferencia)} páginas en el PDF."
            ),
            valor_actual=f"PDF: {total_pdf_pages} págs",
            valor_esperado=f">= {max_requerido} págs",
        ))
    elif diferencia > 0:
        pass  # Páginas sobrantes son aceptables (advertencia, no error)

    return AnalysisResult(
        nombre="Cobertura PDF",
        total_revisados=len(records),
        errores=errores,
        info_extra={
            "pdf_total": total_pdf_pages,
            "max_requerido": max_requerido,
            "diferencia": diferencia,
            "estado": "OK" if diferencia >= 0 else "INSUFICIENTE",
        },
    )


# ── Helpers internos ──────────────────────────────────────────────────────────

def _salto_aprobado(desde_int: int, hasta_int: int, exclusions: list) -> bool:
    """Verifica si el salto entre folios está cubierto por una regla de exclusión."""
    for excl in exclusions:
        if getattr(excl, 'tipo', '') == 'SALTO':
            try:
                excl_desde = folio_to_int(int(excl.desde), 'r')
                excl_hasta = folio_to_int(int(excl.hasta), 'v')
                if excl_desde <= desde_int and excl_hasta >= hasta_int:
                    return True
            except Exception:
                pass
    return False


def _int_to_folio_str(n: int):
    """Convierte entero plano a (num, cara)."""
    if n % 2 == 1:
        return (n + 1) // 2, 'r'
    return n // 2, 'v'


def _extraer_anio(registro_str: str) -> Optional[int]:
    """Extrae el año del campo registro o fecha (ej: '1891-001' o '15/03/1891' → 1891)."""
    if not registro_str:
        return None
    match = re.search(r'(\d{4})', str(registro_str).strip())
    if match:
        return int(match.group(1))
    return None
