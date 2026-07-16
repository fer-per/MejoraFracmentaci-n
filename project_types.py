"""
project_types.py — Interfaces de datos para el Escritorio del Archivista.
Equivalente TypeScript → Python usando dataclasses.
"""
from dataclasses import dataclass, field
from typing import Optional, Literal
from datetime import datetime


@dataclass
class InventoryRecord:
    """Fila de Inventario extraída del Excel/CSV."""
    id: str                      # ID incremental autogenerado (#0001, #0002)
    fila: int                    # Número de fila real de la hoja de cálculo
    registro: str                # Código del expediente (ej: "1892-001")
    escribano: str               # Nombre del notario / escribano histórico
    protocolo: str               # ID del protocolo físico (ej: "P-124")
    folios: str                  # Rango de folios original (ej: "002r-003v" o "140")
    pg_pdf: str                  # Páginas correspondientes en el PDF (ej: "1-2")
    titulo: str                  # Asunto o título del documento
    estado: str = ""  # '' | 'REVISAR' | 'FRAGMENTADO'
    fecha_inicio: str = ""
    fecha_fin: str = ""
    interesado1: str = ""
    interesado2: str = ""


@dataclass
class ExclusionRule:
    """Regla de Exclusión: Saltos de secuencia o portadas."""
    id: str
    tipo: str                    # 'SALTO' | 'IGNORAR'
    desde: int                   # Folio desde
    hasta: int                   # Folio hasta
    motivo: str                  # Comentario explicativo
    tipo_contenido: Optional[str] = None  # Para IGNORAR: 'Hoja en Blanco' | 'Portada' | 'Separador'


@dataclass
class SystemLog:
    """Log de Sistema para la Consola interactiva."""
    timestamp: str               # Formato HH:MM:SS
    tipo: str                    # 'INFO' | 'WARN' | 'ERR' | 'SUCCESS'
    mensaje: str

    @staticmethod
    def now(tipo: str, mensaje: str) -> "SystemLog":
        ts = datetime.now().strftime("%H:%M:%S")
        return SystemLog(timestamp=ts, tipo=tipo, mensaje=mensaje)


@dataclass
class SugerenciaCorreccion:
    """Sugerencia de Corrección Inteligente (Discrepancia detectada)."""
    id: str
    registro_id: str              # ID del registro asociado
    tipo_error: str               # "SALTO DE FOLIO" | "ERROR FORMATO"
    descripcion: str              # Justificación detallada del error
    valor_actual: str             # Valor erróneo detectado
    valor_sugerido: str           # Propuesta corregida calculada por algoritmo
    escribano: str
    folios_original: str
    rango_sugerido: str
    paginas_pdf: str
    paginas_sugeridas: str
    fecha_original: str
    fecha_validada: str


@dataclass
class AppState:
    """Estado global compartido de la aplicación."""
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
    
    # Campos añadidos para motor de cálculo real
    segmentos: list = field(default_factory=list)      # Lista de dicts: {'folio_inicio': str, 'pag_pdf_inicio': int}
    overrides: dict = field(default_factory=dict)      # dict: {registro_id: paginas_pdf_overridden_str}
    page_map: dict = field(default_factory=dict)       # dict: {original_page: new_page} para reordenamiento PDF
    output_dir: Optional[str] = None
    acervo_num: str = "7"

