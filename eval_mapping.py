import json
import re
from pathlib import Path

from jiwer import wer, cer


def normalize(text: str, lang: str = "en") -> str:
    text = text.lower().strip()
    text = text.replace("ё", "е")

    if lang not in {"ja", "jp"}:
        text = re.sub(r"[^\w\s']", " ", text, flags=re.UNICODE)

    return re.sub(r"\s+", " ", text).strip()

def evaluate(ref_text: str, hyp_text: str, lang: str):
    ref_norm = normalize(ref_text, lang)
    hyp_norm = normalize(hyp_text, lang)

    return {
        "wer": round(wer(ref_norm, hyp_norm), 4) if ref_norm else None,
        "cer": round(cer(ref_norm, hyp_norm), 4) if ref_norm else None,
        "ref_words": len(ref_norm.split()),
        "hyp_words": len(hyp_norm.split()),
        "ref_chars": len(ref_norm),
        "hyp_chars": len(hyp_norm),
    }


mapping = json.loads(Path("refs/mapping.json").read_text(encoding="utf-8"))

rows = []
for item in mapping:
    if not item.get("hyp"):
        continue

    ref_text = Path(item["ref"]).read_text(encoding="utf-8")
    hyp_json = json.loads(Path(item["hyp"]).read_text(encoding="utf-8"))
    hyp_text = hyp_json.get("plainLyrics", "")

    metrics = evaluate(ref_text, hyp_text, item["lang"])

    row = {
        "key": item["key"],
        "lang": item["lang"],
        "artist": item["artist"],
        "title": item["title"],
        "hyp": item["hyp"],
        **metrics,
    }

    rows.append(row)

Path("outputs/eval_results.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("key,lang,wer,cer,ref_words,hyp_words")
for r in rows:
    print(f"{r['key']},{r['lang']},{r['wer']},{r['cer']},{r['ref_words']},{r['hyp_words']}")

if rows:
    avg_wer = sum(r["wer"] for r in rows if r["wer"] is not None) / len(rows)
    avg_cer = sum(r["cer"] for r in rows if r["cer"] is not None) / len(rows)
    print()
    print(f"AVG WER: {avg_wer:.4f}")
    print(f"AVG CER: {avg_cer:.4f}")
