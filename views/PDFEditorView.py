"""
PDFEditorView.py — Pantalla 5: Editor de PDF.
Reordenar y eliminar páginas del PDF con vista previa de thumbnails.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os

from utils.theme import C, FONT

try:
    import fitz
    from PIL import Image, ImageTk
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False


class PDFEditorView(tk.Frame):
    """Vista de edición de páginas PDF: reordenar, eliminar, guardar copia."""

    THUMB_WIDTH = 140
    MIN_THUMB_WIDTH = 120
    PADDING = 8

    def __init__(self, parent, app_state, on_add_log, **kwargs):
        self.on_navigate_pdf = kwargs.pop("on_navigate_pdf", None)
        self.on_navigate = kwargs.pop("on_navigate", None)
        self.on_load_pdf = kwargs.pop("on_load_pdf", None)
        super().__init__(parent, **kwargs)
        self.app_state = app_state
        self.on_add_log = on_add_log
        self._fitz_doc = None
        self._page_order = []
        self._selected_pages = set()
        self._thumb_photos = []
        self._thumb_cells = []
        self._modified = False
        self.configure(bg=C["background"])
        self._build()
        self.bind("<Map>", lambda e: self.refresh())

    def refresh(self):
        if self.app_state.pdf_path and self.app_state.pdf_path != getattr(self, "_loaded_path", None):
            self._load_pdf(self.app_state.pdf_path)

    # ── Construcción ────────────────────────────────────────────────────────────
    def _build(self):
        # Header
        header = tk.Frame(self, bg=C["background"])
        header.pack(fill="x", padx=24, pady=(16, 8))

        tk.Label(
            header, text="Editor de PDF",
            font=("Segoe UI", 18, "bold"),
            fg=C["primary"], bg=C["background"],
        ).pack(side="left")

        self._file_label = tk.Label(
            header, text="No hay PDF cargado",
            font=("Segoe UI", 9),
            fg=C["secondary"], bg=C["background"],
        )
        self._file_label.pack(side="left", padx=(16, 0), anchor="s", pady=(0, 3))

        self._modified_label = tk.Label(
            header, text="",
            font=("Segoe UI", 9, "bold"),
            fg="#b45309", bg=C["background"],
        )
        self._modified_label.pack(side="right")

        # Toolbar
        toolbar = tk.Frame(self, bg=C["surface_container"], pady=6)
        toolbar.pack(fill="x", padx=24, pady=(0, 8))
        tk.Frame(toolbar, bg=C["outline_variant"], height=1).pack(side="bottom", fill="x")

        self._status_label = tk.Label(
            toolbar,
            text="Seleccione un PDF para comenzar",
            font=("Segoe UI", 9),
            fg=C["secondary"], bg=C["surface_container"],
        )
        self._status_label.pack(side="left", padx=8)

        btn_style = dict(
            font=("Segoe UI", 8, "bold"), relief="flat", bd=0,
            cursor="hand2", padx=10, pady=5,
        )

        self._btn_move_up = tk.Button(
            toolbar, text="⬆ Mover Arriba", fg="#ffffff", bg="#1e3a5f",
            activebackground="#112233", state="disabled",
            command=lambda: self._move_page(-1), **btn_style,
        )
        self._btn_move_up.pack(side="right", padx=4)

        self._btn_move_down = tk.Button(
            toolbar, text="⬇ Mover Abajo", fg="#ffffff", bg="#1e3a5f",
            activebackground="#112233", state="disabled",
            command=lambda: self._move_page(1), **btn_style,
        )
        self._btn_move_down.pack(side="right", padx=4)

        self._btn_delete = tk.Button(
            toolbar, text="✕ Eliminar", fg="#ffffff", bg="#b91c1c",
            activebackground="#991b1b", state="disabled",
            command=self._delete_pages, **btn_style,
        )
        self._btn_delete.pack(side="right", padx=4)

        self._btn_save = tk.Button(
            toolbar, text="💾 Guardar Copia", fg="#ffffff", bg="#1a5c2e",
            activebackground="#14532d", state="disabled",
            command=self._save_copy, **btn_style,
        )
        self._btn_save.pack(side="right", padx=4)

        self._btn_reset = tk.Button(
            toolbar, text="↩ Restablecer", fg=C["secondary"],
            bg=C["surface_low"], activebackground=C["secondary_container"],
            state="disabled", command=self._reset_order, **btn_style,
        )
        self._btn_reset.pack(side="right", padx=4)

        self._btn_load = tk.Button(
            toolbar, text="📂 Cargar PDF", fg="#ffffff", bg=C["primary"],
            activebackground=C["primary_container"],
            command=self._ask_load_pdf, **btn_style,
        )
        self._btn_load.pack(side="right", padx=4)

        if self.on_navigate:
            tk.Button(
                toolbar, text="← Volver", fg=C["secondary"],
                bg=C["surface_low"], activebackground=C["secondary_container"],
                command=lambda: self.on_navigate("workspace"), **btn_style,
            ).pack(side="left", padx=4)

        # Grid de thumbnails con scroll
        grid_host = tk.Frame(self, bg=C["background"])
        grid_host.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._canvas = tk.Canvas(grid_host, bg=C["background"], bd=0, highlightthickness=0)
        self._vsb = tk.Scrollbar(grid_host, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._vsb.set)
        self._vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._grid_frame = tk.Frame(self._canvas, bg=C["background"])
        self._canvas_window = self._canvas.create_window((0, 0), window=self._grid_frame, anchor="nw")

        self._grid_frame.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            self._canvas_window, width=e.width))

        # Mousewheel
        def _on_mousewheel(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._canvas.bind("<MouseWheel>", _on_mousewheel)
        self._grid_frame.bind("<MouseWheel>", _on_mousewheel)

        # Re-render grid on resize for responsive columns
        self._last_cols = 0
        def _on_canvas_resize(event):
            if not self._fitz_doc:
                return
            cell_w = self.THUMB_WIDTH + self.PADDING * 2
            new_cols = max(1, event.width // cell_w)
            if new_cols != self._last_cols:
                self._last_cols = new_cols
                self._render_thumbnails()
        self._canvas.bind("<Configure>", _on_canvas_resize)

        # Estado inicial vacío
        self._draw_placeholder()

    def _draw_placeholder(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()
        ph = tk.Frame(self._grid_frame, bg=C["surface_low"])
        ph.place(relx=0.5, rely=0.4, anchor="center")
        tk.Label(
            ph, text="📄",
            font=("Segoe UI", 48), fg=C["outline"], bg=C["surface_low"],
        ).pack(pady=(0, 8))
        tk.Label(
            ph, text="Cargue un PDF para editar sus páginas",
            font=("Segoe UI", 12), fg=C["secondary"], bg=C["surface_low"],
        ).pack()
        tk.Label(
            ph, text="Use el botón 'Cargar PDF' o cargue desde la pestaña Archivo",
            font=("Segoe UI", 9), fg=C["outline"], bg=C["surface_low"],
        ).pack(pady=(4, 0))

    # ── Carga y renderizado ─────────────────────────────────────────────────────
    def _ask_load_pdf(self):
        path = filedialog.askopenfilename(
            title="Seleccionar PDF",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")],
            initialdir=os.path.dirname(self.app_state.pdf_path or ""),
        )
        if path:
            self._load_pdf(path)

    def _load_pdf(self, path):
        if not path or not os.path.exists(path):
            return
        if not PYMUPDF_OK:
            messagebox.showerror("Error", "PyMuPDF no está instalado.\nInstale con: pip install PyMuPDF")
            return

        try:
            if self._fitz_doc:
                self._fitz_doc.close()
            self._fitz_doc = fitz.open(path)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el PDF:\n{e}")
            return

        self._loaded_path = path
        self.app_state.pdf_path = path
        if not self.app_state.pdf_original_path:
            self.app_state.pdf_original_path = path

        total = len(self._fitz_doc)
        self.app_state.pdf_total_pages = total

        self._page_order = list(range(total))
        self._selected_pages = set()
        self._modified = False
        self.app_state.page_map = {}

        basename = os.path.basename(path)
        self._file_label.configure(text=basename)
        self._modified_label.configure(text="")
        self._update_status()
        self._update_buttons()

        self.on_add_log("INFO", f"PDF cargado en editor: {basename} ({total} páginas)")
        self._render_thumbnails()

    def _render_thumbnails(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()
        self._thumb_photos = []
        self._thumb_cells = []

        if not self._fitz_doc:
            self._draw_placeholder()
            return

        # Calcular columnas según ancho disponible
        available_w = self._canvas.winfo_width()
        if available_w < 10:
            available_w = 700
        cell_w = self.THUMB_WIDTH + self.PADDING * 2
        cols = max(1, available_w // cell_w)

        for idx, orig_idx in enumerate(self._page_order):
            row = idx // cols
            col = idx % cols

            cell = self._create_thumb_cell(idx, orig_idx)
            cell.grid(row=row, column=col, padx=self.PADDING, pady=self.PADDING, sticky="n")
            self._thumb_cells.append(cell)

    def _create_thumb_cell(self, display_idx, orig_idx):
        page_num = orig_idx + 1
        is_selected = orig_idx in self._selected_pages

        border_color = C["primary"] if is_selected else C["outline_variant"]
        border_w = 2 if is_selected else 1

        outer = tk.Frame(self._grid_frame, bg=border_color, padx=border_w, pady=border_w)

        inner = tk.Frame(outer, bg=C["surface"])
        inner.pack(fill="both", expand=True)

        # Thumbnail image
        try:
            page = self._fitz_doc[orig_idx]
            rect = page.rect
            zoom = self.THUMB_WIDTH / rect.width
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            photo = ImageTk.PhotoImage(img)
            self._thumb_photos.append(photo)

            img_lbl = tk.Label(inner, image=photo, bg=C["surface"], cursor="hand2")
            img_lbl.pack(padx=4, pady=(4, 2))
        except Exception:
            img_lbl = tk.Label(
                inner, text="[Error]", font=("Segoe UI", 8),
                fg="#7f1d1d", bg=C["surface_low"], cursor="hand2",
            )
            img_lbl.pack(padx=4, pady=(4, 2), ipadx=20, ipady=30)

        # Page number label
        sel_text = " ●" if is_selected else ""
        lbl = tk.Label(
            inner,
            text=f"Pág. {page_num}{sel_text}",
            font=("Segoe UI", 8, "bold") if is_selected else ("Segoe UI", 8),
            fg=C["primary"] if is_selected else C["secondary"],
            bg=C["surface"],
        )
        lbl.pack(pady=(0, 4))

        # Position label
        pos_lbl = tk.Label(
            inner,
            text=f"Pos: {display_idx + 1}",
            font=("Segoe UI", 7),
            fg=C["outline"], bg=C["surface"],
        )
        pos_lbl.pack()

        # Click handler
        def on_click(e, oi=orig_idx):
            self._toggle_select(oi)

        for w in (outer, inner, img_lbl, lbl, pos_lbl):
            w.bind("<Button-1>", on_click)

        return outer

    def _toggle_select(self, orig_idx):
        if orig_idx in self._selected_pages:
            self._selected_pages.discard(orig_idx)
        else:
            self._selected_pages.add(orig_idx)
        self._update_status()
        self._update_buttons()
        self._render_thumbnails()

    # ── Operaciones ─────────────────────────────────────────────────────────────
    def _move_page(self, direction):
        if not self._selected_pages or len(self._selected_pages) != 1:
            return
        sel = next(iter(self._selected_pages))
        current_pos = self._page_order.index(sel)
        new_pos = current_pos + direction

        if new_pos < 0 or new_pos >= len(self._page_order):
            return

        self._page_order[current_pos], self._page_order[new_pos] = (
            self._page_order[new_pos], self._page_order[current_pos]
        )
        self._modified = True
        self._update_status()
        self._update_buttons()
        self._render_thumbnails()
        self.on_add_log("INFO", f"Página {sel + 1} movida a posición {new_pos + 1}")

    def _delete_pages(self):
        if not self._selected_pages:
            return
        count = len(self._selected_pages)
        pages_str = ", ".join(str(p + 1) for p in sorted(self._selected_pages))

        if not messagebox.askyesno(
            "Eliminar páginas",
            f"¿Eliminar {count} página(s) del PDF?\nPáginas: {pages_str}\n\n"
            "Se creará una copia modificada al guardar.",
        ):
            return

        for p in self._selected_pages:
            if p in self._page_order:
                self._page_order.remove(p)

        self._selected_pages.clear()
        self._modified = True
        self._update_status()
        self._update_buttons()
        self._render_thumbnails()
        self.on_add_log("WARN", f"{count} página(s) eliminadas: {pages_str}")

    def _reset_order(self):
        if not self._fitz_doc:
            return
        self._page_order = list(range(len(self._fitz_doc)))
        self._selected_pages.clear()
        self._modified = False
        self.app_state.page_map = {}
        self._update_status()
        self._update_buttons()
        self._render_thumbnails()
        self._modified_label.configure(text="")
        self.on_add_log("INFO", "Orden de páginas restablecido al original. Page map limpiado.")
        # Restaurar la vista previa al PDF original si existe
        if self.on_load_pdf and self.app_state.pdf_original_path:
            self.app_state.pdf_path = self.app_state.pdf_original_path
            self.on_load_pdf(self.app_state.pdf_original_path)

    def _save_copy(self):
        if not self._fitz_doc or not self._modified:
            return

        path = filedialog.asksaveasfilename(
            title="Guardar Copia del PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="pdf_modificado.pdf",
            initialdir=os.path.dirname(self._loaded_path or ""),
        )
        if not path:
            return

        try:
            new_doc = fitz.open()
            for orig_idx in self._page_order:
                new_doc.insert_pdf(self._fitz_doc, from_page=orig_idx, to_page=orig_idx)
            new_doc.save(path, garbage=4, deflate=True)
            new_doc.close()

            # Construir page_map: {original_page: new_page}
            original_total = len(self._fitz_doc)
            page_map = {}
            for new_pos, orig_idx in enumerate(self._page_order):
                page_map[orig_idx + 1] = new_pos + 1

            # Actualizar AppState
            if not self.app_state.pdf_original_path:
                self.app_state.pdf_original_path = self.app_state.pdf_path
            self.app_state.pdf_path = path
            self.app_state.pdf_total_pages = len(self._page_order)
            self.app_state.page_map = page_map

            # Recalcular pg_pdf para todos los registros
            from utils.folio_engine import mapper_from_state
            mapper = mapper_from_state(self.app_state)
            updated_count = 0
            for rec in self.app_state.records:
                pg_range = mapper.folio_str_to_pdf_range(rec.folios)
                if pg_range:
                    rec.pg_pdf = pg_range
                    updated_count += 1

            self.on_add_log("SUCCESS", f"Copia guardada: {os.path.basename(path)} ({len(self._page_order)} páginas)")
            self.on_add_log("INFO", f"Page map actualizado. {updated_count} registros recalculados.")

            # Recargar el PDF modificado en el editor
            self._fitz_doc.close()
            self._fitz_doc = fitz.open(path)
            self._loaded_path = path
            self._page_order = list(range(len(self._fitz_doc)))
            self._selected_pages.clear()
            self._modified = False
            self._modified_label.configure(text="")

            self._file_label.configure(text=os.path.basename(path))
            self._update_status()
            self._update_buttons()
            self._render_thumbnails()

            # Actualizar la vista previa del PDF en el panel derecho
            if self.on_load_pdf:
                self.on_load_pdf(path)

            result = messagebox.askyesno(
                "PDF Guardado",
                f"Copia modificada guardada exitosamente:\n{path}\n\n"
                f"Total de páginas: {len(self._page_order)}\n"
                f"Registros actualizados: {updated_count}\n\n"
                f"¿Desea volver a la vista anterior?"
            )
            if result and self.on_navigate:
                self.on_navigate("analyzer")

        except Exception as e:
            self.on_add_log("ERR", f"Error al guardar PDF: {e}")
            messagebox.showerror("Error", f"Error al guardar el PDF:\n{e}")

    # ── UI helpers ──────────────────────────────────────────────────────────────
    def _update_status(self):
        total = len(self._page_order) if self._page_order else 0
        sel = len(self._selected_pages)
        mod = " ● Modificado" if self._modified else ""
        self._status_label.configure(
            text=f"{total} páginas | {sel} seleccionada(s){mod}"
        )
        if self._modified:
            self._modified_label.configure(text="● Sin guardar")
        else:
            self._modified_label.configure(text="")

    def _update_buttons(self):
        has_sel = len(self._selected_pages) > 0
        single_sel = len(self._selected_pages) == 1
        state_normal = "normal" if has_sel else "disabled"
        state_single = "normal" if single_sel else "disabled"
        state_mod = "normal" if self._modified else "disabled"

        self._btn_move_up.configure(state=state_single)
        self._btn_move_down.configure(state=state_single)
        self._btn_delete.configure(state=state_normal)
        self._btn_save.configure(state=state_mod)
        self._btn_reset.configure(state=state_mod if self._fitz_doc else "disabled")
