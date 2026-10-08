import json
import os
import re
import hashlib
from datetime import datetime, timedelta, timezone

import requests


OUTPUT_FILE = "basketball.json"

TODAY = datetime.now(timezone.utc).date()

NBA_DAYS_BACK = 180
NBA_DAYS_FORWARD = 30

TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}


# ============================================================
# HTTP
# ============================================================

def get_json(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ İstek hatası: {url}")
        print(f"   {e}")
        return None


# ============================================================
# GENEL
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).strip()
    )


def normalize_team(name):
    name = clean_text(name).lower()

    replacements = {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
        "é": "e",
        "á": "a",
        "à": "a",
        "ä": "a",
        "-": " ",
        "_": " ",
        ".": " ",
        ",": " ",
        "'": "",
        '"': "",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    return re.sub(
        r"\s+",
        " ",
        name
    ).strip()


def safe_int(value):
    if value is None:
        return None

    try:
        return int(value)
    except Exception:
        return None


def make_match_id(
    league,
    season,
    home,
    away,
    utc_date,
):
    raw = "|".join([
        clean_text(league),
        clean_text(season),
        normalize_team(home),
        normalize_team(away),
        clean_text(utc_date),
    ])

    return hashlib.sha1(
        raw.encode("utf-8")
    ).hexdigest()[:20]


# ============================================================
# PERİYOT
# ============================================================

def make_period(home, away):
    home = safe_int(home)
    away = safe_int(away)

    if home is None or away is None:
        return None

    return {
        "home": home,
        "away": away,
        "total": home + away,
    }


def build_periods(home_values, away_values):
    periods = {}

    for i in range(4):
        home = (
            home_values[i]
            if i < len(home_values)
            else None
        )

        away = (
            away_values[i]
            if i < len(away_values)
            else None
        )

        period = make_period(
            home,
            away
        )

        if period is not None:
            periods[f"q{i + 1}"] = period

    return periods


def has_four_periods(periods):
    return (
        isinstance(periods, dict)
        and all(
            f"q{i}" in periods
            for i in range(1, 5)
        )
    )


# ============================================================
# MAÇ OLUŞTUR
# ============================================================

def build_match(
    league,
    season,
    home_team,
    away_team,
    home_score,
    away_score,
    utc_date,
    played,
    status="",
    periods=None,
    match_id=None,
):
    home_team = clean_text(home_team)
    away_team = clean_text(away_team)
    utc_date = clean_text(utc_date)

    if not home_team or not away_team:
        return None

    if not utc_date:
        return None

    home_score = safe_int(home_score)
    away_score = safe_int(away_score)

    if periods is None:
        periods = {}

    if not isinstance(periods, dict):
        periods = {}

    if match_id is None:
        match_id = make_match_id(
            league,
            season,
            home_team,
            away_team,
            utc_date,
        )

    match = {
        "id": str(match_id),
        "league": league,
        "season": season,
        "date": utc_date[:10],
        "utcDate": utc_date,
        "homeTeam": home_team,
        "awayTeam": away_team,
        "homeScore": home_score,
        "awayScore": away_score,
        "played": bool(played),
        "hasPeriodData": has_four_periods(
            periods
        ),
    }

    if status:
        match["status"] = clean_text(
            status
        )

    if has_four_periods(periods):
        match["periods"] = periods

    return match


# ============================================================
# NBA
# ============================================================

def nba_date_range():
    start = TODAY - timedelta(
        days=NBA_DAYS_BACK
    )

    end = TODAY + timedelta(
        days=NBA_DAYS_FORWARD
    )

    current = start

    while current <= end:
        yield current
        current += timedelta(days=1)


def espn_completed(event):
    status = event.get(
        "status",
        {}
    )

    status_type = status.get(
        "type",
        {}
    )

    if status_type.get(
        "completed"
    ) is True:
        return True

    name = clean_text(
        status_type.get("name")
    ).lower()

    state = clean_text(
        status_type.get("state")
    ).lower()

    return (
        name in {
            "final",
            "post",
            "finished",
            "complete",
            "completed",
        }
        or
        state in {
            "final",
            "post",
            "finished",
            "complete",
            "completed",
        }
    )


def parse_espn_event(event):
    competitions = event.get(
        "competitions",
        []
    )

    if not competitions:
        return None

    competition = competitions[0]

    competitors = competition.get(
        "competitors",
        []
    )

    if len(competitors) < 2:
        return None

    home = None
    away = None

    for item in competitors:
        if item.get("homeAway") == "home":
            home = item

        elif item.get("homeAway") == "away":
            away = item

    if not home or not away:
        return None

    home_team = (
        home.get("team", {}).get(
            "displayName"
        )
        or
        home.get("team", {}).get(
            "name"
        )
        or
        home.get("team", {}).get(
            "shortDisplayName"
        )
        or ""
    )

    away_team = (
        away.get("team", {}).get(
            "displayName"
        )
        or
        away.get("team", {}).get(
            "name"
        )
        or
        away.get("team", {}).get(
            "shortDisplayName"
        )
        or ""
    )

    utc_date = (
        event.get("date")
        or
        competition.get("date")
        or ""
    )

    home_score = safe_int(
        home.get("score")
    )

    away_score = safe_int(
        away.get("score")
    )

    status = (
        event.get("status", {})
        .get("type", {})
        .get("description")
        or
        event.get("status", {})
        .get("type", {})
        .get("name")
        or ""
    )

    played = espn_completed(event)

    home_linescores = (
        home.get("linescores")
        or []
    )

    away_linescores = (
        away.get("linescores")
        or []
    )

    home_periods = []

    for item in home_linescores[:4]:
        if isinstance(item, dict):
            home_periods.append(
                safe_int(
                    item.get("value")
                )
            )
        else:
            home_periods.append(
                safe_int(item)
            )

    away_periods = []

    for item in away_linescores[:4]:
        if isinstance(item, dict):
            away_periods.append(
                safe_int(
                    item.get("value")
                )
            )
        else:
            away_periods.append(
                safe_int(item)
            )

    periods = build_periods(
        home_periods,
        away_periods
    )

    return build_match(
        league="NBA",
        season="2026",
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        utc_date=utc_date,
        played=played,
        status=status,
        periods=periods,
        match_id=event.get("id"),
    )


def fetch_nba():
    print()
    print("=" * 60)
    print("🏀 NBA")
    print("=" * 60)

    matches = []

    for current_date in nba_date_range():

        date_string = current_date.strftime(
            "%Y%m%d"
        )

        url = (
            "https://site.api.espn.com/apis/site/v2/"
            "sports/basketball/nba/scoreboard"
            f"?dates={date_string}"
        )

        data = get_json(url)

        if not data:
            continue

        for event in data.get(
            "events",
            []
        ):
            try:
                match = parse_espn_event(
                    event
                )

                if match:
                    matches.append(match)

            except Exception as e:
                print(
                    f"⚠️ NBA maç okunamadı: {e}"
                )

    matches = deduplicate(
        matches
    )

    print(
        f"📦 Toplam: {len(matches)}"
    )

    print(
        f"🏁 Tamamlanan: "
        f"{sum(m['played'] for m in matches)}"
    )

    print(
        f"⏱️ Periyotlu: "
        f"{sum(m['hasPeriodData'] for m in matches)}"
    )

    return matches


# ============================================================
# EUROLEAGUE
# ============================================================

def club_name(value):
    if isinstance(value, str):
        return value

    if not isinstance(value, dict):
        return ""

    return (
        value.get("name")
        or
        value.get("shortName")
        or
        value.get("displayName")
        or
        value.get("code")
        or ""
    )


def parse_partials(value):
    if not isinstance(value, dict):
        return []

    result = []

    for i in range(1, 5):
        result.append(
            safe_int(
                value.get(
                    f"partials{i}"
                )
            )
        )

    return result


def parse_euro_game(game):
    local = (
        game.get("local")
        or {}
    )

    road = (
        game.get("road")
        or {}
    )

    home_team = club_name(
        local.get("club")
        or
        local.get("team")
        or
        local
    )

    away_team = club_name(
        road.get("club")
        or
        road.get("team")
        or
        road
    )

    if not home_team or not away_team:
        return None

    utc_date = (
        game.get("date")
        or
        game.get("utcDate")
        or
        game.get("startDate")
        or
        game.get("dateTime")
        or
        game.get("scheduledDate")
        or ""
    )

    if not utc_date:
        return None

    home_score = safe_int(
        local.get("score")
    )

    away_score = safe_int(
        road.get("score")
    )

    home_partials = parse_partials(
        local.get("partials")
    )

    away_partials = parse_partials(
        road.get("partials")
    )

    periods = build_periods(
        home_partials,
        away_partials
    )

    status = (
        game.get("status")
        or
        game.get("gameStatus")
        or
        game.get("state")
        or ""
    )

    if isinstance(status, dict):
        status = (
            status.get("name")
            or
            status.get("description")
            or
            status.get("status")
            or ""
        )

    status_lower = clean_text(
        status
    ).lower()

    played = None

    for key in (
        "completed",
        "played",
        "isFinished",
        "finished",
    ):
        if isinstance(
            game.get(key),
            bool
        ):
            played = game.get(key)
            break

    if status_lower in {
        "final",
        "finished",
        "complete",
        "completed",
        "post",
    }:
        played = True

    if played is None:

        if (
            has_four_periods(periods)
            and
            home_score is not None
            and
            away_score is not None
        ):

            home_total = sum(
                periods[
                    f"q{i}"
                ]["home"]
                for i in range(1, 5)
            )

            away_total = sum(
                periods[
                    f"q{i}"
                ]["away"]
                for i in range(1, 5)
            )

            if (
                home_total == home_score
                and
                away_total == away_score
            ):
                played = True

    if played is None:
        played = (
            home_score is not None
            and
            away_score is not None
        )

    match_id = (
        game.get("id")
        or
        game.get("gameId")
        or
        game.get("code")
    )

    return build_match(
        league="EuroLeague",
        season="E2026",
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
        utc_date=utc_date,
        played=played,
        status=status,
        periods=periods,
        match_id=match_id,
    )


def fetch_euroleague():
    print()
    print("=" * 60)
    print("🌍 EUROLEAGUE E2026")
    print("=" * 60)

    url = (
        "https://api-live.euroleague.net/v2/"
        "competitions/E/seasons/E2026/games"
    )

    data = get_json(url)

    if not data:
        return []

    raw_games = (
        data.get("data")
        or
        data.get("games")
        or
        []
    )

    print(
        f"📡 API maçları: "
        f"{len(raw_games)}"
    )

    matches = []

    for game in raw_games:

        try:
            match = parse_euro_game(
                game
            )

            if match:
                matches.append(match)

        except Exception as e:
            print(
                f"⚠️ EuroLeague maç okunamadı: {e}"
            )

    matches = deduplicate(
        matches
    )

    print(
        f"✅ Kullanılabilir: "
        f"{len(matches)}"
    )

    print(
        f"🏁 Tamamlanan: "
        f"{sum(m['played'] for m in matches)}"
    )

    print(
        f"⏱️ Periyotlu: "
        f"{sum(m['hasPeriodData'] for m in matches)}"
    )

    return matches


# ============================================================
# DUPLICATE
# ============================================================

def deduplicate(matches):
    unique = {}

    for match in matches:

        key = (
            match.get("league"),
            match.get("season"),
            normalize_team(
                match.get("homeTeam")
            ),
            normalize_team(
                match.get("awayTeam")
            ),
            match.get("date"),
        )

        old = unique.get(key)

        if old is None:
            unique[key] = match
            continue

        old_score = (
            old.get("homeScore") is not None
            and
            old.get("awayScore") is not None
        )

        new_score = (
            match.get("homeScore") is not None
            and
            match.get("awayScore") is not None
        )

        if new_score and not old_score:
            unique[key] = match
            continue

        if (
            match.get("hasPeriodData")
            and
            not old.get("hasPeriodData")
        ):
            unique[key] = match

    return list(
        unique.values()
    )


# ============================================================
# SIRALA
# ============================================================

def sort_matches(matches):
    return sorted(
        matches,
        key=lambda m: (
            m.get("date", ""),
            m.get("utcDate", ""),
            m.get("league", ""),
            m.get("homeTeam", ""),
            m.get("awayTeam", ""),
        )
    )


# ============================================================
# TOPLA
# ============================================================

def collect_all():

    all_matches = []

    # NBA
    nba = fetch_nba()

    all_matches.extend(
        nba
    )

    # SADECE GÜNCEL EUROLEAGUE
    euroleague = fetch_euroleague()

    all_matches.extend(
        euroleague
    )

    all_matches = deduplicate(
        all_matches
    )

    all_matches = sort_matches(
        all_matches
    )

    return all_matches


# ============================================================
# KAYDET
# ============================================================

def save_json(matches):

    payload = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "totalMatches": len(
            matches
        ),

        "matches": matches,
    }

    # Kompakt JSON.
    # History yok, eski sezon yok.
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            payload,
            file,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    size_mb = (
        os.path.getsize(
            OUTPUT_FILE
        )
        / 1024
        / 1024
    )

    print()
    print("=" * 60)
    print("💾 BASKETBALL.JSON")
    print("=" * 60)

    print(
        f"📦 Toplam maç: "
        f"{len(matches)}"
    )

    print(
        f"📁 Dosya boyutu: "
        f"{size_mb:.2f} MB"
    )

    if size_mb >= 95:
        print(
            "⚠️ UYARI: "
            "GitHub 100 MB sınırına yaklaşıldı."
        )


# ============================================================
# ÖZET
# ============================================================

def print_summary(matches):

    leagues = {}

    for match in matches:

        league = match.get(
            "league",
            "Bilinmiyor"
        )

        if league not in leagues:
            leagues[league] = {
                "total": 0,
                "played": 0,
                "periods": 0,
            }

        leagues[league]["total"] += 1

        if match.get("played"):
            leagues[league]["played"] += 1

        if match.get("hasPeriodData"):
            leagues[league]["periods"] += 1

    print()
    print("=" * 60)
    print("🏀 SONUÇ")
    print("=" * 60)

    for league in sorted(
        leagues
    ):

        item = leagues[league]

        print(
            f"{league}: "
            f"{item['total']} maç | "
            f"{item['played']} tamamlanan | "
            f"{item['periods']} periyotlu"
        )

    print()
    print(
        f"🏀 TOPLAM: "
        f"{len(matches)} maç"
    )

    print()
    print(
        "📌 Ligler: NBA + EuroLeague"
    )

    print(
        "📌 EuroLeague: sadece E2026"
    )

    print(
        "📌 E2025 ve E2024 kullanılmıyor."
    )

    print(
        "📌 History alanları JSON'a yazılmıyor."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("🏀 NBA + EUROLEAGUE")
    print("=" * 60)

    print(
        f"📅 Tarih: {TODAY}"
    )

    matches = collect_all()

    if not matches:
        raise RuntimeError(
            "Hiç basketbol verisi alınamadı."
        )

    save_json(
        matches
    )

    print_summary(
        matches
    )

    print()
    print(
        "✅ Güncelleme tamamlandı."
    )


if __name__ == "__main__":
    main()
