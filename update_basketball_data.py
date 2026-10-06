import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


# =========================================================
# AYARLAR
# =========================================================

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT = DATA_DIR / "basketball.json"

EUROLEAGUE_SEASON = "E2026"

EUROLEAGUE_URL = (
    "https://api-live.euroleague.net"
    f"/v2/competitions/E/seasons/{EUROLEAGUE_SEASON}/games"
)

ESPN_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/basketball/nba/scoreboard"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140 Safari/537.36"
    ),
    "Accept": "application/json",
}


# =========================================================
# YARDIMCI
# =========================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_date(value):
    if not value:
        return None

    try:
        text = str(value)

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        return datetime.fromisoformat(text)

    except Exception:
        pass

    try:
        return datetime.strptime(
            str(value)[:10],
            "%Y-%m-%d"
        )

    except Exception:
        return None


# =========================================================
# EUROLEAGUE
# =========================================================

def get_euroleague_games():

    print()
    print("========================================")
    print("🌍 EUROLEAGUE")
    print("========================================")

    try:
        response = requests.get(
            EUROLEAGUE_URL,
            headers=HEADERS,
            timeout=60
        )

        print("HTTP:", response.status_code)

        response.raise_for_status()

        data = response.json()

    except Exception as e:
        print("❌ EuroLeague hatası:", e)
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

    print("📦 EuroLeague ham maç:", len(games))

    matches = []

    for game in games:

        local = game.get("local") or {}
        road = game.get("road") or {}

        local_club = local.get("club") or {}
        road_club = road.get("club") or {}

        home = local_club.get("name")
        away = road_club.get("name")

        if not home or not away:
            continue

        played = bool(game.get("played"))

        home_score = (
            safe_int(local.get("score"))
            if played
            else None
        )

        away_score = (
            safe_int(road.get("score"))
            if played
            else None
        )

        matches.append({
            "id": game.get("id"),
            "league": "EuroLeague",
            "season": EUROLEAGUE_SEASON,
            "date": game.get("date"),
            "utcDate": game.get("utcDate"),
            "round": game.get("round"),
            "homeTeam": home,
            "awayTeam": away,
            "homeScore": home_score,
            "awayScore": away_score,
            "played": played,
            "status": (
                "finished"
                if played
                else "scheduled"
            )
        })

    print("✅ EuroLeague işlenen:", len(matches))

    return matches


# =========================================================
# ESPN NBA - TEK GÜN
# =========================================================

def get_nba_day(date_value):

    date_text = date_value.strftime("%Y%m%d")

    try:
        response = requests.get(
            ESPN_URL,
            params={
                "dates": date_text,
                "limit": 100
            },
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

    except Exception as e:

        print(
            f"   ❌ {date_text} NBA hatası: {e}"
        )

        return []

    events = data.get("events") or []

    matches = []

    for event in events:

        competitions = (
            event.get("competitions")
            or []
        )

        if not competitions:
            continue

        competition = competitions[0]

        competitors = (
            competition.get("competitors")
            or []
        )

        home = None
        away = None

        for competitor in competitors:

            team = competitor.get("team") or {}

            item = {
                "id": team.get("id"),
                "name": (
                    team.get("displayName")
                    or team.get("shortDisplayName")
                    or team.get("name")
                ),
                "abbreviation": (
                    team.get("abbreviation")
                ),
                "score": safe_int(
                    competitor.get("score")
                )
            }

            if competitor.get("homeAway") == "home":
                home = item

            elif competitor.get("homeAway") == "away":
                away = item

        if not home or not away:
            continue

        status_data = (
            event.get("status")
            or {}
        )

        status_type = (
            status_data.get("type")
            or {}
        )

        state = (
            status_type.get("state")
            or ""
        ).lower()

        completed = bool(
            status_type.get("completed")
        )

        played = (
            completed
            or state == "post"
        )

        home_score = (
            home.get("score")
            if played
            else None
        )

        away_score = (
            away.get("score")
            if played
            else None
        )

        matches.append({
            "id": event.get("id"),
            "league": "NBA",
            "season": "2026-27",
            "date": event.get("date"),
            "utcDate": event.get("date"),
            "round": None,

            "homeTeam": home["name"],
            "awayTeam": away["name"],

            "homeScore": home_score,
            "awayScore": away_score,

            "played": played,

            "status": (
                "finished"
                if played
                else "scheduled"
            )
        })

    return matches


# =========================================================
# NBA
# SON 120 GÜN + GELECEK 30 GÜN
# =========================================================

def get_nba_games():

    print()
    print("========================================")
    print("🏀 NBA")
    print("========================================")

    today = datetime.now(timezone.utc).date()

    start = today - timedelta(days=120)
    end = today + timedelta(days=30)

    print(
        f"📅 NBA tarih aralığı: "
        f"{start} → {end}"
    )

    all_matches = []

    current = start

    total_days = (
        end - start
    ).days + 1

    day_number = 0

    while current <= end:

        day_number += 1

        print(
            f"   NBA gün {day_number}/{total_days}: "
            f"{current}"
        )

        games = get_nba_day(
            datetime.combine(
                current,
                datetime.min.time(),
                tzinfo=timezone.utc
            )
        )

        all_matches.extend(games)

        current += timedelta(days=1)

    # Aynı maç iki kere gelirse kaldır.
    unique = {}

    for match in all_matches:

        game_id = match.get("id")

        if game_id:
            unique[game_id] = match

    matches = list(unique.values())

    matches.sort(
        key=lambda x: (
            parse_date(x.get("date"))
            or datetime.max
        )
    )

    print(
        "🏀 NBA toplam maç:",
        len(matches)
    )

    return matches


# =========================================================
# SON 5 İÇ SAHA
# =========================================================

def last_five_home(
    matches,
    team,
    before_date
):

    target = parse_date(before_date)

    if target is None:
        return []

    previous = []

    for match in matches:

        if match.get("homeTeam") != team:
            continue

        if not match.get("played"):
            continue

        if (
            match.get("homeScore") is None
            or match.get("awayScore") is None
        ):
            continue

        match_date = parse_date(
            match.get("date")
        )

        if match_date is None:
            continue

        if match_date >= target:
            continue

        previous.append(match)

    previous.sort(
        key=lambda x: (
            parse_date(x.get("date"))
            or datetime.min
        ),
        reverse=True
    )

    return [
        {
            "date": match.get("date"),
            "opponent": match.get("awayTeam"),
            "scored": match.get("homeScore"),
            "conceded": match.get("awayScore")
        }
        for match in previous[:5]
    ]


# =========================================================
# SON 5 DEPLASMAN
# =========================================================

def last_five_away(
    matches,
    team,
    before_date
):

    target = parse_date(before_date)

    if target is None:
        return []

    previous = []

    for match in matches:

        if match.get("awayTeam") != team:
            continue

        if not match.get("played"):
            continue

        if (
            match.get("homeScore") is None
            or match.get("awayScore") is None
        ):
            continue

        match_date = parse_date(
            match.get("date")
        )

        if match_date is None:
            continue

        if match_date >= target:
            continue

        previous.append(match)

    previous.sort(
        key=lambda x: (
            parse_date(x.get("date"))
            or datetime.min
        ),
        reverse=True
    )

    return [
        {
            "date": match.get("date"),
            "opponent": match.get("homeTeam"),
            "scored": match.get("awayScore"),
            "conceded": match.get("homeScore")
        }
        for match in previous[:5]
    ]


# =========================================================
# SON 5 EKLE
# =========================================================

def add_last_five(matches):

    print()
    print("========================================")
    print("📊 SON 5 VERİLER HESAPLANIYOR")
    print("========================================")

    finished = [
        match
        for match in matches
        if (
            match.get("played")
            and match.get("homeScore") is not None
            and match.get("awayScore") is not None
        )
    ]

    print(
        "Geçmişte kullanılabilir maç:",
        len(finished)
    )

    for match in matches:

        match["homeLast5"] = last_five_home(
            finished,
            match.get("homeTeam"),
            match.get("date")
        )

        match["awayLast5"] = last_five_away(
            finished,
            match.get("awayTeam"),
            match.get("date")
        )

    return matches


# =========================================================
# SON 5 KONTROL
# =========================================================

def print_samples(matches):

    print()
    print("========================================")
    print("🔎 SON 5 KONTROL")
    print("========================================")

    samples = [
        match
        for match in matches
        if (
            not match.get("played")
            and len(match.get("homeLast5", [])) > 0
            and len(match.get("awayLast5", [])) > 0
        )
    ]

    for match in samples[:5]:

        print()
        print(
            f'{match["league"]}: '
            f'{match["homeTeam"]} - '
            f'{match["awayTeam"]}'
        )

        print("EV SON 5:")

        for item in match["homeLast5"]:

            print(
                f'  {item["date"]} | '
                f'{item["scored"]}-'
                f'{item["conceded"]} | '
                f'{item["opponent"]}'
            )

        print("DEP SON 5:")

        for item in match["awayLast5"]:

            print(
                f'  {item["date"]} | '
                f'{item["scored"]}-'
                f'{item["conceded"]} | '
                f'{item["opponent"]}'
            )


# =========================================================
# MAIN
# =========================================================

def main():

    print("🏀 BASKETBOL VERİ GÜNCELLEYİCİ")
    print("========================================")

    euroleague = get_euroleague_games()

    nba = get_nba_games()

    matches = euroleague + nba

    if not matches:

        raise RuntimeError(
            "Hiç basketbol maçı alınamadı."
        )

    matches = add_last_five(matches)

    matches.sort(
        key=lambda x: (
            parse_date(x.get("date"))
            or datetime.max
        )
    )

    nba_finished = sum(
        1
        for match in nba
        if match.get("played")
    )

    euro_finished = sum(
        1
        for match in euroleague
        if match.get("played")
    )

    output = {
        "updatedAt": now_iso(),

        "total": len(matches),

        "nba": len(nba),

        "nbaFinished": nba_finished,

        "euroleague": len(euroleague),

        "euroleagueFinished": euro_finished,

        "matches": matches
    }

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print()
    print("========================================")
    print("✅ VERİ KAYDEDİLDİ")
    print("========================================")

    print("📁", OUTPUT)
    print("🏀 NBA:", len(nba))
    print("   ✅ Oynanan:", nba_finished)

    print(
        "🌍 EuroLeague:",
        len(euroleague)
    )

    print(
        "   ✅ Oynanan:",
        euro_finished
    )

    print(
        "📦 TOPLAM:",
        len(matches)
    )

    print_samples(matches)


if __name__ == "__main__":
    main()
