import json
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT = DATA_DIR / "basketball.json"

EUROLEAGUE_SEASON = "E2026"

EUROLEAGUE_URL = (
    "https://api-live.euroleague.net"
    f"/v2/competitions/E/seasons/{EUROLEAGUE_SEASON}/games"
)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_euroleague_games():
    print()
    print("========================================")
    print("🌍 EUROLEAGUE API KONTROLÜ")
    print("========================================")
    print(f"Sezon: {EUROLEAGUE_SEASON}")
    print()

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/140 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    try:
        response = requests.get(
            EUROLEAGUE_URL,
            headers=headers,
            timeout=60,
        )

        print("HTTP:", response.status_code)

        response.raise_for_status()

        data = response.json()

    except Exception as e:
        print()
        print("❌ EuroLeague API hatası:")
        print(e)
        return []

    if isinstance(data, dict):
        games = data.get("data")

        if not isinstance(games, list):
            games = data.get("games")

        if not isinstance(games, list):
            games = []

    elif isinstance(data, list):
        games = data

    else:
        games = []

    print()
    print("📦 API maç kaydı:", len(games))

    if not games:
        print("❌ API boş veri döndürdü.")
        return []

    # =====================================================
    # HAM API KAYDI
    # =====================================================

    print()
    print("========================================")
    print("🔎 İLK HAM API KAYDI")
    print("========================================")

    print(
        json.dumps(
            games[0],
            ensure_ascii=False,
            indent=2,
        )
    )

    # =====================================================
    # TÜM ALANLARI GÖSTER
    # =====================================================

    print()
    print("========================================")
    print("🔑 İLK KAYDIN ALANLARI")
    print("========================================")

    if isinstance(games[0], dict):
        for key, value in games[0].items():
            print(
                f"{key}: "
                f"{type(value).__name__} = "
                f"{value}"
            )

    # =====================================================
    # SADECE TEST AMAÇLI JSON KAYDI
    # =====================================================

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "updatedAt": now_iso(),
        "euroleagueSeason": EUROLEAGUE_SEASON,
        "count": len(games),
        "rawGames": games,
    }

    OUTPUT.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("========================================")
    print("✅ HAM VERİ KAYDEDİLDİ")
    print("========================================")
    print(f"📁 {OUTPUT}")
    print(f"🌍 EuroLeague maç sayısı: {len(games)}")
    print()
    print("➡️ Şimdi workflow çıktısındaki")
    print("'İLK HAM API KAYDI' bölümünü gönder.")


def main():
    print("🏀 BASKETBOL VERİ KONTROLÜ")
    print(f"EuroLeague sezonu: {EUROLEAGUE_SEASON}")

    get_euroleague_games()


if __name__ == "__main__":
    main()
