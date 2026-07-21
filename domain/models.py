"""
domain/models.py — Entidades del dominio.

Puros dataclasses sin dependencias de frameworks ni infraestructura.
Cada entidad representa un concepto central del negocio.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List


class EstadoRecord(str, Enum):
    REVISAR = "REVISAR"
    VALIDADO = "VALIDADO"
    FRAGMENTADO = "FRAGMENTADO"


@dataclass
class InventoryRecord:
    """Fila de Inventario extraida del Excel/CSV."""
    id: str
    fila: int
    registro: str
    escribano: str
    protocolo: str
    folios: str
    pg_pdf: str
    titulo: str
    estado: str = ""
    fecha_inicio: str = ""
    fecha_fin: str = ""
    interesado1: str = ""
    interesado2: str = ""


@dataclass
class ExclusionRule:
    """Regla de Exclusion: Saltos de secuencia o paginas a ignorar."""
    id: str
    tipo: str
    desde: int
    hasta: int
    motivo: str
    tipo_contenido: Optional[str] = None


@dataclass
class SystemLog:
    """Log de Sistema para la consola interactiva."""
    timestamp: str
    tipo: str
    mensaje: str

    @staticmethod
    def now(tipo: str, mensaje: str) -> "SystemLog":
        ts = datetime.now().strftime("%H:%M:%S")
        return SystemLog(timestamp=ts, tipo=tipo, mensaje=mensaje)


@dataclass
class SugerenciaCorreccion:
    """Sugerencia de Correccion Inteligente."""
    id: str
    registro_id: str
    tipo_error: str
    descripcion: str
    valor_actual: str
    valor_sugerido: str
    escribano: str
    folios_original: str
    rango_sugerido: str
    paginas_pdf: str
    paginas_sugeridas: str
    fecha_original: str
    fecha_validada: str


@dataclass
class AnalysisError:
    """Un error individual detectado por un analizador."""
    record_id: str
    fila: int
    tipo: str
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
            return f"{self.nombre}: {self.total_revisados} registros validados sin incidencias."
        return (
            f"{self.nombre}: {len(self.errores)} error(es) en {self.total_revisados} registros."
        )


@dataclass
class AppState:
    """Estado global compartido de la aplicacion."""
    excel_path: Optional[str] = None
    pdf_path: Optional[str] = None
    pdf_original_path: Optional[str] = None
    records: list = field(default_factory=list)
    exclusions: list = field(default_factory=list)
    logs: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    fila_inicio: int = 2
    fila_fin: int = 500
    folio_inicio: int = 1
    pag_pdf_inicio: int = 1
    current_view: str = "workspace"
    pdf_current_page: int = 1
    pdf_total_pages: int = 450
    pdf_zoom: int = 100
    dual_view_active: bool = True
    segmentos: list = field(default_factory=list)
    overrides: dict = field(default_factory=dict)
    page_map: dict = field(default_factory=dict)
    active_pages: list = field(default_factory=list)
    output_dir: Optional[str] = None
    acervo_num: str = "7"


# ── Domain Constants ──────────────────────────────────────────────────────────
FILA_INICIO_DEFAULT = 2
DEFAULT_EXCEL_SHEET = 0

# Folio analysis
YEAR_MIN = 1500
YEAR_MAX = 2100
MAX_IGNORED_ITERATIONS = 2000
FOLIO_MAX_PAGES = 140

# UI Layout
PDF_PANEL_WIDTH = 340

# Excel parsing
EXCEL_HEADER_OFFSET = 9
DEFAULT_SKIPROWS = 7
