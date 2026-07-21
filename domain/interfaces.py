"""
domain/interfaces.py — Puertos (interfaces) para la capa de infraestructura.

Define contratos que los adaptadores deben implementar.
Permite cambiar implementaciones sin afectar la logica de negocio.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from domain.models import (
    InventoryRecord,
    ExclusionRule,
    SugerenciaCorreccion,
    AnalysisResult,
    AppState,
)


class FolioParserPort(ABC):
    """Puerto para el parser de folios historicos."""

    @abstractmethod
    def parse(self, folio_str: str) -> Optional[tuple]:
        """Interpreta un string de foliacion y retorna tupla numerica."""

    @abstractmethod
    def folio_to_int(self, num: int, cara: str) -> int:
        """Convierte folio con cara a entero plano."""

    @abstractmethod
    def int_to_folio(self, n: int) -> tuple:
        """Convierte entero plano a (num_folio, cara)."""

    @abstractmethod
    def format_folio(self, num: int, cara: str) -> str:
        """Formatea folio como string estilizado."""


class FolioMapperPort(ABC):
    """Puerto para el motor de mapeo folio -> pagina PDF."""

    @abstractmethod
    def folio_str_to_pdf_pages(self, folio_str: str) -> Optional[List[int]]:
        """Convierte string de folio a lista de paginas PDF reales."""

    @abstractmethod
    def folio_str_to_pdf_range(self, folio_str: str) -> Optional[str]:
        """Convierte folio_str a string de rango de paginas PDF."""

    @abstractmethod
    def max_pdf_page(self, records: list) -> int:
        """Calcula la pagina PDF maxima requerida."""


class AnalyzerPort(ABC):
    """Puerto para un analizador de calidad de datos."""

    @abstractmethod
    def analyze(
        self, records: list, exclusions: Optional[list] = None
    ) -> AnalysisResult:
        """Ejecuta el analisis y retorna resultado."""


class ExcelLoaderPort(ABC):
    """Puerto para la carga de archivos Excel de inventario."""

    @abstractmethod
    def load(self, path: str, app_state: AppState) -> "ExcelLoadResult":
        """Carga y procesa un archivo Excel."""


class SessionPersistencePort(ABC):
    """Puerto para persistencia de sesiones."""

    @abstractmethod
    def save(self, app_state: AppState, path: str = None) -> str:
        """Guarda la sesion. Retorna la ruta del archivo."""

    @abstractmethod
    def load(self, app_state: AppState, path: str = None) -> bool:
        """Carga la sesion. Retorna True si fue exitoso."""


class HierarchyBuilderPort(ABC):
    """Puerto para la construccion de jerarquias de carpetas."""

    @abstractmethod
    def build_path(
        self, record: InventoryRecord, app_state: AppState, base_dir: str
    ) -> str:
        """Construye la ruta jerarquica para un registro."""
