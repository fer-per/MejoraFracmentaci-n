"""
WorkspaceView.py — Pantalla 1: Área de Trabajo del Archivista.
Carga de archivos (Excel/PDF), mapeo inicial, preview de inventario y fragmentación.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

from utils.folio_engine import mapper_from_state
from use_cases.excel_processing_use_case import process_excel
from adapters.services import navigate_to_record_pdf, configure_treeview_style
from utils.theme import C


class WorkspaceView(tk.Frame):
    """Vista principal de configuración inicial y fragmentación."""

    def __init__(self, parent, app_state, on_add_log, on_navigate, **kwargs):
        self.on_load_pdf = kwargs.pop("on_load_pdf", None)
        self.on_navigate_pdf = kwargs.pop("on_navigate_pdf", None)
        super().__init__(parent, **kwargs)
        self.app_state = app_state
        self.on_add_log = on_add_log
        self.on_navigate = on_navigate
        self._progress_var = tk.DoubleVar(value=0)
        self._processing = False
        self.configure(bg=C["background"])
        self._build()
        self.bind("<Map>", lambda e: self.refresh())

    def refresh(self):
        self._refresh_preview_table()

    # ── Construcción ────────────────────────────────────────────────────────────
    def _build(self):
        # Scroll canvas
        self._canvas = tk.Canvas(self, bg=C["background"], bd=0, highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._scroll_frame = tk.Frame(self._canvas, bg=C["background"])

        self._scroll_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        )
        self._canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._scroll_frame.bind("<MouseWheel>", self._on_mousewheel)

        self._build_content()

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    def _build_content(self):
        f = self._scroll_frame
        pad = {"padx": 24, "pady": 10}

        # ── Encabezado de la vista ───────────────────────────────────────────────
        header = tk.Frame(f, bg=C["background"])
        header.pack(fill="x", **pad)

        tk.Label(
            header,
            text="Archivo",
            font=("Segoe UI", 18, "bold"),
            fg=C["primary"],
            bg=C["background"],
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Configure los archivos fuente y los parámetros de mapeo para iniciar la fragmentación.",
            font=("Segoe UI", 9),
            fg=C["secondary"],
            bg=C["background"],
        ).pack(anchor="w")

        # ── Paso 1: Tarjeta de carga ─────────────────────────────────────────────
        self._build_upload_card(f, pad)

        # ── Paso 2: Mapeo inicial ────────────────────────────────────────────────
        self._build_mapping_card(f, pad)

        # ── Paso 3: Preview del inventario ──────────────────────────────────────
        self._build_preview_card(f, pad)

    # ── Tarjeta de carga de archivos ────────────────────────────────────────────
    def _build_upload_card(self, parent, pad):
        card = self._make_card(parent, "📁  Paso 1 — Carga de Archivos")

        upload_row = tk.Frame(card, bg=C["surface"])
        upload_row.pack(fill="x", pady=(0, 8))

        # Excel drop zone
        self._excel_zone = self._make_drop_zone(
            upload_row,
            icon="📊",
            label="Inventario Excel",
            sublabel="Arrastra o haz clic (.xlsx)",
            command=self._load_excel,
        )
        self._excel_zone.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # PDF drop zone
        self._pdf_zone = self._make_drop_zone(
            upload_row,
            icon="📄",
            label="PDF Original",
            sublabel="Arrastra o haz clic (.pdf)",
            command=self._load_pdf,
        )
        self._pdf_zone.pack(side="left", fill="both", expand=True)

        # Banner de archivos cargados
        self._file_banner_frame = tk.Frame(card, bg=C["surface"])
        self._file_banner_frame.pack(fill="x")

    def _make_drop_zone(self, parent, icon, label, sublabel, command):
        zone = tk.Frame(
            parent,
            bg=C["surface_low"],
            relief="flat",
            bd=0,
            cursor="hand2",
            height=110,
        )
        zone.pack_propagate(False)

        # Borde simulado
        zone.configure(
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )

        inner = tk.Frame(zone, bg=C["surface_low"])
        inner.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(inner, text=icon, font=("Segoe UI", 22), bg=C["surface_low"]).pack()
        tk.Label(
            inner, text=label, font=("Segoe UI", 9, "bold"),
            fg=C["secondary"], bg=C["surface_low"]
        ).pack()
        tk.Label(
            inner, text=sublabel, font=("Segoe UI", 7),
            fg=C["outline"], bg=C["surface_low"]
        ).pack()

        zone.bind("<Button-1>", lambda e: command())
        inner.bind("<Button-1>", lambda e: command())
        for w in inner.winfo_children():
            w.bind("<Button-1>", lambda e: command())

        zone.bind("<Enter>", lambda e: zone.configure(bg=C["secondary_container"],
                  highlightbackground=C["primary"]))
        zone.bind("<Leave>", lambda e: zone.configure(bg=C["surface_low"],
                  highlightbackground=C["outline_variant"]))

        return zone

    # ── Tarjeta de mapeo ─────────────────────────────────────────────────────────
    def _build_mapping_card(self, parent, pad):
        card = self._make_card(parent, "🗺️  Paso 2 — Parámetros de Mapeo")

        row = tk.Frame(card, bg=C["surface"])
        row.pack(fill="x")

        self._fila_inicio_var = tk.StringVar(value=str(self.app_state.fila_inicio))
        self._fila_fin_var = tk.StringVar(value=str(self.app_state.fila_fin))
        self._folio_inicio_var = tk.StringVar(value=str(self.app_state.folio_inicio))
        self._pag_pdf_var = tk.StringVar(value=str(self.app_state.pag_pdf_inicio))

        inputs = [
            ("Inicia desde fila:", self._fila_inicio_var),
            ("Termina en fila:", self._fila_fin_var),
            ("Folio Inicio Protocolo:", self._folio_inicio_var),
            ("Pág. PDF Inicio:", self._pag_pdf_var),
        ]

        for label_text, var in inputs:
            col = tk.Frame(row, bg=C["surface"])
            col.pack(side="left", expand=True, fill="x", padx=(0, 12))

            tk.Label(
                col, text=label_text,
                font=("Segoe UI", 8),
                fg=C["secondary"],
                bg=C["surface"],
                anchor="w",
            ).pack(fill="x", pady=(0, 2))

            entry = tk.Entry(
                col, textvariable=var,
                font=("Courier New", 10, "bold"),
                fg=C["primary"],
                bg=C["surface_low"],
                relief="flat",
                bd=0,
                justify="center",
                highlightbackground=C["outline_variant"],
                highlightthickness=1,
            )
            entry.pack(fill="x", ipady=6)
            entry.bind("<FocusIn>", lambda e, w=entry: w.configure(
                highlightbackground=C["primary"], highlightthickness=2))
            entry.bind("<FocusOut>", lambda e, w=entry: w.configure(
                highlightbackground=C["outline_variant"], highlightthickness=1))

        # Fila de botón de guardar
        btn_row = tk.Frame(card, bg=C["surface"])
        btn_row.pack(fill="x", pady=(10, 0))

        self._save_mapping_btn = tk.Button(
            btn_row,
            text="💾 Guardar Cambios",
            font=("Segoe UI", 9, "bold"),
            fg=C["white"],
            bg=C["primary"],
            activebackground=C["primary_container"],
            activeforeground=C["white"],
            relief="flat", bd=0,
            cursor="hand2",
            padx=16, pady=6,
            command=self._save_mapping_params,
        )
        self._save_mapping_btn.pack(side="right")

    def _save_mapping_params(self):
        try:
            fila_inicio = int(self._fila_inicio_var.get())
            fila_fin = int(self._fila_fin_var.get())
            folio_inicio = int(self._folio_inicio_var.get())
            pag_pdf_inicio = int(self._pag_pdf_var.get())
            
            if fila_inicio < 2:
                messagebox.showerror("Error de Validación", "La fila de inicio debe ser >= 2 (filas 0-7 son cabecera).")
                return
            if fila_inicio >= fila_fin:
                messagebox.showerror("Error de Validación", "La fila de inicio debe ser menor que la fila fin.")
                return
            if folio_inicio < 1:
                messagebox.showerror("Error de Validación", "El folio inicio debe ser >= 1.")
                return
            if pag_pdf_inicio < 1:
                messagebox.showerror("Error de Validación", "La página PDF inicio debe ser >= 1.")
                return
            
            self.app_state.fila_inicio = fila_inicio
            self.app_state.fila_fin = fila_fin
            self.app_state.folio_inicio = folio_inicio
            self.app_state.pag_pdf_inicio = pag_pdf_inicio
            
            if self.app_state.excel_path:
                self._process_excel_file(self.app_state.excel_path, auto_detect=False)
            
            self.on_add_log("SUCCESS", "Parámetros de mapeo guardados y aplicados correctamente.")
            messagebox.showinfo("Parámetros Guardados", "Los parámetros de mapeo se han guardado con éxito.")
        except ValueError:
            messagebox.showerror("Error de Validación", "Todos los campos deben ser números enteros válidos.")

    # ── Preview de inventario ────────────────────────────────────────────────────
    def _build_preview_card(self, parent, pad):
        self._preview_card = self._make_card(parent, "👁  Paso 3 — Previsualización del Inventario")

        # Fila superior: botón vista expandida
        header_row = tk.Frame(self._preview_card, bg=C["surface"])
        header_row.pack(fill="x", pady=(0, 8))

        tk.Label(
            header_row,
            text="Registros del inventario cargado:",
            font=("Segoe UI", 8),
            fg=C["secondary"],
            bg=C["surface"],
        ).pack(side="left")

        expand_btn = tk.Button(
            header_row,
            text="Vista Expandida →",
            font=("Segoe UI", 8, "bold"),
            fg=C["primary"],
            bg=C["secondary_container"],
            activebackground=C["outline_variant"],
            relief="flat", bd=0,
            cursor="hand2",
            padx=8, pady=3,
            command=lambda: self.on_navigate("analyzer"),
        )
        expand_btn.pack(side="right")



        # Tabla de preview con scrollbar
        cols = ("ID", "Registro", "Escribano", "Protocolo", "Folios", "Pág. PDF")
        configure_treeview_style(
            "Preview.Treeview",
            bg_color=C["surface_low"],
            fg_color=C["secondary"],
            field_bg=C["surface_low"],
            row_height=28,
        )

        tree_frame = tk.Frame(self._preview_card, bg=C["surface"])
        tree_frame.pack(fill="both", expand=True)

        vsb = tk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side="right", fill="y")

        self._preview_tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            height=8,
            style="Preview.Treeview",
            yscrollcommand=vsb.set,
            selectmode="extended",
        )
        vsb.configure(command=self._preview_tree.yview)
        self._preview_tree.pack(side="left", fill="both", expand=True)

        col_widths = {
            "ID": 50, "Registro": 90, "Escribano": 150,
            "Protocolo": 80, "Folios": 80, "Pág. PDF": 80,
        }
        for col in cols:
            self._preview_tree.heading(col, text=col)
            self._preview_tree.column(col, width=col_widths.get(col, 100), anchor="w")

        self._preview_tree.tag_configure("even", background=C["surface_low"])
        self._preview_tree.tag_configure("odd", background=C["surface"])
        self._preview_tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self._preview_tree.bind("<MouseWheel>", lambda e: self._preview_tree.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        self._refresh_preview_table()

    def _refresh_preview_table(self):
        # Limpiar
        for item in self._preview_tree.get_children():
            self._preview_tree.delete(item)

        # Poblar todos los registros
        for i, r in enumerate(self.app_state.records):
            tags = ("even",) if i % 2 == 0 else ("odd",)
            self._preview_tree.insert(
                "", "end", iid=r.id,
                values=(r.fila, r.registro, r.escribano, r.protocolo, r.folios, r.pg_pdf),
                tags=tags
            )

    def _on_row_select(self, event):
        selected = self._preview_tree.selection()
        if not selected:
            return
        navigate_to_record_pdf(
            self._preview_tree, self.app_state.records,
            selected[0], self.on_navigate_pdf
        )



    # ── Carga de archivos ────────────────────────────────────────────────────────
    def _load_excel(self):
        path = filedialog.askopenfilename(
            title="Seleccionar Inventario Excel",
            filetypes=[("Excel", "*.xlsx *.xls"), ("CSV", "*.csv"), ("Todos", "*.*")]
        )
        if path:
            self._process_excel_file(path)

    def _process_excel_file(self, path, auto_detect=True):
        self.app_state.excel_path = path
        filename = os.path.basename(path)
        self._show_file_banner("excel", filename)
        self.on_add_log("INFO", f"Leyendo archivo de inventario: {filename}...")

        result = process_excel(path, self.app_state, auto_detect=auto_detect)

        for tipo, mensaje in result["messages"]:
            self.on_add_log(tipo, mensaje)

        if hasattr(self, "_fila_inicio_var") and self._fila_inicio_var:
            self._fila_inicio_var.set(str(self.app_state.fila_inicio))
        if hasattr(self, "_fila_fin_var") and self._fila_fin_var:
            self._fila_fin_var.set(str(self.app_state.fila_fin))

        self._refresh_preview_table()
        self.on_add_log("SUCCESS", f"Inventario Excel cargado: {result['total_records']} registros importados.")
        if result["total_errors"] > 0:
            self.on_add_log("WARN", f"Se detectaron {result['total_errors']} alertas en la foliacion.")



    def _load_pdf(self):
        path = filedialog.askopenfilename(
            title="Seleccionar PDF Original",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")]
        )
        if path:
            self.app_state.pdf_path = path
            filename = path.split("/")[-1].split("\\")[-1]
            self._show_file_banner("pdf", filename)
            self.on_add_log("SUCCESS", f"PDF maestro cargado: {filename}")

            # Auto-detectar total de páginas del PDF y adaptar parámetros
            try:
                import pypdf
                reader = pypdf.PdfReader(path)
                total_pages = len(reader.pages)
                self.app_state.pdf_total_pages = total_pages
                self.app_state.pag_pdf_inicio = 1
                if hasattr(self, "_pag_pdf_var") and self._pag_pdf_var:
                    self._pag_pdf_var.set("1")
                self.on_add_log("INFO", f"PDF detectado: {total_pages} páginas. Pág. PDF inicio establecida a 1.")
            except Exception:
                pass

            if self.on_load_pdf:
                self.on_load_pdf(path)

    def _show_file_banner(self, tipo, filename):
        # Limpiar banners del mismo tipo si los hay
        for w in self._file_banner_frame.winfo_children():
            if getattr(w, "_banner_tipo", None) == tipo:
                w.destroy()

        icon = "📊" if tipo == "excel" else "📄"
        banner = tk.Frame(
            self._file_banner_frame,
            bg=C["secondary_container"],
            pady=4,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        banner._banner_tipo = tipo
        banner.pack(fill="x", pady=(4, 0))

        tk.Label(
            banner,
            text=f"  {icon}  {filename}",
            font=("Segoe UI", 8),
            fg=C["primary"],
            bg=C["secondary_container"],
            anchor="w",
        ).pack(side="left", padx=8)

        tk.Button(
            banner,
            text="✕",
            font=("Segoe UI", 8),
            fg=C["secondary"],
            bg=C["secondary_container"],
            relief="flat", bd=0,
            cursor="hand2",
            command=lambda t=tipo, b=banner: self._dismiss_banner(t, b),
        ).pack(side="right", padx=8)

    def _dismiss_banner(self, tipo, banner):
        banner.destroy()
        if tipo == "excel":
            self.app_state.excel_path = None
            self.app_state.records = []
            self._refresh_preview_table()
            self.on_add_log("WARN", "Archivo Excel removido del estado.")
        elif tipo == "pdf":
            self.app_state.pdf_path = None
            self.on_add_log("WARN", "Archivo PDF removido del estado.")

    # ── Helper tarjeta ───────────────────────────────────────────────────────────
    def _make_card(self, parent, title: str) -> tk.Frame:
        wrapper = tk.Frame(parent, bg=C["background"])
        wrapper.pack(fill="x", padx=24, pady=(0, 16))

        card = tk.Frame(
            wrapper,
            bg=C["surface"],
            padx=20, pady=16,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        card.pack(fill="x")

        tk.Label(
            card,
            text=title,
            font=("Segoe UI", 10, "bold"),
            fg=C["primary"],
            bg=C["surface"],
        ).pack(anchor="w", pady=(0, 12))

        tk.Frame(card, bg=C["outline_variant"], height=1).pack(fill="x", pady=(0, 12))

        return card
