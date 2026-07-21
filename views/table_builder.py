"""
views/table_builder.py — Constructor de tablas y panel de estadísticas
extraído de ExpandedAnalyzerView.
"""
import tkinter as tk
from tkinter import ttk

from adapters.services import make_treeview_sortable, configure_treeview_style
from domain.models import EstadoRecord
from utils.theme import C


ESTADO_CONFIG = {
    "VALIDADO":   {"bg": "#dbeafe", "fg": "#1e3a5f"},
    "REVISAR":    {"bg": "#fee2e2", "fg": "#7f1d1d"},
    "FRAGMENTADO":{"bg": "#d1fae5", "fg": "#064e3b"},
    "SALTO":      {"bg": "#fee2e2", "fg": "#7f1d1d"},
    "OCR PENDIENTE": {"bg": "#fef9c3", "fg": "#713f12"},
}


class AnalysisTableBuilder:
    """Construye y administra la tabla de análisis y su panel de estadísticas."""

    def __init__(self, app_state):
        self.app_state = app_state
        self._tree = None

    @property
    def tree(self):
        return self._tree

    def build(self, parent, tab, records, error_ids, showing_errors, on_row_select):
        for w in parent.winfo_children():
            w.destroy()

        container = tk.Frame(parent, bg=C["background"])
        container.pack(fill="both", expand=True)

        vsb = tk.Scrollbar(container, orient="vertical")
        vsb.pack(side="right", fill="y")
        hsb = tk.Scrollbar(container, orient="horizontal")
        hsb.pack(side="bottom", fill="x")

        configure_treeview_style(
            "Archivista.Treeview",
            bg_color=C["surface"],
            fg_color=C["tertiary"],
            field_bg=C["surface"],
            row_height=32,
            selected_bg="#f0e8ec",
        )

        base_cols = ("Fila", "Registro", "Escribano", "Protocolo", "Folios", "Pág.PDF", "Título")
        if tab == "topica":
            cols = base_cols + ("Data Tópica", "Estado")
        elif tab == "cronica":
            cols = base_cols + ("Data Crónica", "Estado")
        else:
            cols = base_cols + ("Estado",)

        self._tree = ttk.Treeview(
            container,
            columns=cols,
            show="headings",
            style="Archivista.Treeview",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            selectmode="browse",
        )
        vsb.configure(command=self._tree.yview)
        hsb.configure(command=self._tree.xview)

        col_widths = {
            "Fila": 50, "Registro": 90, "Escribano": 140,
            "Protocolo": 70, "Folios": 90, "Pág.PDF": 70,
            "Título": 100, "Data Tópica": 100, "Data Crónica": 100, "Estado": 100,
        }
        for col in cols:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=col_widths.get(col, 100), anchor="w", minwidth=50)

        self._tree.tag_configure("even", background=C["surface_low"])
        self._tree.tag_configure("odd", background=C["surface"])
        self._tree.tag_configure("revisar", background="#fff0f0")
        self._tree.tag_configure("fragmentado", background="#f0fff4")

        self.populate(self.app_state.records, tab, error_ids, showing_errors)
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<<TreeviewSelect>>", on_row_select)
        self._tree.bind("<MouseWheel>", lambda e: self._tree.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        for col in cols:
            self._tree.heading(col, command=lambda c=col: make_treeview_sortable(self._tree, c, "_sort_reverse"))

        return self._tree

    def populate(self, records, tab, error_ids, showing_errors):
        if self._tree is None:
            return

        for item in self._tree.get_children():
            self._tree.delete(item)

        visible_idx = 0
        for i, r in enumerate(records):
            if showing_errors and r.id not in error_ids:
                continue

            estado_icon = {
                "": "",
                "REVISAR": "⚠️",
                "FRAGMENTADO": "📎"
            }.get(r.estado, "")
            tag = r.estado.lower() if r.estado in ("revisar", "fragmentado") else ("even" if visible_idx % 2 == 0 else "odd")

            f_ini = getattr(r, "fecha_inicio", "")
            f_fin = getattr(r, "fecha_fin", "")
            vals = [r.fila, r.registro, r.escribano, r.protocolo, r.folios, r.pg_pdf, r.titulo]

            if tab == "topica":
                vals.append(r.titulo)
            elif tab == "cronica":
                cronica_str = f"{f_ini} - {f_fin}" if (f_ini or f_fin) else "S/D"
                vals.append(cronica_str)

            disp_estado = f"{estado_icon} {r.estado}".strip()
            vals.append(disp_estado)

            self._tree.insert("", "end", iid=r.id, values=tuple(vals), tags=(tag,))
            visible_idx += 1

    def build_stats(self, parent, on_open_correction, on_open_jump, on_export):
        panel = tk.Frame(
            parent,
            bg=C["surface"],
            padx=12, pady=8,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )

        panel.columnconfigure(0, weight=3)
        panel.columnconfigure(1, weight=3)
        panel.columnconfigure(2, weight=2)
        panel.rowconfigure(0, weight=1)

        left_block = tk.Frame(panel, bg=C["surface"])
        left_block.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        tk.Label(
            left_block, text="📊 Resumen de Calidad",
            font=("Segoe UI", 8, "bold"),
            fg=C["primary"], bg=C["surface"],
        ).pack(anchor="w", pady=(0, 4))

        self._chips_row = tk.Frame(left_block, bg=C["surface"])
        self._chips_row.pack(fill="x")

        self._total_processed_lbl = tk.Label(
            left_block,
            text="",
            font=("Segoe UI", 7, "italic"),
            fg=C["secondary"], bg=C["surface"],
        )
        self._total_processed_lbl.pack(anchor="w", pady=(2, 0))

        center_block = tk.Frame(panel, bg=C["surface"])
        center_block.grid(row=0, column=1, sticky="nsew", padx=10)

        self._integrity_title_lbl = tk.Label(
            center_block,
            text="",
            font=("Segoe UI", 8, "bold"),
            fg=C["primary"], bg=C["surface"],
        )
        self._integrity_title_lbl.pack(anchor="w")

        self._bar_bg = tk.Frame(center_block, bg=C["surface_low"], height=8,
                          highlightbackground=C["outline_variant"], highlightthickness=1)
        self._bar_bg.pack(fill="x", pady=6)

        self._bar_fill = tk.Frame(self._bar_bg, bg="#1a5c2e", height=8)
        self._bar_fill.place(relwidth=0.0, relheight=1)

        right_block = tk.Frame(panel, bg=C["surface"])
        right_block.grid(row=0, column=2, sticky="nsew", padx=(10, 0))

        self._correction_label = tk.Label(
            right_block,
            text="Selecciona fila\ncon alerta para corregir",
            font=("Segoe UI", 7),
            fg=C["outline"],
            bg=C["surface"],
            justify="center",
            width=22,
        )
        self._correction_label.pack(side="left", padx=8)

        self._correction_btn = tk.Button(
            right_block,
            text="🔧 Corregir",
            font=("Segoe UI", 8, "bold"),
            fg="#ffffff",
            bg=C["secondary"],
            activebackground=C["primary"],
            activeforeground="#ffffff",
            relief="flat", bd=0,
            cursor="hand2",
            padx=10, pady=4,
            state="disabled",
            command=on_open_correction,
        )
        self._correction_btn.pack(side="left", padx=4)

        self._jump_btn = tk.Button(
            right_block,
            text="⬆ Registrar Salto",
            font=("Segoe UI", 8, "bold"),
            fg="#ffffff",
            bg="#b45309",
            activebackground="#92400e",
            activeforeground="#ffffff",
            relief="flat", bd=0,
            cursor="hand2",
            padx=10, pady=4,
            state="disabled",
            command=on_open_jump,
        )
        self._jump_btn.pack(side="left", padx=4)

        tk.Button(
            right_block,
            text="⬇️ Exportar (.xlsx)",
            font=("Segoe UI", 8, "bold"),
            fg=C["primary"],
            bg=C["surface_low"],
            activebackground=C["secondary_container"],
            relief="flat", bd=0,
            cursor="hand2",
            padx=10, pady=4,
            command=on_export,
        ).pack(side="left", padx=4)

        self.update_stats()

        return panel

    def update_stats(self):
        if not hasattr(self, "_chips_row") or not self._chips_row:
            return

        stats = self._calc_stats()

        for w in self._chips_row.winfo_children():
            w.destroy()

        stat_items = [
            ("✅ Sin Alertas",  stats["validados"],   "#1a5c2e", "#d1fae5"),
            ("⚠️ Alertas",     stats["revisar"],     "#92400e", "#fef3c7"),
            ("❌ Errores",      stats["errores"],     "#7f1d1d", "#fee2e2"),
            ("📎 Fragmentados", stats["fragmentados"], "#1e3a5f", "#dbeafe"),
        ]

        for idx, (label, value, fg, bg) in enumerate(stat_items):
            chip = tk.Frame(self._chips_row, bg=C["surface"], padx=2)
            chip.grid(row=0, column=idx, sticky="ew")
            self._chips_row.columnconfigure(idx, weight=1)

            tk.Label(
                chip, text=f"{label}: {value}",
                font=("Segoe UI", 8, "bold"),
                fg=fg, bg=bg,
                padx=6, pady=2,
                highlightbackground=C["outline_variant"],
                highlightthickness=1,
            ).pack(fill="x")

        total = len(self.app_state.records)
        self._total_processed_lbl.configure(text=f"Total: {total} registros procesados")

        pct = int(stats["validados"] / max(total, 1) * 100)
        self._integrity_title_lbl.configure(text=f"Integridad de Foliación: {pct}%")
        self._bar_fill.place(relwidth=pct / 100.0, relheight=1)

    def _calc_stats(self) -> dict:
        records = self.app_state.records
        correctos = sum(1 for r in records if r.estado in ("", EstadoRecord.FRAGMENTADO))
        revisar = sum(1 for r in records if r.estado == EstadoRecord.REVISAR)
        fragmentados = sum(1 for r in records if r.estado == EstadoRecord.FRAGMENTADO)
        return {
            "validados":    correctos,
            "revisar":      revisar,
            "errores":      revisar,
            "fragmentados": fragmentados,
        }

    def update_correction_label(self, record, suggestion):
        if suggestion:
            self._correction_label.configure(text=f"Alerta ({suggestion.tipo_error})", fg=C["primary"])
            self._correction_btn.configure(state="normal", bg=C["primary"])
        else:
            self._correction_label.configure(text=f"Registro valido:\n{record.estado}", fg="#1a5c2e")
            self._correction_btn.configure(state="disabled", bg=C["secondary"])

    def update_jump_button(self, has_salto):
        self._jump_btn.configure(
            state="normal" if has_salto else "disabled",
            bg="#b45309" if has_salto else C["secondary"],
        )

    def update_toggle_button_state(self, analysis_done, error_ids, showing_errors, toggle_btn):
        if not analysis_done:
            toggle_btn.configure(
                state="disabled",
                text="  ⚠ Mostrar solo errores  ",
                bg=C["surface_low"], fg=C["primary"],
                activebackground=C["secondary_container"],
            )
        elif len(error_ids) == 0:
            toggle_btn.configure(
                state="disabled",
                text="  ✅ Analizador correcto  ",
                bg="#1a5c2e", fg="#ffffff",
                activebackground="#14532d",
            )
        elif showing_errors:
            toggle_btn.configure(
                state="normal",
                text="  ↩ Regresar a toda la lista  ",
                bg="#d44040", fg="#ffffff",
                activebackground="#b33030",
            )
        else:
            toggle_btn.configure(
                state="normal",
                text="  ⚠ Mostrar solo errores  ",
                bg=C["surface_low"], fg=C["primary"],
                activebackground=C["secondary_container"],
            )
