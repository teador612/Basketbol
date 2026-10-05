import os
import json
import time
from datetime import datetime
from statistics import mean
from zoneinfo import ZoneInfo

import requests


# =========================================================
# AYARLAR
# =========================================================

API_KEY = os.getenv("API_SPORTS_KEY")

if not API_KEY:
    raise RuntimeError("API_SPORTS_KEY bulunamadı.")

DATE = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")

OUTPUT_FILE = "data.json"

NBA_BASE = "https://v2.nba.api-sports.io"
BASKETBALL_BASE = "https://v1.basketball.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}

TIMEOUT = 30

SEASON = 2026

# API-Basketball'da Euroleague ID'yi /leagues üzerinden bulacağız.
EUROLEAGUE_ID = None


# =========================================================
# HTTP
# =========================================================

session = requests.Session()
session.headers.update(HEADERS)


def get_json(url, params=None):
    try:
        r = session.get(
            url,
            params=params,
            timeout=TIMEOUT
        )

        if r.status_code != 200:
            print(f"❌ HTTP {r.status_code}: {url}")
            return {}

        data = r.json()

        if data.get("errors"):
            print("⚠️ API hatası:", data["errors"])

        return data

    except Exception as e:
        print("❌ İstek hatası:", e)
        return {}


# =========================================================
# YARDIMCI
# =========================================================

def to_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except:
        return None


def game_date(game):
    """
    API-NBA:
        date.start

    API-Basketball:
        date
    """

    value = None

    date_obj = game.get("date")

    if isinstance(date_obj, dict):
        value = (
            date_obj.get("start")
            or date_obj.get("start")
            or date_obj.get("date")
        )
    else:
        value = date_obj

    if not value:
        return None

    try:
        value = str(value)

        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")

        dt = datetime.fromisoformat(value)

        if dt.tzinfo:
            dt = dt.astimezone(ZoneInfo("Europe/Istanbul"))

        return dt.date().isoformat()

    except:
        return str(value)[:10]


def is_finished(game):
    """
    API-NBA:
        3 = Finished

    API-Basketball:
        FT / AOT
    """

    status = game.get("status", {})

    if isinstance(status, dict):
        short = status.get("short")
        long_status = str(status.get("long", "")).upper()
    else:
        short = status
        long_status = str(status).upper()

    if str(short) in {"3", "FT", "AOT"}:
        return True

    if long_status in {
        "FINISHED",
        "FINISH",
        "FT",
        "AOT",
        "AFTER OVERTIME"
    }:
        return True

    return False


# =========================================================
# NBA
# =========================================================

def get_nba_today():

    print("\n🏀 NBA maçları alınıyor...")

    # Tarih filtresi bazı hesaplarda boş dönebildiği için
    # sezonun maçlarını alıp Türkiye tarihine göre filtreliyoruz.
    data = get_json(
        f"{NBA_BASE}/games",
        {
            "league": "standard",
            "season": SEASON
        }
    )

    games = data.get("response", [])

    result = []

    for game in games:

        if game_date(game) != DATE:
            continue

        teams = game.get("teams", {})

        home = teams.get("home", {})
        away = (
            teams.get("visitors")
            or teams.get("away")
            or {}
        )

        if not home.get("id") or not away.get("id"):
            continue

        result.append({
            "id": game.get("id"),
            "league": "NBA",
            "league_id": "standard",
            "season": SEASON,
            "home": {
                "id": home.get("id"),
                "name": home.get("name")
            },
            "away": {
                "id": away.get("id"),
                "name": away.get("name")
            },
            "raw": game
        })

    print(f"   📦 NBA: {len(result)} maç")

    return result


# =========================================================
# EUROLEAGUE LIGESINI BUL
# =========================================================

def find_euroleague():

    global EUROLEAGUE_ID

    print("\n🌍 EuroLeague ligi aranıyor...")

    data = get_json(
        f"{BASKETBALL_BASE}/leagues"
    )

    leagues = data.get("response", [])

    for league in leagues:

        name = str(league.get("name", "")).strip().lower()

        if name in {
            "euroleague",
            "euroleague basketball",
            "euroleague - euroleague"
        }:

            EUROLEAGUE_ID = league.get("id")

            print(
                f"   ✅ EuroLeague bulundu: "
                f"{league.get('name')} "
                f"(ID: {EUROLEAGUE_ID})"
            )

            return EUROLEAGUE_ID

    # Daha esnek arama
    for league in leagues:

        name = str(
            league.get("name", "")
        ).lower()

        country = str(
            league.get("country", {}).get("name", "")
        ).lower()

        if (
            "euroleague" in name
            and "women" not in name
        ):
            EUROLEAGUE_ID = league.get("id")

            print(
                f"   ✅ EuroLeague bulundu: "
                f"{league.get('name')} "
                f"(ID: {EUROLEAGUE_ID})"
            )

            return EUROLEAGUE_ID

    print("   ❌ EuroLeague bulunamadı.")

    return None


# =========================================================
# EUROLEGUE BUGÜN
# =========================================================

def get_euroleague_today():

    league_id = find_euroleague()

    if not league_id:
        return []

    print("\n🏀 EuroLeague maçları alınıyor...")

    data = get_json(
        f"{BASKETBALL_BASE}/games",
        {
            "league": league_id,
            "season": SEASON
        }
    )

    games = data.get("response", [])

    result = []

    for game in games:

        if game_date(game) != DATE:
            continue

        teams = game.get("teams", {})

        home = teams.get("home", {})
        away = teams.get("away", {})

        if not home.get("id") or not away.get("id"):
            continue

        result.append({
            "id": game.get("id"),
            "league": "EuroLeague",
            "league_id": league_id,
            "season": SEASON,
            "home": {
                "id": home.get("id"),
                "name": home.get("name")
            },
            "away": {
                "id": away.get("id"),
                "name": away.get("name")
            },
            "raw": game
        })

    print(
        f"   📦 EuroLeague: {len(result)} maç"
    )

    return result


# =========================================================
# NBA MAÇ SKORU
# =========================================================

def extract_nba_score(game, team_id):

    scores = game.get("scores", {})

    home_team = (
        game.get("teams", {})
        .get("home", {})
    )

    away_team = (
        game.get("teams", {})
        .get("visitors")
        or game.get("teams", {}).get("away", {})
    )

    home_score = (
        scores.get("home", {})
        if isinstance(scores.get("home"), dict)
        else {}
    )

    away_score = (
        scores.get("visitors")
        or scores.get("away")
        or {}
    )

    home_points = to_float(
        home_score.get("points")
    )

    away_points = to_float(
        away_score.get("points")
    )

    if home_points is None or away_points is None:
        return None

    if str(home_team.get("id")) == str(team_id):

        return {
            "team_id": team_id,
            "home": True,
            "for": home_points,
            "against": away_points
        }

    if str(away_team.get("id")) == str(team_id):

        return {
            "team_id": team_id,
            "home": False,
            "for": away_points,
            "against": home_points
        }

    return None


# =========================================================
# EUROLEGUE MAÇ SKORU
# =========================================================

def extract_basketball_score(game, team_id):

    scores = game.get("scores", {})

    teams = game.get("teams", {})

    home_team = teams.get("home", {})
    away_team = teams.get("away", {})

    home_score = to_float(
        scores.get("home")
        if not isinstance(scores.get("home"), dict)
        else scores.get("home", {}).get("total")
    )

    away_score = to_float(
        scores.get("away")
        if not isinstance(scores.get("away"), dict)
        else scores.get("away", {}).get("total")
    )

    # Bazı cevaplarda points kullanılabilir
    if home_score is None:
        obj = scores.get("home", {})
        if isinstance(obj, dict):
            home_score = to_float(
                obj.get("points")
                or obj.get("total")
            )

    if away_score is None:
        obj = scores.get("away", {})
        if isinstance(obj, dict):
            away_score = to_float(
                obj.get("points")
                or obj.get("total")
            )

    if home_score is None or away_score is None:
        return None

    if str(home_team.get("id")) == str(team_id):

        return {
            "team_id": team_id,
            "home": True,
            "for": home_score,
            "against": away_score
        }

    if str(away_team.get("id")) == str(team_id):

        return {
            "team_id": team_id,
            "home": False,
            "for": away_score,
            "against": home_score
        }

    return None


# =========================================================
# TAKIM SON 5 MAÇ
# =========================================================

def get_team_history(team_id, league_type):

    if league_type == "NBA":

        url = f"{NBA_BASE}/games"

        params = {
            "team": team_id,
            "season": SEASON
        }

    else:

        url = f"{BASKETBALL_BASE}/games"

        params = {
            "team": team_id,
            "league": EUROLEAGUE_ID,
            "season": SEASON
        }

    data = get_json(url, params)

    games = data.get("response", [])

    completed = []

    for game in games:

        if not is_finished(game):
            continue

        if league_type == "NBA":
            item = extract_nba_score(
                game,
                team_id
            )
        else:
            item = extract_basketball_score(
                game,
                team_id
            )

        if not item:
            continue

        item["date"] = game_date(game)

        completed.append(item)

    # Yeniden eskiye
    completed.sort(
        key=lambda x: x.get("date") or "",
        reverse=True
    )

    return completed


# =========================================================
# SADECE İÇ / DIŞ SAHA
# =========================================================

def get_last_5_home(team_id, league):

    history = get_team_history(
        team_id,
        league
    )

    return [
        x for x in history
        if x["home"]
    ][:5]


def get_last_5_away(team_id, league):

    history = get_team_history(
        team_id,
        league
    )

    return [
        x for x in history
        if not x["home"]
    ][:5]


# =========================================================
# ANALİZ
# =========================================================

def analyse_game(game):

    league = game["league"]

    home_id = game["home"]["id"]
    away_id = game["away"]["id"]

    print(
        f"\n   🔎 {game['home']['name']} "
        f"- {game['away']['name']}"
    )

    home_games = get_last_5_home(
        home_id,
        league
    )

    away_games = get_last_5_away(
        away_id,
        league
    )

    print(
        f"      🏠 Son iç saha: {len(home_games)}"
    )

    print(
        f"      ✈️ Son dış saha: {len(away_games)}"
    )

    if not home_games or not away_games:

        print("      ⚠️ Yeterli veri yok.")

        return None

    home_for = mean(
        x["for"]
        for x in home_games
    )

    home_against = mean(
        x["against"]
        for x in home_games
    )

    away_for = mean(
        x["for"]
        for x in away_games
    )

    away_against = mean(
        x["against"]
        for x in away_games
    )

    # -----------------------------------------------------
    # BEKLENEN SKOR
    # -----------------------------------------------------

    expected_home = (
        home_for + away_against
    ) / 2

    expected_away = (
        away_for + home_against
    ) / 2

    match_total = (
        expected_home + expected_away
    )

    quarter_avg = match_total / 4

    first_half = match_total / 2

    games_count = min(
        len(home_games),
        len(away_games)
    )

    # -----------------------------------------------------
    # GÜVEN
    # -----------------------------------------------------

    confidence_map = {
        5: 85,
        4: 80,
        3: 75,
        2: 65,
        1: 55,
        0: 0
    }

    confidence = confidence_map.get(
        games_count,
        0
    )

    print(
        f"      📊 Beklenen skor: "
        f"{expected_home:.1f} - "
        f"{expected_away:.1f}"
    )

    print(
        f"      📈 Toplam: {match_total:.1f}"
    )

    print(
        f"      🎯 Güven: %{confidence}"
    )

    return {
        "id": game["id"],
        "league": league,
        "league_id": game["league_id"],
        "season": SEASON,

        "home": game["home"]["name"],
        "away": game["away"]["name"],

        "home_team_id": home_id,
        "away_team_id": away_id,

        "games": games_count,

        "home_for_avg": round(home_for, 2),
        "home_against_avg": round(home_against, 2),

        "away_for_avg": round(away_for, 2),
        "away_against_avg": round(away_against, 2),

        "exp_home": round(expected_home, 2),
        "exp_away": round(expected_away, 2),

        "match_total": round(match_total, 2),

        "quarter_avg": round(
            quarter_avg,
            2
        ),

        "first_half": round(
            first_half,
            2
        ),

        "q1": round(quarter_avg, 2),
        "q2": round(quarter_avg, 2),
        "q3": round(quarter_avg, 2),
        "q4": round(quarter_avg, 2),

        "confidence": confidence,

        "date": DATE
    }


# =========================================================
# ANA PROGRAM
# =========================================================

def main():

    print("=" * 55)
    print("🏀 NBA + EUROLEAGUE BASKETBOL ANALİZİ")
    print("=" * 55)

    print(f"📅 Tarih: {DATE}")

    nba_games = get_nba_today()

    euroleague_games = get_euroleague_today()

    all_games = (
        nba_games +
        euroleague_games
    )

    print(
        f"\n🎯 Toplam maç: {len(all_games)}"
    )

    results = []

    for index, game in enumerate(
        all_games,
        1
    ):

        print(
            f"\n[{index}/{len(all_games)}] "
            f"{game['league']}"
        )

        try:

            result = analyse_game(game)

            if result:
                results.append(result)

        except Exception as e:

            print(
                f"      ❌ Analiz hatası: {e}"
            )

        # API'yi gereksiz hızlandırmamak için
        time.sleep(0.2)

    # -----------------------------------------------------
    # JSON
    # -----------------------------------------------------

    output = {
        DATE: results
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("\n" + "=" * 55)

    print(
        f"✅ {len(results)} maç analiz edildi."
    )

    print(
        f"📁 {OUTPUT_FILE} oluşturuldu."
    )

    print("=" * 55)


if __name__ == "__main__":
    main()
