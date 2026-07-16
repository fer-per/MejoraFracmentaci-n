"""
table_helpers.py — Funciones auxiliares compartidas para tablas Treeview.
Búsqueda, filtros, ordenamiento y selección de filas.
"""
import tkinter as tk
from tkinter import ttk


def add_search_bar(parent, tree, columns, on_filter=None, **kwargs):
    """
    Agrega una barra de búsqueda sobre un Treeview.
    Filtra filas en tiempo real por cualquier columna.
    """
    search_frame = tk.Frame(parent, bg=kwargs.get("bg", "#fcf9f8"))
    search_frame.pack(fill="x", padx=kwargs.get("padx", 0), pady=kwargs.get("pady", (0, 4)))

    tk.Label(
        search_frame, text="🔍",
        font=("Segoe UI", 10),
        bg=kwargs.get("bg", "#fcf9f8"),
        fg=kwargs.get("fg", "#7c535d"),
    ).pack(side="left", padx=(0, 4))

    search_var = tk.StringVar()
    search_entry = tk.Entry(
        search_frame,
        textvariable=search_var,
        font=("Segoe UI", 9),
        fg="#32131c",
        bg="#ffffff",
        relief="flat", bd=0,
        highlightbackground="#e0bfbf",
        highlightthickness=1,
    )
    search_entry.pack(side="left", fill="x", expand=True, ipady=3)

    def _apply_filter(*args):
        query = search_var.get().lower().strip()
        _filter_tree(tree, columns, query)
        if on_filter:
            on_filter(query)

    search_var.trace_add("write", _apply_filter)
    return search_frame, search_var


def _filter_tree(tree, columns, query):
    """Filtra las filas del Treeview según la query de búsqueda."""
    for item in tree.get_children():
        values = tree.item(item, "values")
        if query == "":
            tree.item(item, tags=tree.item(item, "tags"))
            # Show all items by re-inserting (hidden items need unhide)
            continue
        match = any(query in str(v).lower() for v in values)
        if not match:
            tree.detach(item)
        else:
            # Re-attach detached items
            try:
                tree.reattach(item, "", "end")
            except Exception:
                pass

    # For items not detached, ensure they're visible
    if query == "":
        # Re-attach all detached items
        for item in tree.detach():
            tree.reattach(item, "", "end")


def make_sortable(tree, columns, reverse_map=None):
    """
    Hace que las columnas de un Treeview sean clickeables para ordenar.
    reverse_map: dict opcional {col_name: bool} para controlar dirección inicial.
    """
    if reverse_map is None:
        reverse_map = {}

    def _sort_column(col, reverse):
        data = [(tree.set(child, col), child) for child in tree.get_children("")]

        # Intentar orden numérico si todos son números
        try:
            data.sort(key=lambda t: int(t[0]), reverse=reverse)
        except (ValueError, TypeError):
            data.sort(key=lambda t: t[0], reverse=reverse)

        for index, (val, child) in enumerate(data):
            tree.move(child, "", index)

        # Toggle direction for next click
        tree.heading(col, command=lambda: _sort_column(col, not reverse))

    for col in columns:
        heading = tree.heading(col)
        old_cmd = heading.get("command", "")
        tree.heading(col, command=lambda c=col: _sort_column(c, reverse_map.get(c, False)))


def navigate_to_record(tree, records, record_id, on_navigate_pdf=None):
    """
    Navega a un registro en la tabla y opcionalmente al PDF.
    Función centralizada reemplazando _on_row_select duplicado.
    """
    record = next((r for r in records if r.id == record_id), None)
    if record and record.pg_pdf and on_navigate_pdf:
        try:
            first_page = int(str(record.pg_pdf).split('-')[0].strip())
            on_navigate_pdf(first_page)
        except (ValueError, IndexError):
            pass
    return record
