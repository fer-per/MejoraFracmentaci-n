"""
theme.py — Paleta de colores y tipografía centralizada del Escritorio del Archivista.
Todas las vistas y componentes deben importar C y FONT de aquí.
"""

C = {
    "primary":             "#570013",
    "primary_container":   "#800020",
    "on_primary":          "#ff828a",
    "background":          "#fcf9f8",
    "surface":             "#ffffff",
    "surface_low":         "#f6f3f2",
    "surface_container":   "#f0edec",
    "surface_high":        "#eae7e7",
    "surface_highest":     "#e5e2e1",
    "outline":             "#8c7071",
    "outline_variant":     "#e0bfbf",
    "tertiary":            "#32131c",
    "on_tertiary":         "#e5e1df",
    "secondary":           "#7c535d",
    "secondary_container": "#ffc9d5",
    "parchment":           "#f4ece1",

    # Common
    "white":               "#ffffff",
    "black":               "#000000",

    # Success / validated
    "success":             "#1a5c2e",
    "success_dark":        "#14532d",
    "success_bg":          "#d1fae5",
    "success_text":        "#064e3b",
    "success_msg_bg":      "#f0fdf4",
    "success_msg_border":  "#bbf7d0",
    "success_msg_text":    "#166534",

    # Error / review
    "error":               "#b91c1c",
    "error_dark":          "#991b1b",
    "error_text":          "#7f1d1d",
    "error_bg":            "#fee2e2",
    "error_bg_alt":        "#fef2f2",
    "error_border":        "#fecaca",
    "error_light":         "#fff0f0",

    # Danger (buttons)
    "danger":              "#d44040",
    "danger_dark":         "#b33030",
    "danger_text":         "#a03030",

    # Warning / jumps
    "warning":             "#b45309",
    "warning_dark":        "#92400e",
    "warning_text":        "#713f12",
    "warning_bg":          "#fef3c7",
    "warning_bg_alt":      "#fef9c3",

    # Info / primary blue
    "info":                "#1e3a5f",
    "info_dark":           "#112233",
    "info_bg":             "#dbeafe",

    # Fragmentado state
    "fragmentado_bg":      "#f0fff4",

    # Selection
    "selected_bg":         "#f0e8ec",

    # Console log tags
    "log_info":            "#a8c4d4",
    "log_warn":            "#f5a742",
    "log_success":         "#4cde7e",

    # Parchment decoration
    "parchment_outer":     "#d4c9b8",
    "parchment_border":    "#c8b89a",
    "parchment_line1":     "#9b8b7a",
    "parchment_line2":     "#8a7a6a",
    "parchment_line3":     "#7a6a5a",
}

FONT = {
    "title_lg":     ("Segoe UI", 18, "bold"),
    "title_md":     ("Segoe UI", 13, "bold"),
    "subtitle":     ("Segoe UI", 10, "bold"),
    "body":         ("Segoe UI", 9),
    "body_sm":      ("Segoe UI", 8),
    "body_xs":      ("Segoe UI", 7),
    "mono":         ("Courier New", 8),
    "mono_sm":      ("Courier New", 7),
    "mono_bold":    ("Courier New", 10, "bold"),
    "mono_lg":      ("Courier New", 14, "bold"),
    "button":       ("Segoe UI", 9, "bold"),
    "button_lg":    ("Segoe UI", 11, "bold"),
    "icon":         ("Segoe UI", 14),
    "icon_lg":      ("Segoe UI", 22),
    "icon_xl":      ("Segoe UI", 48),
}
