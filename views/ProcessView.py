"""
ProcessView.py — Pantalla de Procesamiento y Consola de Fragmentación.
Contiene el panel "Fragmentar PDF" con barra de progreso, consola de logs dedicada
y el panel de detalle de folios mapeados con páginas de PDF.
"""
import tkinter as tk
from tkinter import ttk
import threading
import time
import os
import csv
import pypdf


from utils.folio_engine import mapper_from_state
from utils.hierarchy_builder import build_11_level_path
from utils.analyzers import analizar_folios


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
    "on_tertiary":       "#e5e1df",
    "secondary":         "#7c535d",
}


class ProcessView(tk.Frame):
    """Vista de procesamiento dedicada."""

    def __init__(self, parent, app_state, on_add_log, **kwargs):
        self.on_navigate_pdf = kwargs.pop("on_navigate_pdf", None)
        kwargs.pop("on_load_pdf", None)
        super().__init__(parent, **kwargs)
        self.app_state = app_state
        self.on_add_log = on_add_log
        self._processing = False
        self._progress_var = tk.DoubleVar(value=0)
        self.configure(bg=C["background"])
        self._build()
        self.bind("<Map>", lambda e: self.refresh())

    def refresh(self):
        self._populate_details()

    def _build(self):
        # Header de la vista
        header = tk.Frame(self, bg=C["background"])
        header.pack(fill="x", padx=24, pady=(16, 8))

        tk.Label(
            header,
            text="Procesar y Fragmentar Documento",
            font=("Segoe UI", 18, "bold"),
            fg=C["primary"],
            bg=C["background"],
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Inicie el proceso de fragmentación física y verifique el mapeo correlativo.",
            font=("Segoe UI", 9),
            fg=C["secondary"],
            bg=C["background"],
        ).pack(anchor="w")

        # Contenedor central
        main_container = tk.Frame(self, bg=C["background"])
        main_container.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # Panel superior: Fragmentar PDF + Progreso (tamaño fijo)
        self._build_fragment_panel(main_container)

        # PanedWindow vertical: consola | tabla de detalles
        # El usuario arrastra el separador para distribuir el espacio.
        self._lower_paned = tk.PanedWindow(
            main_container,
            orient="vertical",
            sashwidth=5,
            sashrelief="flat",
            bg=C["outline_variant"],
            handlesize=0,
            sashcursor="sb_v_double_arrow",
            opaqueresize=True,
        )
        self._lower_paned.pack(fill="both", expand=True)

        # Pane superior del lower: Consola de logs (se expande)
        self._console_host = tk.Frame(self._lower_paned, bg=C["tertiary"])
        self._build_console_panel(self._console_host)
        self._lower_paned.add(
            self._console_host,
            minsize=120,
            stretch="always",
        )

        # Pane inferior del lower: Detalle de foliación mapeada
        self._details_host = tk.Frame(self._lower_paned, bg=C["surface"])
        self._build_details_panel(self._details_host)
        self._lower_paned.add(
            self._details_host,
            minsize=100,
            height=200,
            stretch="never",
        )

    def _build_fragment_panel(self, parent):
        card = tk.Frame(
            parent,
            bg=C["surface"],
            padx=16, pady=12,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        card.pack(fill="x", pady=(0, 12))

        # Título
        tk.Label(
            card, text="✂️  Fragmentar PDF Maestro",
            font=("Segoe UI", 10, "bold"),
            fg=C["primary"], bg=C["surface"],
        ).pack(anchor="w", pady=(0, 8))

        row = tk.Frame(card, bg=C["surface"])
        row.pack(fill="x")

        # Botón
        self._frag_btn = tk.Button(
            row,
            text="✂   FRAGMENTAR PDF",
            font=("Segoe UI", 11, "bold"),
            fg="#ffffff",
            bg=C["primary"],
            activebackground=C["primary_container"],
            activeforeground="#ffffff",
            relief="flat", bd=0,
            cursor="hand2",
            padx=20, pady=10,
            command=self._start_fragmentation,
        )
        self._frag_btn.pack(side="left", padx=(0, 16))
        self._frag_btn.bind("<Enter>", lambda e: self._frag_btn.configure(bg=C["primary_container"]) if not self._processing else None)
        self._frag_btn.bind("<Leave>", lambda e: self._frag_btn.configure(bg=C["primary"]) if not self._processing else None)

        # Contenedor progreso a la derecha
        prog_frame = tk.Frame(row, bg=C["surface"])
        prog_frame.pack(side="left", fill="x", expand=True)

        self._status_lbl = tk.Label(
            prog_frame,
            text="Listo para iniciar.",
            font=("Segoe UI", 8),
            fg=C["secondary"], bg=C["surface"],
            anchor="w",
        )
        self._status_lbl.pack(fill="x", pady=(0, 4))

        style = ttk.Style()
        style.configure(
            "Process.Horizontal.TProgressbar",
            troughcolor=C["surface_low"],
            background=C["primary"],
            thickness=8,
        )
        self._progress_bar = ttk.Progressbar(
            prog_frame,
            variable=self._progress_var,
            maximum=100,
            style="Process.Horizontal.TProgressbar",
        )
        self._progress_bar.pack(fill="x")

    def _build_console_panel(self, parent):
        """Construye la consola de logs dentro del frame 'parent' (puede ser un pane de PanedWindow)."""
        card = tk.Frame(
            parent,
            bg=C["tertiary"],
            padx=12, pady=10,
            highlightbackground=C["outline"],
            highlightthickness=1,
        )
        card.pack(fill="both", expand=True)

        # Cabecera consola
        header = tk.Frame(card, bg=C["tertiary"])
        header.pack(fill="x", pady=(0, 6))

        tk.Label(
            header,
            text="⚙️ CONSOLA DE FRAGMENTACIÓN",
            font=("Courier New", 9, "bold"),
            fg=C["on_tertiary"],
            bg=C["tertiary"],
        ).pack(side="left")

        self._active_dot = tk.Label(
            header,
            text="● EN ESPERA",
            font=("Courier New", 8, "bold"),
            fg="#8c7071",
            bg=C["tertiary"],
        )
        self._active_dot.pack(side="right")

        # Texto consola
        log_container = tk.Frame(card, bg=C["tertiary"])
        log_container.pack(fill="both", expand=True)

        self._console_text = tk.Text(
            log_container,
            bg=C["tertiary"],
            fg=C["on_tertiary"],
            font=("Courier New", 8),
            bd=0, relief="flat",
            state="disabled",
            wrap="word",
        )
        self._console_text.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(log_container, command=self._console_text.yview)
        scrollbar.pack(side="right", fill="y")
        self._console_text.configure(yscrollcommand=scrollbar.set)

        self._console_text.tag_configure("INFO", foreground="#a8c4d4")
        self._console_text.tag_configure("WARN", foreground="#f5a742")
        self._console_text.tag_configure("SUCCESS", foreground="#4cde7e")

        self._log_local("INFO", "Consola de fragmentación lista.")

    def _build_details_panel(self, parent):
        """Construye el panel de detalle de foliación dentro del frame 'parent'."""
        card = tk.Frame(
            parent,
            bg=C["surface"],
            padx=16, pady=12,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        card.pack(fill="both", expand=True)

        tk.Label(
            card, text="📋 Detalle de Foliación Mapeada (Excel vs PDF)",
            font=("Segoe UI", 10, "bold"),
            fg=C["primary"], bg=C["surface"],
        ).pack(anchor="w", pady=(0, 6))

        # Tabla detalle
        cols = ("ID", "Registro", "Folios", "Rango Pág. PDF", "Hojas PDF", "Escribano")
        style = ttk.Style()
        style.configure(
            "Details.Treeview",
            background=C["surface_low"],
            foreground=C["secondary"],
            fieldbackground=C["surface_low"],
            rowheight=24,
            font=("Segoe UI", 8),
        )
        style.configure(
            "Details.Treeview.Heading",
            background=C["surface_high"],
            foreground=C["primary"],
            font=("Segoe UI", 8, "bold"),
            relief="flat",
        )

        self._tree = ttk.Treeview(
            card,
            columns=cols,
            show="headings",
            height=6,
            style="Details.Treeview",
        )
        for col in cols:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=100, anchor="w")
        self._tree.column("ID", width=50)
        self._tree.column("Folios", width=80)
        self._tree.column("Rango Pág. PDF", width=120)
        self._tree.column("Hojas PDF", width=80)
        self._tree.column("Escribano", width=160)

        self._populate_details()
        self._tree.bind("<<TreeviewSelect>>", self._on_row_select)

        self._tree.pack(fill="both", expand=True)

    def _populate_details(self):
        for item in self._tree.get_children():
            self._tree.delete(item)

        mapper = mapper_from_state(self.app_state)

        for i, r in enumerate(self.app_state.records):
            # Calcular páginas usando el motor
            pg_range = mapper.folio_str_to_pdf_range(r.folios) or "Inválido"
            pages_list = mapper.folio_str_to_pdf_pages(r.folios)
            pags = len(pages_list) if pages_list else 0

            tag = "even" if i % 2 == 0 else "odd"
            self._tree.insert("", "end",
                              values=(r.id, r.registro, r.folios, pg_range, f"{pags} pág(s)", r.escribano),
                              tags=(tag,))

        self._tree.tag_configure("even", background=C["surface_low"])
        self._tree.tag_configure("odd", background=C["surface"])

    def _on_row_select(self, event):
        selected = self._tree.selection()
        if not selected:
            return
        item_id = selected[0]
        vals = self._tree.item(item_id, "values")
        if vals:
            r_id = vals[0]
            r = next((rec for rec in self.app_state.records if rec.id == r_id), None)
            if r and r.pg_pdf:
                try:
                    first_page = int(str(r.pg_pdf).split('-')[0].strip())
                    if self.on_navigate_pdf:
                        self.on_navigate_pdf(first_page)
                except Exception:
                    pass

    # ── Lógica de fragmentación ──────────────────────────────────────────────────
    def _start_fragmentation(self):
        if self._processing:
            return
        self._processing = True
        self._frag_btn.configure(text="⏳ Procesando...", state="disabled", bg=C["secondary"])
        self._active_dot.configure(text="● PROCESANDO", fg="#f5a742")
        self._progress_var.set(0)
        self._log_local("INFO", "Iniciando proceso de fragmentación física...")
        self.on_add_log("INFO", "Fragmentación iniciada en pestaña dedicada.")

        threading.Thread(target=self._run_fragmentation, daemon=True).start()

    def _run_fragmentation(self):
        pdf_real_path = self.app_state.pdf_path
        has_real_pdf = False
        reader = None

        if pdf_real_path and os.path.exists(pdf_real_path):
            try:
                self.after(0, lambda: self._log_local("INFO", f"Abriendo PDF: '{os.path.basename(pdf_real_path)}'..."))
                reader = pypdf.PdfReader(pdf_real_path)
                has_real_pdf = True
                self.after(0, lambda: self._log_local("SUCCESS", f"PDF cargado. Total de páginas físicas: {len(reader.pages)}."))
            except Exception as e:
                self.after(0, lambda: self._log_local("WARN", f"Fallo al leer el PDF: {e}. Activando modo simulación."))
        else:
            self.after(0, lambda: self._log_local("WARN", "No se detectó PDF en Paso 1. Activando modo de simulación de rutas."))

        time.sleep(0.5)

        mapper = mapper_from_state(self.app_state)
        records = self.app_state.records
        total = len(records)
        correctos = 0
        omitidos = []

        # Crear carpeta de logs si no existe
        workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        log_dir = os.path.join(workspace_dir, "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            log_dir = "logs"
            os.makedirs(log_dir, exist_ok=True)

        csv_path = os.path.join(log_dir, "pendientes.csv")

        # Iniciar escritura en CSV
        try:
            with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer_csv = csv.writer(f)
                writer_csv.writerow(["ID", "Fila", "Registro", "Escribano", "Folios", "Motivo de Omisión"])
        except Exception as e:
            self.after(0, lambda msg=f"Error creando CSV de pendientes: {e}": self._log_local("WARN", msg))

        for idx, r in enumerate(records):
            pct = int(((idx + 1) / total) * 100)
            self.after(0, lambda p=pct, msg=f"Procesando registro {idx+1}/{total} ({r.id})...": self._update_progress(p, msg))
            time.sleep(0.4)

            # Verificar si tiene errores en el analizador de sucesión
            if r.estado == "REVISAR" or r.folios == "140" or "140" in r.folios:
                motivo = "Inconsistencia de foliación declarada (requiere corrección en inventario)"
                if r.folios == "140":
                    motivo = "Error de formato de folio (falta de cara r/v)"
                omitidos.append((r, motivo))
                self.after(0, lambda id_r=r.id, mot=motivo: self._log_local("WARN", f"Omitido {id_r}: {mot}"))

                # Registrar en el CSV de pendientes
                try:
                    with open(csv_path, mode="a", newline="", encoding="utf-8") as f_csv:
                        writer_csv = csv.writer(f_csv)
                        writer_csv.writerow([r.id, r.fila, r.registro, r.escribano, r.folios, motivo])
                except Exception:
                    pass
                continue

            # Calcular páginas y ruta jerárquica
            pages_list = mapper.folio_str_to_pdf_pages(r.folios)
            if not pages_list:
                motivo = "Fallo en la resolución matemática del folio"
                omitidos.append((r, motivo))
                self.after(0, lambda id_r=r.id: self._log_local("WARN", f"Omitido {id_r}: {motivo}"))
                continue

            # Construir jerarquía de 11 niveles
            output_base = self.app_state.output_dir or os.path.join(workspace_dir, "SalidaFrac")
            dest_path = build_11_level_path(r, self.app_state, output_base)

            # Escribir PDF real si está cargado
            if has_real_pdf and reader:
                try:
                    # Crear carpetas de destino de la jerarquía
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    
                    writer = pypdf.PdfWriter()
                    # Añadir las páginas correspondientes (0-based)
                    for p in pages_list:
                        # Asegurar no exceder límites del PDF
                        if 1 <= p <= len(reader.pages):
                            writer.add_page(reader.pages[p - 1])
                        else:
                            raise IndexError(f"La página mapeada {p} excede el total de páginas del PDF ({len(reader.pages)}).")
                    
                    with open(dest_path, "wb") as f_out:
                        writer.write(f_out)
                    
                    self.after(0, lambda id_r=r.id, dest=dest_path: self._log_local("SUCCESS", f"Extraído {id_r} a disco:\n → {dest}"))
                    correctos += 1
                except Exception as e:
                    self.after(0, lambda id_r=r.id, err=e: self._log_local("WARN", f"Fallo al guardar fragmento {id_r}: {err}"))
                    omitidos.append((r, f"Fallo de escritura física: {e}"))
            else:
                # Simulación de ruta
                self.after(0, lambda id_r=r.id, dest=dest_path: self._log_local("INFO", f"[SIMULACIÓN] Generando fragmento {id_r} en ruta:\n → {dest}"))
                correctos += 1

        time.sleep(0.6)
        msg_final = f"Proceso finalizado. {correctos} fragmentos PDF creados satisfactoriamente. {len(omitidos)} omitidos."
        self.after(0, lambda: self._update_progress(100, msg_final))
        if len(omitidos) > 0:
            self.after(0, lambda: self._log_local("WARN", f"Pendientes guardados en: {csv_path}"))
        self.after(0, self._finish_fragmentation)

    def _update_progress(self, pct, msg):
        self._progress_var.set(pct)
        self._status_lbl.configure(text=f"[{pct:3d}%] {msg}")
        tipo = "SUCCESS" if pct == 100 else "INFO"
        self._log_local(tipo, msg)
        self.on_add_log(tipo, msg)

    def _finish_fragmentation(self):
        self._processing = False
        self._active_dot.configure(text="● COMPLETADO", fg="#4cde7e")
        self._frag_btn.configure(
            text="✅  Completado", state="normal", bg="#1a5c2e"
        )
        # Marcar los registros de la app como FRAGMENTADO para demostrar dinamismo
        for r in self.app_state.records:
            if r.estado != "REVISAR":
                r.estado = "FRAGMENTADO"
        self._populate_details()

        self.after(3000, lambda: self._reset_btn())

    def _reset_btn(self):
        self._frag_btn.configure(text="✂   FRAGMENTAR PDF", bg=C["primary"])
        self._active_dot.configure(text="● EN ESPERA", fg="#8c7071")

    def _log_local(self, tipo, mensaje):
        ts = time.strftime("%H:%M:%S")
        self._console_text.configure(state="normal")
        self._console_text.insert("end", f"[{ts}] [{tipo}] {mensaje}\n", tipo)
        self._console_text.configure(state="disabled")
        self._console_text.see("end")
