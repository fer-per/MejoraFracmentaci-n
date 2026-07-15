"""
ExclusionsView.py — Pantalla 3: Configuración de Exclusiones.
Formularios para saltos de folio y páginas a ignorar. Tabla de reglas activas.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import uuid


C = {
    "primary":           "#570013",
    "primary_container": "#800020",
    "on_primary":        "#ff828a",
    "background":        "#fcf9f8",
    "surface":           "#ffffff",
    "surface_low":       "#f6f3f2",
    "surface_container": "#f0edec",
    "surface_high":      "#eae7e7",
    "outline":           "#8c7071",
    "outline_variant":   "#e0bfbf",
    "tertiary":          "#32131c",
    "secondary":         "#7c535d",
    "secondary_container": "#ffc9d5",
}

CONTENIDO_OPTIONS = [
    "Hoja en Blanco",
    "Portada",
    "Separador",
    "Dañada",
]


class ExclusionsView(tk.Frame):
    """Vista de gestión de reglas de exclusión."""

    def __init__(self, parent, app_state, on_add_log, **kwargs):
        self.on_navigate_pdf = kwargs.pop("on_navigate_pdf", None)
        kwargs.pop("on_load_pdf", None)
        super().__init__(parent, **kwargs)
        self.app_state = app_state
        self.on_add_log = on_add_log
        self.configure(bg=C["background"])
        self._build()
        self.bind("<Map>", lambda e: self.refresh())

    def refresh(self):
        self._populate_excel_table()
        self._render_exclusions()
        self._render_segments()

    # ── Construcción ────────────────────────────────────────────────────────────
    def _build(self):
        # PanedWindow vertical: tabla excel arriba | formularios abajo
        self._excl_paned = tk.PanedWindow(
            self,
            orient="vertical",
            sashwidth=5,
            sashrelief="flat",
            bg=C["outline_variant"],
            handlesize=0,
            sashcursor="sb_v_double_arrow",
            opaqueresize=True,
        )
        self._excl_paned.pack(fill="both", expand=True)

        # Pane superior: Tabla Excel (tamaño inicial ~200px)
        self._table_host = tk.Frame(self._excl_paned, bg=C["background"])
        self._excl_paned.add(self._table_host, minsize=140, height=200, stretch="always")
        self._build_excel_table()

        # Pane inferior: Canvas scroll para formularios
        self._bottom_host = tk.Frame(self._excl_paned, bg=C["background"])
        self._excl_paned.add(self._bottom_host, minsize=200, stretch="never")

        canvas = tk.Canvas(self._bottom_host, bg=C["background"], bd=0, highlightthickness=0)
        scrollbar = tk.Scrollbar(self._bottom_host, orient="vertical", command=canvas.yview)
        self._sf = tk.Frame(canvas, bg=C["background"])
        self._sf.bind("<Configure>",
                      lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._sf, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_content()

    def _build_excel_table(self):
        container = tk.Frame(self._table_host, bg=C["background"])
        container.pack(fill="both", expand=True, padx=24, pady=(16, 4))

        vsb = tk.Scrollbar(container, orient="vertical")
        vsb.pack(side="right", fill="y")
        hsb = tk.Scrollbar(container, orient="horizontal")
        hsb.pack(side="bottom", fill="x")

        style = ttk.Style()
        style.configure(
            "ExclTable.Treeview",
            background=C["surface"],
            foreground=C["tertiary"],
            fieldbackground=C["surface"],
            rowheight=28,
            font=("Segoe UI", 8),
        )
        style.configure(
            "ExclTable.Treeview.Heading",
            background=C["surface_high"],
            foreground=C["primary"],
            font=("Segoe UI", 8, "bold"),
            relief="flat",
        )

        cols = ("ID", "Registro", "Escribano", "Protocolo", "Folios", "Pág.PDF", "Título", "Estado")

        self._tree = ttk.Treeview(
            container,
            columns=cols,
            show="headings",
            style="ExclTable.Treeview",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            selectmode="browse",
        )
        vsb.configure(command=self._tree.yview)
        hsb.configure(command=self._tree.xview)

        col_widths = {
            "ID": 50, "Registro": 90, "Escribano": 140,
            "Protocolo": 70, "Folios": 90, "Pág.PDF": 70,
            "Título": 200, "Estado": 100,
        }
        for col in cols:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=col_widths.get(col, 100), anchor="w", minwidth=50)

        self._tree.tag_configure("even", background=C["surface_low"])
        self._tree.tag_configure("odd", background=C["surface"])
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)

    def _populate_excel_table(self):
        if not hasattr(self, "_tree"):
            return
        for item in self._tree.get_children():
            self._tree.delete(item)

        for i, r in enumerate(self.app_state.records):
            estado_icon = {
                "": "",
                "REVISAR": "⚠️",
                "FRAGMENTADO": "📎"
            }.get(r.estado, "")
            disp_estado = f"{estado_icon} {r.estado}".strip()
            tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert(
                "", "end", iid=r.id,
                values=(r.id, r.registro, r.escribano, r.protocolo, r.folios, r.pg_pdf, r.titulo, disp_estado),
                tags=(tag,)
            )

    def _on_row_select(self, event):
        selected = self._tree.selection()
        if not selected:
            return
        r_id = selected[0]
        r = next((rec for rec in self.app_state.records if rec.id == r_id), None)
        if r and r.pg_pdf:
            try:
                first_page = int(str(r.pg_pdf).split('-')[0].strip())
                if self.on_navigate_pdf:
                    self.on_navigate_pdf(first_page)
            except Exception:
                pass

    def _build_content(self):
        # Encabezado
        h = tk.Frame(self._sf, bg=C["background"])
        h.pack(fill="x", padx=24, pady=(16, 8))

        tk.Label(
            h, text="Saltos y Exclusiones",
            font=("Segoe UI", 18, "bold"),
            fg=C["primary"], bg=C["background"],
        ).pack(anchor="w")
        tk.Label(
            h, text="Registre saltos de foliación aprobados y páginas físicas a omitir durante el procesamiento.",
            font=("Segoe UI", 9),
            fg=C["secondary"], bg=C["background"],
        ).pack(anchor="w")

        # Formularios lado a lado en PanedWindow horizontal
        # El usuario puede arrastrar el separador para ajustar cada formulario.
        forms_paned = tk.PanedWindow(
            self._sf,
            orient="horizontal",
            sashwidth=5,
            sashrelief="flat",
            bg=C["outline_variant"],
            handlesize=0,
            sashcursor="sb_h_double_arrow",
            opaqueresize=True,
        )
        forms_paned.pack(fill="x", padx=24, pady=(0, 16))

        # Host para tarjeta de saltos (pane izquierdo)
        jump_host = tk.Frame(forms_paned, bg=C["background"])
        self._build_jump_card(jump_host)
        forms_paned.add(jump_host, minsize=220, stretch="always")

        # Host para tarjeta de ignorar (pane derecho)
        ignore_host = tk.Frame(forms_paned, bg=C["background"])
        self._build_ignore_card(ignore_host)
        forms_paned.add(ignore_host, minsize=220, stretch="always")

        # Tarjeta de Segmentación de PDF (Offsets Múltiples)
        self._build_segments_card()

        # Tabla de exclusiones
        self._build_exclusions_table()

    # ── Tarjeta: Saltos de Página ────────────────────────────────────────────────
    def _build_jump_card(self, parent):
        card = self._make_card(parent, "🚫  Saltos de Página (Page Jumps)")
        card.pack(fill="both", expand=True, padx=(0, 4))

        tk.Label(
            card,
            text="Indica folios que no existen físicamente en el libro original\npor pérdida o daño histórico.",
            font=("Segoe UI", 8),
            fg=C["secondary"], bg=C["surface"],
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        # Inputs numéricos
        row = tk.Frame(card, bg=C["surface"])
        row.pack(fill="x", pady=(0, 8))

        self._jump_desde = tk.StringVar(value="")
        self._jump_hasta = tk.StringVar(value="")

        for label_text, var, placeholder in [
            ("Desde Folio:", self._jump_desde, "ej: 8"),
            ("Hasta Folio:", self._jump_hasta, "ej: 9"),
        ]:
            col = tk.Frame(row, bg=C["surface"])
            col.pack(side="left", expand=True, fill="x", padx=(0, 8))

            tk.Label(col, text=label_text, font=("Segoe UI", 8),
                     fg=C["secondary"], bg=C["surface"]).pack(anchor="w", pady=(0, 2))

            entry = tk.Entry(
                col, textvariable=var,
                font=("Courier New", 12, "bold"),
                fg=C["primary"], bg=C["surface_low"],
                relief="flat", bd=0, justify="center",
                highlightbackground=C["outline_variant"],
                highlightthickness=1,
            )
            entry.pack(fill="x", ipady=6)
            entry.bind("<FocusIn>", lambda e, w=entry: w.configure(
                highlightbackground=C["primary"], highlightthickness=2))
            entry.bind("<FocusOut>", lambda e, w=entry: w.configure(
                highlightbackground=C["outline_variant"], highlightthickness=1))

        # Motivo
        tk.Label(card, text="Motivo:", font=("Segoe UI", 8),
                 fg=C["secondary"], bg=C["surface"]).pack(anchor="w", pady=(8, 2))

        self._jump_motivo = tk.StringVar(value="")
        motivo_entry = tk.Entry(
            card, textvariable=self._jump_motivo,
            font=("Segoe UI", 8),
            fg=C["tertiary"], bg=C["surface_low"],
            relief="flat", bd=0,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        motivo_entry.pack(fill="x", ipady=5, pady=(0, 12))

        # Botón agregar
        tk.Button(
            card,
            text="＋  Registrar Salto",
            font=("Segoe UI", 9, "bold"),
            fg="#ffffff", bg=C["primary"],
            activebackground=C["primary_container"],
            activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2",
            padx=12, pady=7,
            command=self._add_jump,
        ).pack(fill="x")

    # ── Tarjeta: Páginas a Ignorar ───────────────────────────────────────────────
    def _build_ignore_card(self, parent):
        card = self._make_card(parent, "🔕  Páginas a Ignorar")
        card.pack(fill="both", expand=True, padx=(4, 0))

        tk.Label(
            card,
            text="Especifica páginas o rangos del PDF que deben\nsaltarse durante la fragmentación.",
            font=("Segoe UI", 8),
            fg=C["secondary"], bg=C["surface"],
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        # Input de rango
        tk.Label(card, text="Rango de páginas:", font=("Segoe UI", 8),
                 fg=C["secondary"], bg=C["surface"]).pack(anchor="w", pady=(0, 2))

        self._ignore_rango = tk.StringVar(value="")
        range_entry = tk.Entry(
            card, textvariable=self._ignore_rango,
            font=("Courier New", 10),
            fg=C["primary"], bg=C["surface_low"],
            relief="flat", bd=0,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        range_entry.pack(fill="x", ipady=5, pady=(0, 8))

        # Selector de tipo
        tk.Label(card, text="Tipo de contenido:", font=("Segoe UI", 8),
                 fg=C["secondary"], bg=C["surface"]).pack(anchor="w", pady=(0, 2))

        self._ignore_tipo = tk.StringVar(value=CONTENIDO_OPTIONS[0])
        tipo_menu = ttk.Combobox(
            card,
            textvariable=self._ignore_tipo,
            values=CONTENIDO_OPTIONS,
            state="readonly",
            font=("Segoe UI", 9),
        )
        tipo_menu.pack(fill="x", pady=(0, 8))

        # Motivo
        tk.Label(card, text="Nota adicional:", font=("Segoe UI", 8),
                 fg=C["secondary"], bg=C["surface"]).pack(anchor="w", pady=(0, 2))

        self._ignore_nota = tk.StringVar(value="")
        nota_entry = tk.Entry(
            card, textvariable=self._ignore_nota,
            font=("Segoe UI", 8),
            fg=C["tertiary"], bg=C["surface_low"],
            relief="flat", bd=0,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        nota_entry.pack(fill="x", ipady=5, pady=(0, 12))

        # Botón
        tk.Button(
            card,
            text="＋  Agregar Exclusión",
            font=("Segoe UI", 9, "bold"),
            fg="#ffffff", bg=C["primary"],
            activebackground=C["primary_container"],
            activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2",
            padx=12, pady=7,
            command=self._add_ignore,
        ).pack(fill="x")

    # ── Tabla de exclusiones ─────────────────────────────────────────────────────
    def _build_exclusions_table(self):
        wrapper = tk.Frame(self._sf, bg=C["background"])
        wrapper.pack(fill="x", padx=24, pady=(0, 24))

        card = tk.Frame(
            wrapper, bg=C["surface"], padx=20, pady=16,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        card.pack(fill="x")

        header = tk.Frame(card, bg=C["surface"])
        header.pack(fill="x", pady=(0, 8))

        tk.Label(
            header, text="📋  Exclusiones Configuradas",
            font=("Segoe UI", 10, "bold"),
            fg=C["primary"], bg=C["surface"],
        ).pack(side="left")

        tk.Label(
            header,
            text=f"{len(self.app_state.exclusions)} reglas activas",
            font=("Segoe UI", 8),
            fg=C["secondary"], bg=C["surface"],
        ).pack(side="right")

        tk.Frame(card, bg=C["outline_variant"], height=1).pack(fill="x", pady=(0, 8))

        # Contenedor de filas de exclusiones
        self._excl_container = tk.Frame(card, bg=C["surface"])
        self._excl_container.pack(fill="x")

        self._render_exclusions()

    def _render_exclusions(self):
        for w in self._excl_container.winfo_children():
            w.destroy()

        if not self.app_state.exclusions:
            tk.Label(
                self._excl_container,
                text="No hay exclusiones configuradas aún.",
                font=("Segoe UI", 8),
                fg=C["outline"], bg=C["surface"],
            ).pack(pady=16)
            return

        for excl in self.app_state.exclusions:
            self._render_exclusion_row(excl)

    def _render_exclusion_row(self, excl):
        row = tk.Frame(
            self._excl_container, bg=C["surface_low"],
            padx=10, pady=8,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        row.pack(fill="x", pady=3)

        # Tipo pill
        tipo_cfg = {
            "SALTO":  ("#fee2e2", "#7f1d1d"),
            "IGNORAR":("#fef3c7", "#713f12"),
        }.get(excl.tipo, (C["surface_low"], C["secondary"]))

        pill = tk.Label(
            row,
            text=f"  {excl.tipo}  ",
            font=("Segoe UI", 7, "bold"),
            fg=tipo_cfg[1], bg=tipo_cfg[0],
            padx=4, pady=2,
        )
        pill.pack(side="left", padx=(0, 10))

        # Rango
        tk.Label(
            row,
            text=f"Folios {excl.desde} — {excl.hasta}",
            font=("Courier New", 9, "bold"),
            fg=C["primary"], bg=C["surface_low"],
        ).pack(side="left", padx=(0, 10))

        # Motivo
        motivo_text = excl.tipo_contenido or excl.motivo
        tk.Label(
            row,
            text=motivo_text[:50] + ("..." if len(motivo_text) > 50 else ""),
            font=("Segoe UI", 8),
            fg=C["secondary"], bg=C["surface_low"],
        ).pack(side="left", fill="x", expand=True)

        # Botón eliminar (visible en hover)
        del_btn = tk.Button(
            row,
            text="🗑",
            font=("Segoe UI", 10),
            fg="#7f1d1d", bg=C["surface_low"],
            activebackground="#fee2e2",
            relief="flat", bd=0,
            cursor="hand2",
            command=lambda e=excl: self._delete_exclusion(e.id),
        )
        del_btn.pack(side="right")

    # ── Lógica ───────────────────────────────────────────────────────────────────
    def _add_jump(self):
        try:
            desde = int(self._jump_desde.get())
            hasta = int(self._jump_hasta.get())
        except ValueError:
            messagebox.showerror("Error", "Por favor ingresa números válidos para los folios.")
            return

        if desde > hasta:
            messagebox.showerror("Error", "El folio 'Desde' debe ser menor o igual al folio 'Hasta'.")
            return

        motivo = self._jump_motivo.get().strip() or f"Salto aprobado: folios {desde}–{hasta}"

        from types import SimpleNamespace
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from types import SimpleNamespace as _SN
        # Importar ExclusionRule
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "project_types",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "project_types.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ExclusionRule = mod.ExclusionRule

        new_rule = ExclusionRule(
            id=f"EX-{len(self.app_state.exclusions)+1:03d}",
            tipo="SALTO",
            desde=desde,
            hasta=hasta,
            motivo=motivo,
        )
        self.app_state.exclusions.append(new_rule)
        self.on_add_log("INFO", f"Salto registrado: folios {desde}–{hasta}. {motivo}")

        # Limpiar
        self._jump_desde.set("")
        self._jump_hasta.set("")
        self._jump_motivo.set("")
        self._render_exclusions()
        self._run_analysis_and_refresh()

    def _add_ignore(self):
        rango = self._ignore_rango.get().strip()
        if not rango:
            messagebox.showerror("Error", "Por favor ingresa el rango de páginas.")
            return

        tipo_contenido = self._ignore_tipo.get()
        nota = self._ignore_nota.get().strip()
        motivo = nota or f"Contenido omitido: {tipo_contenido}"

        # Parsear rango simple
        try:
            if "-" in rango:
                parts = rango.split("-")
                desde = int(parts[0].strip())
                hasta = int(parts[-1].strip())
            elif "," in rango:
                nums = [int(x.strip()) for x in rango.split(",") if x.strip()]
                desde = min(nums)
                hasta = max(nums)
            else:
                desde = hasta = int(rango.strip())
        except ValueError:
            messagebox.showerror("Error", "Formato de rango inválido. Usa: '1-5' o '1, 3, 7'")
            return

        import sys, os, importlib.util
        spec = importlib.util.spec_from_file_location(
            "project_types",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "project_types.py")
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ExclusionRule = mod.ExclusionRule

        new_rule = ExclusionRule(
            id=f"EX-{len(self.app_state.exclusions)+1:03d}",
            tipo="IGNORAR",
            desde=desde,
            hasta=hasta,
            motivo=motivo,
            tipo_contenido=tipo_contenido,
        )
        self.app_state.exclusions.append(new_rule)
        self.on_add_log("INFO", f"Exclusión agregada: páginas {desde}–{hasta} ({tipo_contenido})")

        self._ignore_rango.set("")
        self._ignore_nota.set("")
        self._render_exclusions()
        self._run_analysis_and_refresh()

    def _delete_exclusion(self, excl_id: str):
        self.app_state.exclusions = [
            e for e in self.app_state.exclusions if e.id != excl_id
        ]
        self.on_add_log("WARN", f"Exclusión {excl_id} eliminada.")
        self._render_exclusions()
        self._run_analysis_and_refresh()

    def _run_analysis_and_refresh(self):
        # 1. Ejecutar análisis de folios automático
        from utils.analyzers import analizar_folios
        res_folios = analizar_folios(self.app_state.records, self.app_state.exclusions)

        # 2. Primero reiniciar todos los estados que estaban en REVISAR a vacío
        for rec in self.app_state.records:
            if rec.estado == "REVISAR":
                rec.estado = ""

        # 3. Marcar como REVISAR los que tienen errores según el nuevo análisis
        for err in res_folios.errores:
            for rec in self.app_state.records:
                if rec.id == err.record_id:
                    rec.estado = "REVISAR"
                    break

        # 4. Actualizar las sugerencias en AppState
        from utils.folio_parser import calculate_suggested_range
        from project_types import SugerenciaCorreccion
        from utils.folio_engine import mapper_from_state
        mapper = mapper_from_state(self.app_state)
        
        self.app_state.suggestions = [s for s in self.app_state.suggestions if s.tipo_error not in ("folios", "SALTO DE FOLIO", "SALTO", "FORMATO", "SOLAPAMIENTO")]
        
        for err in res_folios.errores:
            curr_idx = next((idx for idx, r in enumerate(self.app_state.records) if r.id == err.record_id), None)
            prev_rec = self.app_state.records[curr_idx - 1] if curr_idx and curr_idx > 0 else None
            curr_rec = self.app_state.records[curr_idx] if curr_idx is not None else None

            sug_range = "001r-002v"
            if prev_rec and curr_rec:
                sug_range = calculate_suggested_range(prev_rec, curr_rec) or "001r-002v"

            sug = SugerenciaCorreccion(
                id=f"SUG-{len(self.app_state.suggestions)+1:03d}",
                registro_id=err.record_id,
                tipo_error=err.tipo,
                descripcion=err.descripcion,
                valor_actual=curr_rec.folios if curr_rec else "",
                valor_sugerido=sug_range,
                escribano=curr_rec.escribano if curr_rec else "",
                folios_original=curr_rec.folios if curr_rec else "",
                rango_sugerido=sug_range,
                paginas_pdf=curr_rec.pg_pdf if curr_rec else "",
                paginas_sugeridas=mapper.folio_str_to_pdf_range(sug_range) or "",
                fecha_original="",
                fecha_validada=""
            )
            self.app_state.suggestions.append(sug)

        # 5. Repoblar la tabla Excel en esta pantalla
        self._populate_excel_table()

    # ── Tarjeta: Segmentación de PDF ──────────────────────────────────────────────
    def _build_segments_card(self):
        wrapper = tk.Frame(self._sf, bg=C["background"])
        wrapper.pack(fill="x", padx=24, pady=(0, 16))

        card = tk.Frame(
            wrapper, bg=C["surface"], padx=20, pady=16,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        card.pack(fill="x")

        # Título
        tk.Label(
            card, text="🗺️  Segmentos PDF y Puntos de Corte (Offsets Adicionales)",
            font=("Segoe UI", 10, "bold"),
            fg=C["primary"], bg=C["surface"],
        ).pack(anchor="w", pady=(0, 4))
        tk.Label(
            card,
            text="Si la digitalización física contiene desfases múltiples o saltos de numeración, configure nuevos puntos de corte.",
            font=("Segoe UI", 8),
            fg=C["secondary"], bg=C["surface"],
        ).pack(anchor="w", pady=(0, 10))

        tk.Frame(card, bg=C["outline_variant"], height=1).pack(fill="x", pady=(0, 12))

        # Inputs
        row = tk.Frame(card, bg=C["surface"])
        row.pack(fill="x", pady=(0, 12))

        # Folio Inicio
        f_col = tk.Frame(row, bg=C["surface"])
        f_col.pack(side="left", padx=(0, 12))
        tk.Label(f_col, text="Folio Inicio:", font=("Segoe UI", 8),
                 fg=C["secondary"], bg=C["surface"]).pack(anchor="w")
        self._seg_folio = tk.StringVar(value="")
        f_entry = tk.Entry(f_col, textvariable=self._seg_folio, font=("Courier New", 10),
                           fg=C["primary"], bg=C["surface_low"], relief="flat", bd=0, width=12,
                           highlightbackground=C["outline_variant"], highlightthickness=1)
        f_entry.pack(ipady=4)

        # Página PDF Inicio
        p_col = tk.Frame(row, bg=C["surface"])
        p_col.pack(side="left", padx=(0, 16))
        tk.Label(p_col, text="Pág. PDF Inicio:", font=("Segoe UI", 8),
                 fg=C["secondary"], bg=C["surface"]).pack(anchor="w")
        self._seg_pag = tk.StringVar(value="")
        p_entry = tk.Entry(p_col, textvariable=self._seg_pag, font=("Courier New", 10),
                           fg=C["primary"], bg=C["surface_low"], relief="flat", bd=0, width=12,
                           highlightbackground=C["outline_variant"], highlightthickness=1)
        p_entry.pack(ipady=4)

        # Botón agregar
        tk.Button(
            row,
            text="＋ Agregar Segmento",
            font=("Segoe UI", 8, "bold"),
            fg="#ffffff", bg=C["primary"],
            activebackground=C["primary_container"],
            activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2",
            padx=12, pady=6,
            command=self._add_segment,
        ).pack(side="left", anchor="s")

        # Contenedor de lista de segmentos
        self._seg_list_frame = tk.Frame(card, bg=C["surface"])
        self._seg_list_frame.pack(fill="x")

        self._render_segments()

    def _add_segment(self):
        fol = self._seg_folio.get().strip()
        pag = self._seg_pag.get().strip()

        if not fol or not pag:
            messagebox.showerror("Error", "Completa ambos campos.")
            return

        try:
            pag_val = int(pag)
        except ValueError:
            messagebox.showerror("Error", "Página PDF Inicio debe ser un número entero.")
            return

        # Validar formato de folio
        from utils.folio_parser import parse_folios
        if parse_folios(fol) is None:
            messagebox.showerror("Error", "Folio Inicio inválido (ej: '002r', '401v').")
            return

        # Registrar segmento
        self.app_state.segmentos.append({
            "folio_inicio": fol,
            "pag_pdf_inicio": pag_val
        })
        self.on_add_log("INFO", f"Segmento configurado: {fol} → página PDF {pag_val}")

        self._seg_folio.set("")
        self._seg_pag.set("")
        self._render_segments()

    def _delete_segment(self, index: int):
        if 0 <= index < len(self.app_state.segmentos):
            removed = self.app_state.segmentos.pop(index)
            self.on_add_log("WARN", f"Segmento {removed['folio_inicio']} eliminado.")
            self._render_segments()

    def _render_segments(self):
        for w in self._seg_list_frame.winfo_children():
            w.destroy()

        if not self.app_state.segmentos:
            tk.Label(
                self._seg_list_frame,
                text="No hay segmentos adicionales configurados (se aplica traducción lineal por defecto).",
                font=("Segoe UI", 8, "italic"),
                fg=C["secondary"], bg=C["surface"]
            ).pack(anchor="w")
            return

        for idx, seg in enumerate(self.app_state.segmentos):
            row = tk.Frame(self._seg_list_frame, bg=C["surface_low"], pady=4, padx=8,
                           highlightbackground=C["outline_variant"], highlightthickness=1)
            row.pack(fill="x", pady=2)

            tk.Label(
                row,
                text=f"📍  Folio {seg['folio_inicio']}  ──▶  Corresponde a la Página PDF {seg['pag_pdf_inicio']}",
                font=("Segoe UI", 9, "bold"),
                fg=C["primary"], bg=C["surface_low"]
            ).pack(side="left")

            tk.Button(
                row,
                text="Eliminar",
                font=("Segoe UI", 7, "bold"),
                fg="#a03030", bg=C["surface_low"],
                activebackground="#fee2e2",
                relief="flat", bd=0, cursor="hand2",
                command=lambda i=idx: self._delete_segment(i),
            ).pack(side="right")


    # ── Helper ───────────────────────────────────────────────────────────────────
    def _make_card(self, parent, title: str) -> tk.Frame:
        outer = tk.Frame(parent, bg=C["background"])
        card = tk.Frame(
            outer, bg=C["surface"], padx=20, pady=16,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        card.pack(fill="both", expand=True)

        tk.Label(
            card, text=title,
            font=("Segoe UI", 10, "bold"),
            fg=C["primary"], bg=C["surface"],
        ).pack(anchor="w", pady=(0, 8))
        tk.Frame(card, bg=C["outline_variant"], height=1).pack(fill="x", pady=(0, 12))

        return card
