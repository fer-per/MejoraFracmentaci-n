"""
views/analysis_panels.py — Panel de Cobertura extraído de ExpandedAnalyzerView.
"""
import tkinter as tk
from utils.theme import C


class CoveragePanel:
    """Panel de vista de cobertura del PDF."""

    def __init__(self, parent_frame, app_state, on_add_log):
        self._parent_frame = parent_frame
        self.app_state = app_state
        self.on_add_log = on_add_log
        self._coverage_inner = None
        self._coverage_canvas = None

    def build(self):
        container = tk.Frame(self._parent_frame, bg=C["background"])
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=C["background"], highlightthickness=0)
        vsb = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=C["background"])
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _configure_inner(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _configure_inner)

        def _configure_canvas(e):
            canvas.itemconfig("inner_window", width=e.width)
        canvas.bind("<Configure>", _configure_canvas)
        canvas.itemconfig(canvas.create_window((0, 0), window=inner, anchor="nw"), tags="inner_window")

        self._coverage_inner = inner
        self._coverage_canvas = canvas

        return container

    def refresh_scroll(self):
        if self._coverage_canvas:
            self._coverage_canvas.configure(scrollregion=self._coverage_canvas.bbox("all"))

    def populate(self, res):
        if self._coverage_inner is None:
            return
        if res:
            self._populate_coverage_view(self._coverage_inner, res)
        else:
            self._show_coverage_placeholder(self._coverage_inner)

    def _show_coverage_placeholder(self, parent):
        placeholder = tk.Frame(parent, bg=C["surface"], padx=40, pady=40,
                               highlightbackground=C["outline_variant"], highlightthickness=1)
        placeholder.pack(expand=True, padx=60, pady=60, fill="both")
        tk.Label(placeholder, text="📊 Cobertura del PDF",
                 font=("Segoe UI", 16, "bold"), fg=C["primary"], bg=C["surface"]).pack(pady=(0, 8))
        tk.Label(placeholder, text="Presiona \"▶ Iniciar Análisis\" para evaluar\nsi el PDF cargado cubre todos los folios del inventario.",
                 font=("Segoe UI", 10), fg=C["secondary"], bg=C["surface"], justify="center").pack()

    def _populate_coverage_view(self, parent, res):
        for w in parent.winfo_children():
            w.destroy()

        info = res.info_extra
        pdf_total = info.get("pdf_total", 0)
        max_req = info.get("max_requerido", 0)
        diff = info.get("diferencia", 0)
        estado = info.get("estado", "OK")
        ok = estado == "OK"

        card = tk.Frame(parent, bg=C["surface"], padx=28, pady=24,
                        highlightbackground=C["outline_variant"], highlightthickness=1)
        card.pack(expand=True, padx=60, pady=40, fill="both")

        tk.Label(card, text="📊  Cobertura del PDF",
                 font=("Segoe UI", 16, "bold"), fg=C["primary"], bg=C["surface"]).pack(anchor="w", pady=(0, 16))

        metrics = tk.Frame(card, bg=C["surface"])
        metrics.pack(fill="x", pady=(0, 16))

        def _metric_row(parent, label, value, value_fg):
            row = tk.Frame(parent, bg=C["surface_low"], padx=14, pady=8)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label, font=("Segoe UI", 9, "bold"),
                     fg=C["secondary"], bg=C["surface_low"], width=28, anchor="w").pack(side="left")
            tk.Label(row, text=str(value), font=("Segoe UI", 11, "bold"),
                     fg=value_fg, bg=C["surface_low"]).pack(side="left")

        _metric_row(metrics, "Total páginas del PDF",     f"{pdf_total}",  C["tertiary"])
        _metric_row(metrics, "Máximo de páginas requerido", f"{max_req}",   C["tertiary"])
        diff_fg = C["success"] if ok else C["error"]
        diff_sign = "+" if diff > 0 else ""
        _metric_row(metrics, "Diferencia", f"{diff_sign}{diff}", diff_fg)

        estado_fg = C["success"] if ok else C["error"]
        estado_text = "✅  OK — El PDF cubre todas las páginas requeridas" if ok else "❌  INSUFICIENTE — Faltan páginas en el PDF"
        row = tk.Frame(metrics, bg=C["surface_low"], padx=14, pady=8)
        row.pack(fill="x", pady=3)
        tk.Label(row, text="Estado", font=("Segoe UI", 9, "bold"),
                 fg=C["secondary"], bg=C["surface_low"], width=28, anchor="w").pack(side="left")
        tk.Label(row, text=estado_text, font=("Segoe UI", 11, "bold"),
                 fg=estado_fg, bg=C["surface_low"]).pack(side="left")

        tk.Frame(card, bg=C["outline_variant"], height=1).pack(fill="x", pady=8)
        bar_frame = tk.Frame(card, bg=C["surface"])
        bar_frame.pack(fill="x", pady=8)

        pct = int(min(max_req / max(pdf_total, 1), 1.0) * 100)
        tk.Label(bar_frame, text=f"Cobertura: {pct}%",
                 font=("Segoe UI", 9, "bold"), fg=C["primary"], bg=C["surface"]).pack(anchor="w", pady=(0, 4))

        bar_bg = tk.Frame(bar_frame, bg=C["surface_low"], height=12,
                          highlightbackground=C["outline_variant"], highlightthickness=1)
        bar_bg.pack(fill="x")
        bar_color = C["success"] if ok else C["error"]
        bar_fill = tk.Frame(bar_bg, bg=bar_color, height=12)
        bar_fill.place(relwidth=pct / 100.0, relheight=1)

        if not ok:
            err = res.errores[0] if res.errores else None
            if err:
                tk.Frame(card, bg=C["outline_variant"], height=1).pack(fill="x", pady=8)
                msg_frame = tk.Frame(card, bg=C["error_bg_alt"], padx=14, pady=10,
                                     highlightbackground=C["error_border"], highlightthickness=1)
                msg_frame.pack(fill="x", pady=8)
                tk.Label(msg_frame, text="⚠️  " + err.descripcion,
                         font=("Segoe UI", 9), fg=C["error"], bg=C["error_bg_alt"],
                         wraplength=600, justify="left").pack(anchor="w")
        elif diff > 0:
            tk.Frame(card, bg=C["outline_variant"], height=1).pack(fill="x", pady=8)
            msg_frame = tk.Frame(card, bg=C["success_msg_bg"], padx=14, pady=10,
                                 highlightbackground=C["success_msg_border"], highlightthickness=1)
            msg_frame.pack(fill="x", pady=8)
            tk.Label(msg_frame, text=f"ℹ️  El PDF tiene {diff} página(s) extra después del último folio del inventario.",
                     font=("Segoe UI", 9), fg=C["success_msg_text"], bg=C["success_msg_bg"],
                     wraplength=600, justify="left").pack(anchor="w")
