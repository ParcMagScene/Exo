import json
d = json.load(open(r"D:\EXO\models\cosyvoice_fr\voices.json", encoding="utf-8"))
for v in d:
    pt = v.get("prompt_text", "")
    print(f"{v.get('id'):15s} | file={v.get('file'):20s} | pt_len={len(pt):3d} | text={pt!r}")
