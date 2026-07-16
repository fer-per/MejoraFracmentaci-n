"""
App.py — Contenedor de Estado Global e Hilos de Eventos.
Ensambla Header, Sidebar, vistas y el panel PDFPreview.
"""
import tkinter as tk
from tkinter import ttk
import sys
import os

_ROOT = os.path.dirname(__file__)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from project_types import AppState, SystemLog

from components.Header import Header
from components.Sidebar import Sidebar
from components.PDFPreview import PDFPreview
from views.WorkspaceView import WorkspaceView
from views.ExpandedAnalyzerView import ExpandedAnalyzerView
from views.ExclusionsView import ExclusionsView
from views.PDFEditorView import PDFEditorView
from views.ProcessView import ProcessView
from views.PlaceholderView import PlaceholderView
from utils.mock_data import (
    get_mock_records,
    get_mock_exclusions,
    get_mock_logs,
    get_mock_suggestions,
)


from utils.theme import C
from utils.session_manager import save_session, load_session


class App(tk.Frame):
    """
    Contenedor principal de la aplicación.
    Layout: Header (top) → [Sidebar | ContentArea | PDFPreview]
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.configure(bg=C["background"])

        # ── Estado global ────────────────────────────────────────────────────────
        self.state = AppState()
        self.state.records = []
        self.state.exclusions = []
        self.state.logs = [
            SystemLog.now("INFO", "Sistema inicializado. Listo para cargar inventario Excel y PDF maestro.")
        ]
        self.state.suggestions = []

        self._current_view_key = "workspace"
        self._view_cache = {}

        self._build()

        # Attempt to load previous session
        try:
            if load_session(self.state):
                self._add_log("INFO", "Sesión anterior restaurada correctamente.")
        except Exception:
            pass

        # Keyboard shortcuts
        root = self.winfo_toplevel()
        root.bind("<Control-s>", lambda e: self._save_session())
        root.bind("<Control-n>", lambda e: self._navigate("workspace"))
        root.bind("<Control-1>", lambda e: self._navigate("workspace"))
        root.bind("<Control-2>", lambda e: self._navigate("analyzer"))
        root.bind("<Control-3>", lambda e: self._navigate("exclusions"))
        root.bind("<Control-4>", lambda e: self._navigate("process"))

    # ── Construcción ────────────────────────────────────────────────────────────
    def _build(self):
        # Header
        self._header = Header(
            self,
            app_state=self.state,
            on_toggle_dual_view=self._toggle_pdf_panel,
        )
        self._header.pack(side="top", fill="x")

        # Área central (sidebar + contenido + pdf preview)
        self._body = tk.Frame(self, bg=C["background"])
        self._body.pack(side="top", fill="both", expand=True)

        # Sidebar (gestiona su propio ancho con collapse/expand)
        self._sidebar = Sidebar(
            self._body,
            app_state=self.state,
            on_navigate=self._navigate,
        )
        self._sidebar.pack(side="left", fill="y")

        # PanedWindow horizontal: área de contenido | PDF preview
        # El usuario puede arrastrar el separador para ajustar el espacio.
        self._center_paned = tk.PanedWindow(
            self._body,
            orient="horizontal",
            sashwidth=5,
            sashrelief="flat",
            bg=C["outline_variant"],
            handlesize=0,
            sashcursor="sb_h_double_arrow",
            opaqueresize=True,
        )
        self._center_paned.pack(side="left", fill="both", expand=True)

        # Área de contenido central (pane izquierdo, se expande)
        self._content_area = tk.Frame(self._center_paned, bg=C["background"])
        self._center_paned.add(
            self._content_area,
            minsize=400,
            stretch="always",
        )

        # Host para el panel PDF Preview (pane derecho, ancho inicial 340)
        self._pdf_host = tk.Frame(self._center_paned, bg=C["background"])
        self._pdf_panel = PDFPreview(
            self._pdf_host,
            app_state=self.state,
            on_edit_pdf=lambda: self._navigate("pdf_editor"),
        )
        self._pdf_panel.pack(fill="both", expand=True)
        self._pdf_panel.pack_propagate(False)
        self._center_paned.add(
            self._pdf_host,
            minsize=240,
            width=340,
            stretch="always",
        )

        # Cargar vista inicial
        self._show_view("workspace")

    # ── Navegación ───────────────────────────────────────────────────────────────
    def _navigate(self, view_key: str):
        self._show_view(view_key)

    def _show_view(self, view_key: str):
        # Ocultar vista actual
        for child in self._content_area.winfo_children():
            child.pack_forget()

        # Crear o recuperar vista del caché
        if view_key not in self._view_cache:
            view = self._create_view(view_key)
            self._view_cache[view_key] = view

        view = self._view_cache[view_key]
        view.pack(fill="both", expand=True)
        self._current_view_key = view_key

        # Log de navegación
        names = {
            "workspace": "Archivo",
            "analyzer":  "Tabla de Inventario",
            "exclusions": "Saltos y Exclusiones",
            "process": "Procesar y Fragmentar",
            "documentation": "Documentacion",
            "support": "Soporte Tecnico",
        }
        self._add_log("INFO", f"Navegando a: {names.get(view_key, view_key)}")

    def _create_view(self, view_key: str) -> tk.Frame:
        kwargs = dict(
            parent=self._content_area,
            app_state=self.state,
            on_add_log=self._add_log,
            on_load_pdf=self._pdf_panel.load_pdf,
            on_navigate_pdf=self._pdf_panel.go_to_page,
            bg=C["background"],
        )
        if view_key == "workspace":
            return WorkspaceView(
                **kwargs,
                on_navigate=self._navigate,
            )
        elif view_key == "analyzer":
            return ExpandedAnalyzerView(**kwargs)
        elif view_key == "exclusions":
            return ExclusionsView(**kwargs)
        elif view_key == "pdf_editor":
            return PDFEditorView(**kwargs, on_navigate=self._navigate)
        elif view_key == "process":
            return ProcessView(**kwargs)
        elif view_key in ("documentation", "support"):
            kwargs.pop("on_load_pdf", None)
            kwargs.pop("on_navigate_pdf", None)
            if view_key == "documentation":
                return PlaceholderView(
                    **kwargs,
                    title="Documentación del Sistema",
                    description="Aquí encontrará guías de foliación y manuales de usuario del Fragmentador próximamente.",
                )
            else:
                return PlaceholderView(
                    **kwargs,
                    title="Soporte y Asistencia",
                    description="Canal directo para reportar incidencias del sistema o consultas de foliación.",
                )
        else:
            # Vista vacía de placeholder
            frame = tk.Frame(self._content_area, bg=C["background"])
            tk.Label(
                frame,
                text=f"Vista '{view_key}' en construcción",
                font=("Segoe UI", 14),
                fg="#8c7071",
                bg=C["background"],
            ).place(relx=0.5, rely=0.5, anchor="center")
            return frame

    # ── Panel PDF ─────────────────────────────────────────────────────────────────
    def _toggle_pdf_panel(self, active: bool):
        """Añade o elimina el panel PDF del PanedWindow central."""
        if active:
            self._center_paned.add(
                self._pdf_host,
                minsize=240,
                width=340,
                stretch="always",
            )
        else:
            self._center_paned.forget(self._pdf_host)

    # ── Logs ─────────────────────────────────────────────────────────────────────
    def _add_log(self, tipo: str, mensaje: str):
        log = SystemLog.now(tipo, mensaje)
        self.state.logs.append(log)
        self._pdf_panel.append_log(log)
        # Auto-save session periodically (on every 5th log)
        if len(self.state.logs) % 5 == 0 and self.state.records:
            try:
                save_session(self.state)
            except Exception:
                pass

    def _save_session(self):
        try:
            from utils.session_manager import save_session
            path = save_session(self.state)
            self._add_log("SUCCESS", f"Sesión guardada: {os.path.basename(path)}")
        except Exception as e:
            self._add_log("ERR", f"Error al guardar sesión: {e}")
