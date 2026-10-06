import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import requests


# ============================================================
# AYARLAR
# ============================================================

OUTPUT_FILE = "basketball.json"

TODAY = datetime.now(timezone.utc).date()

NBA_DAYS_BACK = 180
NBA_DAYS_FORWARD = 30

OTHER_ESPN_DAYS_BACK = 365
OTHER_ESPN_DAYS_FORWARD = 30

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
# GENEL YARDIMCILAR
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    value = str(value)
    value = re.sub(r"\s+", " ", value).strip()

    return value


def parse_date(value):
    if not value:
        return None

    value = str(value).strip()

    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        return datetime.fromisoformat(value)
    except Exception:
        pass

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).replace(
                tzinfo=timezone.utc
            )
        except Exception:
            continue

    return None


def date_only(value):
    dt = parse_date(value)

    if dt:
        return dt.astimezone(timezone.utc).date()

    try:
        return datetime.strptime(
            str(value)[:10],
            "%Y-%m-%d"
        ).date()
    except Exception:
        return None


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
        "ö": "o",
        "-": " ",
        "_": " ",
        ".": " ",
        ",": " ",
        "'": "",
        '"': "",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    name = re.sub(r"\s+", " ", name).strip()

    return name


def make_match_id(league, season, home, away, utc_date):
    raw = "|".join(
        [
            clean_text(league),
            clean_text(season),
            normalize_team(home),
            normalize_team(away),
            clean_text(utc_date),
        ]
    )

    import hashlib

    return hashlib.sha1(
        raw.encode("utf-8")
    ).hexdigest()[:20]


# ============================================================
# SKOR
# ============================================================

def safe_int(value):
    if value is None:
        return None

    try:
        return int(value)
    except Exception:
        return None


def is_valid_score(value):
    return value is not None and value >= 0


def make_period(q_home, q_away):
    q_home = safe_int(q_home)
    q_away = safe_int(q_away)

    if q_home is None or q_away is None:
        return None

    return {
        "home": q_home,
        "away": q_away,
        "total": q_home + q_away,
    }


def build_periods(values_home, values_away):
    periods = {}

    for index in range(4):
        home = (
            values_home[index]
            if index < len(values_home)
            else None
        )

        away = (
            values_away[index]
            if index < len(values_away)
            else None
        )

        period = make_period(home, away)

        if period is not None:
            periods[f"q{index + 1}"] = period

    return periods


def periods_have_data(periods):
    if not isinstance(periods, dict):
        return False

    return all(
        f"q{i}" in periods
        for i in range(1, 5)
    )


def periods_total(periods, side):
    total = 0

    for i in range(1, 5):
        q = periods.get(f"q{i}")

        if not isinstance(q, dict):
            return None

        value = safe_int(q.get(side))

        if value is None:
            return None

        total += value

    return total


def periods_match_score(periods, home_score, away_score):
    if not periods_have_data(periods):
        return False

    home_total = periods_total(periods, "home")
    away_total = periods_total(periods, "away")

    if home_total is None or away_total is None:
        return False

    return (
        home_total == home_score
        and away_total == away_score
    )


# ============================================================
# PLAYED DURUMU
# ============================================================

FINAL_STATUS_WORDS = {
    "final",
    "finished",
    "complete",
    "completed",
    "post",
    "postponed",
    "cancelled",
}


def espn_completed(event):
    status = (
        event.get("status")
        or {}
    )

    status_type = (
        status.get("type")
        or {}
    )

    if status_type.get("completed") is True:
        return True

    name = clean_text(
        status_type.get("name")
    ).lower()

    state = clean_text(
        status_type.get("state")
    ).lower()

    return (
        name in FINAL_STATUS_WORDS
        or state in FINAL_STATUS_WORDS
    )


def build_match(
    *,
    league,
    season,
    home_team,
    away_team,
    home_score,
    away_score,
    utc_date,
    played,
    status=None,
    periods=None,
    match_id=None,
):
    home_team = clean_text(home_team)
    away_team = clean_text(away_team)

    if not home_team or not away_team:
        return None

    utc_date = clean_text(utc_date)

    if not utc_date:
        return None

    home_score = safe_int(home_score)
    away_score = safe_int(away_score)

    if not is_valid_score(home_score):
        home_score = None

    if not is_valid_score(away_score):
        away_score = None

    if periods is None:
        periods = {}

    if not isinstance(periods, dict):
        periods = {}

    has_period_data = periods_have_data(periods)

    if played is None:
        played = (
            home_score is not None
            and away_score is not None
        )

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
        "league": clean_text(league),
        "season": clean_text(season),
        "date": utc_date[:10],
        "utcDate": utc_date,
        "homeTeam": home_team,
        "awayTeam": away_team,
        "homeScore": home_score,
        "awayScore": away_score,
        "played": bool(played),
    }

    if status:
        match["status"] = clean_text(status)

    if has_period_data:
        match["hasPeriodData"] = True
        match["periods"] = periods
    else:
        match["hasPeriodData"] = False

    return match


# ============================================================
# ESPN
# ============================================================

def espn_dates(
    days_back,
    days_forward,
):
    start = TODAY - timedelta(days=days_back)
    end = TODAY + timedelta(days=days_forward)

    current = start

    while current <= end:
        yield current
        current += timedelta(days=1)


def fetch_espn_league(
    league,
    sport,
    league_id,
    days_back,
    days_forward,
):
    print()
    print("=" * 60)
    print(f"🏀 {league}")
    print("=" * 60)

    matches = []

    for current_date in espn_dates(
        days_back,
        days_forward,
    ):
        date_string = current_date.strftime(
            "%Y%m%d"
        )

        url = (
            "https://site.api.espn.com/apis/site/v2/sports/"
            f"{sport}/{league_id}/scoreboard"
            f"?dates={date_string}"
        )

        data = get_json(url)

        if not data:
            continue

        events = data.get("events") or []

        for event in events:
            try:
                match = parse_espn_event(
                    event,
                    league=league,
                    season="",
                )

                if match:
                    matches.append(match)

            except Exception as e:
                print(
                    f"⚠️ ESPN maç okunamadı: {e}"
                )

    matches = deduplicate_matches(matches)

    completed = sum(
        1 for m in matches
        if m.get("played")
    )

    perioded = sum(
        1 for m in matches
        if m.get("hasPeriodData")
    )

    print(f"📦 Toplam: {len(matches)}")
    print(f"🏁 Tamamlanan: {completed}")
    print(f"⏱️ Periyotlu: {perioded}")

    return matches


def parse_espn_event(
    event,
    league,
    season="",
):
    competitions = event.get(
        "competitions"
    ) or []

    if not competitions:
        return None

    competition = competitions[0]

    competitors = competition.get(
        "competitors"
    ) or []

    if len(competitors) < 2:
        return None

    home = None
    away = None

    for competitor in competitors:
        if competitor.get("homeAway") == "home":
            home = competitor
        elif competitor.get("homeAway") == "away":
            away = competitor

    if home is None or away is None:
        return None

    home_team = (
        home.get("team", {}).get("displayName")
        or home.get("team", {}).get("name")
        or home.get("team", {}).get("shortDisplayName")
    )

    away_team = (
        away.get("team", {}).get("displayName")
        or away.get("team", {}).get("name")
        or away.get("team", {}).get("shortDisplayName")
    )

    utc_date = (
        event.get("date")
        or competition.get("date")
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
        or event.get("status", {})
        .get("type", {})
        .get("name")
        or ""
    )

    played = espn_completed(event)

    # ESPN period verisi
    home_linescores = (
        home.get("linescores")
        or []
    )

    away_linescores = (
        away.get("linescores")
        or []
    )

    home_periods = [
        safe_int(
            item.get("value")
            if isinstance(item, dict)
            else item
        )
        for item in home_linescores[:4]
    ]

    away_periods = [
        safe_int(
            item.get("value")
            if isinstance(item, dict)
            else item
        )
        for item in away_linescores[:4]
    ]

    periods = build_periods(
        home_periods,
        away_periods,
    )

    return build_match(
        league=league,
        season=season,
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


# ============================================================
# EUROLEAGUE / EUROCUP
# ============================================================

def fetch_euroleague_season(
    competition,
    season,
    history_only=False,
):
    print()
    print("=" * 60)
    print(f"🌍 {competition} - {season}")
    print("=" * 60)

    url = (
        "https://api-live.euroleague.net/v2/competitions/"
        f"{quote(competition)}/seasons/{quote(season)}/games"
    )

    data = get_json(url)

    if not data:
        print("❌ API verisi alınamadı.")
        return []

    raw_games = data.get("data")

    if raw_games is None:
        raw_games = data.get("games")

    if raw_games is None:
        raw_games = []

    if not isinstance(raw_games, list):
        raw_games = []

    print(
        f"📡 API maçları: {len(raw_games)}"
    )

    matches = []

    for game in raw_games:
        try:
            match = parse_euro_game(
                game,
                competition=competition,
                season=season,
            )

            if not match:
                continue

            # Eski sezonlar sadece tarihsel örneklem için.
            # Oynanmamış maçları tutmuyoruz.
            if history_only and not match.get("played"):
                continue

            matches.append(match)

        except Exception as e:
            print(
                f"⚠️ EuroLeague maç okunamadı: {e}"
            )

    matches = deduplicate_matches(matches)

    completed = sum(
        1 for m in matches
        if m.get("played")
    )

    perioded = sum(
        1 for m in matches
        if m.get("hasPeriodData")
    )

    print(
        f"✅ Kullanılabilir: {len(matches)}"
    )
    print(
        f"🏁 Tamamlanan: {completed}"
    )
    print(
        f"⏱️ Periyotlu: {perioded}"
    )

    return matches


def find_nested(obj, keys):
    if not isinstance(obj, dict):
        return None

    for key in keys:
        if key in obj:
            return obj[key]

    return None


def club_name(club):
    if isinstance(club, str):
        return club

    if not isinstance(club, dict):
        return ""

    return (
        club.get("name")
        or club.get("shortName")
        or club.get("displayName")
        or club.get("code")
        or ""
    )


def parse_partial_list(partials):
    if not isinstance(partials, dict):
        return []

    values = []

    for i in range(1, 5):
        value = (
            partials.get(f"partials{i}")
            or partials.get(f"partial{i}")
        )

        values.append(
            safe_int(value)
        )

    return values


def parse_euro_game(
    game,
    competition,
    season,
):
    if not isinstance(game, dict):
        return None

    local = (
        game.get("local")
        or game.get("home")
        or {}
    )

    road = (
        game.get("road")
        or game.get("away")
        or {}
    )

    home_team = club_name(
        local.get("club")
        or local.get("team")
        or local
    )

    away_team = club_name(
        road.get("club")
        or road.get("team")
        or road
    )

    if not home_team or not away_team:
        return None

    utc_date = (
        game.get("date")
        or game.get("utcDate")
        or game.get("startDate")
        or game.get("dateTime")
        or game.get("scheduledDate")
    )

    if not utc_date:
        return None

    home_score = safe_int(
        local.get("score")
    )

    away_score = safe_int(
        road.get("score")
    )

    home_partial_obj = (
        local.get("partials")
        or {}
    )

    away_partial_obj = (
        road.get("partials")
        or {}
    )

    home_values = parse_partial_list(
        home_partial_obj
    )

    away_values = parse_partial_list(
        away_partial_obj
    )

    periods = build_periods(
        home_values,
        away_values,
    )

    # Öncelikli olarak API'deki açık durum bilgisi
    played = None

    for key in (
        "completed",
        "played",
        "isFinished",
        "finished",
    ):
        if key in game:
            value = game.get(key)

            if isinstance(value, bool):
                played = value
                break

    status = (
        game.get("status")
        or game.get("gameStatus")
        or game.get("state")
        or ""
    )

    if isinstance(status, dict):
        status = (
            status.get("name")
            or status.get("description")
            or status.get("status")
            or ""
        )

    status_lower = clean_text(
        status
    ).lower()

    if status_lower in FINAL_STATUS_WORDS:
        played = True

    # Eğer açık final bilgisi yoksa:
    # 4 periyot + final skor eşleşiyorsa tamamlanmış kabul et.
    if played is None:
        if (
            home_score is not None
            and away_score is not None
            and periods_match_score(
                periods,
                home_score,
                away_score,
            )
        ):
            played = True

    # Hâlâ belli değilse skorun varlığına bak.
    # Bu API'de geçmiş tamamlanmış maçların skoru bulunuyor.
    if played is None:
        played = (
            home_score is not None
            and away_score is not None
        )

    match_id = (
        game.get("id")
        or game.get("gameId")
        or game.get("code")
    )

    return build_match(
        league=(
            "EuroLeague"
            if competition == "E"
            else "EuroCup"
        ),
        season=season,
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


# ============================================================
# DUPLICATE
# ============================================================

def deduplicate_matches(matches):
    unique = {}

    for match in matches:
        if not match:
            continue

        key = (
            match.get("league", ""),
            match.get("season", ""),
            normalize_team(
                match.get("homeTeam", "")
            ),
            normalize_team(
                match.get("awayTeam", "")
            ),
            match.get("date", ""),
        )

        old = unique.get(key)

        if old is None:
            unique[key] = match
            continue

        # Daha dolu kayıt kazanır.
        old_score_count = sum(
            x is not None
            for x in (
                old.get("homeScore"),
                old.get("awayScore"),
            )
        )

        new_score_count = sum(
            x is not None
            for x in (
                match.get("homeScore"),
                match.get("awayScore"),
            )
        )

        old_period = bool(
            old.get("hasPeriodData")
        )

        new_period = bool(
            match.get("hasPeriodData")
        )

        if (
            new_score_count > old_score_count
            or (
                new_score_count == old_score_count
                and new_period
                and not old_period
            )
        ):
            unique[key] = match

    return list(unique.values())


# ============================================================
# SIRALAMA
# ============================================================

def sort_matches(matches):
    def key(match):
        return (
            match.get("date", ""),
            match.get("utcDate", ""),
            match.get("league", ""),
            match.get("homeTeam", ""),
            match.get("awayTeam", ""),
        )

    return sorted(
        matches,
        key=key,
    )


# ============================================================
# ANA VERİ TOPLAMA
# ============================================================

def collect_all():
    all_matches = []

    # --------------------------------------------------------
    # NBA
    # --------------------------------------------------------

    nba = fetch_espn_league(
        league="NBA",
        sport="basketball",
        league_id="nba",
        days_back=NBA_DAYS_BACK,
        days_forward=NBA_DAYS_FORWARD,
    )

    all_matches.extend(nba)

    # --------------------------------------------------------
    # NBL
    # --------------------------------------------------------

    nbl = fetch_espn_league(
        league="NBL",
        sport="basketball",
        league_id="aus.nbl",
        days_back=OTHER_ESPN_DAYS_BACK,
        days_forward=OTHER_ESPN_DAYS_FORWARD,
    )

    all_matches.extend(nbl)

    # --------------------------------------------------------
    # NBA G LEAGUE
    # --------------------------------------------------------

    g_league = fetch_espn_league(
        league="NBA G League",
        sport="basketball",
        league_id="nba-g-league",
        days_back=OTHER_ESPN_DAYS_BACK,
        days_forward=OTHER_ESPN_DAYS_FORWARD,
    )

    all_matches.extend(g_league)

    # --------------------------------------------------------
    # EUROLEAGUE
    #
    # E2026 = güncel sezon
    # E2025 / E2024 = tarihsel örneklem
    # --------------------------------------------------------

    for season in (
        "E2026",
        "E2025",
        "E2024",
    ):
        history_only = season != "E2026"

        euroleague = fetch_euroleague_season(
            competition="E",
            season=season,
            history_only=history_only,
        )

        all_matches.extend(euroleague)

    # --------------------------------------------------------
    # EUROCUP
    #
    # U2026 = güncel sezon
    # U2025 / U2024 = tarihsel örneklem
    # --------------------------------------------------------

    for season in (
        "U2026",
        "U2025",
        "U2024",
    ):
        history_only = season != "U2026"

        eurocup = fetch_euroleague_season(
            competition="U",
            season=season,
            history_only=history_only,
        )

        all_matches.extend(eurocup)

    all_matches = deduplicate_matches(
        all_matches
    )

    all_matches = sort_matches(
        all_matches
    )

    return all_matches


# ============================================================
# JSON KAYDET
# ============================================================

def save_json(matches):
    payload = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "totalMatches": len(matches),
        "matches": matches,
    }

    # COMPACT JSON:
    # Dosya boyutunu ciddi şekilde azaltır.
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            payload,
            f,
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
    print("💾 basketball.json")
    print("=" * 60)
    print(
        f"📦 Maç sayısı: {len(matches)}"
    )
    print(
        f"📁 Dosya boyutu: {size_mb:.2f} MB"
    )

    if size_mb >= 95:
        print(
            "⚠️ UYARI: Dosya GitHub 100 MB sınırına yaklaşıyor."
        )


# ============================================================
# ÖZET
# ============================================================

def print_summary(matches):
    print()
    print("=" * 60)
    print("🏀 TOPLAM BASKETBOL VERİSİ")
    print("=" * 60)

    leagues = {}

    for match in matches:
        league = match.get(
            "league",
            "Bilinmiyor",
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

    for league in sorted(leagues):
        item = leagues[league]

        print(
            f"{league}: "
            f"{item['total']} maç | "
            f"{item['played']} tamamlanan | "
            f"{item['periods']} periyotlu"
        )

    print()
    print(
        f"🏀 TOPLAM MAÇ: {len(matches)}"
    )

    print(
        "ℹ️ History alanları maçların içine "
        "tekrar tekrar yazılmıyor."
    )

    print(
        "ℹ️ predictions.py geçmişi basketball.json "
        "içindeki maçlardan oluşturacak."
    )


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("🏀 BASKETBOL VERİ TOPLAYICI")
    print("=" * 60)

    print(
        f"📅 Bugün UTC: {TODAY}"
    )

    matches = collect_all()

    if not matches:
        raise RuntimeError(
            "Hiç basketbol maçı alınamadı."
        )

    save_json(matches)

    print_summary(matches)

    print()
    print("✅ Basketbol verileri başarıyla güncellendi.")


if __name__ == "__main__":
    main()
