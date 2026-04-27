import json
import time
from pathlib import Path

from faster_whisper import WhisperModel


AUDIO_EXTS = {".m4a", ".wav", ".mp3", ".flac"}
LANG_MAP = {
    "en": "en",
    "es": "es",
    "fr": "fr",
    "ru": "ru",
    "it": "it",
    "pt": "pt",
    "pl": "pl",
    "jp": "ja",
}


def collect_audio_files(root: str = "dataset"):
    files = []
    for path in Path(root).rglob("*"):
        if path.is_file() and path.suffix.lower() in AUDIO_EXTS:
            files.append(path)
    return sorted(files)


def detect_lang_from_path(path: Path):
    parts = path.parts
    for part in parts:
        if part in LANG_MAP:
            return LANG_MAP[part]
    return None

def transcribe_one(model: WhisperModel, audio_path: Path):
    started_at = time.time()
    language_hint = detect_lang_from_path(audio_path)

    segments, info = model.transcribe(
        str(audio_path),
        language=language_hint,
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
        "file": str(audio_path),
        "model": "faster-whisper-large-v3",
        "language_hint": language_hint,
        "detected_language": info.language,
        "language_probability": info.language_probability,
        "elapsed_sec": elapsed_sec,
        "plainLyrics": "\n".join(plain_lines),
        "lines": lines,
        "words": words,
    }


def safe_name(path: Path) -> str:
    parts = path.with_suffix("").parts
    return "__".join(parts[-4:]).replace(" ", "_").replace("/", "_")


def main():
    audio_files = collect_audio_files("dataset")

    if not audio_files:
        print("No audio files found in dataset/")
        return

    print(f"Found {len(audio_files)} audio files:")
    for p in audio_files:
        print(" -", p, "| lang_hint:", detect_lang_from_path(p))

    Path("outputs").mkdir(exist_ok=True)

    print("\nLoading model once...")
    model = WhisperModel(
        "large-v3",
        device="cuda",
        compute_type="float16",
    )

    summary = []

    for idx, audio_path in enumerate(audio_files, start=1):
        print(f"\n[{idx}/{len(audio_files)}] Transcribing: {audio_path}")
        try:
            result = transcribe_one(model, audio_path)

            out_path = Path("outputs") / f"{safe_name(audio_path)}.prediction.json"
            out_path.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            print(f"Saved: {out_path}")
            print(f"Language hint: {result['language_hint']}")
            print(f"Detected: {result['detected_language']} ({result['language_probability']:.3f})")
            print(f"Elapsed: {result['elapsed_sec']} sec")
            print("Preview:")
            print(result["plainLyrics"][:800])

            summary.append({
                "file": str(audio_path),
                "output": str(out_path),
                "model": result["model"],
                "language_hint": result["language_hint"],
                "detected_language": result["detected_language"],
                "language_probability": result["language_probability"],
                "elapsed_sec": result["elapsed_sec"],
                "chars": len(result["plainLyrics"]),
                "words": len(result["words"]),
                "lines": len(result["lines"]),
                "error": None,
            })

        except Exception as e:
            print("ERROR:", repr(e))
            summary.append({
                "file": str(audio_path),
                "output": None,
                "model": "faster-whisper-large-v3",
                "language_hint": detect_lang_from_path(audio_path),
                "detected_language": None,
                "language_probability": None,
                "elapsed_sec": None,
                "chars": 0,
                "words": 0,
                "lines": 0,
                "error": repr(e),
            })

    summary_path = Path("outputs") / "summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nDone.")
    print(f"Summary saved: {summary_path}")


if __name__ == "__main__":
    main()
