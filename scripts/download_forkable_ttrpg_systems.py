#!/usr/bin/env python3
"""Download the approved TTRPG source pages and stable files with provenance."""
from __future__ import annotations
import argparse, hashlib, json, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCES=[
 ("dnd-srd-5.2.1","https://www.dndbeyond.com/srd","https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf","CC-BY-4.0; use the attribution printed in the PDF"),
 ("cairn-barebones","https://cairnrpg.com/barebones/rules/barebones-character-creation/",None,"Check the current Cairn licence and attribution page before adaptation"),
 ("fate-accelerated","https://fate-srd.com/fate-accelerated",None,"Check the current Fate SRD licensing page before adaptation"),
 ("basic-fantasy","https://www.basicfantasy.org/",None,"Check the licence in the selected rules PDF before adaptation"),
 ("ironsworn-starforged-playkit","https://tomkinpress.com/collections/downloads-for-ironsworn-starforged/products/ironsworn-starforged-playkit",None,"Free playkit; check its included terms before redistribution or adaptation"),
 ("blades-in-the-dark","https://bladesinthedark.com/downloads",None,"Check the current licensing page and each downloaded file before adaptation"),
]

def fetch(url,path):
    request=urllib.request.Request(url,headers={"User-Agent":"CourseTools/1.0"})
    try:
        with urllib.request.urlopen(request,timeout=90) as response:
            data=response.read(); content_type=response.headers.get_content_type()
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as error:
        return {"archived":False,"error":str(error)}
    path.write_bytes(data); return {"archived":True,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"content_type":content_type}

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--destination",type=Path,required=True); a=p.parse_args(); a.destination.mkdir(parents=True,exist_ok=True)
    records=[]
    for slug,page,download,note in SOURCES:
        folder=a.destination/slug; folder.mkdir(exist_ok=True)
        (folder/"source.url").write_text(page+"\n",encoding="utf-8")
        page_record=fetch(page,folder/"source-page.html")
        record={"slug":slug,"source_page":page,"source_page_file":str((folder/"source-page.html").relative_to(a.destination)),"licensing_note":note,**page_record}
        if download:
            file=folder/Path(download).name; (folder/"download.url").write_text(download+"\n",encoding="utf-8"); record["download_url"]=download; record["download_file"]=str(file.relative_to(a.destination)); record["download"]=fetch(download,file)
        records.append(record)
    manifest={"schema":"forkable-ttrpg-sources/v1","retrieved_at":datetime.now(timezone.utc).isoformat(),"records":records}
    (a.destination/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    (a.destination/"README.md").write_text("# Approved source systems\n\nThese archived pages preserve discovery and provenance. Follow each current source URL and verify its licence before adapting or redistributing rules. Free access does not by itself grant adaptation rights. See `manifest.json` for retrieval hashes and notes.\n",encoding="utf-8")
    print(json.dumps(manifest,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
