"""
WorkspaceView.py — Pantalla 1: Área de Trabajo del Archivista.
Carga de archivos (Excel/PDF), mapeo inicial, preview de inventario y fragmentación.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import os
import re
import pandas as pd

from utils.folio_engine import mapper_from_state
from project_types import InventoryRecord
from project_types import SugerenciaCorreccion
from utils.hierarchy_builder import RomanToSigloArabic
from utils.analyzers import analizar_folios
from utils.folio_parser import calculate_suggested_range
from utils.theme import C, FONT


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
            fg="#ffffff",
            bg=C["primary"],
            activebackground=C["primary_container"],
            activeforeground="#ffffff",
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
                self._process_excel_file(self.app_state.excel_path)
            
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
        cols = ("ID", "Registro", "Escribano", "Folios", "Pág. PDF", "Estado")
        style = ttk.Style()
        style.configure(
            "Preview.Treeview",
            background=C["surface_low"],
            foreground=C["secondary"],
            fieldbackground=C["surface_low"],
            rowheight=28,
            font=("Segoe UI", 8),
        )
        style.configure(
            "Preview.Treeview.Heading",
            background=C["surface_high"],
            foreground=C["primary"],
            font=("Segoe UI", 8, "bold"),
            relief="flat",
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
            "Folios": 80, "Pág. PDF": 80, "Estado": 110,
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
            estado_icon = {
                "": "",
                "REVISAR": "⚠️",
                "FRAGMENTADO": "📎"
            }.get(r.estado, "")
            disp_estado = f"{estado_icon} {r.estado}".strip()
            tags = ("even",) if i % 2 == 0 else ("odd",)
            self._preview_tree.insert(
                "", "end", iid=r.id,
                values=(r.id, r.registro, r.escribano, r.folios, r.pg_pdf, disp_estado),
                tags=tags
            )

    def _on_row_select(self, event):
        selected = self._preview_tree.selection()
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



    # ── Carga de archivos ────────────────────────────────────────────────────────
    def _load_excel(self):
        path = filedialog.askopenfilename(
            title="Seleccionar Inventario Excel",
            filetypes=[("Excel", "*.xlsx *.xls"), ("CSV", "*.csv"), ("Todos", "*.*")]
        )
        if path:
            self._process_excel_file(path)

    def _process_excel_file(self, path):
        self.app_state.excel_path = path
        filename = os.path.basename(path)
        self._show_file_banner("excel", filename)
        self.on_add_log("INFO", f"Leyendo archivo de inventario: {filename}...")

        # ── 1. Lectura de Metadatos Globales (Filas 4 y 7)
        siglo_detectado = "XIX"
        acervo_detectado = "7"
        
        try:
            # Leer las primeras 7 filas para extraer metadatos sin saltar
            if not path.lower().endswith('.csv'):
                meta_df = pd.read_excel(path, nrows=7, header=None)
                if len(meta_df) >= 4:
                    celda_siglo = str(meta_df.iloc[3, 0])
                    # Buscar patrón "Seccion: XVI" o similar
                    match_s = re.search(r'secci[oó]n:\s*([A-Za-z0-9]+)', celda_siglo, re.IGNORECASE)
                    if match_s:
                        siglo_detectado = match_s.group(1).upper()
                
                if len(meta_df) >= 7:
                    celda_acervo = str(meta_df.iloc[6, 0])
                    # Buscar patrón "Código del fondo: N7" o "n07"
                    match_a = re.search(r'c[oó]digo\s+del\s+fondo:\s*[Nn]0*(\d+)', celda_acervo, re.IGNORECASE)
                    if match_a:
                        acervo_detectado = match_a.group(1)
        except Exception as e:
            self.on_add_log("WARN", f"No se pudieron extraer metadatos globales de las filas 4/7: {e}. Usando valores por defecto.")

        # Convertir Siglo Romano a Arábigo
        siglo_arabigo = RomanToSigloArabic(siglo_detectado)
        self.app_state.acervo_num = acervo_detectado
        self.on_add_log("SUCCESS", f"Metadatos extraídos: Acervo N° {acervo_detectado}, Siglo Romano '{siglo_detectado}' (Arábigo {siglo_arabigo}).")

        # ── 2. Cargar DataFrame de datos omitiendo las primeras 7 filas
        try:
            if path.lower().endswith('.csv'):
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path, skiprows=7)
        except Exception as e:
            messagebox.showerror("Error", f"Fallo al abrir el archivo de datos:\n{e}")
            self.on_add_log("ERR", f"Fallo al leer celdas: {e}")
            return

        # Limpiar espacios en nombres de columnas
        df.columns = [str(c).strip() for c in df.columns]
        
        # Filtrar columnas Unnamed de pandas
        cols = [c for c in df.columns if not str(c).startswith("Unnamed:")]

        # Mapeo de columnas según consideraciones_excel.md
        col_map = {
            "registro": None, "escribano": None, "protocolo": None,
            "folios": None, "titulo": None, "fecha_inicio": None,
            "fecha_fin": None, "interesado1": None, "interesado2": None
        }

        # Buscadores heurísticos estrictos
        for c in cols:
            c_clean = c.lower().replace("\n", " ").strip()
            if "n° de registro" in c_clean or "numero de registro" in c_clean:
                col_map["registro"] = c
            elif "escribano" in c_clean or "notario" in c_clean:
                col_map["escribano"] = c
            elif "n° de prot" in c_clean or "protocolo" in c_clean:
                col_map["protocolo"] = c
            elif "n° de folios" in c_clean or "folios" in c_clean:
                col_map["folios"] = c
            elif "titulo estandar" in c_clean or "titulo" in c_clean:
                col_map["titulo"] = c
            elif "interesado 1" in c_clean or "interesado1" in c_clean:
                col_map["interesado1"] = c
            elif "interesado 2" in c_clean or "interesado2" in c_clean:
                col_map["interesado2"] = c
            elif "fecha inicial" in c_clean or "data cronica 1" in c_clean or ("data cr" in c_clean and "1" in c_clean):
                col_map["fecha_inicio"] = c
            elif "fecha final" in c_clean or "data cronica 2" in c_clean or ("data cr" in c_clean and "2" in c_clean):
                col_map["fecha_fin"] = c

        # Fallback heurístico simple si no se mapeó todo
        for key, possible_names in [
            ("registro", ["registro", "id", "expediente"]),
            ("escribano", ["escribano", "notario"]),
            ("protocolo", ["prot", "protocolo", "tomo"]),
            ("folios", ["folios", "rango", "paginas"]),
            ("titulo", ["titulo", "asunto", "desc"]),
            ("fecha_inicio", ["inicial", "inicio", "fecha 1"]),
            ("fecha_fin", ["final", "fin", "fecha 2"]),
            ("interesado1", ["interesado 1", "interesado"]),
            ("interesado2", ["interesado 2"])
        ]:
            if col_map[key] is None:
                for c in cols:
                    if any(pn in c.lower() for pn in possible_names):
                        col_map[key] = c
                        break

        # Forzar mapeo específico de columnas por posición si existen suficientes columnas
        if len(df.columns) >= 5:
            col_map["titulo"] = df.columns[4]      # Columna 5 (E) es Data Tópica
        if len(df.columns) >= 6:
            col_map["fecha_inicio"] = df.columns[5] # Columna 6 (F) es Data Crónica

        # Limpiar registros y sugerencias anteriores
        self.app_state.records = []
        self.app_state.suggestions = []

        # Construir FolioMapper dinámico
        mapper = mapper_from_state(self.app_state)

        # Fila inicio y fin (1-indexed en la UI, index real en pandas)
        # La UI configura la fila inicio/fin del Excel real. 
        # Como saltamos las primeras 7 filas, la fila 8 es la cabecera (index 0).
        # Fila de datos en Excel 9 -> índice pandas 0.
        # Por tanto, index pandas = fila_excel - 9.
        fila_inicio_idx = max(0, self.app_state.fila_inicio - 9)
        fila_fin_idx = min(len(df), self.app_state.fila_fin - 8)

        records_temp = []
        for i in range(fila_inicio_idx, fila_fin_idx):
            row_data = df.iloc[i]
            
            # Obtener primera celda para verificar si es fila decorativa
            first_cell = str(row_data.iloc[0]).strip()
            
            # ── 3. Filtro de Marcadores de Sección (Filas Decorativas)
            if re.match(r'^\s*(protocolo|registro)\b', first_cell, re.IGNORECASE):
                # Omitir fila completa decorativa
                continue

            # Obtener datos sanitizados (NaN -> "") e ignorar espacios
            def get_val(key):
                val = row_data.get(col_map[key])
                if pd.isna(val) or str(val).strip().lower() in ["nan", "nat"]:
                    return ""
                return str(val).strip()

            reg = get_val("registro")
            esc = get_val("escribano")
            prot = get_val("protocolo")
            fols = get_val("folios")
            tit = get_val("titulo")
            f_ini = get_val("fecha_inicio")
            f_fin = get_val("fecha_fin")
            int1 = get_val("interesado1")
            int2 = get_val("interesado2")

            # Evitar filas completamente vacías
            if not reg and not esc and not fols:
                continue

            # Calcular fila de Excel real: fila_excel = index_pandas + 7 + 2 = index_pandas + 9
            fila_excel_real = i + 9
            r_id = f"#{len(records_temp) + 1:04d}"
            
            # Calcular páginas PDF usando el motor
            pg_range = mapper.folio_str_to_pdf_range(fols) or "1"

            # Crear InventoryRecord con campos de apoyo para jerarquía
            rec = InventoryRecord(
                id=r_id,
                fila=fila_excel_real,
                registro=reg if reg else f"REG-{r_id}",
                escribano=esc if esc else "Sin Escribano",
                protocolo=prot if prot else "S/P",
                folios=fols if fols else "001r",
                pg_pdf=pg_range,
                titulo=tit if tit else "Sin Título",
                estado=""
            )
            # Guardamos los campos extendidos en el record de forma dinámica
            rec.fecha_inicio = f_ini
            rec.fecha_fin = f_fin
            rec.interesado1 = int1
            rec.interesado2 = int2
            
            records_temp.append(rec)

        self.app_state.records = records_temp

        # Ejecutar análisis de folios automático para clasificar alertas en background
        res_folios = analizar_folios(self.app_state.records, self.app_state.exclusions)

        # Poblar sugerencias y marcar como REVISAR los que tienen errores
        for err in res_folios.errores:
            # Marcar el registro
            for rec in self.app_state.records:
                if rec.id == err.record_id:
                    rec.estado = "REVISAR"
                    break

            # Generar sugerencia de corrección inteligente
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

        self._refresh_preview_table()
        self.on_add_log("SUCCESS", f"Inventario Excel cargado: {len(self.app_state.records)} registros importados de forma real.")
        if len(res_folios.errores) > 0:
            self.on_add_log("WARN", f"Se detectaron {len(res_folios.errores)} alertas en la foliación física.")



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
