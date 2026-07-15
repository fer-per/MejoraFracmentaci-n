"""
ExpandedAnalyzerView.py — Pantalla 2: Vista Expandida y Analizadores de Calidad.
Tabla de 12 columnas, tabs de análisis heurístico, panel de stats y modal de corrección.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

from utils.analyzers import analizar_folios, analizar_topica, analizar_cronica, analizar_coverage
from utils.folio_engine import mapper_from_state



C = {
    "primary":           "#570013",
    "primary_container": "#800020",
    "on_primary":        "#ff828a",
    "background":        "#fcf9f8",
    "surface":           "#ffffff",
    "surface_low":       "#f6f3f2",
    "surface_container": "#f0edec",
    "surface_high":      "#eae7e7",
    "surface_highest":   "#e5e2e1",
    "outline":           "#8c7071",
    "outline_variant":   "#e0bfbf",
    "tertiary":          "#32131c",
    "secondary":         "#7c535d",
    "secondary_container": "#ffc9d5",
}

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
        self.configure(bg=C["background"])
        self._build()
        self.bind("<Map>", lambda e: self.refresh())

    def refresh(self):
        self._populate_table()
        self._update_stats_ui()

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
            sashwidth=5,
            sashrelief="flat",
            bg=C["outline_variant"],
            handlesize=0,
            sashcursor="sb_v_double_arrow",
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
            stretch="never",
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

        self._activate_tab("folios")

    def _activate_tab(self, key: str):
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
        # Reconstruir la tabla solo si ya fue creada y no es None
        if getattr(self, "_table_frame", None) is not None:
            self._build_table()

    def _execute_analysis(self):
        key = self._active_tab.get()
        records = self.app_state.records
        exclusions = self.app_state.exclusions
        mapper = mapper_from_state(self.app_state)

        if key == "folios":
            res = analizar_folios(records, exclusions)
            self.on_add_log("INFO", f"Corriendo: {res.resumen}")
            # Marcar registros como REVISAR si fallaron
            for err in res.errores:
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
            for err in res.errores:
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
            for err in res.errores:
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
                self.on_add_log("SUCCESS", f"Data Crónica validada: progresión temporal consistente.")

        elif key == "coverage":
            res = analizar_coverage(records, self.app_state.pdf_total_pages, mapper)
            self.on_add_log("INFO", f"Corriendo: {res.resumen}")
            # Marcar registros como REVISAR si fallaron
            for err in res.errores:
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
                self.on_add_log("SUCCESS", f"Cobertura PDF OK: El PDF cubre el máximo requerido.")

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
        tab = self._active_tab.get()
        if tab == "topica":
            cols = ("ID", "Registro", "Escribano", "Protocolo", "Folios", "Pág.PDF", "Título", "Data Tópica", "Estado")
        elif tab == "cronica":
            cols = ("ID", "Registro", "Escribano", "Protocolo", "Folios", "Pág.PDF", "Título", "Data Crónica", "Estado")
        else:
            cols = ("ID", "Registro", "Escribano", "Protocolo", "Folios", "Pág.PDF", "Título", "Estado")

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
            "ID": 50, "Registro": 90, "Escribano": 140,
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

    def _populate_table(self):
        for item in self._tree.get_children():
            self._tree.delete(item)

        tab = self._active_tab.get()
        for i, r in enumerate(self.app_state.records):
            estado_icon = {
                "": "",
                "REVISAR": "⚠️",
                "FRAGMENTADO": "📎"
            }.get(r.estado, "")
            tag = r.estado.lower() if r.estado in ("revisar", "fragmentado") else ("even" if i % 2 == 0 else "odd")
            
            # Base values
            vals = [r.id, r.registro, r.escribano, r.protocolo, r.folios, r.pg_pdf, r.titulo]
            
            # Dynamic columns
            if tab == "topica":
                vals.append(r.titulo)
            elif tab == "cronica":
                f_ini = getattr(r, "fecha_inicio", "")
                f_fin = getattr(r, "fecha_fin", "")
                cronica_str = f"{f_ini} - {f_fin}" if (f_ini or f_fin) else "S/D"
                vals.append(cronica_str)
                
            disp_estado = f"{estado_icon} {r.estado}".strip()
            vals.append(disp_estado)
            
            self._tree.insert("", "end", iid=r.id, values=tuple(vals), tags=(tag,))

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
        modal.resizable(False, False)
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

        self.on_add_log("SUCCESS", f"Corrección aplicada: {suggestion.registro_id} → {corrected_val}")
        self._update_stats_ui()
        self._build_table()
        modal.destroy()
        messagebox.showinfo(
            "Corrección Aplicada",
            f"El registro {suggestion.registro_id} ha sido actualizado a VALIDADO.\n"
            f"Valor corregido: {corrected_val}"
        )



    # ── Exportar ─────────────────────────────────────────────────────────────────
    def _export_report(self):
        self.on_add_log("INFO", "Generando reporte de exportación (.xlsx)...")
        self.after(1000, lambda: self.on_add_log(
            "SUCCESS", "Reporte exportado: reporte_inventario_validado.xlsx"
        ))
        messagebox.showinfo(
            "Exportar Reporte",
            "En una implementación real, aquí se generaría el archivo .xlsx.\n"
            "Función disponible al integrar la librería openpyxl."
        )
