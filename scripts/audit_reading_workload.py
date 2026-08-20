#!/usr/bin/env python3
"""Measure assigned-reading words and generate weekly Canvas workload summaries."""
from __future__ import annotations

import argparse, html, json, math, re, subprocess, tempfile, sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from canvas_automation import jsonc
START = "<!-- generated:weekly-workload:start -->"
END = "<!-- generated:weekly-workload:end -->"

class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in {"script","style","nav","header","footer"}: self.skip += 1
    def handle_endtag(self, tag):
        if tag in {"script","style","nav","header","footer"} and self.skip: self.skip -= 1
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)

def load_jsonc(path: Path):
    return jsonc.load_jsonc(path)

def count_words(path: Path) -> int:
    if path.suffix.lower()==".pdf":
        run=subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True, check=True)
        text=run.stdout
        if len(re.findall(r"\w+", text)) < 50:
            with tempfile.TemporaryDirectory(prefix="reading_ocr_") as folder:
                stem=Path(folder)/"page"
                subprocess.run(["pdftoppm","-jpeg","-r","200",str(path),str(stem)],check=True,capture_output=True)
                parts=[]
                for image in sorted(Path(folder).glob("page-*.jpg")):
                    ocr=subprocess.run(["tesseract",str(image),"stdout","-l","eng"],capture_output=True,text=True,check=True)
                    parts.append(ocr.stdout)
                text="\n".join(parts)
            if len(re.findall(r"\w+", text)) < 50:
                raise ValueError(f"PDF has no usable text layer and OCR produced too little text: {path}")
    elif path.suffix.lower() in {".html", ".htm"}:
        parser=Text(); parser.feed(path.read_text(encoding="utf-8", errors="ignore")); text=" ".join(parser.parts)
    else: text=path.read_text(encoding="utf-8", errors="ignore")
    return len(re.findall(r"\b[\w]+(?:[’'-][\w]+)*\b", text, re.UNICODE))

def calculate(config):
    results={}
    rate=config["reading_words_per_minute"]
    for week, spec in config["weeks"].items():
        words=0; measured=0; estimated=[]
        for item in spec["materials"]:
            source=ROOT/item["source"] if item.get("source") else None
            if source and source.exists(): value=count_words(source); measured += 1
            elif "estimated_words" in item: value=item["estimated_words"]; estimated.append(item["id"])
            else: raise ValueError(f"week {week} material {item['id']} has no readable source or estimate")
            words += value
        reading=math.ceil(words/rate)
        raw_other=spec.get("other_minutes",0)
        target=config.get("target_weekly_minutes")
        other=max(0,target-reading) if raw_other=="auto" else raw_other
        allocation={}
        if raw_other=="auto":
            profile=config["allocation_profiles"][spec["profile"]]
            remaining=other
            for index,(name,weight) in enumerate(profile.items()):
                value=remaining if index==len(profile)-1 else round(other*weight)
                allocation[name]=value; remaining-=value
        total=reading+other
        band=config["weekly_target_minutes"]
        results[week]={"words":words,"reading_minutes":reading,"other_minutes":other,"total_minutes":total,
                       "within_target":band["minimum"] <= total <= band["maximum"], "allocation":allocation,
                       "measured":measured,"estimated":estimated,"page":spec["page"]}
    return results

def block(week, result, rate):
    status="measured from local copies"
    if result["estimated"]: status += "; estimates used for " + ", ".join(result["estimated"])
    hours=result["total_minutes"]/60
    labels={"viewing_and_play":"viewing and play","quiz_and_review":"quiz and review","team_coordination":"team coordination","project_work":"project work"}
    detail="; ".join(f"{labels.get(k,k.replace('_',' '))} {v} min" for k,v in result["allocation"].items())
    return (f'{START}<section class="weekly-workload" aria-labelledby="workload-{week}">'
      f'<h2 id="workload-{week}">Estimated weekly workload</h2><ul>'
      f'<li><strong>Assigned reading:</strong> {result["words"]:,} words, about {result["reading_minutes"]} minutes at {rate} words per minute.</li>'
      f'<li><strong>Viewing, play, coordination, review, and project work:</strong> about {result["other_minutes"]} minutes ({detail}).</li>'
      f'<li><strong>Total:</strong> about {hours:.1f} hours.</li></ul>'
      f'<p><small>Planning estimate ({html.escape(status)}). Reading and production times vary by person and access method.</small></p></section>{END}')

def update(config, results, check=False):
    stale=[]
    for week,result in results.items():
        path=ROOT/result["page"]; source=path.read_text(encoding="utf-8"); generated=block(week,result,config["reading_words_per_minute"])
        # Canvas removes HTML comments but retains the section. Remove either
        # representation (and any accidental duplicates) before inserting one
        # canonical generated block.
        target=re.sub(re.escape(START)+r".*?"+re.escape(END), "", source, flags=re.S)
        target=re.sub(
            r'<section\b[^>]*class="[^"]*\bweekly-workload\b[^"]*"[^>]*>.*?</section>',
            "", target, flags=re.S | re.I,
        )
        marker="<h2>Required materials</h2>"
        target=target.replace(marker, generated+marker, 1) if marker in target else target.replace("<aside>", generated+"<aside>",1)
        if target != source:
            if check: stale.append(str(path.relative_to(ROOT)))
            else: path.write_text(target, encoding="utf-8")
    return stale

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--config",type=Path,default=ROOT/"course/reading-workload.config.jsonc"); p.add_argument("--check",action="store_true"); p.add_argument("--strict-balance",action="store_true"); p.add_argument("--json",action="store_true"); a=p.parse_args()
    config=load_jsonc(a.config); results=calculate(config); stale=update(config,results,a.check)
    if a.json: print(json.dumps(results,indent=2))
    else:
        for w,r in results.items(): print(f"Week {w}: {r['words']:,} words; {r['total_minutes']/60:.1f} h total"+(" [REVIEW]" if not r["within_target"] else ""))
    if stale: print("Stale workload blocks: "+", ".join(stale)); return 1
    if a.strict_balance and any(not r["within_target"] for r in results.values()): return 2
    return 0
if __name__ == "__main__": raise SystemExit(main())
