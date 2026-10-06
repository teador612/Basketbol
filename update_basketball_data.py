import json
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests


# ============================================================
# AYARLAR
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "basketball.json"

REQUEST_TIMEOUT = 30

NBA_DAYS_BACK = 180
NBA_DAYS_FORWARD = 30

ESPN_LEAGUES = [
    {
        "name": "NBA",
        "slug": "nba",
        "pastDays": 180,
        "futureDays": 30,
    },
    {
        "name": "NBL",
        "slug": "nbl",
        "pastDays": 365,
        "futureDays": 30,
    },
    {
        "name": "NBA G League",
        "slug": "nba-development",
        "pastDays": 365,
        "futureDays": 30,
    },
]


# EuroLeague / EuroCup
# Güncel sezon + geçmiş sezonlar.
EUROLEAGUE_SEASONS = [
    "E2026",
    "E2025",
    "E2024",
]

EUROCUP_SEASONS = [
    "U2026",
    "U2025",
    "U2024",
]


ESPN_BASE = (
    "https://site.api.espn.com/apis/site/v2/sports/"
    "basketball"
)

EUROLEAGUE_URL = (
    "https://api-live.euroleague.net/v2/competitions/"
    "{competition}/seasons/{season}/games"
)


# ============================================================
# HTTP
# ============================================================

SESSION = requests.Session()

SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; BasketballDataBot/1.0)"
        ),
        "Accept": "application/json",
    }
)


def get_json(url, params=None):
    try:
        response = SESSION.get(
            url,
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        return response.json()

    except Exception as exc:
        print(f"   ⚠️ İstek hatası: {exc}")
        return None


# ============================================================
# YARDIMCILAR
# ============================================================

def safe_float(value):
    try:
        if value is None:
            return None

        return float(value)

    except Exception:
        return None


def normalize_text(value):
    if value is None:
        return ""

    return (
        str(value)
        .strip()
        .lower()
    )


def parse_iso(value):
    if not value:
        return None

    try:
        text = str(value)

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    except Exception:
        return None


def iso_utc(dt):
    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return dt.astimezone(
        timezone.utc
    ).isoformat()


def get_match_datetime(match):
    return (
        parse_iso(match.get("utcDate"))
        or parse_iso(match.get("date"))
    )


# ============================================================
# PERİYOTLAR
# ============================================================

def make_periods(
    q1_home,
    q1_away,
    q2_home,
    q2_away,
    q3_home,
    q3_away,
    q4_home,
    q4_away,
):
    values = [
        q1_home,
        q1_away,
        q2_home,
        q2_away,
        q3_home,
        q3_away,
        q4_home,
        q4_away,
    ]

    if any(v is None for v in values):
        return {}, False

    q1_home = float(q1_home)
    q1_away = float(q1_away)

    q2_home = float(q2_home)
    q2_away = float(q2_away)

    q3_home = float(q3_home)
    q3_away = float(q3_away)

    q4_home = float(q4_home)
    q4_away = float(q4_away)

    return {
        "q1": {
            "home": q1_home,
            "away": q1_away,
            "total": q1_home + q1_away,
        },
        "q2": {
            "home": q2_home,
            "away": q2_away,
            "total": q2_home + q2_away,
        },
        "q3": {
            "home": q3_home,
            "away": q3_away,
            "total": q3_home + q3_away,
        },
        "q4": {
            "home": q4_home,
            "away": q4_away,
            "total": q4_home + q4_away,
        },
    }, True


# ============================================================
# ESPN
# ============================================================

def fetch_espn_league(
    league_name,
    slug,
    past_days,
    future_days,
):
    print()
    print("=" * 60)
    print(f"🏀 {league_name}")
    print("=" * 60)

    now = datetime.now(timezone.utc)

    start_date = (
        now - timedelta(days=past_days)
    ).date()

    end_date = (
        now + timedelta(days=future_days)
    ).date()

    print(
        f"📅 Tarih aralığı: "
        f"{start_date} → {end_date}"
    )

    all_events = {}

    current = start_date

    while current <= end_date:

        date_text = current.strftime(
            "%Y%m%d"
        )

        url = (
            f"{ESPN_BASE}/"
            f"{slug}/scoreboard"
        )

        data = get_json(
            url,
            params={
                "dates": date_text,
                "limit": 1000,
            },
        )

        if data:

            events = data.get(
                "events",
                [],
            )

            for event in events:

                event_id = str(
                    event.get("id")
                    or ""
                )

                if event_id:
                    all_events[event_id] = event

        current += timedelta(days=1)

    matches = []

    for event in all_events.values():

        match = parse_espn_event(
            event,
            league_name,
        )

        if match:
            matches.append(match)

    matches.sort(
        key=lambda m: (
            get_match_datetime(m)
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        )
    )

    completed = sum(
        1 for m in matches
        if m.get("played")
    )

    perioded = sum(
        1 for m in matches
        if m.get("hasPeriodData")
    )

    print(
        f"   📦 Toplam: {len(matches)}"
    )

    print(
        f"   🏁 Tamamlanan: {completed}"
    )

    print(
        f"   ⏱️ Periyotlu: {perioded}"
    )

    return matches


def parse_espn_event(
    event,
    league_name,
):
    try:
        event_id = str(
            event.get("id")
            or ""
        )

        if not event_id:
            return None

        competitions = event.get(
            "competitions",
            [],
        )

        if not competitions:
            return None

        competition = competitions[0]

        competitors = competition.get(
            "competitors",
            [],
        )

        if len(competitors) < 2:
            return None

        home = None
        away = None

        for competitor in competitors:

            if competitor.get(
                "homeAway"
            ) == "home":
                home = competitor

            elif competitor.get(
                "homeAway"
            ) == "away":
                away = competitor

        if not home or not away:
            return None

        home_team = (
            home.get("team", {})
        )

        away_team = (
            away.get("team", {})
        )

        home_name = (
            home_team.get("displayName")
            or home_team.get("shortDisplayName")
            or home_team.get("name")
        )

        away_name = (
            away_team.get("displayName")
            or away_team.get("shortDisplayName")
            or away_team.get("name")
        )

        if not home_name or not away_name:
            return None

        home_score = safe_float(
            home.get("score")
        )

        away_score = safe_float(
            away.get("score")
        )

        status_data = (
            competition.get(
                "status"
            )
            or event.get("status")
            or {}
        )

        status_type = (
            status_data.get("type", {})
        )

        status_name = normalize_text(
            status_type.get("name")
            or status_type.get("description")
            or status_type.get("state")
        )

        completed_status = (
            status_type.get("completed")
            is True
        )

        played = (
            completed_status
            and home_score is not None
            and away_score is not None
        )

        periods, has_periods = (
            parse_espn_periods(
                competition
            )
        )

        date_value = (
            event.get("date")
            or competition.get("date")
        )

        dt = parse_iso(date_value)

        utc_date = (
            iso_utc(dt)
            if dt
            else date_value
        )

        season = (
            event.get("season", {})
            .get("slug")
            or event.get("season", {})
            .get("year")
        )

        return {
            "id": event_id,

            "league": league_name,

            "season": season,

            "date": (
                dt.strftime("%Y-%m-%d")
                if dt
                else None
            ),

            "utcDate": utc_date,

            "homeTeam": home_name,

            "awayTeam": away_name,

            "homeScore": (
                home_score
                if played
                else None
            ),

            "awayScore": (
                away_score
                if played
                else None
            ),

            "played": played,

            "status": (
                "final"
                if played
                else status_name
            ),

            "hasPeriodData": has_periods,

            "periods": periods,
        }

    except Exception:
        return None


def parse_espn_periods(
    competition
):
    competitors = competition.get(
        "competitors",
        [],
    )

    home = None
    away = None

    for c in competitors:

        if c.get("homeAway") == "home":
            home = c

        elif c.get("homeAway") == "away":
            away = c

    if not home or not away:
        return {}, False

    home_lines = home.get(
        "linescores",
        [],
    )

    away_lines = away.get(
        "linescores",
        [],
    )

    if len(home_lines) < 4:
        return {}, False

    if len(away_lines) < 4:
        return {}, False

    qh = []
    qa = []

    for i in range(4):

        h = safe_float(
            home_lines[i].get(
                "value"
            )
        )

        a = safe_float(
            away_lines[i].get(
                "value"
            )
        )

        if h is None or a is None:
            return {}, False

        qh.append(h)
        qa.append(a)

    return make_periods(
        qh[0],
        qa[0],
        qh[1],
        qa[1],
        qh[2],
        qa[2],
        qh[3],
        qa[3],
    )


# ============================================================
# EUROLEAGUE / EUROCUP
# ============================================================

def fetch_euroleague_season(
    competition,
    season,
    league_name,
):
    print()
    print("=" * 60)
    print(
        f"🏀 {league_name} "
        f"({season})"
    )
    print("=" * 60)

    url = EUROLEAGUE_URL.format(
        competition=competition,
        season=season,
    )

    data = get_json(url)

    if not data:
        print("   ❌ API verisi alınamadı")
        return []

    if isinstance(data, dict):
        games = (
            data.get("data")
            or data.get("games")
            or data.get("content")
            or []
        )
    elif isinstance(data, list):
        games = data
    else:
        games = []

    print(
        f"   📡 API maçları: {len(games)}"
    )

    matches = []

    for game in games:

        match = parse_euro_game(
            game,
            league_name,
            season,
        )

        if match:
            matches.append(match)

    matches.sort(
        key=lambda m: (
            get_match_datetime(m)
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        )
    )

    completed = sum(
        1 for m in matches
        if m.get("played")
    )

    perioded = sum(
        1 for m in matches
        if m.get("hasPeriodData")
    )

    print(
        f"   ✅ Kullanılabilir: "
        f"{len(matches)}"
    )

    print(
        f"   🏁 Tamamlanan: "
        f"{completed}"
    )

    print(
        f"   ⏱️ Periyotlu: "
        f"{perioded}"
    )

    return matches


def parse_euro_game(
    game,
    league_name,
    season,
):
    try:

        game_id = (
            game.get("id")
            or game.get("gameId")
            or game.get("code")
        )

        if game_id is None:
            return None

        local = game.get(
            "local"
        ) or {}

        road = game.get(
            "road"
        ) or {}

        home_club = local.get(
            "club"
        ) or {}

        away_club = road.get(
            "club"
        ) or {}

        home_name = (
            home_club.get("name")
            or local.get("name")
        )

        away_name = (
            away_club.get("name")
            or road.get("name")
        )

        if not home_name or not away_name:
            return None

        home_score = safe_float(
            local.get("score")
        )

        away_score = safe_float(
            road.get("score")
        )

        status_values = [
            game.get("status"),
            game.get("gameStatus"),
            game.get("state"),
        ]

        status_text = " ".join(
            normalize_text(v)
            for v in status_values
            if v is not None
        )

        # EuroLeague API'sinde skor bulunan eski
        # maçlar için ayrıca canlı durum kontrolü.
        finished_words = [
            "final",
            "finished",
            "complete",
            "completed",
            "ended",
        ]

        explicit_final = any(
            word in status_text
            for word in finished_words
        )

        # API'deki oyun tarihini bul.
        date_value = (
            game.get("date")
            or game.get("utcDate")
            or game.get("startDate")
            or game.get("gameDate")
        )

        dt = parse_iso(date_value)

        if dt is None:

            for key in (
                "start",
                "startTime",
                "timestamp",
            ):
                candidate = game.get(key)

                if candidate:
                    dt = parse_iso(
                        candidate
                    )

                    if dt:
                        break

        periods, has_periods = (
            parse_euro_periods(
                local,
                road,
            )
        )

        # Çok önemli:
        # Eski maçlarda skor + dört periyot varsa
        # tamamlanmış kabul edilebilir.
        period_final = (
            has_periods
            and home_score is not None
            and away_score is not None
        )

        played = (
            home_score is not None
            and away_score is not None
            and (
                explicit_final
                or period_final
            )
        )

        return {
            "id": str(game_id),

            "league": league_name,

            "season": season,

            "date": (
                dt.strftime("%Y-%m-%d")
                if dt
                else None
            ),

            "utcDate": (
                iso_utc(dt)
                if dt
                else date_value
            ),

            "homeTeam": home_name,

            "awayTeam": away_name,

            "homeScore": (
                home_score
                if played
                else None
            ),

            "awayScore": (
                away_score
                if played
                else None
            ),

            "played": played,

            "status": (
                "final"
                if played
                else (
                    status_text
                    or "scheduled"
                )
            ),

            "hasPeriodData": has_periods,

            "periods": periods,
        }

    except Exception:
        return None


def parse_euro_periods(
    local,
    road,
):
    local_partials = (
        local.get("partials")
        or {}
    )

    road_partials = (
        road.get("partials")
        or {}
    )

    values_home = []
    values_away = []

    for i in range(1, 5):

        h = safe_float(
            local_partials.get(
                f"partials{i}"
            )
        )

        a = safe_float(
            road_partials.get(
                f"partials{i}"
            )
        )

        if h is None or a is None:
            return {}, False

        values_home.append(h)
        values_away.append(a)

    return make_periods(
        values_home[0],
        values_away[0],
        values_home[1],
        values_away[1],
        values_home[2],
        values_away[2],
        values_home[3],
        values_away[3],
    )


# ============================================================
# GEÇMİŞ HESAPLAMA
# ============================================================

def build_team_histories(matches):
    """
    Her maç için sadece o maçtan önce oynanmış
    aynı lig maçlarını takım geçmişine ekler.
    """

    matches_sorted = sorted(
        matches,
        key=lambda m: (
            get_match_datetime(m)
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        )
    )

    histories = {}

    for match in matches_sorted:

        league = normalize_text(
            match.get("league")
        )

        home = normalize_text(
            match.get("homeTeam")
        )

        away = normalize_text(
            match.get("awayTeam")
        )

        if not home or not away:
            continue

        home_key = (
            league,
            home,
        )

        away_key = (
            league,
            away,
        )

        home_history = list(
            histories.get(
                home_key,
                []
            )
        )

        away_history = list(
            histories.get(
                away_key,
                []
            )
        )

        match["homeHistory"] = (
            home_history
        )

        match["awayHistory"] = (
            away_history
        )

        # Son 5 geriye dönük uyumluluk
        match["homeLast5"] = (
            home_history[-5:]
        )

        match["awayLast5"] = (
            away_history[-5:]
        )

        # Sadece tamamlanmış maçlar geçmişe girer.
        if not match.get("played"):
            continue

        home_score = safe_float(
            match.get("homeScore")
        )

        away_score = safe_float(
            match.get("awayScore")
        )

        if home_score is None or away_score is None:
            continue

        date_value = match.get(
            "date"
        )

        utc_date = match.get(
            "utcDate"
        )

        periods = match.get(
            "periods"
        ) or {}

        home_record = {
            "date": date_value,
            "utcDate": utc_date,
            "opponent": (
                match.get("awayTeam")
            ),
            "scored": home_score,
            "conceded": away_score,
            "isHome": True,
            "periods": periods,
            "hasPeriodData": bool(
                match.get(
                    "hasPeriodData"
                )
            ),
            "matchId": match.get(
                "id"
            ),
            "league": match.get(
                "league"
            ),
            "season": match.get(
                "season"
            ),
        }

        away_record = {
            "date": date_value,
            "utcDate": utc_date,
            "opponent": (
                match.get("homeTeam")
            ),
            "scored": away_score,
            "conceded": home_score,
            "isHome": False,
            "periods": periods,
            "hasPeriodData": bool(
                match.get(
                    "hasPeriodData"
                )
            ),
            "matchId": match.get(
                "id"
            ),
            "league": match.get(
                "league"
            ),
            "season": match.get(
                "season"
            ),
        }

        histories.setdefault(
            home_key,
            []
        ).append(
            home_record
        )

        histories.setdefault(
            away_key,
            []
        ).append(
            away_record
        )

    return matches_sorted, histories


# ============================================================
# TEKRARLARI TEMİZLE
# ============================================================

def deduplicate_matches(matches):

    unique = {}

    for match in matches:

        league = normalize_text(
            match.get("league")
        )

        home = normalize_text(
            match.get("homeTeam")
        )

        away = normalize_text(
            match.get("awayTeam")
        )

        dt = get_match_datetime(
            match
        )

        date_key = (
            dt.isoformat()
            if dt
            else str(
                match.get("date")
            )
        )

        key = (
            league,
            home,
            away,
            date_key,
        )

        old = unique.get(key)

        if old is None:
            unique[key] = match
            continue

        # Daha dolu olan kaydı koru.
        old_score = (
            old.get("homeScore")
            is not None
        )

        new_score = (
            match.get("homeScore")
            is not None
        )

        old_period = bool(
            old.get(
                "hasPeriodData"
            )
        )

        new_period = bool(
            match.get(
                "hasPeriodData"
            )
        )

        if new_period and not old_period:
            unique[key] = match

        elif new_score and not old_score:
            unique[key] = match

    return list(
        unique.values()
    )


# ============================================================
# İSTATİSTİK
# ============================================================

def calculate_statistics(matches):

    leagues = {}

    for match in matches:

        league = (
            match.get("league")
            or "Bilinmeyen"
        )

        if league not in leagues:
            leagues[league] = {
                "matches": 0,
                "completed": 0,
                "perioded": 0,
            }

        leagues[league]["matches"] += 1

        if match.get("played"):
            leagues[league][
                "completed"
            ] += 1

        if match.get(
            "hasPeriodData"
        ):
            leagues[league][
                "perioded"
            ] += 1

    return leagues


# ============================================================
# ANA
# ============================================================

def main():

    print()
    print("=" * 60)
    print(
        "🏀 BASKETBOL ÇOKLU LİG "
        "VERİ GÜNCELLEME"
    )
    print("=" * 60)

    now = datetime.now(
        timezone.utc
    )

    print(
        f"📅 Güncelleme: "
        f"{now.isoformat()}"
    )

    all_matches = []

    # --------------------------------------------------------
    # ESPN
    # --------------------------------------------------------

    for config in ESPN_LEAGUES:

        matches = fetch_espn_league(
            config["name"],
            config["slug"],
            config["pastDays"],
            config["futureDays"],
        )

        all_matches.extend(
            matches
        )

    # --------------------------------------------------------
    # EUROLEAGUE
    # --------------------------------------------------------

    euroleague_matches = []

    for season in EUROLEAGUE_SEASONS:

        matches = fetch_euroleague_season(
            "E",
            season,
            "EuroLeague",
        )

        euroleague_matches.extend(
            matches
        )

        time.sleep(0.5)

    all_matches.extend(
        euroleague_matches
    )

    # --------------------------------------------------------
    # EUROCUP
    # --------------------------------------------------------

    eurocup_matches = []

    for season in EUROCUP_SEASONS:

        matches = fetch_euroleague_season(
            "U",
            season,
            "EuroCup",
        )

        eurocup_matches.extend(
            matches
        )

        time.sleep(0.5)

    all_matches.extend(
        eurocup_matches
    )

    # --------------------------------------------------------
    # TEKRARLARI TEMİZLE
    # --------------------------------------------------------

    all_matches = deduplicate_matches(
        all_matches
    )

    # --------------------------------------------------------
    # GEÇMİŞLER
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("📚 TAKIM GEÇMİŞLERİ")
    print("=" * 60)

    matches, histories = (
        build_team_histories(
            all_matches
        )
    )

    team_count = len(histories)

    print(
        f"   🏀 Geçmişi bulunan takım: "
        f"{team_count}"
    )

    print(
        "   ℹ️ Eski sezonlar geçmiş "
        "örneklemine dahil edildi."
    )

    print(
        "   ℹ️ Tahmin sistemi son "
        "10 uygun maçı kullanabilir."
    )

    # --------------------------------------------------------
    # İSTATİSTİK
    # --------------------------------------------------------

    statistics = calculate_statistics(
        matches
    )

    total = len(matches)

    completed = sum(
        1
        for m in matches
        if m.get("played")
    )

    perioded = sum(
        1
        for m in matches
        if m.get(
            "hasPeriodData"
        )
    )

    # --------------------------------------------------------
    # KAYDET
    # --------------------------------------------------------

    output = {
        "source": [
            "ESPN",
            "EuroLeague API",
            "EuroCup API",
        ],

        "updatedAt": now.isoformat(),

        "generatedAt": now.isoformat(),

        "settings": {
            "historyMatches": 10,
            "pastSeasons": True,
            "leagueSeparatedHistory": True,
        },

        "statistics": {
            "totalMatches": total,
            "completed": completed,
            "perioded": perioded,
            "leagues": statistics,
        },

        "matches": matches,
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

    # --------------------------------------------------------
    # SONUÇ
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print("📦 TOPLAM")
    print("=" * 60)

    print(
        f"🎯 Toplam maç: {total}"
    )

    print(
        f"🏁 Tamamlanan: {completed}"
    )

    print(
        f"⏱️ Periyotlu: {perioded}"
    )

    print()
    print("🏆 Ligler:")

    for league, stats in sorted(
        statistics.items()
    ):

        print(
            f"   • {league}: "
            f"{stats['matches']} maç | "
            f"{stats['completed']} tamamlanan | "
            f"{stats['perioded']} periyotlu"
        )

    print()
    print("=" * 60)
    print("💾 VERİ KAYDEDİLDİ")
    print("=" * 60)

    print(
        f"📁 {OUTPUT_FILE}"
    )

    print(
        f"🏀 Toplam maç: {total}"
    )

    print(
        f"🏁 Tamamlanan: {completed}"
    )

    print(
        f"⏱️ Periyotlu: {perioded}"
    )

    print()
    print("=" * 60)
    print("✅ İŞLEM TAMAMLANDI")
    print("=" * 60)


if __name__ == "__main__":
    main()
