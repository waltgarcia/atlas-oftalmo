---
name: atlas-oftalmo
description: "Use when building or extending the ophthalmology study atlas."
version: 1.0.0
author: Walter Garcia Ortiz
license: MIT
metadata:
  hermes:
    tags: [ophthalmology, atlas, fundoscopy, enarm, wikimedia-commons, study]
---

# Atlas de oftalmología

Local study atlas of ophthalmology (fundoscopy + anterior segment) with gallery, study mode,
quiz and arrow labels, built on freely licensed Wikimedia Commons images.

## When to use

- You need fundus/anterior-segment images for a specific diagnosis to study or teach.
- You are extending the atlas with a new topic, language or image source.
- You are refreshing the image set and it came back full of landscapes and book plates.

## Run

```bash
python curar.py            # download/refresh images -> imagenes/ + atlas.db
python app.py --port 8195  # http://127.0.0.1:8195
python refill.py           # top up thin topics
python qc_hojas.py         # contact sheets in _qc/ (needs pillow)
```

## Golden rule when curating images

**Never search Commons by free text.** "Fundus" also means the bottom of a valley and "cataract"
is a dam: free-text search returns landscapes, 19th-century engravings, microscopy and portraits
of patients. Start from curated categories (`Category:Fundus of retinal detachment`,
`Category:Hyphema`, `Category:Refractive errors`, `Category:Fundus of glaucoma`, ...) and filter
extensions (no svg/ogg/pdf/tif).

Even then junk slips in. Cheap QC loop:

1. `python qc_hojas.py` builds numbered contact sheets in `_qc/`.
2. Look at them and delete the ids that do not belong (people, engravings, charts, instruments).
3. `python refill.py` tops up the topics that ended up thin, from narrower categories.

Useful delete patterns: portraits/scenes (`Africa Partnerships`, `wounded prisoner`,
`surgeon performing`), book plates (`A treatise on diagnostic methods`, `EB1911`, `Abadie`),
instrument plates (`double sheet showing various ophthalmology`), infographics (Blausen, COVID
symptom collages), and anything whose title mentions a map, valley or satellite.

## Labels

`etiquetas(id, imagen_id, x, y, texto, color)` with `x,y` normalized 0-1. The front end draws a
chip + line + arrowhead in an SVG over the image. Each view needs its own canvas id
(`lienzo-lb`, `lienzo-est`) and `pintarFlechas(slot)` takes the slot: with a single shared id the
arrows render in the hidden lightbox canvas instead of the active view.

## Windows pitfall

`allow_reuse_address` lets a stale process keep the port: if code changes do not show up, check
`Get-NetTCPConnection -LocalPort 8195 -State Listen`, kill that PID and start again.

## Structure

- `TEMAS` in `curar.py`: topic -> (group, [categories], cap).
- `contenido/notas_es.json`: findings, "exam trap" and distractors per topic (translate here).
- Routes: `/api/datos`, `/api/examen?n=10`, `/imagenes/<path>`, `POST /api/etiqueta[...]`.

## Licensing

Every image row stores author, license and source URL; the UI shows the credit. Personal study is
fine; public redistribution requires reviewing each image license individually.
