"""Wrap site/app.html (a body fragment, also published as a Claude artifact) into a full index.html for static hosting."""
from pathlib import Path
site = Path(__file__).resolve().parents[1] / "site"
frag = (site / "app.html").read_text()
head_end = frag.index("</style>") + len("</style>")
html = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<meta name="description" content="US county death rates: overdose, suicide, homicide, firearm, heart disease, life expectancy. Data from CDC NCHS and County Health Rankings.">\n'
        '<style>body{margin:0}[hidden]{display:none!important}</style>\n'
        + frag[:head_end] + "\n</head>\n<body>\n" + frag[head_end:] + "\n</body>\n</html>\n")
(site / "index.html").write_text(html)
print("wrote", site / "index.html")
