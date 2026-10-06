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

NBA_URL = (
    "https://cdn.nba.com/static/json/staticData/"
    "scheduleLeagueV2.json"
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# =========================================================
# EUROLEGUE
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
            timeout=60,
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

        played = bool(game.get("played", False))

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
            "gameCode": game.get("gameCode"),
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
            ),
        })

    print("✅ EuroLeague işlenen:", len(matches))

    return matches


# =========================================================
# NBA
# =========================================================

def get_nba_games():
    print()
    print("========================================")
    print("🏀 NBA")
    print("========================================")

    try:
        response = requests.get(
            NBA_URL,
            headers=HEADERS,
            timeout=60,
        )

        print("HTTP:", response.status_code)

        response.raise_for_status()

        data = response.json()

    except Exception as e:
        print("❌ NBA hatası:", e)
        return []

    schedule = data.get("leagueSchedule") or {}

    game_dates = schedule.get("gameDates") or []

    print("📅 NBA gün blokları:", len(game_dates))

    matches = []

    for day in game_dates:

        games = day.get("games") or []

        for game in games:

            game_id = game.get("gameId")

            home = game.get("homeTeam") or {}
            away = game.get("awayTeam") or {}

            home_name = (
                home.get("teamName")
                or home.get("teamTricode")
            )

            away_name = (
                away.get("teamName")
                or away.get("teamTricode")
            )

            if not home_name or not away_name:
                continue

            status_code = safe_int(
                game.get("gameStatus")
            )

            # NBA:
            # 1 = scheduled
            # 2 = live
            # 3 = final
            played = status_code == 3

            home_score = None
            away_score = None

            if played:
                home_score = safe_int(
                    home.get("score")
                )

                away_score = safe_int(
                    away.get("score")
                )

            game_date = (
                game.get("gameDateTimeUTC")
                or game.get("gameDateTime")
                or day.get("gameDate")
            )

            matches.append({
                "id": game_id,
                "gameCode": game.get("gameCode"),
                "league": "NBA",
                "season": str(
                    schedule.get("seasonYear")
                    or "2026"
                ),
                "date": game_date,
                "utcDate": game.get(
                    "gameDateTimeUTC"
                ),
                "round": None,
                "homeTeam": home_name,
                "awayTeam": away_name,
                "homeScore": home_score,
                "awayScore": away_score,
                "played": played,
                "status": (
                    "finished"
                    if played
                    else (
                        "live"
                        if status_code == 2
                        else "scheduled"
                    )
                ),
            })

    print("🏀 NBA işlenen:", len(matches))

    return matches


# =========================================================
# SON 5 İÇ SAHA / DEPLASMAN
# =========================================================

def parse_date(value):
    if not value:
        return None

    try:
        text = str(value)

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        return datetime.fromisoformat(text)

    except Exception:
        try:
            return datetime.strptime(
                str(value)[:10],
                "%Y-%m-%d",
            )
        except Exception:
            return None


def get_last_five_home(matches, team, before_date):
    result = []

    target_date = parse_date(before_date)

    if target_date is None:
        return result

    candidates = []

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

        if match_date >= target_date:
            continue

        candidates.append(match)

    candidates.sort(
        key=lambda x: parse_date(x.get("date"))
        or datetime.min,
        reverse=True,
    )

    for match in candidates[:5]:
        result.append({
            "date": match.get("date"),
            "opponent": match.get("awayTeam"),
            "scored": match.get("homeScore"),
            "conceded": match.get("awayScore"),
        })

    return result


def get_last_five_away(matches, team, before_date):
    result = []

    target_date = parse_date(before_date)

    if target_date is None:
        return result

    candidates = []

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

        if match_date >= target_date:
            continue

        candidates.append(match)

    candidates.sort(
        key=lambda x: parse_date(x.get("date"))
        or datetime.min,
        reverse=True,
    )

    for match in candidates[:5]:
        result.append({
            "date": match.get("date"),
            "opponent": match.get("homeTeam"),
            "scored": match.get("awayScore"),
            "conceded": match.get("homeScore"),
        })

    return result


# =========================================================
# MAÇLARA SON 5 VERİSİNİ EKLE
# =========================================================

def add_recent_stats(matches):

    print()
    print("========================================")
    print("📊 SON 5 VERİLER HESAPLANIYOR")
    print("========================================")

    finished = [
        m for m in matches
        if m.get("played")
        and m.get("homeScore") is not None
        and m.get("awayScore") is not None
    ]

    print(
        "Geçmişte kullanılabilir maç:",
        len(finished)
    )

    for match in matches:

        match["homeLast5"] = get_last_five_home(
            finished,
            match.get("homeTeam"),
            match.get("date"),
        )

        match["awayLast5"] = get_last_five_away(
            finished,
            match.get("awayTeam"),
            match.get("date"),
        )

    return matches


# =========================================================
# ÖZET
# =========================================================

def print_sample(matches):

    print()
    print("========================================")
    print("🔎 SON 5 VERİ ÖRNEĞİ")
    print("========================================")

    upcoming = [
        m for m in matches
        if not m.get("played")
        and (
            len(m.get("homeLast5", [])) > 0
            or len(m.get("awayLast5", [])) > 0
        )
    ]

    for match in upcoming[:3]:

        print()
        print(
            f'{match["league"]}: '
            f'{match["homeTeam"]} - '
            f'{match["awayTeam"]}'
        )

        print("Ev takımının son 5 iç saha:")

        for item in match["homeLast5"]:
            print(
                f'  {item["date"]} | '
                f'{item["scored"]} - '
                f'{item["conceded"]} | '
                f'{item["opponent"]}'
            )

        print("Deplasman takımının son 5 deplasman:")

        for item in match["awayLast5"]:
            print(
                f'  {item["date"]} | '
                f'{item["scored"]} - '
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

    all_matches = euroleague + nba

    if not all_matches:
        raise RuntimeError(
            "NBA ve EuroLeague verisi alınamadı."
        )

    all_matches = add_recent_stats(
        all_matches
    )

    all_matches.sort(
        key=lambda x: (
            parse_date(x.get("date"))
            or datetime.max
        )
    )

    euro_finished = sum(
        1
        for m in euroleague
        if m.get("played")
    )

    nba_finished = sum(
        1
        for m in nba
        if m.get("played")
    )

    output = {
        "updatedAt": now_iso(),

        "total": len(all_matches),

        "nba": len(nba),

        "nbaFinished": nba_finished,

        "euroleague": len(euroleague),

        "euroleagueFinished": euro_finished,

        "matches": all_matches,
    }

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

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

    print("📁", OUTPUT)
    print("🏀 NBA:", len(nba))
    print("   ✅ Oynanan:", nba_finished)
    print("🌍 EuroLeague:", len(euroleague))
    print("   ✅ Oynanan:", euro_finished)
    print("📦 TOPLAM:", len(all_matches))

    print_sample(all_matches)


if __name__ == "__main__":
    main()
