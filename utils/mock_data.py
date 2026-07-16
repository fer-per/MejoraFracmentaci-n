"""
mock_data.py — Datos de pre-carga para la demostración del Archivista.
Simula un protocolo notarial histórico con deliberadas inconsistencias de folios.
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from project_types import InventoryRecord, ExclusionRule, SystemLog, SugerenciaCorreccion
from utils.folio_engine import FolioMapper

mapper_demo = FolioMapper(folio_inicio_num=1, pag_pdf_inicio=1)


def get_mock_records() -> list:
    """Retorna una lista de registros notariales históricos de demostración."""
    records = [
        InventoryRecord(
            id="#0001", fila=2, registro="1891-001",
            escribano="Ramírez, Juan de Dios",
            protocolo="P-124",
            folios="001r-002v", pg_pdf="",
            titulo="Escritura de compraventa de inmueble urbano",
            estado="VALIDADO"
        ),
        InventoryRecord(
            id="#0002", fila=3, registro="1891-002",
            escribano="Ramírez, Juan de Dios",
            protocolo="P-124",
            folios="003r-005v", pg_pdf="",
            titulo="Poder notarial para representación judicial",
            estado="VALIDADO"
        ),
        InventoryRecord(
            id="#0003", fila=4, registro="1891-003",
            escribano="Ramírez, Juan de Dios",
            protocolo="P-124",
            folios="006r-007v", pg_pdf="",
            titulo="Testamento abierto ante notario",
            estado="VALIDADO"
        ),
        InventoryRecord(
            id="#0004", fila=5, registro="1891-004",
            escribano="Morales, Petra Inés",
            protocolo="P-124",
            folios="010r-011v", pg_pdf="",
            titulo="Arrendamiento de finca rústica",
            estado="REVISAR"
        ),
        InventoryRecord(
            id="#0005", fila=6, registro="1891-005",
            escribano="Morales, Petra Inés",
            protocolo="P-124",
            folios="012r-013v", pg_pdf="",
            titulo="Contrato de censo enfitéutico",
            estado="VALIDADO"
        ),
        InventoryRecord(
            id="#0006", fila=7, registro="1891-006",
            escribano="Morales, Petra Inés",
            protocolo="P-124",
            folios="014r-015v", pg_pdf="",
            titulo="Escritura de hipoteca sobre bienes raíces",
            estado="VALIDADO"
        ),
        InventoryRecord(
            id="#0007", fila=8, registro="1891-007",
            escribano="Castillo, Fermín",
            protocolo="P-125",
            folios="016r-018v", pg_pdf="",
            titulo="Constitución de sociedad mercantil",
            estado="VALIDADO"
        ),
        InventoryRecord(
            id="#0008", fila=9, registro="1891-008",
            escribano="Castillo, Fermín",
            protocolo="P-125",
            folios="140",
            titulo="Acta de defunción ante escribano",
            estado="REVISAR",
            pg_pdf="33-34"
        ),
        InventoryRecord(
            id="#0009", fila=10, registro="1892-001",
            escribano="Castillo, Fermín",
            protocolo="P-125",
            folios="021r-023v", pg_pdf="",
            titulo="Inventario de bienes del finado",
            estado="VALIDADO"
        ),
        InventoryRecord(
            id="#0010", fila=11, registro="1892-002",
            escribano="Herrera, Dolores",
            protocolo="P-126",
            folios="024r-026v", pg_pdf="",
            titulo="Testamento cerrado con cláusula fideicomisaria",
            estado="FRAGMENTADO"
        ),
        InventoryRecord(
            id="#0011", fila=12, registro="1892-003",
            escribano="Herrera, Dolores",
            protocolo="P-126",
            folios="027r-029v", pg_pdf="",
            titulo="Poder para testar a favor de heredero único",
            estado="FRAGMENTADO"
        ),
        InventoryRecord(
            id="#0012", fila=13, registro="1892-004",
            escribano="Herrera, Dolores",
            protocolo="P-126",
            folios="030r-031v", pg_pdf="",
            titulo="Acuerdo de partición hereditaria extrajudicial",
            estado="VALIDADO"
        ),
    ]
    for r in records:
        if not r.pg_pdf:
            calculated = mapper_demo.folio_str_to_pdf_range(r.folios)
            r.pg_pdf = calculated or "1"
    return records


def get_mock_exclusions() -> list:
    """Retorna reglas de exclusión de demostración."""
    return [
        ExclusionRule(
            id="EX-001", tipo="SALTO",
            desde=8, hasta=9,
            motivo="Folios 008-009 arrancados por deterioro físico del legajo original (siglo XIX)"
        ),
        ExclusionRule(
            id="EX-002", tipo="IGNORAR",
            desde=19, hasta=20,
            motivo="Hojas en blanco de separación entre protocolos",
            tipo_contenido="Hoja en Blanco"
        ),
    ]


def get_mock_logs() -> list:
    """Retorna logs de demostración."""
    return [
        SystemLog(timestamp="10:24:01", tipo="INFO",
                  mensaje="Sistema inicializado. Versión 2.1.4 — Archivista Pro"),
        SystemLog(timestamp="10:24:03", tipo="INFO",
                  mensaje="Cargando configuración del workspace..."),
        SystemLog(timestamp="10:24:05", tipo="SUCCESS",
                  mensaje="Inventario 'Protocolo_P124_1891.xlsx' cargado — 12 registros detectados"),
        SystemLog(timestamp="10:24:07", tipo="INFO",
                  mensaje="Iniciando análisis de secuencia correlativa de folios..."),
        SystemLog(timestamp="10:24:09", tipo="WARN",
                  mensaje="[#0004] Salto detectado: esperado '008r', encontrado '010r' — delta +4 unidades"),
        SystemLog(timestamp="10:24:09", tipo="WARN",
                  mensaje="[#0008] Error de formato en folio '140' — falta indicador de cara (r/v)"),
        SystemLog(timestamp="10:24:10", tipo="SUCCESS",
                  mensaje="Análisis completado. 10 registros VALIDADOS, 2 requieren revisión"),
    ]


def get_mock_suggestions() -> list:
    """Retorna sugerencias de corrección de demostración."""
    return [
        SugerenciaCorreccion(
            id="SUG-001",
            registro_id="#0004",
            tipo_error="SALTO DE FOLIO",
            descripcion=(
                "Se detectó un salto de 4 unidades en la secuencia correlativa esperada. "
                "El registro anterior (#0003) termina en el folio 007v. "
                "Se esperaba que este registro comenzara en 008r, "
                "pero el inventario declara 010r, generando un hueco no justificado "
                "de los folios 008r al 009v (4 páginas físicas)."
            ),
            valor_actual="010r-011v",
            valor_sugerido="008r-009v",
            escribano="Morales, Petra Inés",
            folios_original="010r-011v",
            rango_sugerido="008r-009v",
            paginas_pdf="15-18",
            paginas_sugeridas="15-18",
            fecha_original="1891-03-15",
            fecha_validada="1891-03-15"
        ),
        SugerenciaCorreccion(
            id="SUG-002",
            registro_id="#0008",
            tipo_error="ERROR FORMATO",
            descripcion=(
                "El folio '140' no contiene indicador de cara (r/v). "
                "El algoritmo no puede determinar si es recto o verso, "
                "impidiendo el cálculo correlativo. "
                "Basado en la secuencia del registro anterior (#0007 termina en 018v), "
                "se sugiere '019r' como valor corregido."
            ),
            valor_actual="140",
            valor_sugerido="019r",
            escribano="Castillo, Fermín",
            folios_original="140",
            rango_sugerido="019r-020v",
            paginas_pdf="33-34",
            paginas_sugeridas="33-34",
            fecha_original="1891-07-22",
            fecha_validada="1891-07-22"
        ),
    ]
