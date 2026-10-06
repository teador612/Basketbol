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


def find_value(obj, names):
    if not isinstance(obj, dict):
        return None

    lower = {
        str(k).lower(): v
        for k, v in obj.items()
    }

    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]

    return None


def get_euroleague_games():
    print()
    print("========================================")
    print("🌍 EUROLEAGUE VERİLERİ")
    print("========================================")

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

        response.raise_for_status()

        data = response.json()

    except Exception as e:
        print(f"❌ EuroLeague API hatası: {e}")
        return []

    if isinstance(data, dict):
        games = data.get("data", [])

        if not isinstance(games, list):
            games = data.get("games", [])

    elif isinstance(data, list):
        games = data

    else:
        games = []

    print(f"📦 API maç kaydı: {len(games)}")

    result = []

    for game in games:

        if not isinstance(game, dict):
            continue

        game_code = find_value(
            game,
            [
                "gameCode",
                "gamecode",
                "code",
                "gameId",
                "id",
            ],
        )

        date = find_value(
            game,
            [
                "date",
                "gameDate",
                "startDate",
                "startTime",
            ],
        )

        home_team = find_value(
            game,
            [
                "localTeamName",
                "homeTeamName",
                "localTeam",
                "homeTeam",
                "home",
            ],
        )

        away_team = find_value(
            game,
            [
                "roadTeamName",
                "awayTeamName",
                "roadTeam",
                "awayTeam",
                "away",
            ],
        )

        home_score = find_value(
            game,
            [
                "localScore",
                "homeScore",
                "localPoints",
                "homePoints",
            ],
        )

        away_score = find_value(
            game,
            [
                "roadScore",
                "awayScore",
                "roadPoints",
                "awayPoints",
            ],
        )

        if isinstance(home_team, dict):
            home_team = find_value(
                home_team,
                [
                    "name",
                    "teamName",
                    "clubName",
                ],
            )

        if isinstance(away_team, dict):
            away_team = find_value(
                away_team,
                [
                    "name",
                    "teamName",
                    "clubName",
                ],
            )

        if game_code is None:
            continue

        status = "scheduled"

        try:
            if home_score is not None and away_score is not None:
                home_score = int(home_score)
                away_score = int(away_score)
                status = "finished"
            else:
                home_score = None
                away_score = None
        except Exception:
            home_score = None
            away_score = None

        result.append({
            "id": f"EL-{game_code}",
            "gameCode": str(game_code),
            "league": "EuroLeague",
            "season": EUROLEAGUE_SEASON,
            "date": date,
            "homeTeam": home_team,
            "awayTeam": away_team,
            "homeScore": home_score,
            "awayScore": away_score,
            "status": status,
            "source": "euroleague_api",
        })

    print(f"🌍 EuroLeague toplam maç: {len(result)}")

    return result


def save_data(euroleague_games):

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    unique = {}

    for game in euroleague_games:
        key = game.get("id")

        if key:
            unique[key] = game

    games = list(unique.values())

    games.sort(
        key=lambda x: str(
            x.get("date") or ""
        )
    )

    output = {
        "updatedAt": now_iso(),
        "euroleagueSeason": EUROLEAGUE_SEASON,
        "count": len(games),
        "matches": games,
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
    print(f"🌍 EuroLeague: {len(games)}")


def main():

    print("🏀 BASKETBOL VERİ GÜNCELLEYİCİ")
    print(f"EuroLeague: {EUROLEAGUE_SEASON}")

    euroleague = get_euroleague_games()

    if not euroleague:
        raise RuntimeError(
            "EuroLeague verisi alınamadı."
        )

    save_data(euroleague)


if __name__ == "__main__":
    main()
