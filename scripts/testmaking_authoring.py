#!/usr/bin/env python3
"""Manage canonical Testmaker Markdown for both PDF forms and mapped Canvas quizzes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_TESTMAKING = Path("private/testmaking")
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
from canvas_automation import jsonc
from canvas_automation.testmaker import Pool, Question, parse_testmaker, question_payload
from canvas_automation.test_forms import build_forms
from canvas_automation.util import fresh_out_dir
from sandbox_course_lifecycle import GuardedCanvas


def cid(config): return int(re.search(r"/courses/(\d+)", config["course_url"]).group(1))
def plain(html): return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)
def group_list(value): return value.get("quiz_groups", []) if isinstance(value, dict) else value


def question_markdown(question: dict) -> str:
    stem = plain(question.get("question_text"))
    qtype = question.get("question_type")
    if qtype == "text_only_question": return f"[Paragraph.] {stem}"
    if qtype in {"multiple_choice_question", "multiple_answers_question"}:
        answers = question.get("answers") or []
        correct = next((plain(a.get("html") or a.get("text")) for a in answers if a.get("weight", 0) > 0), "")
        wrong = [plain(a.get("html") or a.get("text")) for a in answers if a.get("weight", 0) <= 0]
        return " ".join([f"[Question.] {stem}", f"[Answer.] {correct}"] + [f"[Distractor.] {item}" for item in wrong])
    return f"[Question.] {stem}"


def export_live(root, server, initialize):
    config = jsonc.load_and_validate(root / "course/course.config.jsonc"); course_id = cid(config)
    canvas = GuardedCanvas(server, course_id); canvas.health()
    path = root / PRIVATE_TESTMAKING / "testmaking-manifest.json"
    if path.exists() and not initialize: raise ValueError("Testmaking manifest exists; use --initialize to replace the baseline")
    quizzes = canvas.raw("GET", f"/courses/{course_id}/quizzes", params={"per_page": 100})
    entries = []
    for quiz in sorted(quizzes, key=lambda q: q["title"]):
        questions = canvas.raw("GET", f"/courses/{course_id}/quizzes/{quiz['id']}/questions", params={"per_page": 100})
        groups = {g["id"]: g for g in group_list(canvas.raw("GET", f"/courses/{course_id}/quizzes/{quiz['id']}/groups", params={"per_page": 100}))}
        blocks=[]; emitted=set()
        for question in questions:
            gid=question.get("quiz_group_id")
            if gid and gid not in emitted:
                blocks.append(f"[Each version take {groups.get(gid, {}).get('pick_count', 1)} of the following options.]")
                emitted.add(gid)
            value=question_markdown(question)
            blocks.append("[Option.] " + value if gid else value)
        source=f"private/testmaking/questions/{safe(quiz['title'])}.md"
        target=root/source; target.parent.mkdir(parents=True,exist_ok=True); target.write_text("\n\n".join(blocks)+"\n",encoding="utf-8")
        entries.append({
            "key": safe(quiz["title"]), "title": quiz["title"], "canvas_quiz_id": quiz["id"], "source": source,
            "pdf": {"title": quiz["title"], "versions": 3, "seed": "1"},
            "canvas": {key: quiz.get(key) for key in ("description","time_limit","allowed_attempts","shuffle_answers","one_question_at_a_time","show_correct_answers","published","due_at","unlock_at","lock_at")},
        })
    manifest={"schema":"canvas-testmaking-authoring/v1","course_id":course_id,"requires_reinitialization":False,"source_format":"Testmaker Markdown","quizzes":entries}
    path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return {"course_id":course_id,"quizzes":len(entries),"manifest":str(path)}


def safe(value): return re.sub(r"[^a-z0-9]+","-",value.casefold()).strip("-")


def load(root):
    config=jsonc.load_and_validate(root/"course/course.config.jsonc")
    manifest=json.loads((root/PRIVATE_TESTMAKING/"testmaking-manifest.json").read_text())
    if manifest.get("requires_reinitialization"): raise RuntimeError("Run testmaking export-live --initialize for this target first")
    if manifest["course_id"] != cid(config): raise RuntimeError("Testmaking manifest and course config target different courses")
    return config,manifest


def planned_items(parsed):
    items=[]; number=0; pool_number=0
    for item in parsed.items:
        if isinstance(item,Pool):
            pool_number+=1; items.append({"kind":"pool","name":f"Testmaker pool {pool_number}","take":item.take,"questions":item.questions})
        else:
            number+=1; items.append({"kind":"question","name":f"Question {number}","question":item})
    return items


def source_signature(parsed):
    return [(q.stem, q.answer or "", tuple(q.distractors)) for q in parsed.questions]


def live_signature(questions):
    result=[]
    for item in questions:
        if item.get("question_type") == "text_only_question": continue
        answers=item.get("answers") or []
        correct=next((plain(a.get("html") or a.get("text")) for a in answers if a.get("weight",0)>0),"")
        distractors=tuple(plain(a.get("html") or a.get("text")) for a in answers if a.get("weight",0)<=0)
        result.append((plain(item.get("question_text")),correct,distractors))
    return result


def verify(root, server=None):
    _,manifest=load(root); reports=[]
    canvas=GuardedCanvas(server,manifest["course_id"]) if server else None
    if canvas: canvas.health()
    for quiz in manifest["quizzes"]:
        parsed=parse_testmaker(root/quiz["source"]); report={"key":quiz["key"],"source":quiz["source"],"questions":len(parsed.questions),"valid":True}
        if canvas:
            live=canvas.raw("GET",f"/courses/{manifest['course_id']}/quizzes/{quiz['canvas_quiz_id']}/questions",params={"per_page":100})
            report["canvas_question_count"]=len(live); report["canvas_current"]=live_signature(live)==source_signature(parsed)
        reports.append(report)
    return {"status":"PASS" if all(r.get("canvas_current",True) for r in reports) else "DRIFT","quizzes":reports}


def build_pdf(root, selected=None):
    _,manifest=load(root); outputs=[]
    for quiz in manifest["quizzes"]:
        if selected and quiz["key"] != selected: continue
        out=root/"out/testmaking-authoring"/quiz["key"]
        built=build_forms(root/quiz["source"],out,quiz["pdf"]["title"],quiz["pdf"]["versions"],quiz["pdf"]["seed"])
        outputs.append({"key":quiz["key"],"output":str(out),"source_sha256":built["source_sha256"]})
    return {"built":outputs}


def apply(root, server, confirm):
    _,manifest=load(root); course_id=manifest["course_id"]
    if confirm != f"SYNC-TESTMAKING-{course_id}": raise ValueError(f"Apply requires --confirm SYNC-TESTMAKING-{course_id}")
    canvas=GuardedCanvas(server,course_id); canvas.health()
    if canvas.raw("GET",f"/courses/{course_id}").get("workflow_state") != "unpublished":
        raise RuntimeError("Refusing testmaking synchronization because the target course is published")
    parsed={q["key"]:parse_testmaker(root/q["source"]) for q in manifest["quizzes"]}
    for quiz in manifest["quizzes"]:
        live_quiz=canvas.raw("GET",f"/courses/{course_id}/quizzes/{quiz['canvas_quiz_id']}")
        if live_quiz.get("published"):
            raise RuntimeError(f"Refusing to replace questions in published quiz: {quiz['title']}")
    out=fresh_out_dir(root/"out/testmaking-authoring","canvas-question-backup"); changes=[]
    for quiz in manifest["quizzes"]:
        qid=quiz["canvas_quiz_id"]
        live=canvas.raw("GET",f"/courses/{course_id}/quizzes/{qid}/questions",params={"per_page":100})
        groups=group_list(canvas.raw("GET",f"/courses/{course_id}/quizzes/{qid}/groups",params={"per_page":100}))
        (out/f"{quiz['key']}.json").write_text(json.dumps({"quiz":quiz,"questions":live,"groups":groups},indent=2)+"\n")
        for question in live: canvas.raw("DELETE",f"/courses/{course_id}/quizzes/{qid}/questions/{question['id']}")
        for group in groups: canvas.raw("DELETE",f"/courses/{course_id}/quizzes/{qid}/groups/{group['id']}")
        number=0
        for item in planned_items(parsed[quiz["key"]]):
            if item["kind"]=="pool":
                created=canvas.raw("POST",f"/courses/{course_id}/quizzes/{qid}/groups",{"quiz_groups":[{"name":item["name"],"pick_count":item["take"],"question_points":1}]})
                group=(created[0] if isinstance(created,list) else created); gid=group["id"]
                for question in item["questions"]:
                    number+=1; canvas.raw("POST",f"/courses/{course_id}/quizzes/{qid}/questions",question_payload(question,name=f"Question {number}",mcq_points=1,written_points=5,group_id=gid))
            else:
                number+=1; canvas.raw("POST",f"/courses/{course_id}/quizzes/{qid}/questions",question_payload(item["question"],name=f"Question {number}",mcq_points=1,written_points=5))
        settings={k:v for k,v in quiz["canvas"].items() if v is not None}
        canvas.raw("PUT",f"/courses/{course_id}/quizzes/{qid}",{"quiz":settings})
        changes.append({"key":quiz["key"],"questions":number})
    return {"status":"APPLIED","backup":str(out),"quizzes":changes}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,default=ROOT);p.add_argument("--server",default="http://127.0.0.1:5055")
    sub=p.add_subparsers(dest="command",required=True);e=sub.add_parser("export-live");e.add_argument("--initialize",action="store_true")
    sub.add_parser("verify");b=sub.add_parser("build-pdf");b.add_argument("--quiz");a=sub.add_parser("apply");a.add_argument("--confirm",required=True)
    args=p.parse_args();root=args.root.resolve()
    if args.command=="export-live":result=export_live(root,args.server,args.initialize)
    elif args.command=="verify":result=verify(root,args.server)
    elif args.command=="build-pdf":result=build_pdf(root,args.quiz)
    else:result=apply(root,args.server,args.confirm)
    print(json.dumps(result,indent=2,sort_keys=True));return 0

if __name__=="__main__":raise SystemExit(main())
