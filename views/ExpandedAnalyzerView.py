"""
ExpandedAnalyzerView.py — Pantalla 2: Vista Expandida y Analizadores de Calidad.
Tabla de 12 columnas, tabs de análisis heurístico, panel de stats y modal de corrección.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

import os
from utils.analyzers import analizar_folios, analizar_topica, analizar_cronica, analizar_coverage
from utils.folio_engine import mapper_from_state
from utils.folio_parser import parse_folios
from utils.theme import C, FONT

ESTADO_CONFIG = {
    "VALIDADO":   {"bg": "#dbeafe", "fg": "#1e3a5f"},
    "REVISAR":    {"bg": "#fee2e2", "fg": "#7f1d1d"},
    "FRAGMENTADO":{"bg": "#d1fae5", "fg": "#064e3b"},
    "SALTO":      {"bg": "#fee2e2", "fg": "#7f1d1d"},
    "OCR PENDIENTE": {"bg": "#fef9c3", "fg": "#713f12"},
}

ANALYZER_TABS = [
    ("🗂  FOLIOS",   "folios"),
    ("📍 TÓPICA",   "topica"),
    ("📅 CRÓNICA",  "cronica"),
    ("📊 COVERAGE", "coverage"),
]


class ExpandedAnalyzerView(tk.Frame):
    """Vista expandida de análisis con grilla de 12 columnas y modal de corrección."""

    def __init__(self, parent, app_state, on_add_log, **kwargs):
        self.on_navigate_pdf = kwargs.pop("on_navigate_pdf", None)
        kwargs.pop("on_load_pdf", None)
        super().__init__(parent, **kwargs)
        self.app_state = app_state
        self.on_add_log = on_add_log
        self._selected_record = None
        self._active_tab = tk.StringVar(value="folios")
        self._showing_errors_only = False
        self._last_analysis_key = None
        self._per_tab_error_ids = {}
        self._per_tab_showing_errors = {}
        self._per_tab_analysis_done = {}
        self._per_tab_results = {}
        self.configure(bg=C["background"])
        self._build()
        self.bind("<Map>", lambda e: self.refresh())

    def refresh(self):
        self._populate_table()
        self._update_stats_ui()
        if hasattr(self, "_coverage_canvas") and self._coverage_canvas:
            self._coverage_canvas.configure(scrollregion=self._coverage_canvas.bbox("all"))

    # ── Construcción ────────────────────────────────────────────────────────────
    def _build(self):
        # Header fijo arriba
        self._build_header()

        # Inicialización ficticia para evitar errores de atributo al crear las pestañas
        self._table_frame = None
        self._build_analyzer_tabs()

        # PanedWindow vertical: tabla (arriba) | panel de estadísticas (abajo)
        outer = tk.Frame(self, bg=C["background"])
        outer.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._main_paned = tk.PanedWindow(
            outer,
            orient="vertical",
            sashwidth=6,
            sashrelief="flat",
            bg=C["outline_variant"],
            handlesize=0,
            opaqueresize=True,
        )
        self._main_paned.pack(fill="both", expand=True)

        # Pane superior: tabla de registros
        self._table_frame = tk.Frame(self._main_paned, bg=C["background"])
        self._main_paned.add(
            self._table_frame,
            minsize=160,
            stretch="always",
        )

        # Pane inferior: panel de estadísticas (altura inicial ~120px)
        self._stats_panel = self._build_stats_panel(self._main_paned)
        self._main_paned.add(
            self._stats_panel,
            minsize=90,
            height=120,
            stretch="always",
        )

        self._build_table()

    def _build_header(self):
        h = tk.Frame(self, bg=C["background"])
        h.pack(fill="x", padx=16, pady=(16, 8))

        tk.Label(
            h,
            text="Analizadores de Calidad",
            font=("Segoe UI", 18, "bold"),
            fg=C["primary"],
            bg=C["background"],
        ).pack(side="left")

        tk.Label(
            h,
            text="Validación heurística de la integridad y consistencia de la foliación.",
            font=("Segoe UI", 9),
            fg=C["secondary"],
            bg=C["background"],
        ).pack(side="left", padx=(16, 0), anchor="s", pady=(0, 3))

    def _build_analyzer_tabs(self):
        tabs_frame = tk.Frame(
            self,
            bg=C["surface_container"],
            pady=6,
        )
        tabs_frame.pack(fill="x", padx=16, pady=(0, 8))
        tk.Frame(tabs_frame, bg=C["outline_variant"], height=1).pack(side="bottom", fill="x")

        self._tab_btns = {}
        for label, key in ANALYZER_TABS:
            btn = tk.Button(
                tabs_frame,
                text=label,
                font=("Segoe UI", 8, "bold"),
                fg=C["secondary"],
                bg=C["surface_container"],
                activeforeground=C["primary"],
                activebackground=C["secondary_container"],
                relief="flat", bd=0,
                cursor="hand2",
                padx=14, pady=6,
                command=lambda k=key: self._activate_tab(k),
            )
            btn.pack(side="left", padx=2)
            self._tab_btns[key] = btn

        # Botón para iniciar análisis manualmente
        self._run_analysis_btn = tk.Button(
            tabs_frame,
            text="▶ Iniciar Análisis",
            font=("Segoe UI", 9, "bold"),
            fg="#ffffff",
            bg="#1e3a5f",
            activebackground="#112233",
            relief="flat", bd=0,
            cursor="hand2",
            padx=14, pady=5,
            command=self._execute_analysis,
        )
        self._run_analysis_btn.pack(side="right", padx=10)

        # Botón toggle: mostrar solo errores / regresar a toda la lista
        self._toggle_errors_btn = tk.Button(
            tabs_frame,
            text="  ⚠ Mostrar solo errores  ",
            font=("Segoe UI", 8, "bold"),
            fg=C["primary"],
            bg=C["surface_low"],
            activebackground=C["secondary_container"],
            activeforeground=C["primary"],
            relief="flat", bd=0,
            cursor="hand2",
            padx=10, pady=5,
            command=self._toggle_error_filter,
            state="disabled",
        )
        self._toggle_errors_btn.pack(side="right", padx=(0, 4))
        self._add_hover_effect(self._toggle_errors_btn, C["secondary_container"], C["surface_low"])

        self._activate_tab("folios")

    def _update_toggle_button_state(self, key=None):
        if key is None:
            key = self._active_tab.get()
        analysis_done = self._per_tab_analysis_done.get(key, False)
        error_ids = self._per_tab_error_ids.get(key, set())
        showing_errors = self._per_tab_showing_errors.get(key, False)

        if not analysis_done:
            self._toggle_errors_btn.configure(
                state="disabled",
                text="  ⚠ Mostrar solo errores  ",
                bg=C["surface_low"], fg=C["primary"],
                activebackground=C["secondary_container"],
            )
        elif len(error_ids) == 0:
            self._toggle_errors_btn.configure(
                state="disabled",
                text="  ✅ Analizador correcto  ",
                bg="#1a5c2e", fg="#ffffff",
                activebackground="#14532d",
            )
        elif showing_errors:
            self._toggle_errors_btn.configure(
                state="normal",
                text="  ↩ Regresar a toda la lista  ",
                bg="#d44040", fg="#ffffff",
                activebackground="#b33030",
            )
        else:
            self._toggle_errors_btn.configure(
                state="normal",
                text="  ⚠ Mostrar solo errores  ",
                bg=C["surface_low"], fg=C["primary"],
                activebackground=C["secondary_container"],
            )

    def _activate_tab(self, key: str):
        # Guardar estado del tab actual
        current = self._active_tab.get()
        self._per_tab_showing_errors[current] = self._showing_errors_only

        for k, btn in self._tab_btns.items():
            if k == key:
                btn.configure(
                    bg=C["secondary_container"],
                    fg=C["primary"],
                    relief="groove",
                )
            else:
                btn.configure(
                    bg=C["surface_container"],
                    fg=C["secondary"],
                    relief="flat",
                )
        self._active_tab.set(key)
        # Restaurar estado del tab destino
        self._showing_errors_only = self._per_tab_showing_errors.get(key, False)
        self._update_toggle_button_state(key)
        # Reconstruir la tabla solo si ya fue creada y no es None
        if getattr(self, "_table_frame", None) is not None:
            self._build_table()

    def _add_hover_effect(self, widget, hover_color, normal_color):
        def _get_leave_bg():
            txt = widget.cget("text")
            if "✅ Analizador correcto" in txt:
                return "#1a5c2e"
            if "Regresar" in txt:
                return "#d44040"
            key = self._active_tab.get()
            if self._per_tab_showing_errors.get(key, False):
                return "#d44040"
            return normal_color
        def on_enter(e):
            if str(widget["state"]) != "disabled":
                txt = widget.cget("text")
                if "✅ Analizador correcto" in txt or "Regresar" in txt:
                    return
                widget.configure(bg=hover_color)
        def on_leave(e):
            if str(widget["state"]) != "disabled":
                widget.configure(bg=_get_leave_bg())
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def _toggle_error_filter(self):
        """Alterna entre mostrar solo errores y toda la lista."""
        self._showing_errors_only = not self._showing_errors_only
        key = self._active_tab.get()
        self._per_tab_showing_errors[key] = self._showing_errors_only
        self._update_toggle_button_state(key)
        self._populate_table()

    def _execute_analysis(self):
        key = self._active_tab.get()
        records = self.app_state.records
        exclusions = self.app_state.exclusions
        mapper = mapper_from_state(self.app_state)

        # Resetear estado de errores previos de este tipo de analizador
        self._per_tab_error_ids[key] = set()
        self._per_tab_analysis_done[key] = True
        self._last_analysis_key = key

        if key == "folios":
            res = analizar_folios(records, exclusions)
            self.on_add_log("INFO", f"Corriendo: {res.resumen}")
            for err in res.errores:
                self._per_tab_error_ids[key].add(err.record_id)
                for rec in self.app_state.records:
                    if rec.id == err.record_id:
                        rec.estado = "REVISAR"
                        break
            self._update_stats_ui()
            self._build_table()

            if not res.ok:
                for err in res.errores:
                    self.on_add_log("WARN", f"[{err.record_id}] Fila {err.fila} - {err.tipo}: {err.descripcion}")
            else:
                self.on_add_log("SUCCESS", "Sucesión de folios 100% íntegra y secuencial.")

        elif key == "topica":
            res = analizar_topica(records)
            self.on_add_log("INFO", f"Corriendo: {res.resumen}")
            # Solo marcar REVISAR los registros con errores de topica
            for err in res.errores:
                self._per_tab_error_ids[key].add(err.record_id)
                for rec in self.app_state.records:
                    if rec.id == err.record_id:
                        rec.estado = "REVISAR"
                        break
            self._populate_other_suggestions(res.errores, "TÓPICA")
            self._update_stats_ui()
            self._build_table()

            if not res.ok:
                for err in res.errores:
                    self.on_add_log("WARN", f"[{err.record_id}] Fila {err.fila}: {err.descripcion}")
            else:
                self.on_add_log("SUCCESS", "Data Tópica validada: sin caracteres inválidos ni campos vacíos.")

        elif key == "cronica":
            res = analizar_cronica(records)
            self.on_add_log("INFO", f"Corriendo: {res.resumen}")
            # Solo marcar REVISAR los registros con errores de cronica
            for err in res.errores:
                self._per_tab_error_ids[key].add(err.record_id)
                for rec in self.app_state.records:
                    if rec.id == err.record_id:
                        rec.estado = "REVISAR"
                        break
            self._populate_other_suggestions(res.errores, "CRÓNICA")
            self._update_stats_ui()
            self._build_table()

            if not res.ok:
                for err in res.errores:
                    self.on_add_log("WARN", f"[{err.record_id}] Fila {err.fila}: {err.descripcion}")
            else:
                self.on_add_log("SUCCESS", "Data Crónica validada: progresión temporal consistente.")

        elif key == "coverage":
            res = analizar_coverage(records, self.app_state.pdf_total_pages, mapper)
            self._per_tab_results["coverage"] = res
            self.on_add_log("INFO", f"Corriendo: {res.resumen}")
            for err in res.errores:
                self._per_tab_error_ids[key].add(err.record_id)
                for rec in self.app_state.records:
                    if rec.id == err.record_id:
                        rec.estado = "REVISAR"
                        break
            self._update_stats_ui()
            self._build_table()

            if not res.ok:
                for err in res.errores:
                    self.on_add_log("WARN", f"Cobertura PDF insuficiente: {err.descripcion}")
            else:
                self.on_add_log("SUCCESS", "Cobertura PDF OK: El PDF cubre el máximo requerido.")

        # Actualizar estado del botón según resultado
        self._update_toggle_button_state(key)

    def _populate_other_suggestions(self, errores, tipo_analisis):
        from project_types import SugerenciaCorreccion
        # Limpiar sugerencias anteriores de este tipo
        self.app_state.suggestions = [s for s in self.app_state.suggestions if s.tipo_error != tipo_analisis]
        
        for err in errores:
            rec = next((r for r in self.app_state.records if r.id == err.record_id), None)
            if not rec:
                continue
            
            valor_act = err.valor_actual
            if tipo_analisis == "TÓPICA":
                import re
                sug_val = re.sub(r'[<>{}[\]\\|^`~]', '', valor_act)
                desc = "Título con caracteres inválidos"
            elif tipo_analisis == "CRÓNICA":
                sug_val = "1891"
                desc = "Regresión de fecha o formato inválido"
            else:
                sug_val = valor_act
                desc = err.descripcion
                
            sug = SugerenciaCorreccion(
                id=f"SUG-{len(self.app_state.suggestions)+1:03d}",
                registro_id=err.record_id,
                tipo_error=tipo_analisis,
                descripcion=err.descripcion or desc,
                valor_actual=valor_act,
                valor_sugerido=sug_val,
                escribano=rec.escribano,
                folios_original=rec.folios,
                rango_sugerido=rec.folios,
                paginas_pdf=rec.pg_pdf,
                paginas_sugeridas=rec.pg_pdf,
                fecha_original=getattr(rec, "fecha_inicio", ""),
                fecha_validada=sug_val
            )
            self.app_state.suggestions.append(sug)


    # ── Tabla principal ──────────────────────────────────────────────────────────
    def _build_table(self):
        # Destruir tabla anterior si existe
        for w in self._table_frame.winfo_children():
            w.destroy()

        tab = self._active_tab.get()

        # Coverage usa un dashboard en lugar de tabla
        if tab == "coverage":
            self._build_coverage_view()
            return

        # Contenedor con scroll
        container = tk.Frame(self._table_frame, bg=C["background"])
        container.pack(fill="both", expand=True)

        # Scrollbars
        vsb = tk.Scrollbar(container, orient="vertical")
        vsb.pack(side="right", fill="y")
        hsb = tk.Scrollbar(container, orient="horizontal")
        hsb.pack(side="bottom", fill="x")

        # Configurar estilo de la grilla
        style = ttk.Style()
        style.configure(
            "Archivista.Treeview",
            background=C["surface"],
            foreground=C["tertiary"],
            fieldbackground=C["surface"],
            rowheight=32,
            font=("Segoe UI", 8),
        )
        style.configure(
            "Archivista.Treeview.Heading",
            background=C["surface_high"],
            foreground=C["primary"],
            font=("Segoe UI", 8, "bold"),
            relief="flat",
        )
        style.map("Archivista.Treeview", background=[("selected", "#f0e8ec")])

        # Columnas dinámicas según el tab activo
        base_cols = ("Fila", "Registro", "Escribano", "Protocolo", "Folios", "Pág.PDF", "Título")
        if tab == "topica":
            cols = base_cols + ("Data Tópica", "Estado")
        elif tab == "cronica":
            cols = base_cols + ("Data Crónica", "Estado")
        else:
            cols = base_cols + ("Estado",)

        self._tree = ttk.Treeview(
            container,
            columns=cols,
            show="headings",
            style="Archivista.Treeview",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            selectmode="browse",
        )
        vsb.configure(command=self._tree.yview)
        hsb.configure(command=self._tree.xview)

        # Anchos de columnas
        col_widths = {
            "Fila": 50, "Registro": 90, "Escribano": 140,
            "Protocolo": 70, "Folios": 90, "Pág.PDF": 70,
            "Título": 100, "Data Tópica": 100, "Data Crónica": 100, "Estado": 100,
        }
        for col in cols:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=col_widths.get(col, 100), anchor="w", minwidth=50)

        # Tags de color
        self._tree.tag_configure("even", background=C["surface_low"])
        self._tree.tag_configure("odd", background=C["surface"])
        self._tree.tag_configure("revisar", background="#fff0f0")
        self._tree.tag_configure("fragmentado", background="#f0fff4")

        self._populate_table()
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self._tree.bind("<MouseWheel>", lambda e: self._tree.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Make columns sortable
        for col in cols:
            self._tree.heading(col, command=lambda c=col: self._sort_treeview(c))

    def _build_coverage_view(self):
        container = tk.Frame(self._table_frame, bg=C["background"])
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=C["background"], highlightthickness=0)
        vsb = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=C["background"])
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _configure_inner(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _configure_inner)

        def _configure_canvas(e):
            canvas.itemconfig("inner_window", width=e.width)
        canvas.bind("<Configure>", _configure_canvas)
        canvas.itemconfig(canvas.create_window((0, 0), window=inner, anchor="nw"), tags="inner_window")

        self._coverage_inner = inner
        self._coverage_canvas = canvas

        res = self._per_tab_results.get("coverage")
        if not res:
            self._show_coverage_placeholder(inner)
            return

        self._populate_coverage_view(inner, res)

    def _show_coverage_placeholder(self, parent):
        placeholder = tk.Frame(parent, bg=C["surface"], padx=40, pady=40,
                               highlightbackground=C["outline_variant"], highlightthickness=1)
        placeholder.pack(expand=True, padx=60, pady=60, fill="both")
        tk.Label(placeholder, text="📊 Cobertura del PDF",
                 font=("Segoe UI", 16, "bold"), fg=C["primary"], bg=C["surface"]).pack(pady=(0, 8))
        tk.Label(placeholder, text="Presiona \"▶ Iniciar Análisis\" para evaluar\nsi el PDF cargado cubre todos los folios del inventario.",
                 font=("Segoe UI", 10), fg=C["secondary"], bg=C["surface"], justify="center").pack()

    def _populate_coverage_view(self, parent, res):
        for w in parent.winfo_children():
            w.destroy()

        info = res.info_extra
        pdf_total = info.get("pdf_total", 0)
        max_req = info.get("max_requerido", 0)
        diff = info.get("diferencia", 0)
        estado = info.get("estado", "OK")
        ok = estado == "OK"

        # ── Card principal
        card = tk.Frame(parent, bg=C["surface"], padx=28, pady=24,
                        highlightbackground=C["outline_variant"], highlightthickness=1)
        card.pack(expand=True, padx=60, pady=40, fill="both")

        # Header
        tk.Label(card, text="📊  Cobertura del PDF",
                 font=("Segoe UI", 16, "bold"), fg=C["primary"], bg=C["surface"]).pack(anchor="w", pady=(0, 16))

        # Grid de métricas
        metrics = tk.Frame(card, bg=C["surface"])
        metrics.pack(fill="x", pady=(0, 16))

        def _metric_row(parent, label, value, value_fg):
            row = tk.Frame(parent, bg=C["surface_low"], padx=14, pady=8)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, font=("Segoe UI", 9, "bold"),
                     fg=C["secondary"], bg=C["surface_low"], width=28, anchor="w").pack(side="left")
            tk.Label(row, text=str(value), font=("Segoe UI", 11, "bold"),
                     fg=value_fg, bg=C["surface_low"]).pack(side="left")

        _metric_row(metrics, "Total páginas del PDF",     f"{pdf_total}",  C["tertiary"])
        _metric_row(metrics, "Máximo de páginas requerido", f"{max_req}",   C["tertiary"])
        diff_fg = "#1a5c2e" if ok else "#b91c1c"
        diff_sign = "+" if diff > 0 else ""
        _metric_row(metrics, "Diferencia", f"{diff_sign}{diff}", diff_fg)

        # Estado
        estado_fg = "#1a5c2e" if ok else "#b91c1c"
        estado_text = "✅  OK — El PDF cubre todas las páginas requeridas" if ok else "❌  INSUFICIENTE — Faltan páginas en el PDF"
        row = tk.Frame(metrics, bg=C["surface_low"], padx=14, pady=8)
        row.pack(fill="x", pady=3)
        tk.Label(row, text="Estado", font=("Segoe UI", 9, "bold"),
                 fg=C["secondary"], bg=C["surface_low"], width=28, anchor="w").pack(side="left")
        tk.Label(row, text=estado_text, font=("Segoe UI", 11, "bold"),
                 fg=estado_fg, bg=C["surface_low"]).pack(side="left")

        # ── Barra de cobertura
        tk.Frame(card, bg=C["outline_variant"], height=1).pack(fill="x", pady=8)
        bar_frame = tk.Frame(card, bg=C["surface"])
        bar_frame.pack(fill="x", pady=8)

        pct = int(min(max_req / max(pdf_total, 1), 1.0) * 100)
        tk.Label(bar_frame, text=f"Cobertura: {pct}%",
                 font=("Segoe UI", 9, "bold"), fg=C["primary"], bg=C["surface"]).pack(anchor="w", pady=(0, 4))

        bar_bg = tk.Frame(bar_frame, bg=C["surface_low"], height=12,
                          highlightbackground=C["outline_variant"], highlightthickness=1)
        bar_bg.pack(fill="x")
        bar_color = "#1a5c2e" if ok else "#b91c1c"
        bar_fill = tk.Frame(bar_bg, bg=bar_color, height=12)
        bar_fill.place(relwidth=pct / 100.0, relheight=1)

        # ── Mensaje detallado
        if not ok:
            err = res.errores[0] if res.errores else None
            if err:
                tk.Frame(card, bg=C["outline_variant"], height=1).pack(fill="x", pady=8)
                msg_frame = tk.Frame(card, bg="#fef2f2", padx=14, pady=10,
                                     highlightbackground="#fecaca", highlightthickness=1)
                msg_frame.pack(fill="x", pady=8)
                tk.Label(msg_frame, text="⚠️  " + err.descripcion,
                         font=("Segoe UI", 9), fg="#b91c1c", bg="#fef2f2",
                         wraplength=600, justify="left").pack(anchor="w")
        elif diff > 0:
            tk.Frame(card, bg=C["outline_variant"], height=1).pack(fill="x", pady=8)
            msg_frame = tk.Frame(card, bg="#f0fdf4", padx=14, pady=10,
                                 highlightbackground="#bbf7d0", highlightthickness=1)
            msg_frame.pack(fill="x", pady=8)
            tk.Label(msg_frame, text=f"ℹ️  El PDF tiene {diff} página(s) extra después del último folio del inventario.",
                     font=("Segoe UI", 9), fg="#166534", bg="#f0fdf4",
                     wraplength=600, justify="left").pack(anchor="w")

    def _populate_table(self):
        tab = self._active_tab.get()

        if tab == "coverage":
            if hasattr(self, "_coverage_inner") and self._coverage_inner:
                res = self._per_tab_results.get("coverage")
                if res:
                    self._populate_coverage_view(self._coverage_inner, res)
                else:
                    self._show_coverage_placeholder(self._coverage_inner)
            return

        for item in self._tree.get_children():
            self._tree.delete(item)

        error_ids = self._per_tab_error_ids.get(tab, set())
        visible_idx = 0
        for i, r in enumerate(self.app_state.records):
            # Filtrar: si se muestra solo errores, saltar registros sin error en el analizador actual
            if self._showing_errors_only and r.id not in error_ids:
                continue

            estado_icon = {
                "": "",
                "REVISAR": "⚠️",
                "FRAGMENTADO": "📎"
            }.get(r.estado, "")
            tag = r.estado.lower() if r.estado in ("revisar", "fragmentado") else ("even" if visible_idx % 2 == 0 else "odd")
            
            # Base values
            f_ini = getattr(r, "fecha_inicio", "")
            f_fin = getattr(r, "fecha_fin", "")
            vals = [r.fila, r.registro, r.escribano, r.protocolo, r.folios, r.pg_pdf, r.titulo]
            
            # Dynamic columns
            if tab == "topica":
                vals.append(r.titulo)
            elif tab == "cronica":
                cronica_str = f"{f_ini} - {f_fin}" if (f_ini or f_fin) else "S/D"
                vals.append(cronica_str)
                
            disp_estado = f"{estado_icon} {r.estado}".strip()
            vals.append(disp_estado)
            
            self._tree.insert("", "end", iid=r.id, values=tuple(vals), tags=(tag,))
            visible_idx += 1

    def _sort_treeview(self, col):
        """Sort treeview column on header click."""
        data = [(self._tree.set(child, col), child) for child in self._tree.get_children("")]
        try:
            data.sort(key=lambda t: int(t[0].replace('#', '').replace('%', '')), reverse=getattr(self, f'_sort_reverse_{col}', False))
        except (ValueError, TypeError):
            data.sort(key=lambda t: t[0], reverse=getattr(self, f'_sort_reverse_{col}', False))
        
        for index, (val, child) in enumerate(data):
            self._tree.move(child, "", index)
        
        setattr(self, f'_sort_reverse_{col}', not getattr(self, f'_sort_reverse_{col}', False))

    # ── Panel lateral de estadísticas ────────────────────────────────────────────
    def _build_stats_panel(self, parent) -> tk.Frame:
        """Construye el panel de estadísticas en un grid responsive."""
        panel = tk.Frame(
            parent,
            bg=C["surface"],
            padx=12, pady=8,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        
        # Grid layout
        panel.columnconfigure(0, weight=3) # Chips
        panel.columnconfigure(1, weight=3) # Integrity bar
        panel.columnconfigure(2, weight=2) # Buttons/Actions
        panel.rowconfigure(0, weight=1)

        # ── BLOQUE 1 (Izquierda): Chips de estadísticas ──
        left_block = tk.Frame(panel, bg=C["surface"])
        left_block.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        tk.Label(
            left_block, text="📊 Resumen de Calidad",
            font=("Segoe UI", 8, "bold"),
            fg=C["primary"], bg=C["surface"],
        ).pack(anchor="w", pady=(0, 4))

        self._chips_row = tk.Frame(left_block, bg=C["surface"])
        self._chips_row.pack(fill="x")

        # Total Label
        self._total_processed_lbl = tk.Label(
            left_block,
            text="",
            font=("Segoe UI", 7, "italic"),
            fg=C["secondary"], bg=C["surface"],
        )
        self._total_processed_lbl.pack(anchor="w", pady=(2, 0))

        # ── BLOQUE 2 (Centro): Integridad y progreso ──
        center_block = tk.Frame(panel, bg=C["surface"])
        center_block.grid(row=0, column=1, sticky="nsew", padx=10)

        self._integrity_title_lbl = tk.Label(
            center_block,
            text="",
            font=("Segoe UI", 8, "bold"),
            fg=C["primary"], bg=C["surface"],
        )
        self._integrity_title_lbl.pack(anchor="w")

        # Barra de integridad compacta
        self._bar_bg = tk.Frame(center_block, bg=C["surface_low"], height=8,
                          highlightbackground=C["outline_variant"], highlightthickness=1)
        self._bar_bg.pack(fill="x", pady=6)

        self._bar_fill = tk.Frame(self._bar_bg, bg="#1a5c2e", height=8)
        self._bar_fill.place(relwidth=0.0, relheight=1)

        # ── BLOQUE 3 (Derecha): Corrección y Acciones ──
        right_block = tk.Frame(panel, bg=C["surface"])
        right_block.grid(row=0, column=2, sticky="nsew", padx=(10, 0))

        self._correction_label = tk.Label(
            right_block,
            text="Selecciona fila\ncon alerta para corregir",
            font=("Segoe UI", 7),
            fg=C["outline"],
            bg=C["surface"],
            justify="center",
            width=22,
        )
        self._correction_label.pack(side="left", padx=8)

        self._correction_btn = tk.Button(
            right_block,
            text="🔧 Corregir",
            font=("Segoe UI", 8, "bold"),
            fg="#ffffff",
            bg=C["secondary"],
            activebackground=C["primary"],
            activeforeground="#ffffff",
            relief="flat", bd=0,
            cursor="hand2",
            padx=10, pady=4,
            state="disabled",
            command=self._open_correction_modal,
        )
        self._correction_btn.pack(side="left", padx=4)

        self._jump_btn = tk.Button(
            right_block,
            text="⬆ Registrar Salto",
            font=("Segoe UI", 8, "bold"),
            fg="#ffffff",
            bg="#b45309",
            activebackground="#92400e",
            activeforeground="#ffffff",
            relief="flat", bd=0,
            cursor="hand2",
            padx=10, pady=4,
            state="disabled",
            command=self._open_jump_modal,
        )
        self._jump_btn.pack(side="left", padx=4)

        tk.Button(
            right_block,
            text="⬇️ Exportar (.xlsx)",
            font=("Segoe UI", 8, "bold"),
            fg=C["primary"],
            bg=C["surface_low"],
            activebackground=C["secondary_container"],
            relief="flat", bd=0,
            cursor="hand2",
            padx=10, pady=4,
            command=self._export_report,
        ).pack(side="left", padx=4)

        self._update_stats_ui()

        return panel

    def _update_stats_ui(self):
        stats = self._calc_stats()
        
        # Limpiar chips viejos
        for w in self._chips_row.winfo_children():
            w.destroy()

        stat_items = [
            ("✅ Sin Alertas",  stats["validados"],   "#1a5c2e", "#d1fae5"),
            ("⚠️ Alertas",     stats["revisar"],     "#92400e", "#fef3c7"),
            ("❌ Errores",      stats["errores"],     "#7f1d1d", "#fee2e2"),
            ("📎 Fragmentados", stats["fragmentados"], "#1e3a5f", "#dbeafe"),
        ]

        for idx, (label, value, fg, bg) in enumerate(stat_items):
            chip = tk.Frame(self._chips_row, bg=C["surface"], padx=2)
            chip.grid(row=0, column=idx, sticky="ew")
            self._chips_row.columnconfigure(idx, weight=1)
            
            tk.Label(
                chip, text=f"{label}: {value}",
                font=("Segoe UI", 8, "bold"),
                fg=fg, bg=bg,
                padx=6, pady=2,
                highlightbackground=C["outline_variant"],
                highlightthickness=1,
            ).pack(fill="x")

        total = len(self.app_state.records)
        self._total_processed_lbl.configure(text=f"Total: {total} registros procesados")

        pct = int(stats["validados"] / max(total, 1) * 100)
        self._integrity_title_lbl.configure(text=f"Integridad de Foliación: {pct}%")
        self._bar_fill.place(relwidth=pct / 100.0, relheight=1)

    def _calc_stats(self) -> dict:
        records = self.app_state.records
        correctos = sum(1 for r in records if r.estado in ("", "FRAGMENTADO"))
        revisar = sum(1 for r in records if r.estado == "REVISAR")
        fragmentados = sum(1 for r in records if r.estado == "FRAGMENTADO")
        return {
            "validados":    correctos,
            "revisar":      revisar,
            "errores":      revisar,
            "fragmentados": fragmentados,
        }

    # ── Selección de fila ────────────────────────────────────────────────────────
    def _on_row_select(self, event):
        selected = self._tree.selection()
        if not selected:
            return
        record_id = selected[0]
        self._selected_record = next(
            (r for r in self.app_state.records if r.id == record_id), None
        )
        if self._selected_record:
            self.on_add_log("INFO", f"Registro seleccionado: {self._selected_record.id} — {self._selected_record.titulo[:40]}...")
            
            # Navegar PDF a la página correspondiente
            if self._selected_record.pg_pdf:
                try:
                    first_page = int(str(self._selected_record.pg_pdf).split('-')[0].strip())
                    if self.on_navigate_pdf:
                        self.on_navigate_pdf(first_page)
                except Exception:
                    pass

            suggestion = next(
                (s for s in self.app_state.suggestions if s.registro_id == record_id), None
            )
            if suggestion:
                self._correction_label.configure(
                    text=f"⚠️ Alerta ({suggestion.tipo_error})",
                    fg=C["primary"],
                )
                self._correction_btn.configure(state="normal", bg=C["primary"])
            else:
                self._correction_label.configure(
                    text=f"✅ Registro válido:\n{self._selected_record.estado}",
                    fg="#1a5c2e",
                )
                self._correction_btn.configure(state="disabled", bg=C["secondary"])

            # Mostrar botón de salto solo si hay error de tipo SALTO
            has_salto = any(
                s.registro_id == record_id
                for s in self.app_state.suggestions
                if "SALTO" in s.tipo_error.upper()
            )
            if has_salto:
                self._jump_btn.configure(state="normal", bg="#b45309")
            else:
                self._jump_btn.configure(state="disabled", bg=C["secondary"])

    # ── Modal de corrección inteligente ─────────────────────────────────────────
    def _open_correction_modal(self):
        if not self._selected_record:
            return
        suggestion = next(
            (s for s in self.app_state.suggestions
             if s.registro_id == self._selected_record.id), None
        )
        if not suggestion:
            return

        modal = tk.Toplevel(self)
        modal.title("Corrección Inteligente")
        modal.configure(bg=C["surface"])
        modal.geometry("780x520")
        modal.minsize(600, 400)
        modal.resizable(True, True)
        modal.grab_set()

        # Centrar
        modal.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 780) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 520) // 2
        modal.geometry(f"+{x}+{y}")

        self._build_modal_content(modal, suggestion)

    def _build_modal_content(self, modal, s):
        # ── Encabezado del modal ─────────────────────────────────────────────────
        header = tk.Frame(modal, bg=C["primary"], pady=12, padx=20)
        header.pack(fill="x")

        tk.Label(
            header,
            text=f"⚠️  Corrección Inteligente  —  Registro {s.registro_id}",
            font=("Segoe UI", 11, "bold"),
            fg="#ffffff",
            bg=C["primary"],
        ).pack(side="left")

        tk.Label(
            header,
            text=s.tipo_error,
            font=("Courier New", 8, "bold"),
            fg=C["on_primary"],
            bg=C["primary"],
        ).pack(side="right")

        # ── Cuerpo: dos columnas ─────────────────────────────────────────────────
        body = tk.Frame(modal, bg=C["surface"], padx=20, pady=16)
        body.pack(fill="both", expand=True)

        # Columna izquierda (5/12)
        left_col = tk.Frame(body, bg=C["surface"])
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 16))

        tk.Label(
            left_col,
            text="Contexto del Error",
            font=("Segoe UI", 9, "bold"),
            fg=C["primary"],
            bg=C["surface"],
        ).pack(anchor="w", pady=(0, 6))

        # Caja de descripción
        desc_frame = tk.Frame(
            left_col, bg=C["surface_low"],
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
            padx=10, pady=10,
        )
        desc_frame.pack(fill="x", pady=(0, 12))

        tk.Label(
            desc_frame,
            text=s.descripcion,
            font=("Segoe UI", 8),
            fg=C["tertiary"],
            bg=C["surface_low"],
            wraplength=280,
            justify="left",
        ).pack(anchor="w")

        # Metadatos
        tk.Label(
            left_col,
            text="Metadatos del Registro",
            font=("Segoe UI", 9, "bold"),
            fg=C["primary"],
            bg=C["surface"],
        ).pack(anchor="w", pady=(0, 6))

        meta_rows = [
            ("ID Registro:", s.registro_id),
            ("Escribano:", s.escribano),
            ("Folio Original:", s.folios_original),
            ("Páginas PDF:", s.paginas_pdf),
        ]
        for lbl, val in meta_rows:
            r = tk.Frame(left_col, bg=C["surface"])
            r.pack(fill="x", pady=2)
            tk.Label(r, text=lbl, font=("Segoe UI", 8),
                     fg=C["secondary"], bg=C["surface"], width=16, anchor="w").pack(side="left")
            tk.Label(r, text=val, font=("Courier New", 8, "bold"),
                     fg=C["tertiary"], bg=C["surface"]).pack(side="left")

        # Columna derecha (7/12)
        right_col = tk.Frame(body, bg=C["surface"])
        right_col.pack(side="right", fill="both", expand=True)

        tk.Label(
            right_col,
            text="Comparación Detallada",
            font=("Segoe UI", 9, "bold"),
            fg=C["primary"],
            bg=C["surface"],
        ).pack(anchor="w", pady=(0, 8))

        # Grid 2x2 de comparación
        grid = tk.Frame(right_col, bg=C["surface"])
        grid.pack(fill="x", pady=(0, 12))

        self._make_compare_box(grid, "Valor Actual (Error)",
                               s.valor_actual, "#fee2e2", "#7f1d1d", row=0, col=0)
        self._make_compare_box(grid, "Valor Sugerido ✎",
                               s.valor_sugerido, "#d1fae5", "#064e3b", row=0, col=1, editable=True)
        self._make_compare_box(grid, "Rango Original",
                               s.folios_original, "#fef3c7", "#713f12", row=1, col=0)
        self._make_compare_box(grid, "Rango Sugerido",
                               s.rango_sugerido, "#dbeafe", "#1e3a5f", row=1, col=1)

        # Botones de acción
        btn_frame = tk.Frame(right_col, bg=C["surface"])
        btn_frame.pack(fill="x", pady=(8, 0))

        tk.Button(
            btn_frame,
            text="Cancelar",
            font=("Segoe UI", 9),
            fg=C["secondary"],
            bg=C["surface_low"],
            relief="flat", bd=0,
            cursor="hand2",
            padx=16, pady=8,
            command=lambda: modal.destroy(),
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_frame,
            text="✅  Aplicar Correcciones",
            font=("Segoe UI", 9, "bold"),
            fg="#ffffff",
            bg="#1a5c2e",
            activebackground="#14532d",
            relief="flat", bd=0,
            cursor="hand2",
            padx=16, pady=8,
            command=lambda: self._apply_correction(s, modal),
        ).pack(side="left")

    def _make_compare_box(self, parent, title, value, bg, fg, row, col, editable=False):
        box = tk.Frame(
            parent, bg=bg,
            padx=10, pady=8,
            highlightbackground=fg,
            highlightthickness=1,
        )
        box.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)

        tk.Label(
            box, text=title,
            font=("Segoe UI", 7, "bold"),
            fg=fg, bg=bg,
        ).pack(anchor="w")

        if editable:
            self._editable_var = tk.StringVar(value=value)
            entry = tk.Entry(
                box, textvariable=self._editable_var,
                font=("Courier New", 14, "bold"),
                fg=fg, bg=bg,
                relief="flat", bd=0,
                justify="center",
            )
            entry.pack(fill="x", pady=(4, 0))
        else:
            tk.Label(
                box, text=value,
                font=("Courier New", 14, "bold"),
                fg=fg, bg=bg,
            ).pack(anchor="w", pady=(4, 0))

    def _apply_correction(self, suggestion, modal):
        corrected_val = self._editable_var.get().strip() if hasattr(self, "_editable_var") else suggestion.valor_sugerido
        
        # Actualizar el estado del registro a vacío (sin error)
        for record in self.app_state.records:
            if record.id == suggestion.registro_id:
                record.estado = ""
                if suggestion.tipo_error == "folios" or "FOLIO" in suggestion.tipo_error:
                    record.folios = corrected_val
                elif suggestion.tipo_error == "TÓPICA":
                    record.titulo = corrected_val
                elif suggestion.tipo_error == "CRÓNICA":
                    record.fecha_inicio = corrected_val
                break

        # Eliminar la sugerencia
        self.app_state.suggestions = [
            s for s in self.app_state.suggestions if s.id != suggestion.id
        ]

        # Limpiar error del per-tab correspondiente
        tipo = suggestion.tipo_error.upper()
        tab_key = "folios" if "FOLIO" in tipo else "topica" if tipo == "TÓPICA" else "cronica" if tipo == "CRÓNICA" else None
        if tab_key and tab_key in self._per_tab_error_ids:
            self._per_tab_error_ids[tab_key].discard(suggestion.registro_id)

        self.on_add_log("SUCCESS", f"Corrección aplicada: {suggestion.registro_id} → {corrected_val}")
        self._update_stats_ui()
        self._update_toggle_button_state()
        self._build_table()
        modal.destroy()
        messagebox.showinfo(
            "Corrección Aplicada",
            f"El registro {suggestion.registro_id} ha sido actualizado a VALIDADO.\n"
            f"Valor corregido: {corrected_val}"
        )

    # ── Modal de salto con vista previa PDF ──────────────────────────────────────
    def _open_jump_modal(self):
        if not self._selected_record:
            return

        rec = self._selected_record
        records = self.app_state.records
        idx = next((i for i, r in enumerate(records) if r.id == rec.id), None)
        if idx is None:
            return

        # Calcular contexto: 2 registros arriba y 2 abajo
        ctx_start = max(0, idx - 2)
        ctx_end = min(len(records) - 1, idx + 2)
        context_records = records[ctx_start:ctx_end + 1]

        # Rango de folios del contexto completo
        mapper = mapper_from_state(self.app_state)
        all_pages = []
        for cr in context_records:
            pages = mapper.folio_str_to_pdf_pages(cr.folios)
            if pages:
                all_pages.extend(pages)

        if not all_pages:
            messagebox.showinfo(
                "Vista Previa",
                "No se pudieron mapear las páginas PDF para los folios de este registro."
            )
            return

        pdf_min_page = min(all_pages)
        pdf_max_page = max(all_pages)

        # Detectar salto: buscar el error SALTO asociado a este registro
        salto_suggestion = next(
            (s for s in self.app_state.suggestions
             if s.registro_id == rec.id and "SALTO" in s.tipo_error.upper()),
            None,
        )

        # Valores auto-calculados para el salto
        # El salto cubre desde el folio esperado (valor_esperado) hasta el inicio del registro actual
        desde_folio = salto_suggestion.valor_esperado if salto_suggestion else ""
        hasta_folio = ""
        parsed = parse_folios(rec.folios)
        if parsed:
            hasta_num, hasta_cara = parsed[0], parsed[1]
            hasta_folio = f"{hasta_num:03d}{hasta_cara}"

        # ── Crear modal ──────────────────────────────────────────────────────────
        modal = tk.Toplevel(self)
        modal.title("Registrar Salto — Vista Previa")
        modal.configure(bg=C["surface"])
        modal.geometry("960x620")
        modal.resizable(True, True)
        modal.minsize(760, 480)
        modal.grab_set()

        modal.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 960) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 620) // 2
        modal.geometry(f"+{max(0,x)}+{max(0,y)}")

        # ── Header ───────────────────────────────────────────────────────────────
        header = tk.Frame(modal, bg="#92400e", pady=10, padx=16)
        header.pack(fill="x")

        tk.Label(
            header,
            text=f"⬆  Registrar Salto  —  Registro {rec.id}",
            font=("Segoe UI", 11, "bold"),
            fg="#ffffff", bg="#92400e",
        ).pack(side="left")

        tk.Label(
            header,
            text=f"Folios: {rec.folios}  |  Pág PDF: {pdf_min_page}–{pdf_max_page}",
            font=("Courier New", 9),
            fg="#fef3c7", bg="#92400e",
        ).pack(side="right")

        # ── Cuerpo: PanedWindow horizontal (PDF preview | formulario) ────────────
        body = tk.PanedWindow(
            modal, orient="horizontal",
            sashwidth=4, sashrelief="flat",
            bg=C["outline_variant"], opaqueresize=True,
        )
        body.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Panel izquierdo: mini vista previa PDF ────────────────────────────────
        pdf_frame = tk.Frame(body, bg=C["surface_low"])
        body.add(pdf_frame, minsize=280, stretch="always")

        pdf_header = tk.Frame(pdf_frame, bg=C["surface_container"], pady=4, padx=8)
        pdf_header.pack(fill="x")
        tk.Label(
            pdf_header,
            text=f"Vista Previa PDF  (pág. {pdf_min_page}–{pdf_max_page})",
            font=("Segoe UI", 9, "bold"),
            fg=C["primary"], bg=C["surface_container"],
        ).pack(side="left")
        tk.Label(
            pdf_header,
            text=f"{len(context_records)} registros de contexto",
            font=("Segoe UI", 8),
            fg=C["secondary"], bg=C["surface_container"],
        ).pack(side="right")

        pdf_canvas = tk.Canvas(
            pdf_frame, bg=C["surface_low"],
            highlightthickness=0,
        )
        pdf_vsb = tk.Scrollbar(pdf_frame, orient="vertical", command=pdf_canvas.yview)
        pdf_canvas.configure(yscrollcommand=pdf_vsb.set)
        pdf_vsb.pack(side="right", fill="y")
        pdf_canvas.pack(fill="both", expand=True)

        pdf_inner = tk.Frame(pdf_canvas, bg=C["surface_low"])
        pdf_canvas_window = pdf_canvas.create_window((0, 0), window=pdf_inner, anchor="nw")

        def _on_pdf_inner_configure(e):
            pdf_canvas.configure(scrollregion=bbox)
        pdf_inner.bind("<Configure>", lambda e: pdf_canvas.configure(
            scrollregion=pdf_canvas.bbox("all")))

        def _on_pdf_canvas_configure(e):
            pdf_canvas.itemconfig(pdf_canvas_window, width=e.width)
        pdf_canvas.bind("<Configure>", _on_pdf_canvas_configure)

        # Renderizar páginas del contexto
        self._render_modal_pdf_pages(pdf_inner, pdf_canvas, all_pages, context_records, idx - ctx_start)

        # Mousewheel para el canvas del PDF
        def _on_pdf_mousewheel(event):
            pdf_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        pdf_canvas.bind("<MouseWheel>", _on_pdf_mousewheel)
        pdf_inner.bind("<MouseWheel>", _on_pdf_mousewheel)

        # ── Panel derecho: formulario de salto ────────────────────────────────────
        form_frame = tk.Frame(body, bg=C["surface"], padx=16, pady=12)
        body.add(form_frame, minsize=260, stretch="never")

        tk.Label(
            form_frame,
            text="Datos del Salto",
            font=("Segoe UI", 10, "bold"),
            fg=C["primary"], bg=C["surface"],
        ).pack(anchor="w", pady=(0, 10))

        # Info del registro seleccionado
        info_card = tk.Frame(
            form_frame, bg=C["surface_low"],
            highlightbackground=C["outline_variant"], highlightthickness=1,
            padx=10, pady=8,
        )
        info_card.pack(fill="x", pady=(0, 12))

        for lbl, val in [
            ("Registro:", rec.id),
            ("Escribano:", rec.escribano),
            ("Folios:", rec.folios),
            ("Pág PDF:", rec.pg_pdf),
        ]:
            row = tk.Frame(info_card, bg=C["surface_low"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=lbl, font=("Segoe UI", 8),
                     fg=C["secondary"], bg=C["surface_low"], width=12, anchor="w").pack(side="left")
            tk.Label(row, text=val, font=("Courier New", 8, "bold"),
                     fg=C["tertiary"], bg=C["surface_low"]).pack(side="left")

        tk.Frame(form_frame, bg=C["outline_variant"], height=1).pack(fill="x", pady=8)

        # Campos del salto
        tk.Label(
            form_frame,
            text="Rango de folios a excluir del salto:",
            font=("Segoe UI", 8, "bold"),
            fg=C["primary"], bg=C["surface"],
        ).pack(anchor="w", pady=(0, 6))

        desde_frame = tk.Frame(form_frame, bg=C["surface"])
        desde_frame.pack(fill="x", pady=3)
        tk.Label(desde_frame, text="Desde Folio:", font=("Segoe UI", 8),
                 fg=C["secondary"], bg=C["surface"], width=14, anchor="w").pack(side="left")
        jump_desde_var = tk.StringVar(value=str(desde_folio))
        tk.Entry(desde_frame, textvariable=jump_desde_var,
                 font=("Courier New", 10, "bold"), width=12,
                 fg=C["tertiary"], bg="#fef3c7",
                 relief="solid", bd=1,
                 highlightbackground=C["outline_variant"], highlightthickness=1,
                 justify="center").pack(side="left", padx=4)

        hasta_frame = tk.Frame(form_frame, bg=C["surface"])
        hasta_frame.pack(fill="x", pady=3)
        tk.Label(hasta_frame, text="Hasta Folio:", font=("Segoe UI", 8),
                 fg=C["secondary"], bg=C["surface"], width=14, anchor="w").pack(side="left")
        jump_hasta_var = tk.StringVar(value=str(hasta_folio))
        tk.Entry(hasta_frame, textvariable=jump_hasta_var,
                 font=("Courier New", 10, "bold"), width=12,
                 fg=C["tertiary"], bg="#fef3c7",
                 relief="solid", bd=1,
                 highlightbackground=C["outline_variant"], highlightthickness=1,
                 justify="center").pack(side="left", padx=4)

        tk.Label(form_frame, text="Motivo (opcional):", font=("Segoe UI", 8),
                 fg=C["secondary"], bg=C["surface"]).pack(anchor="w", pady=(8, 3))
        jump_motivo_var = tk.StringVar(
            value=f"Salto aprobado: folios {desde_folio}–{hasta_folio}"
        )
        tk.Entry(form_frame, textvariable=jump_motivo_var,
                 font=("Segoe UI", 9), width=30,
                 fg=C["tertiary"], bg=C["surface_low"],
                 relief="solid", bd=1,
                 highlightbackground=C["outline_variant"], highlightthickness=1,
                 ).pack(fill="x", pady=3)

        # Descripción del error
        if salto_suggestion:
            tk.Frame(form_frame, bg=C["outline_variant"], height=1).pack(fill="x", pady=8)
            tk.Label(
                form_frame,
                text="Error detectado:",
                font=("Segoe UI", 8, "bold"),
                fg="#92400e", bg=C["surface"],
            ).pack(anchor="w", pady=(0, 4))
            tk.Label(
                form_frame,
                text=salto_suggestion.descripcion,
                font=("Segoe UI", 8),
                fg=C["tertiary"], bg=C["surface"],
                wraplength=220, justify="left",
            ).pack(anchor="w")

        # ── Botones de acción ─────────────────────────────────────────────────────
        tk.Frame(form_frame, bg=C["outline_variant"], height=1).pack(fill="x", pady=8)

        btn_frame = tk.Frame(form_frame, bg=C["surface"])
        btn_frame.pack(fill="x", pady=(4, 0))

        def _on_cancel():
            modal.destroy()

        def _on_apply():
            self._apply_jump(
                desde_var=jump_desde_var,
                hasta_var=jump_hasta_var,
                motivo_var=jump_motivo_var,
                modal=modal,
            )

        tk.Button(
            btn_frame,
            text="Cancelar",
            font=("Segoe UI", 9),
            fg=C["secondary"], bg=C["surface_low"],
            activebackground=C["secondary_container"],
            relief="flat", bd=0, cursor="hand2",
            padx=14, pady=8,
            command=_on_cancel,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_frame,
            text="✅  Agregar Cambios",
            font=("Segoe UI", 9, "bold"),
            fg="#ffffff", bg="#1a5c2e",
            activebackground="#14532d",
            relief="flat", bd=0, cursor="hand2",
            padx=14, pady=8,
            command=_on_apply,
        ).pack(side="left")

    def _render_modal_pdf_pages(self, parent, canvas, pages, context_records, highlight_idx):
        """Renderiza páginas PDF en el canvas del modal con indicadores de contexto."""
        try:
            import fitz
            from PIL import Image, ImageTk
        except ImportError:
            tk.Label(
                parent,
                text="PyMuPDF no disponible.\nNo se puede renderizar la vista previa.",
                font=("Segoe UI", 9), fg=C["secondary"], bg=C["surface_low"],
            ).pack(pady=40)
            return

        pdf_path = self.app_state.pdf_path
        if not pdf_path or not os.path.exists(pdf_path):
            tk.Label(
                parent,
                text="No hay PDF cargado.\nCargue un PDF para ver la vista previa.",
                font=("Segoe UI", 9), fg=C["secondary"], bg=C["surface_low"],
            ).pack(pady=40)
            return

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            tk.Label(
                parent,
                text=f"Error al abrir PDF:\n{e}",
                font=("Segoe UI", 9), fg="#7f1d1d", bg=C["surface_low"],
            ).pack(pady=40)
            return

        render_width = 380
        img_refs = []

        for i, page_num in enumerate(pages):
            if page_num < 1 or page_num > len(doc):
                continue

            is_highlight = (i == highlight_idx)

            # Etiqueta de separación entre registros de contexto
            if i > 0 and context_records and (i < len(context_records)):
                sep = tk.Frame(parent, bg=C["outline_variant"], height=1)
                sep.pack(fill="x", padx=8, pady=4)

            # Label de registro
            if i < len(context_records):
                cr = context_records[i]
                lbl_bg = "#fef3c7" if is_highlight else C["surface_container"]
                lbl_fg = "#92400e" if is_highlight else C["secondary"]
                tag_text = " << SELECCIONADO >>" if is_highlight else ""
                rec_label = tk.Label(
                    parent,
                    text=f"  {cr.id} — {cr.folios}  (pág. {page_num}){tag_text}",
                    font=("Segoe UI", 8, "bold") if is_highlight else ("Segoe UI", 8),
                    fg=lbl_fg, bg=lbl_bg,
                    anchor="w", padx=6, pady=3,
                )
                rec_label.pack(fill="x", padx=4)

            # Renderizar página
            try:
                page = doc[page_num - 1]
                rect = page.rect
                zoom = render_width / rect.width
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                photo = ImageTk.PhotoImage(img)
                img_refs.append(photo)

                border_color = "#b45309" if is_highlight else C["outline_variant"]
                border_width = 2 if is_highlight else 1

                page_frame = tk.Frame(
                    parent, bg=border_color,
                    padx=border_width, pady=border_width,
                )
                page_frame.pack(padx=8, pady=4, fill="x")

                lbl = tk.Label(page_frame, image=photo, bg=C["surface_low"])
                lbl.pack()
            except Exception:
                tk.Label(
                    parent,
                    text=f"Error renderizando pág. {page_num}",
                    font=("Segoe UI", 8), fg="#7f1d1d", bg=C["surface_low"],
                ).pack(pady=4)

        doc.close()

        # Guardar referencias para evitar garbage collection
        parent._img_refs = img_refs

    def _apply_jump(self, desde_var, hasta_var, motivo_var, modal):
        """Aplica el salto: crea la exclusión, re-analiza y refresca."""
        desde_str = desde_var.get().strip()
        hasta_str = hasta_var.get().strip()
        motivo = motivo_var.get().strip()

        if not desde_str or not hasta_str:
            messagebox.showerror("Error", "Debe indicar ambos folios (Desde y Hasta).")
            return

        try:
            desde = int(desde_str)
            hasta = int(hasta_str)
        except ValueError:
            messagebox.showerror("Error", "Los folios deben ser números enteros.")
            return

        if desde > hasta:
            messagebox.showerror("Error", "El folio 'Desde' debe ser menor o igual al folio 'Hasta'.")
            return

        if not motivo:
            motivo = f"Salto aprobado: folios {desde}–{hasta}"

        from project_types import ExclusionRule

        new_rule = ExclusionRule(
            id=f"EX-{len(self.app_state.exclusions)+1:03d}",
            tipo="SALTO",
            desde=desde,
            hasta=hasta,
            motivo=motivo,
        )
        self.app_state.exclusions.append(new_rule)
        self.on_add_log("INFO", f"Salto registrado desde Analizador: folios {desde}–{hasta}. {motivo}")

        # Re-ejecutar análisis de folios
        from utils.analyzers import analizar_folios
        res = analizar_folios(self.app_state.records, self.app_state.exclusions)
        self._per_tab_analysis_done["folios"] = True

        # Limpiar sugerencias de tipo SALTO y re-resetar estados REVISAR
        self.app_state.suggestions = [
            s for s in self.app_state.suggestions if "SALTO" not in s.tipo_error.upper()
        ]
        for rec in self.app_state.records:
            if rec.estado == "REVISAR":
                rec.estado = ""

        # Marcar registros con errores
        self._per_tab_error_ids["folios"] = set()
        for err in res.errores:
            self._per_tab_error_ids["folios"].add(err.record_id)
            for rec in self.app_state.records:
                if rec.id == err.record_id:
                    rec.estado = "REVISAR"
                    break

        # Regenerar sugerencias de salto si aún hay errores
        if not res.ok:
            from utils.folio_parser import folio_to_int, int_to_folio
            from project_types import SugerenciaCorreccion
            expected = None
            prev_hasta = None
            for r in self.app_state.records:
                parsed = parse_folios(r.folios)
                if parsed is None:
                    expected = None
                    prev_hasta = None
                    continue
                d_num, d_cara, h_num, h_cara = parsed
                d_int = folio_to_int(d_num, d_cara)
                h_int = folio_to_int(h_num, h_cara)
                if expected is not None and d_int != expected:
                    num_e, cara_e = int_to_folio(expected)
                    sug = SugerenciaCorreccion(
                        id=f"SUG-{len(self.app_state.suggestions)+1:03d}",
                        registro_id=r.id,
                        tipo_error="SALTO DE FOLIO",
                        descripcion=f"Salto detectado. Se esperaba '{num_e:03d}{cara_e}', se encontró '{r.folios[:6]}'.",
                        valor_actual=r.folios,
                        valor_sugerido=f"{num_e:03d}{cara_e}-{h_num:03d}{h_cara}",
                        escribano=r.escribano,
                        folios_original=r.folios,
                        rango_sugerido=f"{num_e:03d}{cara_e}-{h_num:03d}{h_cara}",
                        paginas_pdf=r.pg_pdf,
                        paginas_sugeridas=r.pg_pdf,
                        fecha_original=getattr(r, "fecha_inicio", ""),
                        fecha_validada=getattr(r, "fecha_inicio", ""),
                    )
                    self.app_state.suggestions.append(sug)
                expected = h_int + 1
                prev_hasta = h_int

        # Actualizar UI
        self.on_add_log("SUCCESS", f"Salto {desde}–{hasta} registrado. Análisis re-ejecutado.")
        self._update_stats_ui()
        self._build_table()
        modal.destroy()

        # Desactivar botón de salto si ya no hay errores de tipo SALTO
        has_salto_remaining = any(
            "SALTO" in s.tipo_error.upper() for s in self.app_state.suggestions
        )
        if not has_salto_remaining:
            self._jump_btn.configure(state="disabled", bg=C["secondary"])
        self._per_tab_showing_errors["folios"] = False
        self._showing_errors_only = False
        self._update_toggle_button_state("folios")

        self.on_add_log("SUCCESS", f"Análisis re-ejecutado tras registrar salto.")


    # ── Exportar ─────────────────────────────────────────────────────────────────
    def _export_report(self):
        from tkinter import filedialog
        from utils.theme import C as _C
        path = filedialog.asksaveasfilename(
            title="Exportar Reporte",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile="reporte_inventario_validado.xlsx",
        )
        if not path:
            return
        self.on_add_log("INFO", "Generando reporte de exportación (.xlsx)...")
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Inventario"
            headers = ["ID", "Registro", "Escribano", "Protocolo", "Folios", "Pág.PDF", "Título", "Estado"]
            ws.append(headers)
            for r in self.app_state.records:
                ws.append([r.id, r.registro, r.escribano, r.protocolo, r.folios, r.pg_pdf, r.titulo, r.estado])
            
            if self.app_state.suggestions:
                ws2 = wb.create_sheet("Sugerencias")
                ws2.append(["ID", "Registro", "Tipo Error", "Valor Actual", "Valor Sugerido", "Descripción"])
                for s in self.app_state.suggestions:
                    ws2.append([s.id, s.registro_id, s.tipo_error, s.valor_actual, s.valor_sugerido, s.descripcion])
            
            wb.save(path)
            self.on_add_log("SUCCESS", f"Reporte exportado: {os.path.basename(path)}")
            from tkinter import messagebox
            messagebox.showinfo("Exportar Reporte", f"Reporte generado exitosamente:\n{path}")
        except ImportError:
            self.on_add_log("WARN", "Librería openpyxl no instalada. Instale con: pip install openpyxl")
            from tkinter import messagebox
            messagebox.showerror("Error", "Se requiere openpyxl para exportar.\nInstale con: pip install openpyxl")
        except Exception as e:
            self.on_add_log("ERR", f"Error al exportar: {e}")
            from tkinter import messagebox
            messagebox.showerror("Error", f"Error al generar reporte:\n{e}")
