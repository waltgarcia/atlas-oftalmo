#!/usr/bin/env python3
"""Atlas de oftalmología para el ENARM — galería, modo estudio y examen.

    python app.py                # http://127.0.0.1:8195
    python app.py --host 0.0.0.0

Imágenes: Wikimedia Commons con licencia libre (autor y licencia visibles).
El contenido clínico (qué ver, trampa de examen) es material de estudio propio.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sqlite3
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "atlas.db")
SITIO = os.path.join(BASE, "sitio")
IMG = os.path.join(BASE, "imagenes")

# ---------------------------------------------------------------- contenido clínico
def cargar_notas() -> dict[str, dict]:
    """Contenido clínico: un JSON editable por tema (claves, trampa, grupo)."""
    ruta = os.path.join(BASE, "contenido", "notas_es.json")
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


NOTAS = cargar_notas()

DISTRACTORES = {
    "Fundoscopía": ["Fondo de ojo normal", "Retinopatía diabética", "Oclusión venosa de la retina",
                    "Oclusión arterial de la retina", "Retinopatía hipertensiva",
                    "Glaucoma (excavación papilar)", "Degeneración macular (DMAE)",
                    "Desprendimiento de retina", "Retinoblastoma", "Retinosis pigmentaria",
                    "Neuritis óptica / papila", "Retinopatía diabética en primer nivel"],
    "Defectos y segmento anterior": ["Catarata", "Conjuntivitis", "Orzuelo y chalazión",
                                     "Pterigión y pinguécula", "Queratocono", "Contusión ocular y orbitaria",
                                     "Defectos refractivos", "Estrabismo", "Uveítis / ojo rojo"],
}

MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(DB, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def init_etiquetas() -> None:
    con = conectar()
    con.execute("""CREATE TABLE IF NOT EXISTS etiquetas(
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     imagen_id INTEGER NOT NULL,
                     x REAL NOT NULL, y REAL NOT NULL,
                     texto TEXT NOT NULL,
                     color TEXT DEFAULT '#ffd166')""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_et_img ON etiquetas(imagen_id)")
    con.commit()
    con.close()


def etiquetas_de(con, imagen_id: int) -> list[dict]:
    return [dict(r) for r in con.execute(
        "SELECT id, x, y, texto, color FROM etiquetas WHERE imagen_id=? ORDER BY id", (imagen_id,))]


def datos() -> dict:
    con = conectar()
    filas = [dict(r) for r in con.execute("SELECT * FROM imagenes ORDER BY tema, id")]
    ets: dict[int, list] = {}
    for r in con.execute("SELECT id, imagen_id, x, y, texto, color FROM etiquetas ORDER BY id"):
        ets.setdefault(r["imagen_id"], []).append(dict(r))
    con.close()
    temas: dict[str, dict] = {}
    for f in filas:
        t = f["tema"]
        if t not in temas:
            info = NOTAS.get(t, {})
            temas[t] = {"nombre": t, "grupo": f["grupo"] or info.get("grupo", ""),
                        "claves": info.get("claves", []), "trampa": info.get("trampa", ""),
                        "imagenes": []}
        temas[t]["imagenes"].append({**{k: f[k] for k in ("id", "archivo", "titulo", "autor",
                                                          "licencia", "fuente", "descripcion")},
                                     "etiquetas": ets.get(f["id"], [])})
    orden = {t: i for i, t in enumerate(NOTAS)}
    lista = sorted(temas.values(), key=lambda x: (0 if x["grupo"] == "Fundoscopía" else 1,
                                                  orden.get(x["nombre"], 99)))
    return {"temas": lista, "total_imagenes": len(filas)}


class Handler(BaseHTTPRequestHandler):
    server_version = "AtlasOftalmo/1.0"

    def log_message(self, *a):
        pass

    def _bytes(self, cuerpo: bytes, ctype: str, codigo: int = 200):
        self.send_response(codigo)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, obj, codigo=200):
        self._bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8", codigo)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path in ("/", "/index.html"):
            ruta = os.path.join(SITIO, "index.html")
            if not os.path.exists(ruta):
                return self._bytes(b"falta sitio/index.html", "text/plain", 500)
            return self._bytes(open(ruta, "rb").read(), "text/html; charset=utf-8")

        if u.path == "/api/datos":
            return self._json(datos())

        if u.path == "/api/examen":
            q = urllib.parse.parse_qs(u.query)
            n = max(4, min(30, int((q.get("n") or ["10"])[0])))
            con = conectar()
            filas = [dict(r) for r in con.execute("SELECT * FROM imagenes")]
            con.close()
            if len(filas) < 4:
                return self._json({"error": "faltan imágenes"}, 400)
            random.shuffle(filas)
            preguntas = []
            for f in filas[:n]:
                tema = f["tema"]
                grupo = f["grupo"] or NOTAS.get(tema, {}).get("grupo", "Fundoscopía")
                otros = [t for t in DISTRACTORES.get(grupo, []) if t != tema]
                opciones = random.sample(otros, k=min(3, len(otros))) + [tema]
                random.shuffle(opciones)
                preguntas.append({"imagen": f["archivo"], "titulo": f["titulo"],
                                  "credito": {"autor": f["autor"], "licencia": f["licencia"],
                                              "fuente": f["fuente"]},
                                  "opciones": opciones, "correcta": tema})
            return self._json({"preguntas": preguntas})

        if u.path.startswith("/imagenes/"):
            rel = urllib.parse.unquote(u.path[len("/imagenes/"):])
            destino = os.path.abspath(os.path.join(IMG, rel))
            if not destino.startswith(os.path.abspath(IMG)) or not os.path.exists(destino):
                return self._json({"error": "no encontrada"}, 404)
            ext = os.path.splitext(destino)[1].lower()
            return self._bytes(open(destino, "rb").read(), MIME.get(ext, "application/octet-stream"))

        return self._json({"error": "ruta desconocida"}, 404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            d = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            d = {}

        if u.path == "/api/etiqueta":
            img = d.get("imagen_id")
            texto = (d.get("texto") or "").strip()
            if not img or not texto:
                return self._json({"error": "faltan datos"}, 400)
            x = min(1.0, max(0.0, float(d.get("x") or 0)))
            y = min(1.0, max(0.0, float(d.get("y") or 0)))
            con = conectar()
            cur = con.execute("INSERT INTO etiquetas(imagen_id,x,y,texto,color) VALUES(?,?,?,?,?)",
                              (int(img), x, y, texto[:120], d.get("color") or "#ffd166"))
            con.commit()
            con.close()
            return self._json({"ok": True, "id": cur.lastrowid})

        m = re.match(r"^/api/etiqueta/(\d+)$", u.path)
        if m:
            eid = int(m.group(1))
            con = conectar()
            if "texto" in d:
                con.execute("UPDATE etiquetas SET texto=? WHERE id=?", ((d["texto"] or "")[:120], eid))
            if "color" in d:
                con.execute("UPDATE etiquetas SET color=? WHERE id=?", (d["color"], eid))
            if "x" in d and "y" in d:
                con.execute("UPDATE etiquetas SET x=?, y=? WHERE id=?",
                            (min(1, max(0, float(d["x"]))), min(1, max(0, float(d["y"]))), eid))
            con.commit()
            con.close()
            return self._json({"ok": True})

        m = re.match(r"^/api/etiqueta/(\d+)/borrar$", u.path)
        if m:
            con = conectar()
            con.execute("DELETE FROM etiquetas WHERE id=?", (int(m.group(1)),))
            con.commit()
            con.close()
            return self._json({"ok": True})

        return self._json({"error": "ruta desconocida"}, 404)


def main() -> None:
    ap = argparse.ArgumentParser(description="Atlas de oftalmología ENARM")
    ap.add_argument("--port", type=int, default=int(os.environ.get("ATLAS_PORT", 8195)))
    ap.add_argument("--host", default=os.environ.get("ATLAS_HOST", "0.0.0.0"))
    a = ap.parse_args()
    if not os.path.exists(DB):
        raise SystemExit("Falta atlas.db: corre primero  python curar.py")
    init_etiquetas()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"Atlas de oftalmología en http://{a.host}:{a.port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
