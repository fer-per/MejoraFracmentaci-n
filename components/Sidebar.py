"""
Sidebar.py — Panel lateral colapsable del Escritorio del Archivista.
256px expandido → 80px colapsado. Navegación entre las vistas principales.
"""
import tkinter as tk
from tkinter import ttk
from utils.theme import C, FONT

# (label, ícono_emoji, view_key)
NAV_ITEMS = [
    ("Archivo",                 "📂", "workspace"),
    ("Tabla de Inventario",  "📊", "analyzer"),
    ("Saltos/Exclusiones",   "🚫", "exclusions"),
    ("Procesar",             "⚙",  "process"),
]

BOTTOM_ITEMS = [
    ("Documentación", "❓", "documentation"),
    ("Soporte",       "💬", "support"),
]


class Sidebar(tk.Frame):
    """
    Barra lateral de navegación con colapso animado.
    """

    EXPANDED_W = 240
    COLLAPSED_W = 68

    def __init__(self, parent, app_state, on_navigate, **kwargs):
        super().__init__(parent, **kwargs)
        self.app_state = app_state
        self.on_navigate = on_navigate
        self._expanded = True
        self._active_view = tk.StringVar(value="workspace")
        self._btn_refs = {}

        self.configure(
            bg=C["surface_container"],
            width=self.EXPANDED_W,
        )
        self.pack_propagate(False)

        # Separador derecho
        sep = tk.Frame(self, bg=C["outline_variant"], width=1)
        sep.pack(side="right", fill="y")

        self._build()

    # ── Construcción ────────────────────────────────────────────────────────────
    def _build(self):
        self._inner = tk.Frame(self, bg=C["surface_container"])
        self._inner.pack(fill="both", expand=True)

        # Botón colapsar / expandir
        self._toggle_btn = tk.Button(
            self._inner,
            text="◀",
            font=("Segoe UI", 10),
            fg=C["secondary"],
            bg=C["surface_high"],
            activebackground=C["secondary_container"],
            relief="flat", bd=0,
            cursor="hand2",
            command=self._toggle_collapse,
            padx=8, pady=4,
        )
        self._toggle_btn.pack(fill="x", padx=8, pady=(10, 4))

        # Botón "Nueva Fragmentación"
        self._new_btn = tk.Button(
            self._inner,
            text="  ＋  Nueva Fragmentación",
            font=("Segoe UI", 9, "bold"),
            fg="#ffffff",
            bg=C["primary"],
            activebackground=C["primary_container"],
            activeforeground="#ffffff",
            relief="flat", bd=0,
            cursor="hand2",
            padx=10, pady=8,
            command=self._new_fragmentation,
        )
        self._new_btn.pack(fill="x", padx=8, pady=(4, 12))
        self._add_hover(self._new_btn, C["primary_container"], C["primary"], "#ffffff", "#ffffff")

        # Separador
        tk.Frame(self._inner, bg=C["outline_variant"], height=1).pack(fill="x", padx=8, pady=(0, 8))

        # Ítems de navegación principales
        self._nav_btns = {}
        for label, icon, view_key in NAV_ITEMS:
            widgets = self._make_nav_btn(label, icon, view_key)
            self._btn_refs[view_key + label] = widgets[0]
            self._nav_btns[view_key] = widgets

        # Spacer que empuja los items inferiores al fondo
        spacer = tk.Frame(self._inner, bg=C["surface_container"])
        spacer.pack(fill="both", expand=True)

        # Separador
        tk.Frame(self._inner, bg=C["outline_variant"], height=1).pack(fill="x", padx=8, pady=8)

        # Ítems inferiores (pegados al fondo)
        for label, icon, view_key in BOTTOM_ITEMS:
            self._make_nav_btn(label, icon, view_key)

        # Activar "Archivo" visualmente por defecto (sin navegar, App aún construyendo)
        if "workspace" in self._nav_btns:
            ws = self._nav_btns["workspace"]
            self._set_active("workspace", *ws, call_navigate=False)

    def _make_nav_btn(self, label: str, icon: str, view_key):
        frame = tk.Frame(self._inner, bg=C["surface_container"], cursor="hand2")
        frame.pack(fill="x", padx=6, pady=1)

        # Indicador activo izquierdo
        indicator = tk.Frame(frame, bg=C["surface_container"], width=4)
        indicator.pack(side="left", fill="y")

        icon_lbl = tk.Label(
            frame, text=icon,
            font=("Segoe UI", 14),
            fg=C["secondary"],
            bg=C["surface_container"],
            width=2,
        )
        icon_lbl.pack(side="left", padx=(4, 6), pady=6)

        text_lbl = tk.Label(
            frame, text=label,
            font=("Segoe UI", 9),
            fg=C["secondary"],
            bg=C["surface_container"],
            anchor="w",
        )
        text_lbl.pack(side="left", fill="x", expand=True)
        self._text_labels_for_collapse = getattr(self, '_text_labels_for_collapse', [])
        self._text_labels_for_collapse.append(text_lbl)

        def on_click(vk=view_key, fr=frame, ind=indicator, il=icon_lbl, tl=text_lbl):
            if vk:
                self._set_active(vk, fr, ind, il, tl)

        for w in (frame, icon_lbl, text_lbl, indicator):
            w.bind("<Button-1>", lambda e, f=on_click: f())
            w.bind("<Enter>", lambda e, fr=frame, il=icon_lbl, tl=text_lbl:
                   self._on_hover(fr, il, tl, True))
            w.bind("<Leave>", lambda e, fr=frame, il=icon_lbl, tl=text_lbl:
                   self._on_hover(fr, il, tl, False))

        widgets = (frame, indicator, icon_lbl, text_lbl)
        self._nav_btns[view_key] = widgets
        return widgets

    # ── Interacciones ────────────────────────────────────────────────────────────
    def _set_active(self, view_key, frame, indicator, icon_lbl, text_lbl, call_navigate=True):
        # Resetear todos los ítems
        for child in self._inner.winfo_children():
            if isinstance(child, tk.Frame) and child != frame:
                child.configure(bg=C["surface_container"])
                for w in child.winfo_children():
                    try:
                        w.configure(bg=C["surface_container"])
                        if isinstance(w, tk.Label):
                            w.configure(fg=C["secondary"])
                    except Exception:
                        pass

        # Activar el ítem seleccionado
        frame.configure(bg=C["secondary_container"])
        icon_lbl.configure(bg=C["secondary_container"], fg=C["primary"])
        text_lbl.configure(bg=C["secondary_container"], fg=C["primary"])
        indicator.configure(bg=C["primary"])

        self._active_view.set(view_key)
        if call_navigate and self.on_navigate:
            self.on_navigate(view_key)

    def _on_hover(self, frame, icon_lbl, text_lbl, entering: bool):
        if entering:
            frame.configure(bg=C["surface_highest"])
            icon_lbl.configure(bg=C["surface_highest"])
            text_lbl.configure(bg=C["surface_highest"])
        else:
            frame.configure(bg=C["surface_container"])
            icon_lbl.configure(bg=C["surface_container"])
            text_lbl.configure(bg=C["surface_container"])

    def _toggle_collapse(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.configure(width=self.EXPANDED_W)
            self._toggle_btn.configure(text="◀")
            for lbl in getattr(self, '_text_labels_for_collapse', []):
                lbl.pack(side="left", fill="x", expand=True)
        else:
            self.configure(width=self.COLLAPSED_W)
            self._toggle_btn.configure(text="▶")
            for lbl in getattr(self, '_text_labels_for_collapse', []):
                lbl.pack_forget()

    def clear_selection(self):
        self._active_view.set("")
        for child in self._inner.winfo_children():
            if isinstance(child, tk.Frame):
                child.configure(bg=C["surface_container"])
                for w in child.winfo_children():
                    try:
                        w.configure(bg=C["surface_container"])
                        if isinstance(w, tk.Label):
                            w.configure(fg=C["secondary"])
                    except Exception:
                        pass

    def set_active_view(self, view_key: str):
        if view_key in self._nav_btns:
            widgets = self._nav_btns[view_key]
            self._set_active(view_key, *widgets, call_navigate=False)
        else:
            self.clear_selection()

    # ── Helpers ──────────────────────────────────────────────────────────────────
    def _new_fragmentation(self):
        from tkinter import messagebox
        if messagebox.askyesno("Nueva Fragmentación", "¿Desea iniciar una nueva sesión de fragmentación?\nSe perderán los datos no guardados."):
            self.app_state.records = []
            self.app_state.exclusions = []
            self.app_state.suggestions = []
            self.app_state.logs = []
            self.app_state.excel_path = None
            self.app_state.pdf_path = None
            self.on_navigate("workspace")

    @staticmethod
    def _add_hover(widget, h_bg, n_bg, h_fg=None, n_fg=None):
        def on_enter(e):
            widget.configure(bg=h_bg)
            if h_fg:
                widget.configure(fg=h_fg)
        def on_leave(e):
            widget.configure(bg=n_bg)
            if n_fg:
                widget.configure(fg=n_fg)
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
