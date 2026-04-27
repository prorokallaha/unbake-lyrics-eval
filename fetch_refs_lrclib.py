import json
import urllib.parse
import urllib.request
from pathlib import Path


TRACKS = [
    {
        "key": "rockstar",
        "artist": "Post Malone",
        "title": "rockstar",
        "lang": "en",
        "hyp_contains": "Post_Malone",
    },
    {
        "key": "bellakeo",
        "artist": "Peso Pluma",
        "title": "BELLAKEO",
        "lang": "es",
        "hyp_contains": "BELLAKEO",
    },
    {
        "key": "bruce_wayne",
        "artist": "Peso Pluma",
        "title": "BRUCE WAYNE",
        "lang": "es",
        "hyp_contains": "BRUCE_WAYNE",
    },
    {
        "key": "solicitado",
        "artist": "Peso Pluma",
        "title": "SOLICITADO",
        "lang": "es",
        "hyp_contains": "SOLICITADO",
    },
    {
        "key": "place_de_la_republique",
        "artist": "Coeur de Pirate",
        "title": "Place de la Republique",
        "lang": "fr",
        "hyp_contains": "Place_de_la",
    },
    {
        "key": "last_of_us",
        "artist": "Miyagi",
        "title": "Last of Us",
        "lang": "ru",
        "hyp_contains": "Last_of_Us",
    },
    {
        "key": "diko_naprimer",
        "artist": "PHARAOH",
        "title": "Дико, например",
        "lang": "ru",
        "hyp_contains": "Pharaoh",
    },
]


def find_hyp_file(marker: str):
    files = sorted(Path("outputs").glob("*.prediction.json"))
    matches = [p for p in files if marker.lower() in p.name.lower()]
    return matches[0] if matches else None



def lrclib_search(artist: str, title: str):
    params = urllib.parse.urlencode({
        "artist_name": artist,
        "track_name": title,
    })

    url = "https://lrclib.net/api/search?" + params

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "lyrics-sync-eval/0.1"},
    )

    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    refs_dir = Path("refs")
    refs_dir.mkdir(exist_ok=True)

    mapping = []

    for t in TRACKS:
        print("\nSearching:", t["artist"], "-", t["title"])

        hyp_file = find_hyp_file(t["hyp_contains"])
        print("Hyp:", hyp_file)

        try:
            results = lrclib_search(t["artist"], t["title"])
        except Exception as e:
            print("LRCLIB ERROR:", repr(e))
            results = []

        if not results:
            print("No LRCLIB results")
            continue

        best = results[0]
        lyrics = best.get("plainLyrics") or ""
        synced = best.get("syncedLyrics") or ""

        if not lyrics.strip():
            print("No plainLyrics in best result")
            continue

        ref_path = refs_dir / f"{t['key']}.ref.txt"
        ref_path.write_text(lyrics, encoding="utf-8")

        meta_path = refs_dir / f"{t['key']}.lrclib_meta.json"
        meta_path.write_text(json.dumps(best, ensure_ascii=False, indent=2), encoding="utf-8")

        print("Saved ref:", ref_path)
        print("LRCLIB:", best.get("artistName"), "-", best.get("trackName"))
        print("Has synced:", bool(synced))

        mapping.append({
            "key": t["key"],
            "lang": t["lang"],
            "ref": str(ref_path),
            "hyp": str(hyp_file) if hyp_file else None,
            "artist": t["artist"],
            "title": t["title"],
            "lrclib_artist": best.get("artistName"),
            "lrclib_track": best.get("trackName"),
            "has_synced": bool(synced),
        })

    Path("refs/mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nSaved mapping: refs/mapping.json")


if __name__ == "__main__":
    main()
