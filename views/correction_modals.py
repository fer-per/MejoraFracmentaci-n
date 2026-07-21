"""
views/correction_modals.py — Modales de corrección y salto extraídos de ExpandedAnalyzerView.
"""
import tkinter as tk
from tkinter import messagebox
import os

from utils.theme import C
from utils.folio_engine import mapper_from_state
from utils.folio_parser import parse_folios
from domain.models import ExclusionRule


class CorrectionModal:
    """Modal de corrección inteligente para registros con errores."""

    def __init__(self, parent_view, app_state, on_add_log):
        self._parent_view = parent_view
        self.app_state = app_state
        self.on_add_log = on_add_log
        self._editable_var = None

    def show(self, selected_record, suggestion, on_apply_callback):
        self._on_apply_callback = on_apply_callback
        self._suggestion = suggestion

        modal = tk.Toplevel(self._parent_view)
        modal.title("Corrección Inteligente")
        modal.configure(bg=C["surface"])
        modal.geometry("780x520")
        modal.minsize(600, 400)
        modal.resizable(True, True)
        modal.grab_set()

        modal.update_idletasks()
        x = self._parent_view.winfo_rootx() + (self._parent_view.winfo_width() - 780) // 2
        y = self._parent_view.winfo_rooty() + (self._parent_view.winfo_height() - 520) // 2
        modal.geometry(f"+{x}+{y}")

        self._build_modal_content(modal, suggestion)

    def _build_modal_content(self, modal, s):
        header = tk.Frame(modal, bg=C["primary"], pady=12, padx=20)
        header.pack(fill="x")

        tk.Label(
            header,
            text=f"⚠️  Corrección Inteligente  —  Registro {s.registro_id}",
            font=("Segoe UI", 11, "bold"),
            fg=C["white"],
            bg=C["primary"],
        ).pack(side="left")

        tk.Label(
            header,
            text=s.tipo_error,
            font=("Courier New", 8, "bold"),
            fg=C["on_primary"],
            bg=C["primary"],
        ).pack(side="right")

        body = tk.Frame(modal, bg=C["surface"], padx=20, pady=16)
        body.pack(fill="both", expand=True)

        left_col = tk.Frame(body, bg=C["surface"])
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 16))

        tk.Label(
            left_col,
            text="Contexto del Error",
            font=("Segoe UI", 9, "bold"),
            fg=C["primary"],
            bg=C["surface"],
        ).pack(anchor="w", pady=(0, 6))

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

        right_col = tk.Frame(body, bg=C["surface"])
        right_col.pack(side="right", fill="both", expand=True)

        tk.Label(
            right_col,
            text="Comparación Detallada",
            font=("Segoe UI", 9, "bold"),
            fg=C["primary"],
            bg=C["surface"],
        ).pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(right_col, bg=C["surface"])
        grid.pack(fill="x", pady=(0, 12))

        self._make_compare_box(grid, "Valor Actual (Error)",
                               s.valor_actual, C["error_bg"], C["error_text"], row=0, col=0)
        self._make_compare_box(grid, "Valor Sugerido ✎",
                               s.valor_sugerido, C["success_bg"], C["success_text"], row=0, col=1, editable=True)
        self._make_compare_box(grid, "Rango Original",
                               s.folios_original, C["warning_bg"], C["warning_text"], row=1, col=0)
        self._make_compare_box(grid, "Rango Sugerido",
                               s.rango_sugerido, C["info_bg"], C["info"], row=1, col=1)

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
            fg=C["white"],
            bg=C["success"],
            activebackground=C["success_dark"],
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
        corrected_val = self._editable_var.get().strip() if self._editable_var else suggestion.valor_sugerido

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

        self.app_state.suggestions = [
            s for s in self.app_state.suggestions if s.id != suggestion.id
        ]

        self.on_add_log("SUCCESS", f"Corrección aplicada: {suggestion.registro_id} → {corrected_val}")
        self._on_apply_callback(suggestion, corrected_val)
        modal.destroy()
        messagebox.showinfo(
            "Corrección Aplicada",
            f"El registro {suggestion.registro_id} ha sido actualizado a VALIDADO.\n"
            f"Valor corregido: {corrected_val}"
        )


class JumpModal:
    """Modal de registro de salto con vista previa PDF."""

    def __init__(self, parent_view, app_state, on_add_log, per_tab_error_ids,
                 per_tab_analysis_done, per_tab_showing_errors):
        self._parent_view = parent_view
        self.app_state = app_state
        self.on_add_log = on_add_log
        self._per_tab_error_ids = per_tab_error_ids
        self._per_tab_analysis_done = per_tab_analysis_done
        self._per_tab_showing_errors = per_tab_showing_errors

    def show(self, selected_record, on_refresh_callback):
        self._on_refresh_callback = on_refresh_callback
        rec = selected_record
        records = self.app_state.records
        idx = next((i for i, r in enumerate(records) if r.id == rec.id), None)
        if idx is None:
            return

        ctx_start = max(0, idx - 2)
        ctx_end = min(len(records) - 1, idx + 2)
        context_records = records[ctx_start:ctx_end + 1]

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

        salto_suggestion = next(
            (s for s in self.app_state.suggestions
             if s.registro_id == rec.id and "SALTO" in s.tipo_error.upper()),
            None,
        )

        desde_folio = salto_suggestion.valor_esperado if salto_suggestion else ""
        hasta_folio = ""
        parsed = parse_folios(rec.folios)
        if parsed:
            hasta_num, hasta_cara = parsed[0], parsed[1]
            hasta_folio = f"{hasta_num:03d}{hasta_cara}"

        modal = tk.Toplevel(self._parent_view)
        modal.title("Registrar Salto — Vista Previa")
        modal.configure(bg=C["surface"])
        modal.geometry("960x620")
        modal.resizable(True, True)
        modal.minsize(760, 480)
        modal.grab_set()

        modal.update_idletasks()
        x = self._parent_view.winfo_rootx() + (self._parent_view.winfo_width() - 960) // 2
        y = self._parent_view.winfo_rooty() + (self._parent_view.winfo_height() - 620) // 2
        modal.geometry(f"+{max(0,x)}+{max(0,y)}")

        header = tk.Frame(modal, bg=C["warning_dark"], pady=10, padx=16)
        header.pack(fill="x")

        tk.Label(
            header,
            text=f"⬆  Registrar Salto  —  Registro {rec.id}",
            font=("Segoe UI", 11, "bold"),
            fg=C["white"], bg=C["warning_dark"],
        ).pack(side="left")

        tk.Label(
            header,
            text=f"Folios: {rec.folios}  |  Pág PDF: {pdf_min_page}–{pdf_max_page}",
            font=("Courier New", 9),
            fg=C["warning_bg"], bg=C["warning_dark"],
        ).pack(side="right")

        body = tk.PanedWindow(
            modal, orient="horizontal",
            sashwidth=4, sashrelief="flat",
            bg=C["outline_variant"], opaqueresize=True,
        )
        body.pack(fill="both", expand=True, padx=8, pady=8)

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

        pdf_inner.bind("<Configure>", lambda e: pdf_canvas.configure(
            scrollregion=pdf_canvas.bbox("all")))

        def _on_pdf_canvas_configure(e):
            pdf_canvas.itemconfig(pdf_canvas_window, width=e.width)
        pdf_canvas.bind("<Configure>", _on_pdf_canvas_configure)

        self._render_modal_pdf_pages(pdf_inner, pdf_canvas, all_pages, context_records, idx - ctx_start)

        def _on_pdf_mousewheel(event):
            pdf_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        pdf_canvas.bind("<MouseWheel>", _on_pdf_mousewheel)
        pdf_inner.bind("<MouseWheel>", _on_pdf_mousewheel)

        form_frame = tk.Frame(body, bg=C["surface"], padx=16, pady=12)
        body.add(form_frame, minsize=260, stretch="never")

        tk.Label(
            form_frame,
            text="Datos del Salto",
            font=("Segoe UI", 10, "bold"),
            fg=C["primary"], bg=C["surface"],
        ).pack(anchor="w", pady=(0, 10))

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
                 fg=C["tertiary"], bg=C["warning_bg"],
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
                 fg=C["tertiary"], bg=C["warning_bg"],
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

        if salto_suggestion:
            tk.Frame(form_frame, bg=C["outline_variant"], height=1).pack(fill="x", pady=8)
            tk.Label(
                form_frame,
                text="Error detectado:",
                font=("Segoe UI", 8, "bold"),
                fg=C["warning_dark"], bg=C["surface"],
            ).pack(anchor="w", pady=(0, 4))
            tk.Label(
                form_frame,
                text=salto_suggestion.descripcion,
                font=("Segoe UI", 8),
                fg=C["tertiary"], bg=C["surface"],
                wraplength=220, justify="left",
            ).pack(anchor="w")

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
            fg=C["white"], bg=C["success"],
            activebackground=C["success_dark"],
            relief="flat", bd=0, cursor="hand2",
            padx=14, pady=8,
            command=_on_apply,
        ).pack(side="left")

    def _render_modal_pdf_pages(self, parent, canvas, pages, context_records, highlight_idx):
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

            if i > 0 and context_records and (i < len(context_records)):
                sep = tk.Frame(parent, bg=C["outline_variant"], height=1)
                sep.pack(fill="x", padx=8, pady=4)

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
        parent._img_refs = img_refs

    def _apply_jump(self, desde_var, hasta_var, motivo_var, modal):
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

        new_rule = ExclusionRule(
            id=f"EX-{len(self.app_state.exclusions)+1:03d}",
            tipo="SALTO",
            desde=desde,
            hasta=hasta,
            motivo=motivo,
        )
        self.app_state.exclusions.append(new_rule)
        self.on_add_log("INFO", f"Salto registrado desde Analizador: folios {desde}–{hasta}. {motivo}")

        from use_cases.analyzer_use_case import reanalyze_with_exclusions
        res = reanalyze_with_exclusions(self.app_state)
        self._per_tab_analysis_done["folios"] = True
        self._per_tab_error_ids["folios"] = set()
        for err in res.errores:
            self._per_tab_error_ids["folios"].add(err.record_id)

        self.on_add_log("SUCCESS", f"Salto {desde}–{hasta} registrado. Análisis re-ejecutado.")
        modal.destroy()

        self._on_refresh_callback()
