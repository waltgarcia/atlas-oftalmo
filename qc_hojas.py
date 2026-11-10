# -*- coding: utf-8 -*-
"""Hoja de contacto para revisar de un vistazo qué imágenes no corresponden."""
import os, sqlite3
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "atlas.db")
SAL = os.path.join(BASE, "_qc")
os.makedirs(SAL, exist_ok=True)

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
filas = [dict(r) for r in
         con.execute("SELECT id, tema, archivo, titulo FROM imagenes ORDER BY tema, id")]

COLS, W, H = 6, 230, 200
por_hoja = 30
hojas = []
for i in range(0, len(filas), por_hoja):
    lote = filas[i:i + por_hoja]
    filas_n = (len(lote) + COLS - 1) // COLS
    hoja = Image.new("RGB", (COLS * W, filas_n * H), (12, 16, 22))
    dib = ImageDraw.Draw(hoja)
    for j, f in enumerate(lote):
        x, y = (j % COLS) * W, (j // COLS) * H
        try:
            im = Image.open(os.path.join(BASE, f["archivo"])).convert("RGB")
            im.thumbnail((W - 8, H - 26))
            hoja.paste(im, (x + 4, y + 20))
        except Exception:
            pass
        dib.text((x + 4, y + 4), f"#{f['id']} {f['tema'][:22]}", fill=(255, 210, 0))
        dib.text((x + 4, y + H - 18), f["titulo"][:34], fill=(150, 165, 185))
    ruta = os.path.join(SAL, f"qc_{len(hojas)+1}.jpg")
    hoja.save(ruta, quality=82)
    hojas.append((ruta, lote))
    print(ruta, "→ ids", lote[0]["id"], "a", lote[-1]["id"])

for ruta, lote in hojas:
    print("\n==", os.path.basename(ruta))
    for f in lote:
        print(f"  #{f['id']:3} {f['tema'][:34]:36} {f['titulo'][:48]}")
