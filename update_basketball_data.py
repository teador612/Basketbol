import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from nba_api.stats.endpoints import leaguegamelog


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT = DATA_DIR / "basketball.json"

NBA_SEASON = "2026-27"
EUROLEAGUE_SEASON = "E2026"

EUROLEAGUE_URL = (
    "https://api-live.euroleague.net"
    f"/v2/competitions/E/seasons/{EUROLEAGUE_SEASON}/games"
)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def clean_value(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


# =========================================================
# NBA
# =========================================================

def get_nba_games():
    print()
    print("========================================")
    print("🏀 NBA VERİLERİ")
    print("========================================")

    rows = []

    for season_type in ["Regular Season", "Playoffs", "Pre Season"]:
        print(f"📅 {NBA_SEASON} - {season_type}")

        try:
            result = leaguegamelog.LeagueGameLog(
                counter=0,
                direction="ASC",
                league_id="00",
                player_or_team_abbreviation="T",
                season=NBA_SEASON,
                season_type_all_star=season_type,
                sorter="DATE",
                timeout=60,
            )

            df = result.league_game_log.get_data_frame()

            if df.empty:
                print("   Veri yok.")
                continue

            # Her NBA maçı iki takım satırı olarak gelir.
            for game_id, group in df.groupby("GAME_ID"):
                group = group.copy()

                if len(group) < 2:
                    continue

                home = group[
                    group["MATCHUP"].astype(str).str.contains(" vs. ")
                ]

                away = group[
                    group["MATCHUP"].astype(str).str.contains(" @ ")
                ]

                if home.empty or away.empty:
                    continue

                h = home.iloc[0]
                a = away.iloc[0]

                rows.append({
                    "id": str(game_id),
                    "league": "NBA",
                    "season": NBA_SEASON,
                    "stage": season_type,
                    "date": str(h["GAME_DATE"]),
                    "homeTeam": str(h["TEAM_NAME"]),
                    "awayTeam": str(a["TEAM_NAME"]),
                    "homeScore": int(h["PTS"]),
                    "awayScore": int(a["PTS"]),
                    "status": "finished",
                    "source": "nba_api",
                })

            print(f"   ✓ {len(df)} takım kaydı işlendi.")

        except Exception as e:
            print(f"   ❌ NBA hatası: {e}")

    # Aynı maçı tekrar etme
    unique = {}

    for game in rows:
        unique[game["id"]] = game

    rows = list(unique.values())

    print(f"🏀 NBA toplam maç: {len(rows)}")

    return rows


# =========================================================
# EUROLeague
# =========================================================

def find_value(obj, names):
    """
    API alan isimleri değişebildiği için
    birkaç olası alan adını kontrol eder.
    """

    if not isinstance(obj, dict):
        return None

    lower = {
        str(k).lower(): v
        for k, v in obj.items()
    }

    for name in names:
        key = name.lower()

        if key in lower:
            return lower[key]

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

    # API genellikle data[] döndürüyor.
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

        # Bazı API cevaplarında takım bilgilerinin
        # nesne içinde gelme ihtimaline karşı.
        if isinstance(home_team, dict):
            home_team = find_value(
                home_team,
                ["name", "teamName", "clubName"]
            )

        if isinstance(away_team, dict):
            away_team = find_value(
                away_team,
                ["name", "teamName", "clubName"]
            )

        if game_code is None:
            continue

        status = "scheduled"

        if (
            home_score is not None
            and away_score is not None
        ):
            try:
                home_score = int(home_score)
                away_score = int(away_score)
                status = "finished"
            except Exception:
                home_score = None
                away_score = None

        result.append({
            "id": f"EL-{game_code}",
            "gameCode": str(game_code),
            "league": "EuroLeague",
            "season": EUROPEAN_SEASON if False else EUROPEAN_SEASON,
            "date": date,
            "homeTeam": home_team,
            "awayTeam": away_team,
            "homeScore": home_score,
            "awayScore": away_score,
            "status": status,
            "source": "euroleague_api",
        })

    # Yukarıdaki sezon değerini açık şekilde düzelt.
    for game in result:
        game["season"] = EUROLEAGUE_SEASON

    print(f"🌍 EuroLeague toplam maç: {len(result)}")

    return result


# =========================================================
# KAYDET
# =========================================================

def save_data(nba_games, euroleague_games):

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_games = nba_games + euroleague_games

    # ID bazında tekilleştir
    unique = {}

    for game in all_games:
        unique[
            f"{game.get('league')}-{game.get('id')}"
        ] = game

    all_games = list(unique.values())

    all_games.sort(
        key=lambda x: str(x.get("date") or "")
    )

    output = {
        "updatedAt": now_iso(),
        "nbaSeason": NBA_SEASON,
        "euroleagueSeason": EUROLEAGUE_SEASON,
        "count": len(all_games),
        "matches": all_games,
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
    print(f"🏀 Toplam maç: {len(all_games)}")

    nba_count = sum(
        1 for x in all_games
        if x.get("league") == "NBA"
    )

    euro_count = sum(
        1 for x in all_games
        if x.get("league") == "EuroLeague"
    )

    print(f"NBA: {nba_count}")
    print(f"EuroLeague: {euro_count}")


def main():
    print("🏀 BASKETBOL VERİ GÜNCELLEYİCİ")
    print(f"NBA: {NBA_SEASON}")
    print(f"EuroLeague: {EUROLEAGUE_SEASON}")

    nba = get_nba_games()

    time.sleep(2)

    euroleague = get_euroleague_games()

    save_data(nba, euroleague)


if __name__ == "__main__":
    main()
