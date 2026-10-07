"""Wrap site/app.html (a body fragment, also published as a Claude artifact) into a full index.html for static hosting.

Also embeds schema.org Dataset markup (JSON-LD) built from data/meta.json, which is what Google Dataset Search
and other crawlers read.
"""
import json
from pathlib import Path

site = Path(__file__).resolve().parents[1] / "site"
SPACE = "https://huggingface.co/spaces/dinoclub/mortal-gis"
frag = (site / "app.html").read_text()
head_end = frag.index("</style>") + len("</style>")


def jsonld():
    try:
        meta = json.loads((site / "data" / "meta.json").read_text())
    except (OSError, ValueError):
        return ""
    measures = meta.get("measures", [])
    years = sorted({int(p) for m in measures for p in m.get("periods", []) if str(p).isdigit()})
    used = {s for m in measures for s in (m.get("sources") or [])}
    sources = [v for k, v in (meta.get("sources") or {}).items() if not used or k in used]
    for l in meta.get("incidents", []):
        if l.get("sourceUrl"):
            sources.append({"label": l.get("source"), "url": l["sourceUrl"]})
    seen, based_on = set(), []
    for s in sources:
        if s.get("url") and s["url"] not in seen:
            seen.add(s["url"])
            based_on.append({"@type": "Dataset", "name": s.get("label") or s["url"], "url": s["url"]})
    doc = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "MortalGIS: US county death rates, 1968 to today",
        "description": ("Death rates and counts for every US county by cause (all causes, drug overdose, suicide, homicide, "
                        "firearm, heart disease, stroke, traffic, weather), counted where people lived and where they died, "
                        "plus locations of deaths from medical examiner, police and federal incident records. "
                        "Built weekly from CDC NCHS / WONDER, NBER, SEER, NHTSA FARS, NOAA and local open data."),
        "url": SPACE,
        "keywords": ["mortality", "death rates", "county", "overdose", "suicide", "homicide", "firearm", "CDC WONDER", "United States"],
        "isAccessibleForFree": True,
        "spatialCoverage": {"@type": "Place", "name": "United States"},
        "temporalCoverage": f"{years[0]}/{years[-1]}" if years else None,
        "dateModified": meta.get("generated"),
        "creator": {"@type": "Person", "name": "Dinoclub"},
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json",
                          "contentUrl": f"{SPACE}/resolve/main/data/m_{m['key']}.json",
                          "name": m.get("label")} for m in measures],
        "variableMeasured": [m.get("label") for m in measures],
        "isBasedOn": based_on,
    }
    doc = {k: v for k, v in doc.items() if v is not None}
    return '<script type="application/ld+json">' + json.dumps(doc, separators=(",", ":")).replace("</", "<\\/") + "</script>\n"


html = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="description" content="US county death rates from 1968 to today: overdose, suicide, homicide, firearm, heart disease, stroke, traffic and weather deaths, where people lived and where they died, with death locations from medical examiner and police records.">\n'
        + jsonld() +
        '<style>body{margin:0}[hidden]{display:none!important}</style>\n'
        + frag[:head_end] + "\n</head>\n<body>\n" + frag[head_end:] + "\n</body>\n</html>\n")
(site / "index.html").write_text(html)
print("wrote", site / "index.html")
