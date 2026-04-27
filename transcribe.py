import json
import sys
import time
from pathlib import Path

from faster_whisper import WhisperModel


def transcribe(audio_path: str, lang: str | None = None):
    started_at = time.time()

    model = WhisperModel(
        "large-v3",
        device="cuda",
        compute_type="float16",
    )

    segments, info = model.transcribe(
        audio_path,
        language=lang,
        word_timestamps=True,
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
        hallucination_silence_threshold=2.0,
    )

    words = []
    lines = []
    plain_lines = []
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue

        plain_lines.append(text)

        lines.append({
            "text": text,
            "start_ms": int(seg.start * 1000),
            "end_ms": int(seg.end * 1000),
            "avg_logprob": getattr(seg, "avg_logprob", None),
            "no_speech_prob": getattr(seg, "no_speech_prob", None),
        })

        if seg.words:
            for w in seg.words:
                word = w.word.strip()
                if not word:
                    continue

                words.append({
                    "word": word,
                    "start_ms": int(w.start * 1000) if w.start is not None else None,
                    "end_ms": int(w.end * 1000) if w.end is not None else None,
                    "confidence": getattr(w, "probability", None),
                })

    elapsed_sec = round(time.time() - started_at, 2)

    return {
        "model": "faster-whisper-large-v3",
        "language": info.language,
        "language_probability": info.language_probability,
        "elapsed_sec": elapsed_sec,
        "plainLyrics": "\n".join(plain_lines),
        "lines": lines,
        "words": words,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py audio_path [language]")
        sys.exit(1)

    audio_path = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else None

    result = transcribe(audio_path, lang)

    audio_name = Path(audio_path).stem
    out_path = Path("outputs") / f"{audio_name}.prediction.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Saved: {out_path}")
    print(f"Language: {result['language']} ({result['language_probability']:.3f})")
    print(f"Elapsed: {result['elapsed_sec']} sec")
    print("Preview:")
    print(result["plainLyrics"][:1500])
