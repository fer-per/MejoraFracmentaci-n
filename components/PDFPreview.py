"""
PDFPreview.py — Visor de PDF integrado con renderizado virtual (lazy loading).
Solo renderiza las páginas visibles en el viewport + buffer, evitando saturar RAM.
"""
import tkinter as tk
from tkinter import ttk
import math
import os
from utils.theme import C, FONT


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
    BUF_PAGES = 4

    def __init__(self, parent, app_state, **kwargs):
        self.on_edit_pdf = kwargs.pop("on_edit_pdf", None)
        super().__init__(parent, **kwargs)
        self.app_state = app_state
        self.configure(bg=C["surface_low"], bd=0)

        self._fitz_doc = None
        self._current_pdf_path = None
        self._page_widgets = {}
        self._page_images = {}
        self._page_heights = {}
        self._total_pdf_pages = 0
        self._pending_render_job = None
        self._spacer_widgets = []
        self._last_visible_range = None
        self._last_width = -1

        self._build()

    def _build(self):
        toolbar = tk.Frame(self, bg=C["surface_container"], height=40)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)

        tk.Frame(toolbar, bg=C["outline_variant"], height=1).pack(side="bottom", fill="x")

        nav_frame = tk.Frame(toolbar, bg=C["surface_container"])
        nav_frame.pack(side="right", padx=8)

        # Botón Editar PDF (izquierda del toolbar)
        if self.on_edit_pdf:
            tk.Button(
                toolbar, text="✏ Editar", font=("Segoe UI", 8, "bold"),
                fg="#ffffff", bg="#b45309",
                activebackground="#92400e", activeforeground="#ffffff",
                relief="flat", bd=0, cursor="hand2",
                padx=8, pady=2,
                command=self.on_edit_pdf,
            ).pack(side="left", padx=(8, 4))

        tk.Button(
            nav_frame, text="\u25c0", font=("Segoe UI", 9),
            fg=C["secondary"], bg=C["surface_container"],
            relief="flat", bd=0, cursor="hand2",
            command=self._prev_page,
        ).pack(side="left")

        self._page_var = tk.StringVar(value="1")
        self._page_entry = tk.Entry(
            nav_frame,
            textvariable=self._page_var,
            font=("Courier New", 8),
            fg=C["primary"],
            bg=C["surface_container"],
            relief="flat",
            bd=0,
            width=4,
            justify="center",
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        self._page_entry.pack(side="left", padx=2)
        self._page_entry.bind("<Return>", self._on_page_entry)
        self._page_entry.bind("<FocusIn>", lambda e: self._page_entry.configure(
            highlightbackground=C["primary"], highlightthickness=1))
        self._page_entry.bind("<FocusOut>", lambda e: self._page_entry.configure(
            highlightbackground=C["outline_variant"], highlightthickness=1))

        self._total_lbl = tk.Label(
            nav_frame,
            text="/ --",
            font=("Courier New", 8),
            fg=C["secondary"],
            bg=C["surface_container"],
            padx=2,
        )
        self._total_lbl.pack(side="left")

        tk.Button(
            nav_frame, text="\u25b6", font=("Segoe UI", 9),
            fg=C["secondary"], bg=C["surface_container"],
            relief="flat", bd=0, cursor="hand2",
            command=self._next_page,
        ).pack(side="left")

        zoom_frame = tk.Frame(toolbar, bg=C["surface_container"])
        zoom_frame.pack(side="right", padx=(0, 4))

        tk.Button(
            zoom_frame, text="\uff0d", font=("Segoe UI", 9),
            fg=C["secondary"], bg=C["surface_container"],
            relief="flat", bd=0, cursor="hand2",
            command=self._zoom_out,
        ).pack(side="left")

        self._zoom_lbl = tk.Label(
            zoom_frame,
            text=f"{self.app_state.pdf_zoom}%",
            font=("Courier New", 8),
            fg=C["secondary"],
            bg=C["surface_container"],
            width=4,
        )
        self._zoom_lbl.pack(side="left")

        tk.Button(
            zoom_frame, text="\uff0b", font=("Segoe UI", 9),
            fg=C["secondary"], bg=C["surface_container"],
            relief="flat", bd=0, cursor="hand2",
            command=self._zoom_in,
        ).pack(side="left")

        self._canvas = tk.Canvas(
            self,
            bg=C["surface_low"],
            bd=0,
            highlightthickness=0,
        )

        self._scrollbar = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._scrollbar.pack(side="right", fill="y")

        self._canvas.pack(side="left", fill="both", expand=True)
        self._canvas.configure(yscrollcommand=self._on_scroll)

        self._pages_frame = tk.Frame(self._canvas, bg=C["surface_low"])
        self._canvas_window = self._canvas.create_window((0, 0), window=self._pages_frame, anchor="nw")

        self._pages_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        self._canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self._pages_frame.bind("<MouseWheel>", self._on_mouse_wheel)

        self._render_current()

    def _on_frame_configure(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event=None):
        canvas_width = event.width if event else self._canvas.winfo_width()
        self._canvas.itemconfigure(self._canvas_window, width=canvas_width)
        if getattr(self, "_last_width", 0) != canvas_width:
            self._last_width = canvas_width
            self._render_current()

    def _on_mouse_wheel(self, event):
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._sync_page_from_scroll()

    def _on_scroll(self, first, last):
        self._scrollbar.set(first, last)
        if self._fitz_doc and PYMUPDF_OK:
            self._schedule_lazy_render()
        self._sync_page_from_scroll()

    def _sync_page_from_scroll(self):
        try:
            first = float(self._scrollbar.get()[0])
            children = sorted(self._page_widgets.items())
            total_height = self._pages_frame.winfo_height()
            if children and total_height > 0:
                current_y = first * total_height
                best_idx = 0
                min_diff = float("inf")
                for idx, (pg, w) in enumerate(children):
                    cy = w.winfo_y()
                    diff = abs(cy - current_y)
                    if diff < min_diff:
                        min_diff = diff
                        best_idx = pg
                if self.app_state.pdf_current_page != best_idx + 1:
                    self.app_state.pdf_current_page = best_idx + 1
                    self._page_var.set(str(best_idx + 1))
        except Exception:
            pass

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

    def go_to_page(self, page: int):
        total = self._total_pdf_pages
        if total <= 0:
            return
        page = max(1, min(page, total))
        self.app_state.pdf_current_page = page
        self._page_var.set(str(page))
        self._total_lbl.configure(text=f"/ {total}")

        self.after(50, lambda: self._scroll_to_page(page - 1))

    def _scroll_to_page(self, page_idx):
        if page_idx in self._page_widgets:
            widget = self._page_widgets[page_idx]
            y = widget.winfo_y()
            total_height = self._pages_frame.winfo_height()
            if total_height > 0:
                fraction = y / total_height
                fraction = max(0.0, min(1.0, fraction))
                self._canvas.yview_moveto(fraction)
                self._schedule_lazy_render()

    def _zoom_in(self):
        self.app_state.pdf_zoom = min(200, self.app_state.pdf_zoom + 25)
        self._zoom_lbl.configure(text=f"{self.app_state.pdf_zoom}%")
        self._render_current()

    def _zoom_out(self):
        self.app_state.pdf_zoom = max(25, self.app_state.pdf_zoom - 25)
        self._zoom_lbl.configure(text=f"{self.app_state.pdf_zoom}%")
        self._render_current()

    def load_pdf(self, path: str):
        if not path or not os.path.exists(path):
            return

        self._current_pdf_path = path

        if PYMUPDF_OK:
            try:
                if self._fitz_doc:
                    self._fitz_doc.close()
                self._fitz_doc = fitz.open(path)
                total = len(self._fitz_doc)
                self._total_pdf_pages = total
                self.app_state.pdf_total_pages = total
                self._total_lbl.configure(text=f"/ {total}")
                self._render_current()
                self.go_to_page(1)
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

        self.go_to_page(1)

    def _render_current(self, preserve_page=True):
        saved_page = self.app_state.pdf_current_page if preserve_page else 1

        for w in self._page_widgets.values():
            w.destroy()
        self._page_widgets.clear()
        self._page_images.clear()
        self._page_heights.clear()
        self._last_visible_range = None
        self._remove_parchment()

        if PYMUPDF_OK and self._fitz_doc:
            self._total_pdf_pages = len(self._fitz_doc)
            if self._total_pdf_pages > 0:
                self._place_spacers()
                self._schedule_lazy_render()
                if self._total_pdf_pages >= saved_page:
                    self.app_state.pdf_current_page = saved_page
                    self._page_var.set(str(saved_page))
                    self._total_lbl.configure(text=f"/ {self._total_pdf_pages}")
                    self._scroll_to_page(saved_page - 1)
        else:
            self._draw_parchment()

    def _place_spacers(self):
        for w in self._spacer_widgets:
            w.destroy()
        self._spacer_widgets = []

        total = self._total_pdf_pages
        if total <= 0:
            return

        w = self._canvas.winfo_width()
        if w < 10:
            w = 350

        page_height = self._estimate_page_height(w)
        total_height = total * page_height

        top_spacer = tk.Frame(self._pages_frame, bg=C["surface_low"], height=0)
        top_spacer.pack(side="top", fill="x")
        self._spacer_widgets.append(top_spacer)

        for i in range(total):
            slot_frame = tk.Frame(self._pages_frame, bg=C["surface_low"],
                                  height=page_height, width=w - 30)
            slot_frame.pack(pady=8, anchor="center")
            slot_frame.pack_propagate(False)
            slot_frame.bind("<MouseWheel>", self._on_mouse_wheel)
            self._page_widgets[i] = slot_frame

        bottom_spacer = tk.Frame(self._pages_frame, bg=C["surface_low"], height=0)
        bottom_spacer.pack(side="bottom", fill="x")
        self._spacer_widgets.append(bottom_spacer)

    def _estimate_page_height(self, canvas_width):
        if not self._fitz_doc or len(self._fitz_doc) == 0:
            return 500
        try:
            page = self._fitz_doc[0]
            r = page.rect
            aspect = r.height / r.width
            fit_w = max(50, canvas_width - 30) * (self.app_state.pdf_zoom / 100.0)
            return int(fit_w * aspect)
        except Exception:
            return 500

    def _schedule_lazy_render(self):
        if self._pending_render_job:
            self.after_cancel(self._pending_render_job)
        self._pending_render_job = self.after(30, self._do_lazy_render)

    def _do_lazy_render(self):
        self._pending_render_job = None
        if not self._fitz_doc or not PYMUPDF_OK:
            return

        visible_range = self._get_visible_page_range()
        if not visible_range:
            return

        vis_start, vis_end = visible_range

        last_range = getattr(self, "_last_visible_range", None)
        if last_range == (vis_start, vis_end):
            return
        self._last_visible_range = (vis_start, vis_end)

        for idx in self._page_widgets:
            slot = self._page_widgets[idx]
            in_view = vis_start <= idx <= vis_end
            if in_view and idx not in self._page_images:
                self._render_single_page(idx, slot)

        for idx in self._page_widgets:
            slot = self._page_widgets[idx]
            in_view = vis_start <= idx <= vis_end
            if not in_view and idx in self._page_images:
                self._unrender_page(idx, slot)

    def _get_visible_page_range(self):
        if not self._page_widgets:
            return None

        try:
            first_str, last_str = self._scrollbar.get()
            first = float(first_str) if first_str else 0.0
            last = float(last_str) if last_str else 1.0
        except (ValueError, ZeroDivisionError):
            first, last = 0.0, 1.0

        total = self._total_pdf_pages
        start_idx = max(0, int(first * total) - self.BUF_PAGES)
        end_idx = min(total - 1, int(last * total) + self.BUF_PAGES)

        return (start_idx, end_idx)

    def _render_single_page(self, page_idx, slot_frame):
        try:
            page = self._fitz_doc[page_idx]
            page_rect = page.rect

            w = self._canvas.winfo_width()
            if w < 10:
                w = 350

            fit_zoom = max(0.05, (w - 30) / page_rect.width * (self.app_state.pdf_zoom / 100.0))
            mat = fitz.Matrix(fit_zoom, fit_zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            photo = ImageTk.PhotoImage(img)

            for child in slot_frame.winfo_children():
                child.destroy()

            lbl = tk.Label(slot_frame, image=photo, bg=C["surface_low"])
            lbl.pack(fill="both", expand=True)
            lbl.bind("<MouseWheel>", self._on_mouse_wheel)
            slot_frame.configure(height=pix.height, width=pix.width)

            self._page_images[page_idx] = photo
        except Exception as e:
            print(f"[PDFPreview] Error renderizando página {page_idx}: {e}")

    def _unrender_page(self, page_idx, slot_frame):
        for child in slot_frame.winfo_children():
            child.destroy()
        slot_frame.configure(height=slot_frame.winfo_reqheight())
        self._page_images.pop(page_idx, None)

    def _remove_parchment(self):
        try:
            self._canvas.delete("parchment")
        except Exception:
            pass

    def _draw_parchment(self, event=None):
        self._remove_parchment()
        c = self._canvas
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 10 or h < 10:
            w, h = 350, 600

        c.configure(scrollregion=(0, 0, w, h))

        c.create_rectangle(8, 8, w - 4, h - 4, fill="#d4c9b8", outline="", tags="parchment")
        c.create_rectangle(4, 4, w - 8, h - 8, fill=C["parchment"], outline="#c8b89a", width=1, tags="parchment")

        for i, alpha in enumerate([0.03, 0.04, 0.05]):
            r = 60 + i * 40
            cx, cy = w * 0.15, h * 0.2
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill="#c8b89a", outline="", stipple="gray12", tags="parchment")

        line_colors = ["#9b8b7a", "#8a7a6a", "#7a6a5a"]
        line_y = 55
        for i in range(20):
            length = int((w - 60) * (0.7 + 0.3 * math.sin(i * 0.7)))
            color = line_colors[i % 3]
            lw = 1 if i % 4 != 0 else 2
            c.create_line(28, line_y, 28 + length, line_y, fill=color, width=lw, smooth=True, tags="parchment")
            line_y += 18
            if line_y > h - 80:
                break

        page = self.app_state.pdf_current_page
        folio_text = f"Folio {page:03d}r"
        c.create_rectangle(w - 80, h - 52, w - 10, h - 20, fill=C["surface_high"], outline=C["outline_variant"], tags="parchment")
        c.create_text(w - 45, h - 36, text=folio_text, font=("Courier New", 7, "bold"), fill=C["secondary"], tags="parchment")

        cx, cy = w // 2, h // 2
        r_outer, r_inner = 45, 32
        for angle in range(0, 360, 12):
            rad = math.radians(angle)
            rad_end = math.radians(angle + 8)
            x1 = cx + r_outer * math.cos(rad)
            y1 = cy + r_outer * math.sin(rad)
            x2 = cx + r_outer * math.cos(rad_end)
            y2 = cy + r_outer * math.sin(rad_end)
            c.create_line(x1, y1, x2, y2, fill=C["primary"], width=2, tags="parchment")

        c.create_oval(cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner, outline=C["primary"], width=1, fill="", tags="parchment")
        c.create_text(cx, cy - 10, text="ARCHIVO", font=("Segoe UI", 7, "bold"), fill=C["primary"], tags="parchment")
        c.create_text(cx, cy + 2, text="\u2726", font=("Segoe UI", 12), fill=C["primary"], tags="parchment")
        c.create_text(cx, cy + 16, text="HIST\u00d3RICO", font=("Segoe UI", 7, "bold"), fill=C["primary"], tags="parchment")
        c.create_text(cx, cy + 30, text="1891", font=("Courier New", 7), fill=C["on_primary"], tags="parchment")

        if not self._current_pdf_path:
            c.create_text(
                w // 2, h - 24,
                text="Cargue un PDF para ver la previsualizaci\u00f3n real",
                font=("Segoe UI", 7, "italic"),
                fill=C["outline"],
                tags="parchment",
            )

    def append_log(self, log):
        pass
