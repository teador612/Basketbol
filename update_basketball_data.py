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
    print("🌍 EUROLEAGUE VERİLERİ")
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

    print("📦 API maç kaydı:", len(games))

    return games


def convert_game(game):
    local = game.get("local") or {}
    road = game.get("road") or {}

    local_club = local.get("club") or {}
    road_club = road.get("club") or {}

    home_name = local_club.get("name")
    away_name = road_club.get("name")

    if not home_name or not away_name:
        return None

    played = bool(game.get("played", False))

    home_score = local.get("score")
    away_score = road.get("score")

    # Oynanmamış maçlarda API 0-0 döndürüyor.
    # Bu nedenle skorları None yapıyoruz.
    if not played:
        home_score = None
        away_score = None
    else:
        try:
            home_score = int(home_score)
        except (TypeError, ValueError):
            home_score = None

        try:
            away_score = int(away_score)
        except (TypeError, ValueError):
            away_score = None

    return {
        "id": game.get("id"),
        "gameCode": game.get("gameCode"),
        "league": "EuroLeague",
        "season": EUROLEAGUE_SEASON,
        "round": game.get("round"),
        "date": game.get("date"),
        "utcDate": game.get("utcDate"),
        "homeTeam": home_name,
        "awayTeam": away_name,
        "homeScore": home_score,
        "awayScore": away_score,
        "played": played,
        "status": "finished" if played else "scheduled",
    }


def main():
    print("🏀 BASKETBOL VERİ GÜNCELLEYİCİ")
    print("========================================")

    games = get_euroleague_games()

    if not games:
        raise RuntimeError("EuroLeague maç verisi alınamadı.")

    matches = []

    for game in games:
        converted = convert_game(game)

        if converted:
            matches.append(converted)

    if not matches:
        raise RuntimeError(
            "EuroLeague maçları dönüştürülemedi."
        )

    finished = [
        m for m in matches
        if m["played"]
        and m["homeScore"] is not None
        and m["awayScore"] is not None
    ]

    scheduled = [
        m for m in matches
        if not m["played"]
    ]

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output = {
        "source": EUROLEAGUE_URL,
        "updatedAt": now_iso(),
        "euroleagueSeason": EUROLEAGUE_SEASON,
        "total": len(matches),
        "finished": len(finished),
        "scheduled": len(scheduled),
        "matches": matches,
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
    print("✅ VERİ KAYDEDİLDİ")
    print("========================================")
    print(f"📁 {OUTPUT}")
    print(f"🏀 Toplam maç: {len(matches)}")
    print(f"✅ Oynanmış/skorlu: {len(finished)}")
    print(f"📅 Oynanmamış: {len(scheduled)}")

    print()
    print("========================================")
    print("🔎 ÖRNEK MAÇLAR")
    print("========================================")

    for match in matches[:5]:
        print(
            f'{match["date"]} | '
            f'{match["homeTeam"]} - {match["awayTeam"]} | '
            f'{match["homeScore"]} - {match["awayScore"]} | '
            f'{match["status"]}'
        )


if __name__ == "__main__":
    main()
