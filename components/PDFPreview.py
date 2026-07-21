"""
PDFPreview.py — Visor de PDF con renderizado directo tipo Acrobat.
Pinta paginas directamente sobre el Canvas en posiciones fijas calculadas,
sin crear frames intermedios. Solo renderiza las paginas visibles.
"""
import tkinter as tk
import math
import os
from utils.theme import C


try:
    import fitz
    from PIL import Image, ImageTk
    PYMUPDF_OK = True
except ImportError:
    try:
        from PIL import Image, ImageTk
    except ImportError:
        pass
    PYMUPDF_OK = False


class PDFPreview(tk.Frame):
    BUF_PAGES = 3
    PAGE_GAP = 10

    def __init__(self, parent, app_state, **kwargs):
        self.on_edit_pdf = kwargs.pop("on_edit_pdf", None)
        super().__init__(parent, **kwargs)
        self.app_state = app_state
        self.configure(bg=C["surface_low"], bd=0)

        self._fitz_doc = None
        self._current_pdf_path = None
        self._total_pdf_pages = 0
        self._page_height = 700
        self._page_width = 300

        self._rendered_items = {}
        self._rendered_photos = {}
        self._pending_job = None
        self._last_range = None
        self._last_width = -1

        self._active_pages = None

        self._build()

    def _build(self):
        toolbar = tk.Frame(self, bg=C["surface_container"], height=50)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        tk.Frame(toolbar, bg=C["outline_variant"], height=1).pack(side="bottom", fill="x")

        nav_frame = tk.Frame(toolbar, bg=C["surface_container"])
        nav_frame.pack(side="right", padx=8)

        tk.Button(
            nav_frame, text="\u25c0", font=("Segoe UI", 12, "bold"),
            fg=C["secondary"], bg=C["surface_container"],
            relief="flat", bd=0, cursor="hand2",
            padx=6, pady=2,
            command=self._prev_page,
        ).pack(side="left", padx=(0, 2))

        self._page_var = tk.StringVar(value="1")
        self._page_entry = tk.Entry(
            nav_frame,
            textvariable=self._page_var,
            font=("Courier New", 10, "bold"),
            fg=C["primary"],
            bg=C["surface_container"],
            relief="flat",
            bd=0,
            width=5,
            justify="center",
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        self._page_entry.pack(side="left", padx=2, ipady=2)
        self._page_entry.bind("<Return>", self._on_page_entry)
        self._page_entry.bind("<FocusIn>", lambda e: self._page_entry.configure(
            highlightbackground=C["primary"], highlightthickness=1))
        self._page_entry.bind("<FocusOut>", lambda e: self._page_entry.configure(
            highlightbackground=C["outline_variant"], highlightthickness=1))

        self._total_lbl = tk.Label(
            nav_frame, text="/ --",
            font=("Courier New", 10, "bold"), fg=C["secondary"],
            bg=C["surface_container"], padx=4,
        )
        self._total_lbl.pack(side="left")

        tk.Button(
            nav_frame, text="\u25b6", font=("Segoe UI", 12, "bold"),
            fg=C["secondary"], bg=C["surface_container"],
            relief="flat", bd=0, cursor="hand2",
            padx=6, pady=2,
            command=self._next_page,
        ).pack(side="left", padx=(2, 0))

        zoom_frame = tk.Frame(toolbar, bg=C["surface_container"])
        zoom_frame.pack(side="right", padx=(0, 8))

        tk.Button(
            zoom_frame, text="\u2212", font=("Segoe UI", 14, "bold"),
            fg=C["white"], bg=C["warning"],
            activebackground=C["warning_dark"], activeforeground=C["white"],
            relief="flat", bd=0, cursor="hand2",
            padx=6, pady=1,
            command=self._zoom_out,
        ).pack(side="left", padx=(0, 2))

        self._zoom_lbl = tk.Label(
            zoom_frame, text=f"{self.app_state.pdf_zoom}%",
            font=("Courier New", 10, "bold"), fg=C["primary"],
            bg=C["surface_container"], width=5,
        )
        self._zoom_lbl.pack(side="left")

        tk.Button(
            zoom_frame, text="+", font=("Segoe UI", 14, "bold"),
            fg=C["white"], bg=C["warning"],
            activebackground=C["warning_dark"], activeforeground=C["white"],
            relief="flat", bd=0, cursor="hand2",
            padx=6, pady=1,
            command=self._zoom_in,
        ).pack(side="left", padx=(2, 0))

        self._canvas = tk.Canvas(
            self, bg=C["surface_low"], bd=0, highlightthickness=0,
        )
        self._scrollbar = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas.configure(yscrollcommand=self._on_scrollbar_update)

        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind("<MouseWheel>", self._on_mouse_wheel)

        self.after(100, self._draw_parchment)

    def _on_scrollbar_update(self, first, last):
        self._scrollbar.set(first, last)
        self._sync_page_indicator()
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
                self._draw_parchment()

    def _on_mouse_wheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _recalculate_layout(self):
        if not self._fitz_doc or not PYMUPDF_OK:
            return

        w = self._canvas.winfo_width()
        if w < 10:
            w = 350

        self._compute_page_dimensions(w)
        total_h = self._total_pdf_pages * (self._page_height + self.PAGE_GAP)
        self._canvas.configure(scrollregion=(0, 0, w, total_h))

        self._clear_all_rendered()
        self._last_range = None
        self._schedule_render()

    def _compute_page_dimensions(self, canvas_width):
        if not self._fitz_doc or len(self._fitz_doc) == 0:
            self._page_width = canvas_width - 30
            self._page_height = 700
            return
        try:
            page = self._fitz_doc[0]
            r = page.rect
            aspect = r.height / r.width
            fit_w = max(50, canvas_width - 40) * (self.app_state.pdf_zoom / 100.0)
            self._page_width = int(fit_w)
            self._page_height = int(fit_w * aspect)
        except Exception:
            self._page_width = canvas_width - 30
            self._page_height = 700

    def _page_y_offset(self, page_idx):
        return page_idx * (self._page_height + self.PAGE_GAP)

    def _get_visible_range(self):
        if self._total_pdf_pages <= 0:
            return None
        try:
            first_str, last_str = self._scrollbar.get()
            first = float(first_str) if first_str else 0.0
            last = float(last_str) if last_str else 1.0
        except (ValueError, ZeroDivisionError):
            first, last = 0.0, 1.0

        total_h = self._total_pdf_pages * (self._page_height + self.PAGE_GAP)
        view_top = first * total_h
        view_bottom = last * total_h

        start = max(0, int(view_top / (self._page_height + self.PAGE_GAP)) - self.BUF_PAGES)
        end = min(self._total_pdf_pages - 1,
                  int(view_bottom / (self._page_height + self.PAGE_GAP)) + self.BUF_PAGES)
        return (start, end)

    def _schedule_render(self):
        if self._pending_job:
            self.after_cancel(self._pending_job)
        self._pending_job = self.after(16, self._do_render)

    def _do_render(self):
        self._pending_job = None
        if not self._fitz_doc or not PYMUPDF_OK:
            return

        rng = self._get_visible_range()
        if not rng:
            return

        vis_start, vis_end = rng

        if self._last_range == (vis_start, vis_end):
            return
        self._last_range = (vis_start, vis_end)

        to_remove = [idx for idx in self._rendered_items if idx < vis_start or idx > vis_end]
        for idx in to_remove:
            self._remove_page_from_canvas(idx)

        for idx in range(vis_start, vis_end + 1):
            if idx not in self._rendered_items:
                self._paint_page(idx)

    def _paint_page(self, page_idx):
        if self._active_pages is not None:
            if page_idx < 0 or page_idx >= len(self._active_pages):
                return
            orig_idx = self._active_pages[page_idx]
        else:
            orig_idx = page_idx

        if orig_idx < 0 or orig_idx >= len(self._fitz_doc):
            return

        try:
            page = self._fitz_doc[orig_idx]
            page_rect = page.rect

            zoom = max(0.05, self._page_width / page_rect.width)
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            photo = ImageTk.PhotoImage(img)

            x_center = self._canvas.winfo_width() // 2
            y = self._page_y_offset(page_idx)

            x_start = x_center - pix.width // 2
            x_end = x_center + pix.width // 2
            y_end = y + pix.height

            shadow_id = self._canvas.create_rectangle(
                x_start + 4, y + 4, x_end + 4, y_end + 4,
                fill=C["black"], outline="", stipple="gray25",
            )

            border_id = self._canvas.create_rectangle(
                x_start, y, x_end, y_end,
                fill="", outline=C["outline_variant"], width=1,
            )

            img_id = self._canvas.create_image(
                x_center, y, anchor="n", image=photo,
            )

            self._rendered_items[page_idx] = (img_id, shadow_id, border_id)
            self._rendered_photos[page_idx] = photo
        except Exception as e:
            print(f"[PDFPreview] Error renderizando pagina {page_idx}: {e}")

    def _remove_page_from_canvas(self, page_idx):
        if page_idx in self._rendered_items:
            for item_id in self._rendered_items[page_idx]:
                self._canvas.delete(item_id)
            del self._rendered_items[page_idx]
            self._rendered_photos.pop(page_idx, None)

    def _clear_all_rendered(self):
        for idx in list(self._rendered_items.keys()):
            self._remove_page_from_canvas(idx)
        self._rendered_items.clear()
        self._rendered_photos.clear()

    def _sync_page_indicator(self):
        try:
            first_str = self._scrollbar.get()[0]
            first = float(first_str) if first_str else 0.0
            total_h = self._total_pdf_pages * (self._page_height + self.PAGE_GAP)
            if total_h > 0:
                current_y = first * total_h
                page_idx = int(current_y / (self._page_height + self.PAGE_GAP))
                page_idx = max(0, min(page_idx, self._total_pdf_pages - 1))
                page_num = page_idx + 1
                if self.app_state.pdf_current_page != page_num:
                    self.app_state.pdf_current_page = page_num
                    self._page_var.set(str(page_num))
        except Exception:
            pass

    def load_pdf(self, path: str):
        if not path or not os.path.exists(path):
            return

        self._current_pdf_path = path
        self._active_pages = None

        if PYMUPDF_OK:
            try:
                if self._fitz_doc:
                    self._fitz_doc.close()
                self._fitz_doc = fitz.open(path)
                total = len(self._fitz_doc)
                self._total_pdf_pages = total
                self.app_state.pdf_total_pages = total
                self._total_lbl.configure(text=f"/ {total}")

                self._clear_all_rendered()
                self._last_range = None
                self._last_width = -1
                self.app_state.pdf_current_page = 1
                self._page_var.set("1")

                self._remove_parchment()
                self.update_idletasks()
                self._recalculate_layout()
                return
            except Exception as e:
                print(f"[PDFPreview] Error abriendo PDF con PyMuPDF: {e}")

        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            total = len(reader.pages)
            self._total_pdf_pages = total
            self.app_state.pdf_total_pages = total
            self._total_lbl.configure(text=f"/ {total}")
        except Exception:
            pass

        self._draw_parchment()

    def apply_active_pages(self):
        if not self._fitz_doc or not PYMUPDF_OK:
            return
        active = self.app_state.active_pages
        if active:
            self._active_pages = list(active)
        else:
            self._active_pages = None

        total = len(self._active_pages) if self._active_pages else len(self._fitz_doc)
        self._total_pdf_pages = total
        self.app_state.pdf_total_pages = total
        self._total_lbl.configure(text=f"/ {total}")

        self.app_state.pdf_current_page = 1
        self._page_var.set("1")

        self._clear_all_rendered()
        self._last_range = None
        self._last_width = -1
        self._remove_parchment()
        self.update_idletasks()
        self._recalculate_layout()

    def go_to_page(self, page: int):
        total = self._total_pdf_pages
        if total <= 0:
            return
        page = max(1, min(page, total))
        self.app_state.pdf_current_page = page
        self._page_var.set(str(page))
        self._total_lbl.configure(text=f"/ {total}")

        y = self._page_y_offset(page - 1)
        total_h = total * (self._page_height + self.PAGE_GAP)
        if total_h > 0:
            fraction = y / total_h
            fraction = max(0.0, min(1.0, fraction))
            self._canvas.yview_moveto(fraction)
            self._last_range = None
            self._schedule_render()

    def _prev_page(self):
        if self.app_state.pdf_current_page > 1:
            self.go_to_page(self.app_state.pdf_current_page - 1)

    def _next_page(self):
        if self.app_state.pdf_current_page < self._total_pdf_pages:
            self.go_to_page(self.app_state.pdf_current_page + 1)

    def _on_page_entry(self, event=None):
        try:
            page = int(self._page_var.get())
            page = max(1, min(page, max(1, self._total_pdf_pages)))
            self._page_var.set(str(page))
            self.go_to_page(page)
        except ValueError:
            self._page_var.set(str(self.app_state.pdf_current_page))

    def _zoom_in(self):
        self.app_state.pdf_zoom = min(200, self.app_state.pdf_zoom + 25)
        self._zoom_lbl.configure(text=f"{self.app_state.pdf_zoom}%")
        self._recalculate_layout()

    def _zoom_out(self):
        self.app_state.pdf_zoom = max(25, self.app_state.pdf_zoom - 25)
        self._zoom_lbl.configure(text=f"{self.app_state.pdf_zoom}%")
        self._recalculate_layout()

    def _remove_parchment(self):
        self._canvas.delete("parchment")

    def _draw_parchment(self, event=None):
        self._remove_parchment()
        c = self._canvas
        c.update_idletasks()
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10 or h < 10:
            return

        c.configure(scrollregion=(0, 0, w, h))
        tag = "parchment"

        c.create_rectangle(8, 8, w - 4, h - 4, fill="#d4c9b8", outline="", tags=tag)
        c.create_rectangle(4, 4, w - 8, h - 8, fill=C["parchment"], outline="#c8b89a", width=1, tags=tag)

        for i, alpha in enumerate([0.03, 0.04, 0.05]):
            r = 60 + i * 40
            cx, cy = w * 0.15, h * 0.2
            c.create_oval(cx - r, cy - r, cx + r, cy + r,
                          fill="#c8b89a", outline="", stipple="gray12", tags=tag)

        line_colors = ["#9b8b7a", "#8a7a6a", "#7a6a5a"]
        line_y = 55
        for i in range(20):
            length = int((w - 60) * (0.7 + 0.3 * math.sin(i * 0.7)))
            color = line_colors[i % 3]
            lw = 1 if i % 4 != 0 else 2
            c.create_line(28, line_y, 28 + length, line_y,
                          fill=color, width=lw, smooth=True, tags=tag)
            line_y += 18
            if line_y > h - 80:
                break

        page = self.app_state.pdf_current_page
        folio_text = f"Folio {page:03d}r"
        c.create_rectangle(w - 80, h - 52, w - 10, h - 20,
                           fill=C["surface_high"], outline=C["outline_variant"], tags=tag)
        c.create_text(w - 45, h - 36, text=folio_text,
                      font=("Courier New", 7, "bold"), fill=C["secondary"], tags=tag)

        cx, cy = w // 2, h // 2
        r_outer, r_inner = 45, 32
        for angle in range(0, 360, 12):
            rad = math.radians(angle)
            rad_end = math.radians(angle + 8)
            x1 = cx + r_outer * math.cos(rad)
            y1 = cy + r_outer * math.sin(rad)
            x2 = cx + r_outer * math.cos(rad_end)
            y2 = cy + r_outer * math.sin(rad_end)
            c.create_line(x1, y1, x2, y2, fill=C["primary"], width=2, tags=tag)

        c.create_oval(cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner,
                      outline=C["primary"], width=1, fill="", tags=tag)
        c.create_text(cx, cy - 10, text="ARCHIVO", font=("Segoe UI", 7, "bold"),
                      fill=C["primary"], tags=tag)
        c.create_text(cx, cy + 2, text="\u2726", font=("Segoe UI", 12),
                      fill=C["primary"], tags=tag)
        c.create_text(cx, cy + 16, text="HIST\u00d3RICO", font=("Segoe UI", 7, "bold"),
                      fill=C["primary"], tags=tag)
        c.create_text(cx, cy + 30, text="1891", font=("Courier New", 7),
                      fill=C["on_primary"], tags=tag)

        if not self._current_pdf_path:
            c.create_text(
                w // 2, h - 24,
                text="Cargue un PDF para ver la previsualizaci\u00f3n real",
                font=("Segoe UI", 7, "italic"), fill=C["outline"], tags=tag,
            )

    def append_log(self, log):
        pass
