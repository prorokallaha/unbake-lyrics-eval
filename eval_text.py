import json
import re
import sys
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
        "lang": lang,
        "wer": round(wer(ref_norm, hyp_norm), 4) if ref_norm else None,
        "cer": round(cer(ref_norm, hyp_norm), 4) if ref_norm else None,
        "ref_chars": len(ref_norm),
        "hyp_chars": len(hyp_norm),
        "ref_words": len(ref_norm.split()),
        "hyp_words": len(hyp_norm.split()),
    }


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python eval_text.py ref.txt hyp.txt lang")
        sys.exit(1)

    ref_path = Path(sys.argv[1])
    hyp_path = Path(sys.argv[2])
    lang = sys.argv[3]

    ref_text = ref_path.read_text(encoding="utf-8")
    hyp_text = hyp_path.read_text(encoding="utf-8")

    print(json.dumps(evaluate(ref_text, hyp_text, lang), ensure_ascii=False, indent=2))
