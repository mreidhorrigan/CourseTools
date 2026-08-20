#!/usr/bin/env python3
"""Build a configurable, dossier-ready PDF from canonical course HTML."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, tempfile
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup
from canvas_automation import jsonc

ROOT=Path(__file__).resolve().parents[1]

def expand(value): return Path(value.replace("$ENGINE",str(ROOT)).replace("$HOME",str(Path.home()))).expanduser()

def selected_html(record):
    source=(ROOT/record["source"]).resolve(); allowed=(ROOT/"course/content").resolve()
    if allowed not in source.parents: raise ValueError(f"Dossier source must be under course/content: {record['source']}")
    soup=BeautifulSoup(source.read_text(encoding="utf-8"),"html.parser")
    if record.get("selector"):
        node=soup.select_one(record["selector"])
        if node is None: raise ValueError(f"Selector {record['selector']!r} not found in {record['source']}")
        return str(node)
    return str(soup)

def document_html(title,body,css):
    heading="" if BeautifulSoup(body,"html.parser").find("h1") else f"<h1>{title}</h1>"
    return f'''<!doctype html><html><head><meta charset="utf-8"><title>{title}</title><style>{css}\n@page{{size:Letter;margin:0.7in}} body{{font-size:10.5pt;line-height:1.35}} a{{color:#542788}} table{{font-size:8.5pt}} </style></head><body><main class="canvas-course">{heading}{body}</main></body></html>'''

def build(config_path):
    config=jsonc.load_and_validate(config_path); out_base=expand(config["OUT_DIR"])
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"); run=out_base/f"{stamp}__course-design-dossier"; run.mkdir(parents=True)
    chrome=expand(config.get("chrome_path",shutil.which("google-chrome") or ""))
    if not chrome.is_file(): raise RuntimeError("Google Chrome was not found; set chrome_path in the JSONC config")
    css=(ROOT/"course/styles/canvas.css").read_text(encoding="utf-8"); pdfs=[]
    sections=run/"sections"; sections.mkdir()
    with tempfile.TemporaryDirectory(prefix="course_dossier_") as tmp:
        temp=Path(tmp)
        for i,record in enumerate(config["documents"],1):
            html_path=temp/f"{i:03d}.html"; pdf=sections/f"{i:03d}.pdf"
            html_path.write_text(document_html(record["title"],selected_html(record),css),encoding="utf-8")
            subprocess.run([str(chrome),"--headless","--disable-gpu","--no-pdf-header-footer",f"--print-to-pdf={pdf}",html_path.as_uri()],check=True,capture_output=True)
            pdfs.append((pdf,record["title"]))
        manifest=run/"dossier-manifest.txt"
        manifest.write_text("\n".join(f"{p.resolve()} | {title}" for p,title in pdfs)+"\n",encoding="utf-8")
        tools_dir=expand(config.get("dossier_tools_directory","")); dossier=tools_dir/"dossier.py"
        if not dossier.is_file(): raise RuntimeError("DOSSIER_TOOLS/dossier.py was not found; set dossier_tools_directory in the JSONC config")
        output=run/"course-design-dossier.pdf"; opts=config.get("dossier",{})
        cmd=[shutil.which("python3") or "python3",str(dossier),"--manifest",str(manifest),"-o",str(output),"--format",opts.get("page_number_format","Course dossier {n}"),"--position",opts.get("position","bottom-center")]
        if opts.get("contents",True): cmd.append("--contents")
        subprocess.run(cmd,check=True)
    provenance={"schema":"canvas-course-dossier/v1","created_at":datetime.now(timezone.utc).isoformat(),"config":str(config_path),"documents":config["documents"],"dossier_tools":str(tools_dir),"output":str(output),"sha256":hashlib.sha256(output.read_bytes()).hexdigest()}
    (run/"provenance.json").write_text(json.dumps(provenance,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(provenance,indent=2)); return provenance

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--config",type=Path,default=ROOT/"commands/build-course-dossier.config.jsonc"); a=p.parse_args(); build(a.config.resolve()); return 0
if __name__=="__main__": raise SystemExit(main())
