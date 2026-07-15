"""
main.py — Punto de entrada del Escritorio del Archivista.
Configura la ventana principal y lanza la aplicación.
"""
import tkinter as tk
import sys
import os

# Asegurar que el directorio raíz esté en el path
sys.path.insert(0, os.path.dirname(__file__))

from App import App


def main():
    root = tk.Tk()
    root.title("Escritorio del Archivista — Fragmentador de PDFs Históricos")
    root.geometry("1400x820")
    root.minsize(1100, 650)

    # Intentar maximizar la ventana en Windows
    try:
        root.state("zoomed")
    except Exception:
        pass

    # Color de fondo base
    root.configure(bg="#fcf9f8")

    # Icono de la aplicación (si existe)
    try:
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass

    # Escalar DPI en Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    # Montar la aplicación
    app = App(root)
    app.pack(fill="both", expand=True)

    # Manejar cierre limpio con Ctrl+C o botón X
    def _on_close():
        root.quit()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        _on_close()


if __name__ == "__main__":
    main()
