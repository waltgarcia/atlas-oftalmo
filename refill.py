# -*- coding: utf-8 -*-
"""Relleno dirigido: agrega imágenes de categorías específicas a los temas flojos."""
import json, os, re, sqlite3, time, urllib.parse, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "atlas.db")
API = "https://commons.wikimedia.org/w/api.php"
UA = "AtlasOftalmoENARM/1.0 (estudio medico)"
CAMPOS = ("tema", "grupo", "archivo", "titulo", "autor", "licencia", "fuente", "descripcion")

OBJETIVO = {
    "Fondo de ojo normal": ("Fundoscopía", ["Fundus of the human eye"], 4,
                            r"(normal|fundus|retina|papilla|optic disc)"),
    "Catarata": ("Defectos y segmento anterior", ["Cataract"], 5, r"(cataract|lens|leukocor)"),
    "Defectos refractivos": ("Defectos y segmento anterior",
                             ["Refractive errors", "Myopia", "Astigmatism (eye)", "Presbyopia"], 5,
                             r"(myop|hyperop|astigmat|presbyop|refract|emmetrop)"),
    "Contusión ocular y orbitaria": ("Defectos y segmento anterior",
                                     ["Hyphema", "Subconjunctival hemorrhage", "Eye trauma"], 4,
                                     r"(hyphem|hyphaem|hemorrhage|trauma|contusion|haematoma|hematoma)"),
    "Conjuntivitis": ("Defectos y segmento anterior",
                      ["Conjunctivitis", "Bacterial conjunctivitis", "Viral conjunctivitis"], 4,
                      r"(conjunctiv|chemosis|red eye)"),
    "Glaucoma (excavación papilar)": ("Fundoscopía", ["Fundus of glaucoma"], 3, r"(glaukom|glaucoma|cup)"),
    "Retinoblastoma": ("Fundoscopía", ["Retinoblastoma"], 3, r"(retinoblast|leukocor|leucocor)"),
    "Estrabismo": ("Defectos y segmento anterior", ["Strabismus", "Esotropia", "Exotropia"], 3,
                   r"(strabism|esotrop|exotrop|tropia)"),
}
MALAS = re.compile(r"(map|valley|landschaft|panorama|satellit|aerial|prisoner|surgeon|"
                   r"africa partnerships|engraving|liner|icon|\.svg$|\.ogg$|\.pdf$|\.tif$|\.gif$)", re.I)


def q(p, n=4):
    for i in range(n):
        try:
            u = API + "?" + urllib.parse.urlencode(p)
            return json.load(urllib.request.urlopen(
                urllib.request.Request(u, headers={"User-Agent": UA}), timeout=45))
        except Exception:
            time.sleep(2 + 2 * i)
    return {}


def archivos(cat):
    d = q({"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat,
           "cmtype": "file", "cmlimit": 100, "format": "json"})
    return [m["title"] for m in (d.get("query") or {}).get("categorymembers", [])]


def limpio(n):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", n)[-80:]


con = sqlite3.connect(DB)
con.execute(f"CREATE TABLE IF NOT EXISTS imagenes (id INTEGER PRIMARY KEY, {', '.join(CAMPOS)})")
con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_archivo ON imagenes(archivo)")
total_nuevas = 0
for tema, (grupo, cats, tope, pat) in OBJETIVO.items():
    carpeta = os.path.join(BASE, "imagenes", limpio(tema))
    os.makedirs(carpeta, exist_ok=True)
    faltan = tope
    candidatos = []
    for c in cats:
        for t in archivos(c):
            if MALAS.search(t) or t in candidatos:
                continue
            if pat and not re.search(pat, t, re.I):
                continue
            candidatos.append(t)
        time.sleep(1.2)
    nuevas = 0
    for i in range(0, len(candidatos), 20):
        if nuevas >= faltan:
            break
        d = q({"action": "query", "titles": "|".join(candidatos[i:i + 20]), "prop": "imageinfo",
               "iiprop": "url|extmetadata|mime", "iiurlwidth": 1200, "format": "json"})
        for p in (d.get("query") or {}).get("pages", {}).values():
            if nuevas >= faltan:
                break
            ii = (p.get("imageinfo") or [{}])[0]
            if ii.get("mime") not in ("image/jpeg", "image/png", "image/webp"):
                continue
            tit = p.get("title", "").replace("File:", "")
            meta = ii.get("extmetadata") or {}
            f = lambda k: re.sub(r"<[^>]+>", "", (meta.get(k) or {}).get("value") or "").strip()
            ext = os.path.splitext(urllib.parse.urlparse(ii.get("url", "")).path)[1] or ".jpg"
            destino = os.path.join(carpeta, limpio(tit)[:70] + ext)
            if os.path.exists(destino):
                continue
            try:
                datos = urllib.request.urlopen(urllib.request.Request(
                    ii.get("thumburl") or ii["url"], headers={"User-Agent": UA}), timeout=60).read()
                if len(datos) < 12000:
                    continue
                open(destino, "wb").write(datos)
            except Exception:
                continue
            con.execute(f"INSERT OR IGNORE INTO imagenes ({', '.join(CAMPOS)}) "
                        f"VALUES ({', '.join('?' * len(CAMPOS))})",
                        (tema, grupo, os.path.relpath(destino, BASE).replace("\\", "/"), tit,
                         f("Artist")[:120], f("LicenseShortName")[:40], ii.get("descriptionurl", ""),
                         f("ImageDescription")[:240]))
            nuevas += 1
            total_nuevas += 1
            print(f"  + {tema[:26]:28} {tit[:50]}")
            time.sleep(0.6)
        time.sleep(1.4)
    con.commit()
    print(f"{tema[:40]:42} {nuevas} nuevas")

print("\ntotal nuevas:", total_nuevas)
for r in con.execute("select tema, count(*) from imagenes group by tema order by 2"):
    print(f"  {r[1]:2} {r[0]}")
