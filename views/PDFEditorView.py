"""
PDFEditorView.py — Pantalla 5: Configuración de Paginación del PDF.
Permite reordenar, excluir y configurar el mapeo de páginas del PDF original
para la fragmentación. NO edita el PDF original; solo guarda la configuración
de mapeo que será usada por el motor de fragmentación.
"""
import tkinter as tk
from tkinter import messagebox
import os

from utils.theme import C

try:
    import fitz
    from PIL import Image, ImageTk
    PYMUPDF_OK = True
except ImportError:
    PYMUPDF_OK = False


# ── Constantes de layout ────────────────────────────────────────────────────
THUMB_W  = 130
THUMB_H  = 184
CELL_W   = THUMB_W + 16
CELL_H   = THUMB_H + 36
PAD      = 8
BUF_ROWS = 2


class PDFEditorView(tk.Frame):
    """Vista de configuración de paginación PDF con renderizado virtualizado."""

    def __init__(self, parent, app_state, on_add_log, **kwargs):
        self.on_navigate_pdf = kwargs.pop("on_navigate_pdf", None)
        self.on_navigate     = kwargs.pop("on_navigate", None)
        self.on_config_saved = kwargs.pop("on_config_saved", None)
        kwargs.pop("on_load_pdf", None)
        super().__init__(parent, **kwargs)

        self.app_state  = app_state
        self.on_add_log = on_add_log
        self.configure(bg=C["background"])

        self._fitz_doc       = None
        self._loaded_path    = None
        self._page_order     = []
        self._selected_pages = set()
        self._modified       = False

        self._rendered_photos: dict = {}
        self._rendered_items: dict  = {}

        self._cols       = 1
        self._total_rows = 0
        self._last_range = None
        self._last_width = -1
        self._pending_job = None

        self._undo_stack = []
        self._redo_stack = []

        self._build()
        self.bind("<Map>", lambda e: self.refresh())

    def refresh(self):
        if self.app_state.pdf_path:
            if not self._fitz_doc or self.app_state.pdf_path != self._loaded_path:
                self._load_pdf(self.app_state.pdf_path)
        else:
            self._clear_doc()

    def _clear_doc(self):
        if self._fitz_doc:
            try:
                self._fitz_doc.close()
            except Exception:
                pass
        self._fitz_doc       = None
        self._loaded_path    = None
        self._page_order     = []
        self._selected_pages.clear()
        self._modified       = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._rendered_photos.clear()
        self._rendered_items.clear()
        self._last_range  = None
        self._canvas.delete("all")
        self._draw_placeholder()
        self._file_label.configure(text="No hay PDF cargado")
        self._modified_label.configure(text="")
        self._update_status()
        self._update_buttons()

    def _build(self):
        header = tk.Frame(self, bg=C["background"])
        header.pack(fill="x", padx=24, pady=(16, 8))

        tk.Label(header, text="Configuración de Paginación",
                 font=("Segoe UI", 18, "bold"),
                 fg=C["primary"], bg=C["background"]).pack(side="left")

        self._file_label = tk.Label(header, text="No hay PDF cargado",
                                    font=("Segoe UI", 9),
                                    fg=C["secondary"], bg=C["background"])
        self._file_label.pack(side="left", padx=(16, 0), anchor="s", pady=(0, 3))

        self._modified_label = tk.Label(header, text="",
                                        font=("Segoe UI", 9, "bold"),
                                        fg="#b45309", bg=C["background"])
        self._modified_label.pack(side="right")

        toolbar = tk.Frame(self, bg=C["surface_container"], pady=6)
        toolbar.pack(fill="x", padx=24, pady=(0, 8))
        tk.Frame(toolbar, bg=C["outline_variant"], height=1).pack(side="bottom", fill="x")

        self._status_label = tk.Label(toolbar, text="Cargando PDF...",
                                      font=("Segoe UI", 9),
                                      fg=C["secondary"], bg=C["surface_container"])
        self._status_label.pack(side="left", padx=8)

        bs = dict(font=("Segoe UI", 8, "bold"), relief="flat", bd=0,
                  cursor="hand2", padx=10, pady=5)

        self._btn_move_up = tk.Button(
            toolbar, text="\u2b06 Mover Arriba", fg="#fff", bg="#1e3a5f",
            activebackground="#112233", state="disabled",
            command=lambda: self._move_page(-1), **bs)
        self._btn_move_up.pack(side="right", padx=4)

        self._btn_move_down = tk.Button(
            toolbar, text="\u2b07 Mover Abajo", fg="#fff", bg="#1e3a5f",
            activebackground="#112233", state="disabled",
            command=lambda: self._move_page(1), **bs)
        self._btn_move_down.pack(side="right", padx=4)

        self._btn_delete = tk.Button(
            toolbar, text="\u2715 Eliminar", fg="#fff", bg="#b91c1c",
            activebackground="#991b1b", state="disabled",
            command=self._delete_pages, **bs)
        self._btn_delete.pack(side="right", padx=4)

        self._btn_save = tk.Button(
            toolbar, text="\U0001f4be Guardar Configuración", fg="#fff", bg="#1a5c2e",
            activebackground="#14532d", state="disabled",
            command=self._save_config, **bs)
        self._btn_save.pack(side="right", padx=4)

        self._btn_undo = tk.Button(
            toolbar, text="\u21a9 Deshacer", fg=C["secondary"],
            bg=C["surface_low"], activebackground=C["secondary_container"],
            state="disabled", command=self._undo, **bs)
        self._btn_undo.pack(side="right", padx=4)

        if self.on_navigate:
            tk.Button(toolbar, text="\u2190 Volver", fg=C["secondary"],
                      bg=C["surface_low"], activebackground=C["secondary_container"],
                      command=lambda: self.on_navigate("workspace"), **bs).pack(side="left", padx=4)

        host = tk.Frame(self, bg=C["background"])
        host.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._scrollbar = tk.Scrollbar(host, orient="vertical")
        self._scrollbar.pack(side="right", fill="y")

        self._canvas = tk.Canvas(host, bg=C["surface_low"], bd=0, highlightthickness=0)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas.configure(yscrollcommand=self._on_scrollbar_update)
        self._scrollbar.configure(command=self._canvas.yview)

        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind("<MouseWheel>", lambda e: self._canvas.yview_scroll(
            int(-1 * (e.delta / 120)), "units"))

        self.after(100, self._draw_placeholder)

    def _draw_placeholder(self):
        self._canvas.delete("parchment")
        w = self._canvas.winfo_width()
        h = self._canvas.winfo_height()
        if w < 10 or h < 10:
            return
        tag = "parchment"
        cx, cy = w // 2, h // 2
        self._canvas.configure(scrollregion=(0, 0, w, h))
        self._canvas.create_rectangle(4, 4, w - 4, h - 4,
                                       fill=C["surface_container"],
                                       outline=C["outline_variant"], width=1, tags=tag)
        self._canvas.create_text(cx, cy - 30, text="\U0001f4c4",
                                  font=("Segoe UI", 48), fill=C["outline"], tags=tag)
        if self.app_state.pdf_path:
            self._canvas.create_text(cx, cy + 30,
                                      text="El PDF se carga autom\u00e1ticamente desde Archivo",
                                      font=("Segoe UI", 10), fill=C["secondary"], tags=tag)
        else:
            self._canvas.create_text(cx, cy + 30,
                                      text="Cargue un PDF en la pesta\u00f1a Archivo (Paso 1)",
                                      font=("Segoe UI", 10), fill=C["secondary"], tags=tag)

    def _on_scrollbar_update(self, first, last):
        self._scrollbar.set(first, last)
        if self._fitz_doc and PYMUPDF_OK:
            self._schedule_render()

    def _on_canvas_resize(self, event=None):
        w = event.width if event else self._canvas.winfo_width()
        if w < 10:
            return
        if w != self._last_width:
            self._last_width = w
            if self._fitz_doc and PYMUPDF_OK:
                self._recalculate_layout()
            else:
                self._draw_placeholder()

    def _recalculate_layout(self):
        if not self._fitz_doc:
            return
        w = self._canvas.winfo_width()
        if w < 10:
            w = 700

        self._cols = max(1, w // (CELL_W + PAD))
        self._total_rows = (len(self._page_order) + self._cols - 1) // self._cols

        total_h = PAD + self._total_rows * (CELL_H + PAD)
        self._canvas.configure(scrollregion=(0, 0, w, total_h))

        self._canvas.delete("all")
        self._rendered_items.clear()
        self._last_range = None
        self._schedule_render()

    def _cell_xy(self, row: int, col: int) -> tuple:
        w = self._canvas.winfo_width()
        grid_w = self._cols * (CELL_W + PAD) - PAD
        x_off  = max(PAD, (w - grid_w) // 2)
        x = x_off + col * (CELL_W + PAD)
        y = PAD   + row * (CELL_H + PAD)
        return x, y

    def _schedule_render(self):
        if self._pending_job:
            self.after_cancel(self._pending_job)
        self._pending_job = self.after(16, self._do_render)

    def _do_render(self):
        self._pending_job = None
        if not self._fitz_doc or not PYMUPDF_OK or not self._page_order:
            return

        try:
            first_str, last_str = self._scrollbar.get()
            first = float(first_str) if first_str else 0.0
            last  = float(last_str)  if last_str  else 1.0
        except Exception:
            first, last = 0.0, 1.0

        total_h = PAD + self._total_rows * (CELL_H + PAD)
        if total_h <= 0:
            return

        view_top    = first * total_h
        view_bottom = last  * total_h

        row_first = max(0, int(view_top    / (CELL_H + PAD)) - BUF_ROWS)
        row_last  = min(self._total_rows - 1,
                        int(view_bottom / (CELL_H + PAD)) + BUF_ROWS)

        new_range = (row_first, row_last)
        if new_range == self._last_range:
            return
        self._last_range = new_range

        for (r, c) in list(self._rendered_items.keys()):
            if r < row_first or r > row_last:
                for item_id in self._rendered_items.pop((r, c)):
                    self._canvas.delete(item_id)

        for row in range(row_first, row_last + 1):
            for col in range(self._cols):
                page_pos = row * self._cols + col
                if page_pos >= len(self._page_order):
                    break
                if (row, col) not in self._rendered_items:
                    self._paint_cell(row, col, page_pos)

    def _paint_cell(self, row: int, col: int, page_pos: int):
        orig_idx = self._page_order[page_pos]
        page_num = orig_idx + 1
        is_sel   = orig_idx in self._selected_pages

        x, y = self._cell_xy(row, col)

        fill_bg   = C["secondary_container"] if is_sel else C["surface"]
        outline_c = C["primary"]             if is_sel else C["outline_variant"]
        bw        = 2 if is_sel else 1

        rect_id = self._canvas.create_rectangle(
            x, y, x + CELL_W, y + CELL_H,
            fill=fill_bg, outline=outline_c, width=bw)

        if orig_idx in self._rendered_photos:
            photo = self._rendered_photos[orig_idx]
        else:
            try:
                page = self._fitz_doc[orig_idx]
                zoom = THUMB_W / page.rect.width
                mat  = fitz.Matrix(zoom, zoom)
                pix  = page.get_pixmap(matrix=mat, alpha=False)
                img  = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                if img.height > THUMB_H:
                    img = img.crop((0, 0, img.width, THUMB_H))
                photo = ImageTk.PhotoImage(img)
                self._rendered_photos[orig_idx] = photo
            except Exception:
                photo = None

        if photo:
            img_id = self._canvas.create_image(
                x + CELL_W // 2, y + 4, anchor="n", image=photo)
        else:
            img_id = self._canvas.create_rectangle(
                x + 4, y + 4, x + CELL_W - 4, y + 4 + THUMB_H,
                fill=C["surface_highest"], outline=C["outline_variant"])
            self._canvas.create_text(
                x + CELL_W // 2, y + 4 + THUMB_H // 2,
                text=str(page_num), font=("Segoe UI", 14), fill=C["outline"])

        sel_mark  = " \u25cf" if is_sel else ""
        lbl_color = C["primary"] if is_sel else C["secondary"]
        lbl_font  = ("Segoe UI", 8, "bold") if is_sel else ("Segoe UI", 8)

        lbl_id = self._canvas.create_text(
            x + CELL_W // 2, y + CELL_H - 20,
            text=f"P\u00e1g. {page_num}{sel_mark}",
            font=lbl_font, fill=lbl_color)
        pos_id = self._canvas.create_text(
            x + CELL_W // 2, y + CELL_H - 6,
            text=f"Pos: {page_pos + 1}",
            font=("Segoe UI", 7), fill=C["outline"])

        ids = (rect_id, img_id, lbl_id, pos_id)
        self._rendered_items[(row, col)] = ids

        for item_id in ids:
            self._canvas.tag_bind(
                item_id, "<Button-1>",
                lambda e, oi=orig_idx: self._toggle_select(oi))

    def _load_pdf(self, path: str):
        if not path or not os.path.exists(path):
            return
        if not PYMUPDF_OK:
            messagebox.showerror("Error", "PyMuPDF no est\u00e1 instalado.\npip install PyMuPDF")
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
        self._selected_pages.clear()
        self._modified = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._rendered_photos.clear()
        self._rendered_items.clear()
        self._last_range = None
        self._last_width = -1
        self.app_state.page_map = {}

        self._file_label.configure(text=os.path.basename(path))
        self._modified_label.configure(text="")
        self._update_status()
        self._update_buttons()
        self.on_add_log("INFO", f"PDF cargado: {os.path.basename(path)} ({total} p\u00e1ginas)")

        self._canvas.delete("parchment")
        self.update_idletasks()
        self._recalculate_layout()

    def _toggle_select(self, orig_idx: int):
        if orig_idx in self._selected_pages:
            self._selected_pages.discard(orig_idx)
        else:
            self._selected_pages.add(orig_idx)
        self._update_status()
        self._update_buttons()
        self._canvas.delete("all")
        self._rendered_items.clear()
        self._last_range = None
        self._schedule_render()

    def _push_undo(self):
        self._undo_stack.append({
            "page_order": list(self._page_order),
        })
        self._redo_stack.clear()
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)

    def _undo(self):
        if not self._undo_stack:
            return
        state = self._undo_stack.pop()
        self._redo_stack.append({
            "page_order": list(self._page_order),
        })
        self._page_order = state["page_order"]
        self._selected_pages.clear()
        self._modified = bool(self._undo_stack)
        self._update_status()
        self._update_buttons()
        self._canvas.delete("all")
        self._rendered_items.clear()
        self._last_range = None
        self._recalculate_layout()
        self.on_add_log("INFO", "Acción deshecha.")

    def _move_page(self, direction: int):
        if len(self._selected_pages) != 1:
            return
        sel = next(iter(self._selected_pages))
        cur = self._page_order.index(sel)
        nxt = cur + direction
        if nxt < 0 or nxt >= len(self._page_order):
            return
        self._push_undo()
        self._page_order[cur], self._page_order[nxt] = self._page_order[nxt], self._page_order[cur]
        self._modified = True
        self._update_status()
        self._update_buttons()
        self._canvas.delete("all")
        self._rendered_items.clear()
        self._last_range = None
        self._schedule_render()
        self.on_add_log("INFO", f"P\u00e1gina {sel + 1} movida a posici\u00f3n {nxt + 1}")

    def _delete_pages(self):
        if not self._selected_pages:
            return
        count     = len(self._selected_pages)
        pages_str = ", ".join(str(p + 1) for p in sorted(self._selected_pages))
        if not messagebox.askyesno(
                "Eliminar p\u00e1ginas",
                f"\u00bfEliminar {count} p\u00e1gina(s) de la vista?\n"
                f"P\u00e1ginas: {pages_str}\n\n"
                "Se eliminar\u00e1n de la configuraci\u00f3n.\n"
                "El PDF original no se modifica."):
            return
        self._push_undo()
        for p in self._selected_pages:
            if p in self._page_order:
                self._page_order.remove(p)
            self._rendered_photos.pop(p, None)
        self._selected_pages.clear()
        self._modified = True
        self._update_status()
        self._update_buttons()
        self._canvas.delete("all")
        self._rendered_items.clear()
        self._last_range = None
        self._recalculate_layout()
        self.on_add_log("WARN", f"{count} p\u00e1gina(s) eliminadas de la configuraci\u00f3n: {pages_str}")

    def _save_config(self):
        if not self._fitz_doc:
            return

        active = list(self._page_order)
        total_original = len(self._fitz_doc)

        # ── Construir page_map correcto: {orig_page_1indexed → nueva_posicion_1indexed}
        #
        # active = lista de índices 0-based en el NUEVO orden.
        # Ejemplo original: 5 páginas [0,1,2,3,4]
        #
        # Caso eliminación: active = [0, 2, 4]
        #   page_map = {1→1, 3→2, 5→3}
        #   El mapper calcula raw=3 → busca page_map[3] = 2 → pg_pdf = "2" ✓
        #   raw=2 → no está en map → se salta (página eliminada) ✓
        #
        # Caso reordenamiento: active = [2, 0, 1]  (pág 3 pasa a ser la 1ª)
        #   page_map = {3→1, 1→2, 2→3}
        #   El mapper calcula raw=1 → busca page_map[1] = 2 → pg_pdf = "2" ✓
        #   raw=3 → busca page_map[3] = 1 → pg_pdf = "1" ✓
        #
        # Caso mixto eliminación + reordenamiento: active = [4, 2, 0]
        #   page_map = {5→1, 3→2, 1→3}
        #   Páginas 2 y 4 eliminadas → no están en map → se saltan ✓
        #
        page_map = {}
        for new_pos_0, orig_idx in enumerate(active):
            orig_page  = orig_idx + 1       # 1-indexed original
            new_page   = new_pos_0 + 1      # 1-indexed en el PDF resultante
            page_map[orig_page] = new_page

        self.app_state.page_map = page_map
        self.app_state.active_pages = active
        self.app_state.pdf_total_pages = len(active)

        from utils.folio_engine import mapper_from_state
        mapper  = mapper_from_state(self.app_state)
        updated = 0
        skipped = 0
        for rec in self.app_state.records:
            pg = mapper.folio_str_to_pdf_range(rec.folios)
            if pg:
                rec.pg_pdf = pg
                updated += 1
            else:
                skipped += 1

        deleted_count = total_original - len(active)
        reordered = active != list(range(len(active))) if len(active) == total_original else False

        summary_parts = [f"{len(active)} páginas activas"]
        if deleted_count:
            summary_parts.append(f"{deleted_count} eliminadas")
        if reordered:
            summary_parts.append("reordenadas")

        self.on_add_log("SUCCESS",
                        f"Configuración guardada: {', '.join(summary_parts)}")
        self.on_add_log("INFO",
                        f"Page map actualizado. {updated} registros recalculados, {skipped} omitidos.")

        self._modified = False
        self._modified_label.configure(text="")
        self._update_status()
        self._update_buttons()

        if self.on_config_saved:
            self.on_config_saved()

        messagebox.showinfo(
            "Configuración Guardada",
            f"Se guardó la configuración de paginación:\n\n"
            f"Páginas activas: {len(active)}\n"
            f"Páginas eliminadas: {deleted_count}\n"
            f"Registros recalculados: {updated}\n\n"
            f"La asignación de folios con páginas PDF fue actualizada."
        )

    def _update_status(self):
        total = len(self._page_order)
        sel   = len(self._selected_pages)
        mod   = " \u25cf Modificado" if self._modified else ""
        self._status_label.configure(
            text=f"{total} p\u00e1ginas en configuraci\u00f3n | {sel} seleccionada(s){mod}")
        self._modified_label.configure(text="\u25cf Sin guardar" if self._modified else "")

    def _update_buttons(self):
        has_sel  = len(self._selected_pages) > 0
        one_sel  = len(self._selected_pages) == 1
        is_mod   = self._modified
        has_doc  = self._fitz_doc is not None
        has_undo = len(self._undo_stack) > 0

        self._btn_move_up.configure(state="normal" if one_sel else "disabled")
        self._btn_move_down.configure(state="normal" if one_sel else "disabled")
        self._btn_delete.configure(state="normal" if has_sel else "disabled")
        self._btn_save.configure(state="normal" if is_mod else "disabled")
        self._btn_undo.configure(state="normal" if has_undo else "disabled")
