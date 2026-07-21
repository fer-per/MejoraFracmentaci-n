"""
folio_engine.py — Motor Central de Mapeo Folio → Página PDF.

Implementa la lógica matemática completa descrita en el Sistema de Automatización
Archivística:
  - Conversión notación recto/vuelta a página absoluta.
  - Offset base (folio_inicio → pag_pdf_inicio).
  - Segmentos adicionales de desplazamiento.
  - Desplazamiento recursivo por páginas ignoradas (exclusiones tipo IGNORAR).
"""
from __future__ import annotations
from typing import List, Optional, Tuple
import os

from utils.folio_parser import (
    parse_folios, folio_to_int, int_to_folio, format_folio
)
from domain.models import MAX_IGNORED_ITERATIONS


# ── Tipos internos ───────────────────────────────────────────────────────────

class Segmento:
    """Punto de quiebre de offset adicional en el PDF."""
    def __init__(self, folio_inicio_str: str, pag_pdf_inicio: int):
        parsed = parse_folios(folio_inicio_str)
        if parsed:
            self.folio_int = folio_to_int(parsed[0], parsed[1])
        else:
            self.folio_int = 1
        self.pag_pdf_inicio = pag_pdf_inicio

    def __repr__(self):
        num, cara = int_to_folio(self.folio_int)
        return f"Segmento({format_folio(num, cara)} → pág {self.pag_pdf_inicio})"


class FolioMapper:
    """
    Motor de mapeo completo.

    Parámetros:
        folio_inicio_num:  Número de folio base (ej: 1 para 1r).
        pag_pdf_inicio:    Página real del PDF que corresponde al folio_inicio_num (recto).
        segmentos:         Lista de Segmento para desplazamientos adicionales.
        ignoradas:         Lista de enteros con páginas PDF a ignorar (tras aplicar offset).
    """

    def __init__(
        self,
        folio_inicio_num: int = 1,
        pag_pdf_inicio: int = 1,
        segmentos: Optional[List[Segmento]] = None,
        ignoradas: Optional[List[int]] = None,
        page_map: Optional[dict] = None,
    ):
        self.folio_inicio_num = folio_inicio_num
        self.page_map: Optional[dict] = page_map  # {original_page: new_page}
        
        # Traducir pag_pdf_inicio del espacio de trabajo al espacio original usando page_map
        self.pag_pdf_inicio = pag_pdf_inicio
        if page_map:
            orig_page = None
            for op, np in page_map.items():
                if np == pag_pdf_inicio:
                    orig_page = op
                    break
            if orig_page is not None:
                self.pag_pdf_inicio = orig_page

        self.segmentos: List[Segmento] = sorted(
            segmentos or [], key=lambda s: s.folio_int
        )
        # Traducir los segmentos también si hay page_map
        if page_map:
            for seg in self.segmentos:
                seg_orig = None
                for op, np in page_map.items():
                    if np == seg.pag_pdf_inicio:
                        seg_orig = op
                        break
                if seg_orig is not None:
                    seg.pag_pdf_inicio = seg_orig

        self.ignoradas_set: set = set(ignoradas or [])

    # ── API pública ──────────────────────────────────────────────────────────

    def folio_str_to_pdf_pages(self, folio_str: str) -> Optional[List[int]]:
        """
        Convierte un string de folio en la lista de páginas PDF reales.
        Aplica offset base, segmentos y desplazamiento por páginas ignoradas.

        Retorna None si el folio_str es inválido.
        """
        parsed = parse_folios(folio_str)
        if parsed is None:
            return None

        desde_num, desde_cara, hasta_num, hasta_cara = parsed
        desde_int = folio_to_int(desde_num, desde_cara)
        hasta_int = folio_to_int(hasta_num, hasta_cara)

        pages = []
        for folio_int in range(desde_int, hasta_int + 1):
            raw = self._folio_int_to_raw_pdf(folio_int)
            adjusted = self._shift_by_ignored(raw)
            if self.page_map is not None:
                if adjusted in self.page_map:
                    adjusted = self.page_map[adjusted]
                    if adjusted is None:
                        continue
                else:
                    continue
            pages.append(adjusted)

        return pages

    def folio_str_to_pdf_range(self, folio_str: str) -> Optional[str]:
        """
        Convierte folio_str a un string de rango de páginas PDF ("1-4", "7", etc.)
        """
        pages = self.folio_str_to_pdf_pages(folio_str)
        if not pages:
            return None
        if len(pages) == 1:
            return str(pages[0])
        return f"{pages[0]}-{pages[-1]}"

    def max_pdf_page(self, records: list) -> int:
        """
        Calcula la página PDF máxima requerida por el conjunto de registros.
        Útil para el analizador COVERAGE.
        """
        max_p = 0
        for r in records:
            pages = self.folio_str_to_pdf_pages(r.folios)
            if pages:
                max_p = max(max_p, pages[-1])
        return max_p

    # ── Lógica interna ───────────────────────────────────────────────────────

    def _folio_int_to_raw_pdf(self, folio_int: int) -> int:
        """
        Convierte un folio_int a su número de página PDF *antes* de aplicar ignoradas.
        Busca el segmento más apropiado y aplica la traslación.
        """
        # Buscar segmento activo: el más grande con folio_int <= folio_int
        segmento_activo = None
        for seg in reversed(self.segmentos):
            if folio_int >= seg.folio_int:
                segmento_activo = seg
                break

        if segmento_activo:
            delta = folio_int - segmento_activo.folio_int
            raw = segmento_activo.pag_pdf_inicio + delta
        else:
            # Offset base: folio_inicio_num (en recto, int = 2*folio_inicio_num - 1)
            folio_inicio_int = folio_to_int(self.folio_inicio_num, 'r')
            delta = folio_int - folio_inicio_int
            raw = self.pag_pdf_inicio + delta

        return max(1, raw)

    def _shift_by_ignored(self, raw_page: int) -> int:
        """
        Desplaza la página raw hacia adelante omitiendo las páginas ignoradas.
        Algoritmo iterativo: mientras la página candidata caiga en ignoradas, avanza.
        """
        page = raw_page
        visited = 0
        while page in self.ignoradas_set and visited < MAX_IGNORED_ITERATIONS:
            page += 1
            visited += 1
        return page


# ── Helpers de construcción desde AppState ───────────────────────────────────

def mapper_from_state(app_state) -> FolioMapper:
    """
    Construye un FolioMapper desde el AppState de la aplicación.
    Lee: folio_inicio, pag_pdf_inicio, segmentos, y exclusiones tipo IGNORAR.
    """
    # Páginas ignoradas: las exclusiones tipo IGNORAR con páginas PDF
    ignoradas: List[int] = []
    for excl in getattr(app_state, 'exclusions', []):
        if getattr(excl, 'tipo', '') == 'IGNORAR':
            # Exclusiones de páginas PDF (usamos desde/hasta como páginas de PDF)
            try:
                for p in range(int(excl.desde), int(excl.hasta) + 1):
                    ignoradas.append(p)
            except (TypeError, ValueError):
                pass

    # Segmentos adicionales desde el estado
    segmentos: List[Segmento] = []
    for seg_data in getattr(app_state, 'segmentos', []):
        try:
            seg = Segmento(
                folio_inicio_str=seg_data.get('folio_inicio', '1r'),
                pag_pdf_inicio=int(seg_data.get('pag_pdf_inicio', 1)),
            )
            segmentos.append(seg)
        except Exception:
            pass

    return FolioMapper(
        folio_inicio_num=getattr(app_state, 'folio_inicio', 1),
        pag_pdf_inicio=getattr(app_state, 'pag_pdf_inicio', 1),
        segmentos=segmentos,
        ignoradas=ignoradas,
        page_map=getattr(app_state, 'page_map', None),
    )


def parse_ignored_pages(pages_str: str) -> List[int]:
    """
    Convierte un string de páginas ignoradas como '5, 10-12, 100' a una lista de enteros.
    """
    result = []
    for part in pages_str.split(','):
        part = part.strip()
        if '-' in part:
            try:
                start, end = part.split('-', 1)
                result.extend(range(int(start.strip()), int(end.strip()) + 1))
            except ValueError:
                pass
        elif part.isdigit():
            result.append(int(part))
    return result
