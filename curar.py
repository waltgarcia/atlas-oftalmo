#!/usr/bin/env python3
"""Curador v2 del atlas: baja imágenes de categorías CURADAS de Wikimedia Commons.

La v1 buscaba por texto y traía basura ("fundus" también es el fondo de un valle).
Aquí se parte de categorías de oftalmología, que ya vienen clasificadas por tema.

    python curar.py            # incremental: baja lo que falte
    python curar.py --limpiar  # borra todas las imágenes y la BD, empieza de cero
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import time
import urllib.parse
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(BASE, "imagenes")
DB = os.path.join(BASE, "atlas.db")
API = "https://commons.wikimedia.org/w/api.php"
UA = "AtlasOftalmoENARM/1.0 (estudio medico personal: walter.garciaortiz@gmail.com)"
CAMPOS = ("tema", "grupo", "archivo", "titulo", "autor", "licencia", "fuente", "descripcion")

# tema -> (grupo, [categorías de Commons], tope de imágenes)
TEMAS: dict[str, tuple[str, list[str], int]] = {
    "Fondo de ojo normal": ("Fundoscopía",
        ["Fundus of the human eye", "Ocular fundus with slit lamp", "Fundus photographs"], 5),
    "Retinopatía diabética": ("Fundoscopía",
        ["Fundus of diabetic retinopathy", "Fundus of proliferative diabetic retinopathy",
         "Fundus of retinopathies"], 6),
    "Retinopatía diabética en primer nivel": ("Fundoscopía",
        ["Fundus of diabetic macular edema", "Fundus of diabetic retinopathy"], 4),
    "Oclusión venosa de la retina": ("Fundoscopía",
        ["Fundus of retinal vascular occlusions", "Fundus of branch retinal vein occlusion",
         "Fundus of central retinal vein occlusion"], 5),
    "Oclusión arterial de la retina": ("Fundoscopía",
        ["Fundus of central retinal artery occlusion", "Fundus of retinal vascular occlusions"], 3),
    "Retinopatía hipertensiva": ("Fundoscopía",
        ["Fundus of hypertensive retinopathy", "Fundus of papilledema"], 4),
    "Glaucoma (excavación papilar)": ("Fundoscopía",
        ["Fundus of glaucoma", "Fundus of disorders of optic nerve"], 4),
    "Degeneración macular (DMAE)": ("Fundoscopía",
        ["Fundus of drusen", "Fundus of macular disorders", "Fundus of age-related macular degeneration"], 5),
    "Desprendimiento de retina": ("Fundoscopía",
        ["Fundus of retinal detachment"], 5),
    "Retinoblastoma": ("Fundoscopía",
        ["Retinoblastoma", "Fundus of neoplasms of eye and adnexa"], 4),
    "Retinosis pigmentaria": ("Fundoscopía",
        ["Fundus of retinitis pigmentosa"], 3),
    "Neuritis óptica / papila": ("Fundoscopía",
        ["Fundus of disorders of optic nerve", "Fundus of optic neuritis", "Fundus of papilledema"], 4),
    "Catarata": ("Defectos y segmento anterior",
        ["Cataracts", "Cataract surgery"], 6),
    "Conjuntivitis": ("Defectos y segmento anterior",
        ["Bacterial conjunctivitis", "Viral conjunctivitis", "Allergic conjunctivitis", "Conjunctivitis"], 6),
    "Orzuelo y chalazión": ("Defectos y segmento anterior",
        ["Chalazion", "Hordeolum", "Stye"], 4),
    "Pterigión y pinguécula": ("Defectos y segmento anterior",
        ["Pterygium", "Pinguecula"], 4),
    "Queratocono": ("Defectos y segmento anterior",
        ["Keratoconus"], 4),
    "Contusión ocular y orbitaria": ("Defectos y segmento anterior",
        ["Eye injuries", "Hyphema", "Black eye", "Orbital fractures"], 5),
    "Defectos refractivos": ("Defectos y segmento anterior",
        ["Refractive errors", "Myopia", "Hyperopia", "Astigmatism (eye)", "Presbyopia"], 5),
    "Estrabismo": ("Defectos y segmento anterior",
        ["Strabismus", "Esotropia", "Exotropia"], 4),
    "Uveítis / ojo rojo": ("Defectos y segmento anterior",
        ["Uveitis", "Hypopyon", "Anterior uveitis"], 4),
}

MALAS = re.compile(r"(map|mapa|valley|landschaft|panorama|satellit|aerial|stadt|city|"
                   r"\.svg$|\.ogg$|\.pdf$|\.tif$|\.gif$)", re.I)


def pedir(params: dict, intentos: int = 4) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    for i in range(intentos):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except Exception:
            time.sleep(2 + 3 * i)
    return {}


def archivos_de(cat: str) -> list[str]:
    out, cont = [], None
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat,
             "cmtype": "file", "cmlimit": 100, "format": "json"}
        if cont:
            p["cmcontinue"] = cont
        d = pedir(p)
        out += [m["title"] for m in (d.get("query") or {}).get("categorymembers", [])]
        cont = (d.get("continue") or {}).get("cmcontinue")
        if not cont or len(out) > 200:
            break
        time.sleep(1.5)
    return out


def info(titulos: list[str]) -> dict:
    d = pedir({"action": "query", "titles": "|".join(titulos), "prop": "imageinfo",
               "iiprop": "url|extmetadata|mime|size", "iiurlwidth": 1200, "format": "json"})
    return (d.get("query") or {}).get("pages") or {}


def limpio(n: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", n)[-85:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limpiar", action="store_true")
    a = ap.parse_args()
    if a.limpiar:
        if os.path.isdir(IMG):
            shutil.rmtree(IMG)
        if os.path.exists(DB):
            os.remove(DB)
    os.makedirs(IMG, exist_ok=True)

    con = sqlite3.connect(DB)
    con.execute(f"CREATE TABLE IF NOT EXISTS imagenes (id INTEGER PRIMARY KEY, {', '.join(CAMPOS)})")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_archivo ON imagenes(archivo)")

    for tema, (grupo, cats, tope) in TEMAS.items():
        carpeta = os.path.join(IMG, limpio(tema))
        os.makedirs(carpeta, exist_ok=True)
        puestas = len([f for f in os.listdir(carpeta) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))])
        faltan = max(0, tope - puestas)
        if not faltan:
            print(f"  {tema[:40]:42} ya tiene {puestas}")
            continue
        pendientes: list[str] = []
        for cat in cats:
            if len(pendientes) >= faltan * 3:
                break
            for t in archivos_de(cat):
                if t not in pendientes and not MALAS.search(t):
                    pendientes.append(t)
            time.sleep(1.2)

        nuevas = 0
        for i in range(0, len(pendientes), 20):
            if nuevas >= faltan:
                break
            pagina = info(pendientes[i:i + 20])
            for p in pagina.values():
                if nuevas >= faltan:
                    break
                ii = (p.get("imageinfo") or [{}])[0]
                if ii.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
                    continue
                tit = p.get("title", "").replace("File:", "")
                if MALAS.search(tit):
                    continue
                meta = ii.get("extmetadata") or {}
                def m(k):
                    return re.sub(r"<[^>]+>", "", (meta.get(k) or {}).get("value") or "").strip()
                ext = os.path.splitext(urllib.parse.urlparse(ii.get("url", "")).path)[1] or ".jpg"
                destino = os.path.join(carpeta, limpio(tit)[:70] + ext)
                if os.path.exists(destino):
                    continue
                try:
                    req = urllib.request.Request(ii.get("thumburl") or ii["url"], headers={"User-Agent": UA})
                    with urllib.request.urlopen(req, timeout=60) as r:
                        datos = r.read()
                    if len(datos) < 12000:
                        continue
                    open(destino, "wb").write(datos)
                except Exception:
                    continue
                con.execute(
                    f"INSERT OR IGNORE INTO imagenes ({', '.join(CAMPOS)}) VALUES ({', '.join('?' * len(CAMPOS))})",
                    (tema, grupo, os.path.relpath(destino, BASE).replace("\\", "/"), tit,
                     m("Artist")[:120], m("LicenseShortName")[:40], ii.get("descriptionurl", ""),
                     m("ImageDescription")[:240]))
                nuevas += 1
                time.sleep(0.6)
            time.sleep(1.5)
        con.commit()
        print(f"  {tema[:40]:42} {nuevas} nuevas (tenía {puestas})")

    total = con.execute("SELECT COUNT(*) FROM imagenes").fetchone()[0]
    print(f"\nimágenes en el atlas: {total}")
    for r in con.execute("SELECT tema, COUNT(*) FROM imagenes GROUP BY tema ORDER BY 2 DESC"):
        print(f"  {r[1]:2}  {r[0]}")
    faltan = [t for t in TEMAS if con.execute("SELECT COUNT(*) FROM imagenes WHERE tema=?", (t,)).fetchone()[0] == 0]
    if faltan:
        print("\nSIN imágenes:", ", ".join(faltan))
    con.close()


if __name__ == "__main__":
    main()
