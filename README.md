# Atlas de oftalmología (ENARM)

A **local ophthalmology study atlas** you can run on your own machine: it curates freely
licensed fundus and anterior-segment photographs from Wikimedia Commons, pairs them with the
clinical findings that actually get asked in exams, and turns them into a quiz.

Built originally for the Mexican **ENARM** residency exam, where ophthalmology questions hide
inside "Cirugía General". Everything runs offline with the Python standard library — no build
step, no accounts, no telemetry.

## Features

- **Gallery** — images grouped by topic (fundoscopy / anterior segment) with key findings and an
  "exam trap" line for each one.
- **Study mode** — one topic at a time: large image on the left, findings on the right.
- **Quiz** — random image, four diagnoses to choose from, instant feedback and score.
- **Labels with arrows** — annotate any image with labelled arrows ("papila", "macular edema",
  "flame haemorrhage"). Toggle them on/off globally; labels never appear in quiz mode.
- **Curated, not scraped blindly** — the downloader walks *ophthalmology categories* on Commons
  (free-text search returns valleys for "fundus" and dams for "cataract") and a QC script builds
  numbered contact sheets so a human can cull the bad ones.

## Requirements

Python 3.9+ and nothing else. `pillow` is only needed for the QC contact sheets.

## Quick start

```bash
git clone https://github.com/waltgarcia/atlas-oftalmo
cd atlas-oftalmo
python curar.py            # download images (Wikimedia Commons, CC/PD)
python app.py              # http://127.0.0.1:8195
```

Options:

```bash
python app.py --port 8195 --host 0.0.0.0     # reachable from your phone / LAN
python curar.py --limpiar                    # wipe images + DB and start over
python refill.py                             # top up topics that came out thin
python qc_hojas.py                           # contact sheets in _qc/ for visual QC
```

## Project layout

```
app.py              # HTTP server: gallery, study, quiz, label API
curar.py            # downloader: topic -> Commons categories -> imagenes/ + atlas.db
refill.py           # targeted top-up for weak topics
qc_hojas.py         # numbered contact sheets (needs pillow)
contenido/
  notas_es.json     # clinical content per topic (findings, exam trap, group) - translate here
sitio/index.html    # single-page front end
imagenes/           # downloaded images (git-ignored)
atlas.db            # SQLite: image metadata + labels (git-ignored)
```

## Data model

`imagenes` — one row per image: `tema`, `grupo`, `archivo`, `titulo`, `autor`, `licencia`, `fuente`,
`descripcion`. Credits are shown in the UI, as the licenses require.

`etiquetas` — `imagen_id`, `x`, `y` (0-1, relative to the image), `texto`, `color`.

Adding a topic takes two edits: a line in `TEMAS` (`curar.py`) and an entry in
`contenido/notas_es.json`.

## HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/datos` | topics, images and their labels |
| GET | `/api/examen?n=10` | quiz questions (image + 4 options + answer) |
| GET | `/imagenes/<path>` | image bytes |
| POST | `/api/etiqueta` | add a label `{imagen_id,x,y,texto}` |
| POST | `/api/etiqueta/<id>` | edit text / color / position |
| POST | `/api/etiqueta/<id>/borrar` | delete a label |

## Image licensing

Images come from **Wikimedia Commons** and are used under their own licenses (CC0, CC BY,
CC BY-SA or public domain). Every row stores author, license and source URL, and the UI prints
that credit. If you redistribute this atlas publicly, review each image's license individually.

The clinical text in `contenido/notas_es.json` is original study material, not copied from any
guideline.

## Not a medical device

This is a study aid. It is not validated for diagnosis and must not be used for patient care.

## License

Code: MIT (see `LICENSE`). Images: their own licenses, see above.
