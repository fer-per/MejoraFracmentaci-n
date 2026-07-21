"""
adapters/services.py — Funciones de servicio reutilizables para las vistas.
Consolida código duplicado de treeview sorting, hover effects, style
configuration, navigation y constantes mágicas.
"""
import tkinter as tk
from tkinter import ttk
from typing import List, Optional, Callable

from domain.models import InventoryRecord, AppState


# ── Re-export domain constants ───────────────────────────────────────────────
from domain.models import DEFAULT_SKIPROWS as CALC_SKIPROWS, EXCEL_HEADER_OFFSET as CAL_HEADER_OFFSET


# ── Navegación a registro en PDF ─────────────────────────────────────────────
def navigate_to_record_pdf(
    tree: ttk.Treeview,
    records: List[InventoryRecord],
    record_id: str,
    on_navigate_pdf: Optional[Callable[[int], None]] = None,
) -> Optional[InventoryRecord]:
    """Selecciona un registro en el treeview y navega el PDF a su primera página.

    Patrón duplicado en WorkspaceView, ExpandedAnalyzerView, ExclusionsView y
    ProcessView._on_row_select.

    Returns:
        El registro encontrado, o None si no se encontró o no tiene pg_pdf.
    """
    record = next((r for r in records if r.id == record_id), None)
    if record and record.pg_pdf:
        try:
            first_page = int(str(record.pg_pdf).split("-")[0].strip())
            if on_navigate_pdf:
                on_navigate_pdf(first_page)
        except Exception:
            pass
    return record


# ── Sort de columnas de treeview ─────────────────────────────────────────────
def make_treeview_sortable(
    tree: ttk.Treeview,
    col: str,
    reverse_attr_prefix: str = "_sort",
) -> None:
    """Ordena las filas de un treeview por la columna indicada.

    Patrón duplicado en ExpandedAnalyzerView._sort_treeview y
    ProcessView._sort_treeview.
    """
    data = [(tree.set(child, col), child) for child in tree.get_children("")]
    attr = f"{reverse_attr_prefix}_{col}"
    reverse = getattr(tree, attr, False)
    try:
        data.sort(
            key=lambda t: int(t[0].replace("#", "").replace("%", "")),
            reverse=reverse,
        )
    except (ValueError, TypeError):
        data.sort(key=lambda t: t[0], reverse=reverse)
    for index, (_, child) in enumerate(data):
        tree.move(child, "", index)
    setattr(tree, attr, not reverse)


# ── Efecto hover genérico ────────────────────────────────────────────────────
def add_hover_effect(
    widget: tk.Widget,
    hover_color: str,
    normal_color: str,
    hover_fg: Optional[str] = None,
    normal_fg: Optional[str] = None,
) -> None:
    """Agrega efecto hover a un widget tkinter.

    Patrón duplicado en Header._add_hover, Sidebar._add_hover y
    ExpandedAnalyzerView._add_hover_effect (versión simplificada).
    """

    def _on_enter(_event):
        if str(widget["state"]) != "disabled":
            widget.configure(bg=hover_color)
            if hover_fg:
                widget.configure(fg=hover_fg)

    def _on_leave(_event):
        if str(widget["state"]) != "disabled":
            widget.configure(bg=normal_color)
            if normal_fg:
                widget.configure(fg=normal_fg)

    widget.bind("<Enter>", _on_enter)
    widget.bind("<Leave>", _on_leave)


# ── Estilo de treeview ───────────────────────────────────────────────────────
def configure_treeview_style(
    style_name: str,
    bg_color: str,
    fg_color: str,
    field_bg: str,
    row_height: int = 28,
    font_size: int = 8,
    heading_bg: Optional[str] = None,
    heading_fg: Optional[str] = None,
    selected_bg: Optional[str] = None,
) -> None:
    """Configura un estilo ttk.Treeview con colores, altura y fuente.

    Patrón duplicado en WorkspaceView, ExpandedAnalyzerView, ExclusionsView
    y ProcessView.

    Args:
        style_name: Nombre del estilo (ej. "Preview.Treeview").
        bg_color: Color de fondo del treeview body.
        fg_color: Color de texto del treeview body.
        field_bg: Color de background de las celdas.
        row_height: Altura de cada fila en píxeles.
        font_size: Tamaño de fuente del body.
        heading_bg: Color de fondo del heading (default: surface_high).
        heading_fg: Color de texto del heading (default: primary).
        selected_bg: Color de fondo al seleccionar una fila.
    """
    from utils.theme import C

    style = ttk.Style()
    style.configure(
        style_name,
        background=bg_color,
        foreground=fg_color,
        fieldbackground=field_bg,
        rowheight=row_height,
        font=("Segoe UI", font_size),
    )
    style.configure(
        f"{style_name}.Heading",
        background=heading_bg or C["surface_high"],
        foreground=heading_fg or C["primary"],
        font=("Segoe UI", font_size, "bold"),
        relief="flat",
    )
    if selected_bg:
        style.map(style_name, background=[("selected", selected_bg)])
