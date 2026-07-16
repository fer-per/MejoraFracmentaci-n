"""
PlaceholderView.py — Vista de marcador de posición para secciones próximamente implementadas
como Soporte y Documentación.
"""
import tkinter as tk

from utils.theme import C, FONT


class PlaceholderView(tk.Frame):
    """Vista genérica para módulos en desarrollo o documentación."""

    def __init__(self, parent, app_state, on_add_log, title="Módulo en Desarrollo", description="Esta sección estará disponible próximamente.", **kwargs):
        super().__init__(parent, **kwargs)
        self.app_state = app_state
        self.on_add_log = on_add_log
        self.title = title
        self.description = description
        self.configure(bg=C["background"])
        self._build()

    def _build(self):
        # Contenedor centrado
        card = tk.Frame(
            self,
            bg=C["surface"],
            padx=40, pady=40,
            highlightbackground=C["outline_variant"],
            highlightthickness=1,
        )
        card.place(relx=0.5, rely=0.5, anchor="center")

        # Icono o símbolo decorativo
        tk.Label(
            card,
            text="⏳",
            font=("Segoe UI", 48),
            bg=C["surface"],
        ).pack(pady=(0, 16))

        # Título
        tk.Label(
            card,
            text=self.title,
            font=("Segoe UI", 16, "bold"),
            fg=C["primary"],
            bg=C["surface"],
        ).pack(pady=(0, 8))

        # Descripción
        tk.Label(
            card,
            text=self.description,
            font=("Segoe UI", 10),
            fg=C["secondary"],
            bg=C["surface"],
            justify="center",
            wraplength=350,
        ).pack()

        # Botón sutil
        tk.Frame(card, bg=C["outline_variant"], height=1).pack(fill="x", pady=20)

        tk.Label(
            card,
            text="Escritorio del Archivista v2.1.4",
            font=("Courier New", 8),
            fg=C["secondary"],
            bg=C["surface"],
        ).pack()
