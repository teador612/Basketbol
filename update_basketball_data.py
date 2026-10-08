import json
import re
import time
from datetime import datetime, timedelta, timezone

import requests


# =========================================================
# AYARLAR
# =========================================================

OUTPUT_FILE = "basketball.json"

TODAY = datetime.now(timezone.utc).date()

# NBA TARİH ARALIĞI
# 180 gün geri + 30 gün ileri = 210 günlük tarama
NBA_DAYS_BACK = 180
NBA_DAYS_FORWARD = 30

TIMEOUT = 30


# =========================================================
# URL'LER
# =========================================================

ESPN_NBA_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/basketball/nba/scoreboard"
)

# BSL şimdilik kullanılmıyor.

EUROLEAGUE_API = (
    "https://api-live.euroleague.net/v2/"
    "competitions/E/seasons/E2026/games"
)

EUROCUP_API = (
    "https://api-live.euroleague.net/v2/"
    "competitions/U/seasons/U2026/games"
)


# =========================================================
# HTTP
# =========================================================

SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    ),
    "Accept": "application/json",
})


def get_json(url, params=None, retries=3):
    for attempt in range(retries):
        try:
            response = SESSION.get(
                url,
                params=params,
                timeout=TIMEOUT,
            )

            response.raise_for_status()

            return response.json()

        except Exception as exc:
            print(
                f"❌ İstek hatası: {url}"
            )
            print(f"   {exc}")

            if attempt < retries - 1:
                time.sleep(2)

    return None


# =========================================================
# YARDIMCI FONKSİYONLAR
# =========================================================

def clean_text(value):
    if value is None:
        return ""

    value = str(value)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


def normalize_team(value):
    value = clean_text(value).lower()

    replacements = {
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ü": "u",
        "Ü": "u",
        "ö": "o",
        "Ö": "o",
        "ç": "c",
        "Ç": "c",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = re.sub(r"[^a-z0-9]+", "", value)

    return value


def safe_int(value):
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        return int(value)
    except Exception:
        return None


def make_match_id(league, season, home, away, date):
    raw = (
        f"{league}|{season}|"
        f"{normalize_team(home)}|"
        f"{normalize_team(away)}|"
        f"{date}"
    )

    return normalize_team(raw)


# =========================================================
# PERİYOT
# =========================================================

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


def build_periods(q1=None, q2=None, q3=None, q4=None):
    return {
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "q4": q4,
    }


def has_four_periods(periods):
    if not isinstance(periods, dict):
        return False

    for key in ("q1", "q2", "q3", "q4"):
        value = periods.get(key)

        if not isinstance(value, dict):
            return False

        if value.get("home") is None:
            return False

        if value.get("away") is None:
            return False

    return True


# =========================================================
# GENEL MAÇ OLUŞTURUCU
# =========================================================

def build_match(
    league,
    season,
    match_id,
    date,
    utc_date,
    home_team,
    away_team,
    home_score,
    away_score,
    played,
    status,
    periods,
):
    home_score = safe_int(home_score)
    away_score = safe_int(away_score)

    return {
        "id": str(match_id),

        "league": league,
        "season": season,

        "date": date,
        "utcDate": utc_date,

        "homeTeam": clean_text(home_team),
        "awayTeam": clean_text(away_team),

        "homeScore": home_score,
        "awayScore": away_score,

        "played": bool(played),

        "hasPeriodData": has_four_periods(periods),

        "status": clean_text(status),

        "periods": periods,
    }


# =========================================================
# NBA
# =========================================================

def nba_date_range():
    start = TODAY - timedelta(days=NBA_DAYS_BACK)
    end = TODAY + timedelta(days=NBA_DAYS_FORWARD)

    current = start

    while current <= end:
        yield current

        current += timedelta(days=1)


def espn_completed(event):
    status = (
        event
        .get("status", {})
        .get("type", {})
    )

    return bool(status.get("completed"))


def parse_espn_event(event, league="NBA", season="2026"):
    try:
        competitions = event.get("competitions", [])

        if not competitions:
            return None

        competition = competitions[0]

        competitors = competition.get("competitors", [])

        if len(competitors) < 2:
            return None

        home = None
        away = None

        for team in competitors:
            if team.get("homeAway") == "home":
                home = team

            elif team.get("homeAway") == "away":
                away = team

        if home is None or away is None:
            return None

        home_team = (
            home.get("team", {}).get("displayName")
            or home.get("team", {}).get("name")
            or ""
        )

        away_team = (
            away.get("team", {}).get("displayName")
            or away.get("team", {}).get("name")
            or ""
        )

        home_score = safe_int(home.get("score"))
        away_score = safe_int(away.get("score"))

        utc_date = event.get("date")

        date = None

        if utc_date:
            try:
                parsed_date = datetime.fromisoformat(
                    utc_date.replace("Z", "+00:00")
                )

                date = parsed_date.date().isoformat()

            except Exception:
                pass

        status_type = (
            event
            .get("status", {})
            .get("type", {})
        )

        status = (
            status_type.get("name")
            or status_type.get("description")
            or ""
        )

        played = espn_completed(event)

        # ---------------------------------------------
        # ÇEYREKLER
        # ---------------------------------------------

        home_linescores = home.get("linescores", [])
        away_linescores = away.get("linescores", [])

        q1 = None
        q2 = None
        q3 = None
        q4 = None

        if len(home_linescores) >= 1 and len(away_linescores) >= 1:
            q1 = make_period(
                home_linescores[0].get("value"),
                away_linescores[0].get("value"),
            )

        if len(home_linescores) >= 2 and len(away_linescores) >= 2:
            q2 = make_period(
                home_linescores[1].get("value"),
                away_linescores[1].get("value"),
            )

        if len(home_linescores) >= 3 and len(away_linescores) >= 3:
            q3 = make_period(
                home_linescores[2].get("value"),
                away_linescores[2].get("value"),
            )

        if len(home_linescores) >= 4 and len(away_linescores) >= 4:
            q4 = make_period(
                home_linescores[3].get("value"),
                away_linescores[3].get("value"),
            )

        periods = build_periods(
            q1=q1,
            q2=q2,
            q3=q3,
            q4=q4,
        )

        event_id = event.get("id")

        match_id = make_match_id(
            league,
            season,
            home_team,
            away_team,
            date or "",
        )

        return build_match(
            league=league,
            season=season,
            match_id=event_id or match_id,
            date=date,
            utc_date=utc_date,
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
            played=played,
            status=status,
            periods=periods,
        )

    except Exception as exc:
        print(
            f"⚠️ ESPN maç ayrıştırma hatası: {exc}"
        )

        return None


def fetch_nba():
    print("🏀 NBA verileri çekiliyor...")

    matches = []

    for current_date in nba_date_range():
        date_string = current_date.strftime("%Y%m%d")

        data = get_json(
            ESPN_NBA_URL,
            params={
                "dates": date_string,
            },
        )

        if not data:
            continue

        events = data.get("events", [])

        for event in events:
            match = parse_espn_event(
                event,
                league="NBA",
                season="2026",
            )

            if match:
                matches.append(match)

    print(
        f"✅ NBA: {len(matches)} maç"
    )

    return matches


# =========================================================
# EURO BASKETBALL YARDIMCILARI
# =========================================================

def club_name(club):
    if not isinstance(club, dict):
        return ""

    return clean_text(
        club.get("name")
        or club.get("clubName")
        or club.get("displayName")
        or club.get("shortName")
        or club.get("permanentName")
        or club.get("clubPermanentName")
        or club.get("code")
        or ""
    )


def extract_score(value):
    if isinstance(value, dict):
        for key in (
            "score",
            "points",
            "total",
            "value",
        ):
            if key in value:
                result = safe_int(value.get(key))

                if result is not None:
                    return result

    return safe_int(value)


def parse_partials(game):
    """
    EuroLeague / EuroCup API sürümlerinde
    çeyrek bilgileri farklı alanlarda gelebiliyor.
    """

    q1 = None
    q2 = None
    q3 = None
    q4 = None

    # -----------------------------------------------------
    # 1) periods / partials
    # -----------------------------------------------------

    candidates = [
        game.get("periods"),
        game.get("partials"),
        game.get("quarterScores"),
        game.get("scoresByQuarter"),
        game.get("byQuarter"),
    ]

    for candidate in candidates:
        if not candidate:
            continue

        if isinstance(candidate, dict):
            values = []

            for key in (
                "q1",
                "q2",
                "q3",
                "q4",
                "Q1",
                "Q2",
                "Q3",
                "Q4",
                "1",
                "2",
                "3",
                "4",
            ):
                if key in candidate:
                    values.append(candidate[key])

            if values:
                for index, value in enumerate(values[:4]):
                    if not isinstance(value, dict):
                        continue

                    home = (
                        value.get("home")
                        or value.get("local")
                        or value.get("homeScore")
                        or value.get("localScore")
                    )

                    away = (
                        value.get("away")
                        or value.get("road")
                        or value.get("awayScore")
                        or value.get("roadScore")
                    )

                    period = make_period(
                        home,
                        away,
                    )

                    if index == 0:
                        q1 = period

                    elif index == 1:
                        q2 = period

                    elif index == 2:
                        q3 = period

                    elif index == 3:
                        q4 = period

        elif isinstance(candidate, list):
            for index, value in enumerate(candidate[:4]):
                if not isinstance(value, dict):
                    continue

                home = (
                    value.get("home")
                    or value.get("local")
                    or value.get("homeScore")
                    or value.get("localScore")
                )

                away = (
                    value.get("away")
                    or value.get("road")
                    or value.get("awayScore")
                    or value.get("roadScore")
                )

                period = make_period(
                    home,
                    away,
                )

                if index == 0:
                    q1 = period

                elif index == 1:
                    q2 = period

                elif index == 2:
                    q3 = period

                elif index == 3:
                    q4 = period

    # -----------------------------------------------------
    # 2) endOfQuarter
    # -----------------------------------------------------

    if not has_four_periods(
        build_periods(q1, q2, q3, q4)
    ):
        end_quarter = game.get("endOfQuarter")

        if isinstance(end_quarter, list):
            for index, value in enumerate(
                end_quarter[:4]
            ):
                if not isinstance(value, dict):
                    continue

                home = (
                    value.get("home")
                    or value.get("local")
                    or value.get("homeScore")
                    or value.get("localScore")
                )

                away = (
                    value.get("away")
                    or value.get("road")
                    or value.get("awayScore")
                    or value.get("roadScore")
                )

                period = make_period(
                    home,
                    away,
                )

                if index == 0 and q1 is None:
                    q1 = period

                elif index == 1 and q2 is None:
                    q2 = period

                elif index == 2 and q3 is None:
                    q3 = period

                elif index == 3 and q4 is None:
                    q4 = period

    return build_periods(
        q1=q1,
        q2=q2,
        q3=q3,
        q4=q4,
    )


# =========================================================
# EURO MAÇ PARSER
# =========================================================

def parse_euro_game(
    game,
    league,
    season,
):
    try:
        if not isinstance(game, dict):
            return None

        # -------------------------------------------------
        # TAKIMLAR
        # -------------------------------------------------

        home_obj = (
            game.get("local")
            or game.get("home")
            or game.get("homeTeam")
            or {}
        )

        away_obj = (
            game.get("road")
            or game.get("away")
            or game.get("awayTeam")
            or {}
        )

        home_team = club_name(home_obj)

        away_team = club_name(away_obj)

        if not home_team:
            home_team = clean_text(
                game.get("localTeam")
                or game.get("homeTeamName")
                or ""
            )

        if not away_team:
            away_team = clean_text(
                game.get("roadTeam")
                or game.get("awayTeamName")
                or ""
            )

        if not home_team or not away_team:
            return None

        # -------------------------------------------------
        # SKOR
        # -------------------------------------------------

        home_score = (
            extract_score(
                home_obj.get("score")
                if isinstance(home_obj, dict)
                else None
            )
        )

        away_score = (
            extract_score(
                away_obj.get("score")
                if isinstance(away_obj, dict)
                else None
            )
        )

        if home_score is None:
            home_score = extract_score(
                game.get("homeScore")
                or game.get("localScore")
            )

        if away_score is None:
            away_score = extract_score(
                game.get("awayScore")
                or game.get("roadScore")
            )

        # -------------------------------------------------
        # TARİH
        # -------------------------------------------------

        utc_date = (
            game.get("date")
            or game.get("utcDate")
            or game.get("startDate")
            or game.get("dateTime")
        )

        date = None

        if utc_date:
            try:
                parsed_date = datetime.fromisoformat(
                    str(utc_date).replace("Z", "+00:00")
                )

                date = parsed_date.date().isoformat()

            except Exception:
                date_match = re.search(
                    r"(\d{4})[-/](\d{2})[-/](\d{2})",
                    str(utc_date),
                )

                if date_match:
                    date = (
                        f"{date_match.group(1)}-"
                        f"{date_match.group(2)}-"
                        f"{date_match.group(3)}"
                    )

        # -------------------------------------------------
        # DURUM
        # -------------------------------------------------

        status_obj = game.get("status")

        if isinstance(status_obj, dict):
            status = (
                status_obj.get("name")
                or status_obj.get("description")
                or status_obj.get("type")
                or ""
            )

        else:
            status = (
                status_obj
                or game.get("gameStatus")
                or game.get("statusName")
                or ""
            )

        status = clean_text(status)

        # -------------------------------------------------
        # OYNANDI MI?
        # -------------------------------------------------

        played = game.get("played")

        if played is None:
            played = game.get("isPlayed")

        if played is None:
            played = game.get("completed")

        if played is None:
            status_lower = status.lower()

            if any(
                word in status_lower
                for word in (
                    "finished",
                    "final",
                    "completed",
                    "ended",
                )
            ):
                played = True

            elif any(
                word in status_lower
                for word in (
                    "scheduled",
                    "not started",
                    "upcoming",
                )
            ):
                played = False

            else:
                played = (
                    home_score is not None
                    and away_score is not None
                )

        # -------------------------------------------------
        # PERİYOTLAR
        # -------------------------------------------------

        periods = parse_partials(game)

        # -------------------------------------------------
        # ID
        # -------------------------------------------------

        match_id = (
            game.get("id")
            or game.get("gameCode")
            or game.get("gameId")
        )

        if match_id is None:
            match_id = make_match_id(
                league,
                season,
                home_team,
                away_team,
                date or "",
            )

        return build_match(
            league=league,
            season=season,
            match_id=match_id,
            date=date,
            utc_date=utc_date,
            home_team=home_team,
            away_team=away_team,
            home_score=home_score,
            away_score=away_score,
            played=bool(played),
            status=status,
            periods=periods,
        )

    except Exception as exc:
        print(
            f"⚠️ {league} maç ayrıştırma hatası: {exc}"
        )

        return None


# =========================================================
# EURO API ÇEKME
# =========================================================

def fetch_euroleague():
    print("🏀 EuroLeague verileri çekiliyor...")

    data = get_json(
        EUROLEAGUE_API
    )

    if not data:
        print("❌ EuroLeague verisi alınamadı.")

        return []

    games = data.get("data", data)

    if not isinstance(games, list):
        print("❌ EuroLeague games listesi bulunamadı.")

        return []

    matches = []

    for game in games:
        match = parse_euro_game(
            game,
            league="EuroLeague",
            season="2026",
        )

        if match:
            matches.append(match)

    print(
        f"✅ EuroLeague: {len(matches)} maç"
    )

    return matches


def fetch_eurocup():
    print("🏀 EuroCup verileri çekiliyor...")

    data = get_json(
        EUROCUP_API
    )

    if not data:
        print("❌ EuroCup verisi alınamadı.")

        return []

    games = data.get("data", data)

    if not isinstance(games, list):
        print("❌ EuroCup games listesi bulunamadı.")

        return []

    matches = []

    for game in games:
        match = parse_euro_game(
            game,
            league="EuroCup",
            season="2026",
        )

        if match:
            matches.append(match)

    print(
        f"✅ EuroCup: {len(matches)} maç"
    )

    return matches


# =========================================================
# TEKRARLARI TEMİZLE
# =========================================================

def deduplicate(matches):
    result = {}

    for match in matches:
        key = (
            match.get("league"),
            match.get("season"),
            normalize_team(
                match.get("homeTeam", "")
            ),
            normalize_team(
                match.get("awayTeam", "")
            ),
            match.get("date"),
        )

        result[key] = match

    return list(result.values())


# =========================================================
# SIRALAMA
# =========================================================

def sort_matches(matches):
    def sort_key(match):
        date = match.get("date") or "9999-99-99"

        utc_date = match.get("utcDate") or ""

        return (
            date,
            utc_date,
            match.get("league") or "",
            match.get("homeTeam") or "",
        )

    return sorted(
        matches,
        key=sort_key,
    )


# =========================================================
# TÜM VERİLER
# =========================================================

def collect_all():
    all_matches = []

    # ---------------------------------------------
    # NBA
    # ---------------------------------------------

    all_matches.extend(
        fetch_nba()
    )

    # ---------------------------------------------
    # EuroLeague
    # ---------------------------------------------

    all_matches.extend(
        fetch_euroleague()
    )

    # ---------------------------------------------
    # EuroCup
    # ---------------------------------------------

    all_matches.extend(
        fetch_eurocup()
    )

    # BSL ŞİMDİLİK YOK

    all_matches = deduplicate(
        all_matches
    )

    all_matches = sort_matches(
        all_matches
    )

    return all_matches


# =========================================================
# JSON KAYDET
# =========================================================

def save_json(matches):
    output = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "totalMatches": len(matches),

        "matches": matches,
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    print(
        f"💾 Kaydedildi: {OUTPUT_FILE}"
    )

    print(
        f"📊 Toplam maç: {len(matches)}"
    )


# =========================================================
# ÖZET
# =========================================================

def print_summary(matches):
    counts = {}

    for match in matches:
        league = match.get(
            "league",
            "Bilinmiyor",
        )

        counts[league] = (
            counts.get(league, 0) + 1
        )

    print()
    print("=" * 45)
    print("📊 MAÇ ÖZETİ")
    print("=" * 45)

    for league in sorted(counts):
        print(
            f"{league}: {counts[league]}"
        )

    print("=" * 45)


# =========================================================
# MAIN
# =========================================================

def main():
    print()
    print("🏀 BASKETBALL DATA UPDATE")
    print("=" * 45)

    print(
        f"📅 Bugün: {TODAY}"
    )

    print(
        f"🔎 NBA taraması: "
        f"{NBA_DAYS_BACK} gün geri + "
        f"{NBA_DAYS_FORWARD} gün ileri"
    )

    print(
        "🇪🇺 EuroLeague: E2026"
    )

    print(
        "🇪🇺 EuroCup: U2026"
    )

    print(
        "🇹🇷 BSL: Şimdilik devre dışı"
    )

    print("=" * 45)

    matches = collect_all()

    save_json(
        matches
    )

    print_summary(
        matches
    )

    print()
    print("✅ Güncelleme tamamlandı.")


if __name__ == "__main__":
    main()
