import json
from datetime import datetime, timezone
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

# NBA 2026-27
NBA_URL = (
    "https://data.nba.com/data/10s/v2015/json/"
    "mobile_teams/nba/2026/league/00_full_schedule.json"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
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
            timeout=60
        )

        print("HTTP:", response.status_code)

        response.raise_for_status()

        data = response.json()

    except Exception as e:
        print("❌ NBA hatası:", e)
        return []

    matches = []

    # NBA feed yapısı:
    #
    # lscd
    #   mscd
    #      g
    #
    league_days = data.get("lscd") or []

    print("📅 NBA gün blokları:", len(league_days))

    for day in league_days:

        month_data = day.get("mscd") or {}

        games = month_data.get("g") or []

        for game in games:

            home = game.get("hls") or {}
            away = game.get("vls") or {}

            home_name = (
                home.get("tn")
                or home.get("tc")
                or home.get("ta")
            )

            away_name = (
                away.get("tn")
                or away.get("tc")
                or away.get("ta")
            )

            if not home_name or not away_name:
                continue

            status = str(
                game.get("stt") or ""
            ).strip().lower()

            played = status == "final"

            home_score = None
            away_score = None

            if played:

                home_score = safe_int(
                    home.get("s")
                )

                away_score = safe_int(
                    away.get("s")
                )

                # Skor yoksa final kabul etmiyoruz.
                if (
                    home_score is None
                    or away_score is None
                ):
                    played = False

            game_date = (
                game.get("gdte")
                or day.get("gdte")
            )

            matches.append({
                "id": game.get("gid"),

                "league": "NBA",

                "season": "2026-27",

                "date": game_date,

                "utcDate": None,

                "round": None,

                "homeTeam": home_name,

                "awayTeam": away_name,

                "homeScore": home_score,

                "awayScore": away_score,

                "played": played,

                "status": (
                    "finished"
                    if played
                    else "scheduled"
                )
            })

    print("🏀 NBA işlenen:", len(matches))

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

    result = []

    for match in previous[:5]:

        result.append({
            "date": match.get("date"),
            "opponent": match.get("awayTeam"),
            "scored": match.get("homeScore"),
            "conceded": match.get("awayScore")
        })

    return result


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

    result = []

    for match in previous[:5]:

        result.append({
            "date": match.get("date"),
            "opponent": match.get("homeTeam"),
            "scored": match.get("awayScore"),
            "conceded": match.get("homeScore")
        })

    return result


# =========================================================
# SON 5 VERİLERİNİ EKLE
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
# ANA
# =========================================================

def main():

    print("🏀 BASKETBOL VERİ GÜNCELLEYİCİ")
    print("========================================")

    euroleague = get_euroleague_games()

    nba = get_nba_games()

    # NBA hiç gelmezse sistemi bozma.
    # EuroLeague yine kaydedilsin.
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
        for m in nba
        if m.get("played")
    )

    euro_finished = sum(
        1
        for m in euroleague
        if m.get("played")
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

    # -----------------------------------------------------
    # SON 5 KONTROL
    # -----------------------------------------------------

    print()
    print("========================================")
    print("🔎 SON 5 KONTROL")
    print("========================================")

    samples = [
        m
        for m in matches
        if (
            not m.get("played")
            and len(m.get("homeLast5", [])) > 0
            and len(m.get("awayLast5", [])) > 0
        )
    ]

    for match in samples[:3]:

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
                f'{item["scored"]}-{item["conceded"]} | '
                f'{item["opponent"]}'
            )

        print("DEP SON 5:")

        for item in match["awayLast5"]:

            print(
                f'  {item["date"]} | '
                f'{item["scored"]}-{item["conceded"]} | '
                f'{item["opponent"]}'
            )


if __name__ == "__main__":
    main()
