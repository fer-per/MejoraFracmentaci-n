"""Diagnóstico detallado: ¿por qué no se actualiza el scroll con go_to_page?"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

import tkinter as tk
from components.PDFPreview import PDFPreview
from project_types import AppState

root = tk.Tk()
root.geometry("500x700")
root.update_idletasks()
root.update()

state = AppState()
preview = PDFPreview(root, app_state=state)
preview.pack(fill="both", expand=True)
root.update_idletasks()
root.update()

pdf_path = os.path.join(os.path.dirname(__file__), "test_doc.pdf")
preview.load_pdf(pdf_path)
root.update_idletasks()
root.update()
preview._do_lazy_render()
root.update()

print("=== DIAGNÓSTICO DE SCROLL ===")

# Ver estado inicial del scroll
def show_scroll_state(msg):
    sb = preview._scrollbar.get()
    vr = preview._get_visible_page_range()
    y = preview._canvas.yview()
    print(f"  [{msg}] scrollbar={sb}, canvas.yview={y}")
    if vr:
        print(f"         rango_visible={vr}, images={sorted(preview._page_images.keys())}")
    print(f"         pages_frame height={preview._pages_frame.winfo_height()}")
    print(f"         total_pdf_pages={preview._total_pdf_pages}")

show_scroll_state("inicial")

# Probar yview_moveto directo
print("\n--- yview_moveto(0.0) ---")
preview._canvas.yview_moveto(0.0)
root.update_idletasks()
root.update()
show_scroll_state("despues de yview_moveto(0.0)")

print("\n--- yview_moveto(0.75) ---")
preview._canvas.yview_moveto(0.75)
root.update_idletasks()
root.update()
show_scroll_state("despues de yview_moveto(0.75)")

# Ver si _scroll_to_page funciona
print("\n--- _scroll_to_page(9) directo ---")
preview._scroll_to_page(9)
root.update_idletasks()
root.update()
time.sleep(0.15)
root.update()
show_scroll_state("despues de _scroll_to_page(9)")

# Volver al inicio
print("\n--- _scroll_to_page(0) directo ---")
preview._scroll_to_page(0)
root.update_idletasks()
root.update()
time.sleep(0.15)
root.update()
show_scroll_state("despues de _scroll_to_page(0)")

# Probar go_to_page
print("\n--- go_to_page(8) ---")
preview.go_to_page(8)
root.update_idletasks()
root.update()
time.sleep(0.3)
root.update()
show_scroll_state("despues de go_to_page(8)")

# Verificar el bbox
print("\n--- BBOX ---")
print(f"  canvas.bbox('all'): {preview._canvas.bbox('all')}")
print(f"  scrollregion: {preview._canvas.cget('scrollregion')}")

root.destroy()
