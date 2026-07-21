"""
Header.py — Barra superior de navegación del Escritorio del Archivista.
Contiene: logo, título, botón Vista Dual y avatar/configuración.
"""
import tkinter as tk
import os
from utils.theme import C
from adapters.services import add_hover_effect

try:
    from PIL import Image, ImageTk
    PIL_OK = True
except ImportError:
    PIL_OK = False


class Header(tk.Frame):
    """
    Barra superior fija de la aplicación.
    Altura: adaptativa (mín 56px) | Fondo: surface_container
    """

    def __init__(self, parent, app_state, on_toggle_dual_view, **kwargs):
        self.on_edit_pdf = kwargs.pop("on_edit_pdf", None)
        super().__init__(parent, **kwargs)
        self.app_state = app_state
        self.on_toggle_dual_view = on_toggle_dual_view
        self._dual_active = tk.BooleanVar(value=True)

        self.configure(
            bg=C["surface_container"],
            bd=0,
            relief="flat",
        )
        self._build()

    # ── Construcción ────────────────────────────────────────────────────────────
    def _build(self):
        sep = tk.Frame(self, bg=C["outline_variant"], height=1)
        sep.pack(side="bottom", fill="x")

        # ── Izquierda: Logo + Título ────────────────────────────────────────────
        left = tk.Frame(self, bg=C["surface_container"])
        left.pack(side="left", padx=(16, 0), pady=8)

        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "LogoARA.png")
        self._logo_photo = None
        if PIL_OK and os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                img = img.resize((32, 32), Image.LANCZOS)
                self._logo_photo = ImageTk.PhotoImage(img)
            except Exception:
                self._logo_photo = None

        if self._logo_photo:
            logo_lbl = tk.Label(left, image=self._logo_photo, bg=C["surface_container"])
            logo_lbl.pack(side="left", padx=(0, 10))
        else:
            icon_box = tk.Frame(left, bg=C["primary"], width=32, height=32)
            icon_box.pack(side="left", padx=(0, 10))
            icon_box.pack_propagate(False)
            tk.Label(
                icon_box, text="✦", fg=C["on_primary"], bg=C["primary"],
                font=("Segoe UI", 14, "bold")
            ).place(relx=0.5, rely=0.5, anchor="center")

        title_frame = tk.Frame(left, bg=C["surface_container"])
        title_frame.pack(side="left")

        tk.Label(
            title_frame,
            text="Fragmentador de PDFs Históricos",
            font=("Segoe UI", 13, "bold"),
            fg=C["primary"],
            bg=C["surface_container"],
        ).pack(anchor="w")

        tk.Label(
            title_frame,
            text="Escritorio del Archivista",
            font=("Segoe UI", 8),
            fg=C["secondary"],
            bg=C["surface_container"],
        ).pack(anchor="w")

        # ── Derecha: Acciones ───────────────────────────────────────────────────
        right = tk.Frame(self, bg=C["surface_container"])
        right.pack(side="right", padx=16, pady=8)

        self._dual_btn = tk.Button(
            right,
            text="⊟  Vista Dual",
            font=("Segoe UI", 9),
            fg=C["primary"],
            bg=C["surface_low"],
            activebackground=C["secondary_container"],
            activeforeground=C["primary"],
            relief="flat",
            bd=0,
            padx=10, pady=4,
            cursor="hand2",
            command=self._toggle_dual,
        )
        self._dual_btn.pack(side="left", padx=(0, 4))
        add_hover_effect(self._dual_btn, C["secondary_container"], C["surface_low"])

        if self.on_edit_pdf:
            self._edit_pdf_btn = tk.Button(
                right,
                text="✎  Editar PDF",
                font=("Segoe UI", 9),
                fg=C["white"],
                bg=C["warning"],
                activebackground=C["warning_dark"],
                activeforeground=C["white"],
                relief="flat",
                bd=0,
                padx=10, pady=4,
                cursor="hand2",
                command=self.on_edit_pdf,
            )
            self._edit_pdf_btn.pack(side="left", padx=(0, 8))
            add_hover_effect(self._edit_pdf_btn, C["warning_dark"], C["warning"])

        cfg_btn = tk.Button(
            right,
            text="⚙",
            font=("Segoe UI", 13),
            fg=C["secondary"],
            bg=C["surface_container"],
            activebackground=C["surface_high"],
            relief="flat", bd=0,
            padx=6, pady=2,
            cursor="hand2",
            command=self._open_settings,
        )
        cfg_btn.pack(side="left", padx=(0, 8))

        avatar = tk.Label(
            right,
            text="AR",
            font=("Segoe UI", 9, "bold"),
            fg=C["white"],
            bg=C["primary_container"],
            width=3, height=1,
            padx=4, pady=4,
        )
        avatar.pack(side="left")
        avatar.configure(relief="flat")

    # ── Acciones ────────────────────────────────────────────────────────────────
    def _toggle_dual(self):
        self._dual_active.set(not self._dual_active.get())
        if self._dual_active.get():
            self._dual_btn.configure(text="⊟  Vista Dual")
        else:
            self._dual_btn.configure(text="⊞  Vista Dual")
        self.on_toggle_dual_view(self._dual_active.get())

    # ── Helpers ─────────────────────────────────────────────────────────────────
    def _open_settings(self):
        from tkinter import messagebox
        messagebox.showinfo("Configuración", "Panel de configuración próximamente disponible.")
