"""Payload conversion for Canvas New Quiz Items API."""
from __future__ import annotations
import html, uuid, re
from .testmaker import Question

_NS=uuid.UUID("ac977711-dc31-4f44-a930-9a72fcb2e77d")
def _uid(key): return str(uuid.uuid5(_NS,key))

def new_quiz_item_payload(q: Question, *, name: str, points: float, position: int, image_urls=None) -> dict:
    def rich(text):
        pos=0; out=[]
        for m in re.finditer(r"\[Image:\s*([^\]]+)\]",text,re.I):
            out.append(html.escape(text[pos:m.start()])); n=m.group(1).strip(); u=(image_urls or {}).get(n)
            out.append(f'<img src="{html.escape(u)}" alt="Question image: {html.escape(n)}">' if u else html.escape(m.group(0))); pos=m.end()
        out.append(html.escape(text[pos:])); return "".join(out)
    entry={"title":name,"item_body":f"<p>{rich(q.stem)}</p>","calculator_type":"none"}
    if q.distractors:
        texts=[q.answer,*q.distractors]; ids=[_uid(f"{q.stem}\0{x}\0{i}") for i,x in enumerate(texts)]
        entry.update({"interaction_type_slug":"choice",
          "interaction_data":{"choices":[{"id":i,"position":n+1,"item_body":rich(t)} for n,(i,t) in enumerate(zip(ids,texts))]},
          "properties":{"choices":{"shuffle":True}},"scoring_data":{"value":ids[0]},"scoring_algorithm":"Equivalence"})
    else:
        entry.update({"interaction_type_slug":"essay","interaction_data":{"rce":True},
                      "scoring_data":{"value":None},"scoring_algorithm":"None"})
    return {"item":{"position":position,"points_possible":points,"entry_type":"Item","entry":entry}}
