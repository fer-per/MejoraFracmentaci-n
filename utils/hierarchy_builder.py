"""
hierarchy_builder.py — Generador de la Jerarquía Estricta de 11 Niveles.

Construye rutas físicas sanitizadas en Windows previniendo colisiones de archivos.
Implementa los 11 niveles especificados:
1. ACERVO DOCUMENTAL NUMERO {num_acervo}
2. SIGLO {siglo}
3. FONDO DOCUMENTAL
4. {escribano}
5. {año}
6. PROTOCOLO {protocolo}
7. REGISTRO {registro_id}
8. {titulo_estandar}
9. {mes}
10. {primer_interesado_1}
11. {primer_interesado_2}.pdf
"""
import os
import re
from typing import Tuple

# Mapeo de números romanos a números arábigos de siglos comunes
ROMAN_TO_ARABIC = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17, "XVIII": 18,
    "XIX": 19, "XX": 20, "XXI": 21
}

MESES_NOMBRES = {
    1: "1. ENERO",
    2: "2. FEBRERO",
    3: "3. MARZO",
    4: "4. ABRIL",
    5: "5. MAYO",
    6: "6. JUNIO",
    7: "7. JULIO",
    8: "8. AGOSTO",
    9: "9. SEPTIEMBRE",
    10: "10. OCTUBRE",
    11: "11. NOVIEMBRE",
    12: "12. DICIEMBRE"
}

def sanitize_name(name: str) -> str:
    """Elimina caracteres inválidos para rutas físicas en sistemas de archivos (Windows)."""
    if not name:
        return "SIN_NOMBRE"
    # Reemplazar caracteres reservados de Windows por guion bajo
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', name.strip())
    # Quitar múltiples guiones bajos o espacios
    sanitized = re.sub(r'\s+', ' ', sanitized)
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized.strip()

def RomanToSigloArabic(roman_str: str) -> int:
    """Convierte un siglo romano (ej: XVI) a arábigo (16)."""
    roman_str = roman_str.upper().strip()
    return ROMAN_TO_ARABIC.get(roman_str, 19) # Default siglo XIX (19) si falla

def build_11_level_path(record, app_state, base_dir: str) -> str:
    """
    Construye la ruta de 11 niveles para un InventoryRecord.
    Usa los metadatos extraídos del Excel real.
    """
    # ── NIVEL 1: ACERVO DOCUMENTAL NUMERO {num_acervo}
    acervo_num = getattr(app_state, 'acervo_num', None) or "7"
    nivel1 = f"ACERVO DOCUMENTAL NUMERO {sanitize_name(acervo_num)}"

    # ── Determinar año y mes a partir de fecha_inicio (ej: "15/03/1891")
    fecha_ini = getattr(record, 'fecha_inicio', "")
    anio_extraido = None
    mes_index = 1

    if fecha_ini:
        # Intentar parsear "d/m/yyyy" o "yyyy-mm-dd"
        match_f = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', fecha_ini)
        if match_f:
            anio_extraido = int(match_f.group(3))
            mes_index = int(match_f.group(2))
        else:
            # Intentar yyyy-mm-dd
            match_f2 = re.search(r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})', fecha_ini)
            if match_f2:
                anio_extraido = int(match_f2.group(1))
                mes_index = int(match_f2.group(2))
            else:
                # Buscar cualquier número de 4 dígitos para el año
                match_a = re.search(r'(\d{4})', fecha_ini)
                if match_a:
                    anio_extraido = int(match_a.group(1))

    # Si no se pudo obtener, usar fallback a partir del registro (ej: "1891-001")
    if anio_extraido is None:
        anio_extraido = 1891
        match_reg = re.search(r'(\d{4})', record.registro)
        if match_reg:
            anio_extraido = int(match_reg.group(1))

    # ── NIVEL 2: SIGLO {siglo_arabigo}
    siglo_num = (anio_extraido // 100) + 1
    nivel2 = f"SIGLO {siglo_num}"

    # ── NIVEL 3: FONDO DOCUMENTAL (Texto constante)
    nivel3 = "FONDO DOCUMENTAL"

    # ── NIVEL 4: {escribano}
    nivel4 = sanitize_name(record.escribano)

    # ── NIVEL 5: {año}
    nivel5 = str(anio_extraido)

    # ── NIVEL 6: PROTOCOLO {protocolo}
    nivel6 = f"PROTOCOLO {sanitize_name(record.protocolo)}"

    # ── NIVEL 7: REGISTRO {registro_id}
    nivel7 = f"REGISTRO {sanitize_name(record.id.replace('#', ''))}"

    # ── NIVEL 8: {titulo_estandar}
    t = record.titulo.lower()
    if "compraventa" in t:
        titulo_estandar = "COMPRAVENTA"
    elif "testamento" in t:
        titulo_estandar = "TESTAMENTO"
    elif "poder" in t:
        titulo_estandar = "PODER_NOTARIAL"
    elif "arrendamiento" in t:
        titulo_estandar = "ARRENDAMIENTO"
    elif "hipoteca" in t:
        titulo_estandar = "HIPOTECA"
    else:
        titulo_estandar = "ESCRITURA_VARIAS"
    nivel8 = sanitize_name(titulo_estandar)

    # ── NIVEL 9: {mes}
    nivel9 = MESES_NOMBRES.get(mes_index, "1. ENERO")

    # ── NIVEL 10 y 11: {primer_interesado_1} y {primer_interesado_2}
    int1 = getattr(record, 'interesado1', "").strip()
    int2 = getattr(record, 'interesado2', "").strip()

    interesado_1 = int1 if int1 else f"Interesado_A_{record.id.replace('#', '')}"
    interesado_2 = int2 if int2 else f"Interesado_B_{record.id.replace('#', '')}"

    nivel10 = sanitize_name(interesado_1)
    file_name = f"{sanitize_name(interesado_2)}.pdf"

    # Unir todo
    dir_path = os.path.join(base_dir, nivel1, nivel2, nivel3, nivel4, nivel5, nivel6, nivel7, nivel8, nivel9, nivel10)
    full_path = os.path.join(dir_path, file_name)

    # ── Manejo de colisiones
    if os.path.exists(full_path):
        base, ext = os.path.splitext(file_name)
        counter = 2
        while True:
            new_file_name = f"{base}_{counter}{ext}"
            new_full_path = os.path.join(dir_path, new_file_name)
            if not os.path.exists(new_full_path):
                full_path = new_full_path
                break
            counter += 1

    return full_path
