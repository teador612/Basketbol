import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests


# ============================================================
# AYARLAR
# ============================================================

OUTPUT_FILE = "basketball.json"

NBA_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/"
    "basketball/nba/scoreboard"
)

EUROLEAGUE_URL = (
    "https://api-live.euroleague.net/v2/competitions/"
    "E/seasons/{season}/games"
)

EUROLEAGUE_SEASON = "E2026"

# NBA geçmiş + gelecek
NBA_PAST_DAYS = 180
NBA_FUTURE_DAYS = 30

# EuroLeague sadece mevcut sezon
# E2026 API zaten sezonun tamamını döndürüyor.
EUROLEAGUE_PERIOD_SCAN_LIMIT = 400

REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/140 Safari/537.36"
    ),
    "Accept": "application/json",
}


# ============================================================
# HTTP
# ============================================================

def get_json(url, params=None, retries=4):
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code in (429, 500, 502, 503, 504):
                wait = attempt * 2
                print(
                    f"   ⚠️ HTTP {response.status_code} "
                    f"→ {wait}s bekleniyor..."
                )
                time.sleep(wait)
                continue

            response.raise_for_status()

        except Exception as exc:
            last_error = exc

            if attempt < retries:
                wait = attempt * 2
                print(
                    f"   ⚠️ İstek hatası: {exc} "
                    f"→ {wait}s bekleniyor..."
                )
                time.sleep(wait)

    raise RuntimeError(
        f"API alınamadı: {url} | {last_error}"
    )


# ============================================================
# GENEL YARDIMCILAR
# ============================================================

def safe_int(value):
    if value is None:
        return None

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
            return datetime.fromisoformat(
                text.replace("Z", "+00:00")
            )

        return datetime.fromisoformat(text)

    except Exception:
        return None


def iso_utc(value):
    dt = parse_date(value)

    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc).isoformat()


def date_only(value):
    dt = parse_date(value)

    if dt is None:
        return None

    return dt.date().isoformat()


def now_utc():
    return datetime.now(timezone.utc)


def normalize_name(name):
    if not name:
        return ""

    text = str(name).strip().lower()

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
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return " ".join(text.split())


# ============================================================
# PERİYOTLAR
# ============================================================

def make_periods(
    q1_scored=None,
    q1_conceded=None,
    q2_scored=None,
    q2_conceded=None,
    q3_scored=None,
    q3_conceded=None,
    q4_scored=None,
    q4_conceded=None,
):
    values = [
        q1_scored,
        q1_conceded,
        q2_scored,
        q2_conceded,
        q3_scored,
        q3_conceded,
        q4_scored,
        q4_conceded,
    ]

    if all(v is None for v in values):
        return None

    return {
        "q1": {
            "scored": q1_scored,
            "conceded": q1_conceded,
        },
        "q2": {
            "scored": q2_scored,
            "conceded": q2_conceded,
        },
        "q3": {
            "scored": q3_scored,
            "conceded": q3_conceded,
        },
        "q4": {
            "scored": q4_scored,
            "conceded": q4_conceded,
        },
    }


def periods_from_euroleague_side(side):
    if not isinstance(side, dict):
        return None

    partials = side.get("partials")

    if not isinstance(partials, dict):
        return None

    return make_periods(
        partials.get("partials1"),
        None,
        partials.get("partials2"),
        None,
        partials.get("partials3"),
        None,
        partials.get("partials4"),
        None,
    )


def build_match_periods(
    home_side,
    away_side,
):
    if not isinstance(home_side, dict):
        return None

    if not isinstance(away_side, dict):
        return None

    home_partials = home_side.get("partials")
    away_partials = away_side.get("partials")

    if not isinstance(home_partials, dict):
        return None

    if not isinstance(away_partials, dict):
        return None

    q1h = safe_int(home_partials.get("partials1"))
    q1a = safe_int(away_partials.get("partials1"))

    q2h = safe_int(home_partials.get("partials2"))
    q2a = safe_int(away_partials.get("partials2"))

    q3h = safe_int(home_partials.get("partials3"))
    q3a = safe_int(away_partials.get("partials3"))

    q4h = safe_int(home_partials.get("partials4"))
    q4a = safe_int(away_partials.get("partials4"))

    values = [
        q1h, q1a,
        q2h, q2a,
        q3h, q3a,
        q4h, q4a,
    ]

    if all(v is None for v in values):
        return None

    return {
        "q1": {
            "home": q1h,
            "away": q1a,
            "total": (
                q1h + q1a
                if q1h is not None and q1a is not None
                else None
            ),
        },
        "q2": {
            "home": q2h,
            "away": q2a,
            "total": (
                q2h + q2a
                if q2h is not None and q2a is not None
                else None
            ),
        },
        "q3": {
            "home": q3h,
            "away": q3a,
            "total": (
                q3h + q3a
                if q3h is not None and q3a is not None
                else None
            ),
        },
        "q4": {
            "home": q4h,
            "away": q4a,
            "total": (
                q4h + q4a
                if q4h is not None and q4a is not None
                else None
            ),
        },
    }


def calculate_half_score(periods):
    if not periods:
        return None

    q1 = periods.get("q1", {})
    q2 = periods.get("q2", {})

    q1h = q1.get("home")
    q1a = q1.get("away")
    q2h = q2.get("home")
    q2a = q2.get("away")

    if None in (q1h, q1a, q2h, q2a):
        return None

    return {
        "home": q1h + q2h,
        "away": q1a + q2a,
        "total": q1h + q1a + q2h + q2a,
    }


# ============================================================
# NBA
# ============================================================

def parse_nba_linescores(team):
    linescores = team.get("linescores")

    if not isinstance(linescores, list):
        return None

    values = []

    for item in linescores[:4]:
        if not isinstance(item, dict):
            values.append(None)
            continue

        values.append(
            safe_int(
                item.get("value")
            )
        )

    while len(values) < 4:
        values.append(None)

    if all(v is None for v in values):
        return None

    return values


def build_nba_periods(home_competitor, away_competitor):
    home_scores = parse_nba_linescores(home_competitor)
    away_scores = parse_nba_linescores(away_competitor)

    if not home_scores or not away_scores:
        return None

    if all(v is None for v in home_scores):
        return None

    if all(v is None for v in away_scores):
        return None

    periods = {}

    for index, quarter in enumerate(
        ["q1", "q2", "q3", "q4"]
    ):
        home = home_scores[index]
        away = away_scores[index]

        periods[quarter] = {
            "home": home,
            "away": away,
            "total": (
                home + away
                if home is not None and away is not None
                else None
            ),
        }

    return periods


def get_nba_games():
    print("=" * 60)
    print("🏀 NBA")
    print("=" * 60)

    all_games = []

    start = now_utc() - timedelta(
        days=NBA_PAST_DAYS
    )

    end = now_utc() + timedelta(
        days=NBA_FUTURE_DAYS
    )

    current = start.date()
    end_date = end.date()

    while current <= end_date:
        date_text = current.strftime("%Y%m%d")

        try:
            data = get_json(
                NBA_SCOREBOARD_URL,
                params={
                    "dates": date_text,
                },
            )
        except Exception as exc:
            print(
                f"   ⚠️ {date_text}: {exc}"
            )
            current += timedelta(days=1)
            continue

        events = data.get("events", [])

        for event in events:
            match = normalize_nba_game(event)

            if match:
                all_games.append(match)

        current += timedelta(days=1)

    # ID ile tekilleştir
    unique = {}

    for game in all_games:
        unique[str(game["id"])] = game

    games = list(unique.values())

    games.sort(
        key=lambda x: (
            x.get("utcDate") or ""
        )
    )

    played_count = sum(
        1
        for game in games
        if game.get("played")
    )

    print(
        f"   📦 NBA toplam: {len(games)}"
    )
    print(
        f"   🏁 Oynanan: {played_count}"
    )

    return games


def normalize_nba_game(event):
    if not isinstance(event, dict):
        return None

    competitions = event.get("competitions")

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
        if competitor.get("homeAway") == "home":
            home = competitor

        elif competitor.get("homeAway") == "away":
            away = competitor

    if not home or not away:
        return None

    home_team = (
        home.get("team", {})
        .get("displayName")
    )

    away_team = (
        away.get("team", {})
        .get("displayName")
    )

    if not home_team or not away_team:
        return None

    utc_date = (
        event.get("date")
        or competition.get("date")
    )

    status = (
        competition
        .get("status", {})
        .get("type", {})
    )

    status_name = (
        status.get("name")
        if isinstance(status, dict)
        else None
    )

    completed = (
        status_name == "STATUS_FINAL"
        or status.get("completed") is True
    )

    home_score = safe_int(
        home.get("score")
    )

    away_score = safe_int(
        away.get("score")
    )

    played = (
        completed
        and home_score is not None
        and away_score is not None
    )

    periods = None

    if played:
        periods = build_nba_periods(
            home,
            away,
        )

    return {
        "id": str(
            event.get("id")
        ),
        "league": "NBA",
        "season": (
            event.get("season", {})
            .get("slug")
            or str(
                event.get("season", {})
                .get("year", "")
            )
        ),
        "date": date_only(utc_date),
        "utcDate": iso_utc(utc_date),
        "homeTeam": home_team,
        "awayTeam": away_team,
        "homeScore": home_score if played else None,
        "awayScore": away_score if played else None,
        "played": played,
        "hasPeriodData": periods is not None,
        "periods": periods,
        "homeHistory": [],
        "awayHistory": [],
        "homeLast5": [],
        "awayLast5": [],
    }


# ============================================================
# EUROLEAGUE
# ============================================================

def extract_euroleague_games(data):
    if not isinstance(data, dict):
        return []

    games = data.get("data")

    if isinstance(games, list):
        return games

    if isinstance(games, dict):
        nested = games.get("games")

        if isinstance(nested, list):
            return nested

    if isinstance(data.get("games"), list):
        return data["games"]

    return []


def normalize_euroleague_game(raw):
    if not isinstance(raw, dict):
        return None

    # ========================================================
    # GERÇEK EUROLeague API YAPISI
    #
    # local = ev sahibi
    # road  = deplasman
    # ========================================================

    home = raw.get("local")
    away = raw.get("road")

    if not isinstance(home, dict):
        return None

    if not isinstance(away, dict):
        return None

    home_club = home.get("club")
    away_club = away.get("club")

    if not isinstance(home_club, dict):
        return None

    if not isinstance(away_club, dict):
        return None

    home_name = (
        home_club.get("name")
        or home_club.get("editorialName")
        or home_club.get("abbreviatedName")
    )

    away_name = (
        away_club.get("name")
        or away_club.get("editorialName")
        or away_club.get("abbreviatedName")
    )

    if not home_name or not away_name:
        return None

    game_id = (
        raw.get("id")
        or raw.get("identifier")
        or raw.get("gameCode")
    )

    if game_id is None:
        return None

    utc_date = (
        raw.get("utcDate")
        or raw.get("date")
        or raw.get("localDate")
    )

    home_score = safe_int(
        home.get("score")
    )

    away_score = safe_int(
        away.get("score")
    )

    played = bool(
        raw.get("played")
    )

    # Bazı API kayıtlarında played false olabilir.
    # Ancak gerçek skor varsa maçı oynanmış kabul ediyoruz.
    if (
        home_score is not None
        and away_score is not None
        and (
            home_score > 0
            or away_score > 0
            or raw.get("gameStatus") in (
                "Finished",
                "Ended",
                "Final",
                "Completed",
            )
        )
    ):
        played = True

    periods = None

    if played:
        periods = build_match_periods(
            home,
            away,
        )

    return {
        "id": str(game_id),
        "league": "EuroLeague",
        "season": EUROLEAGUE_SEASON,
        "date": date_only(utc_date),
        "utcDate": iso_utc(utc_date),
        "homeTeam": home_name,
        "awayTeam": away_name,
        "homeScore": home_score if played else None,
        "awayScore": away_score if played else None,
        "played": played,
        "hasPeriodData": periods is not None,
        "periods": periods,
        "homeHistory": [],
        "awayHistory": [],
        "homeLast5": [],
        "awayLast5": [],
        "round": raw.get("round"),
        "roundName": raw.get("roundName"),
        "gameCode": raw.get("gameCode"),
    }


def get_euroleague_games():
    print("=" * 60)
    print("🏀 EUROLEAGUE")
    print("=" * 60)

    print(
        f"📅 Sezon: {EUROLEAGUE_SEASON}"
    )

    url = EUROLEAGUE_URL.format(
        season=EUROLEAGUE_SEASON
    )

    data = get_json(url)

    raw_games = extract_euroleague_games(
        data
    )

    print(
        f"   📡 api-live: {len(raw_games)}"
    )

    games = []

    for raw in raw_games:
        match = normalize_euroleague_game(
            raw
        )

        if match:
            games.append(match)

    # ID ile tekilleştir
    unique = {}

    for game in games:
        unique[str(game["id"])] = game

    games = list(unique.values())

    games.sort(
        key=lambda x: (
            x.get("utcDate") or ""
        )
    )

    played_count = sum(
        1
        for game in games
        if game.get("played")
    )

    period_count = sum(
        1
        for game in games
        if game.get("hasPeriodData")
    )

    print(
        f"   ✅ Kullanılabilir: {len(games)}"
    )

    print(
        f"   🏁 Tamamlanan: {played_count}"
    )

    print(
        f"   ⏱️ Periyotlu: {period_count}"
    )

    return games


# ============================================================
# TAKIM GEÇMİŞİ
# ============================================================

def make_history_record(
    match,
    team_is_home,
):
    if not match.get("played"):
        return None

    if team_is_home:
        team = match.get("homeTeam")
        opponent = match.get("awayTeam")

        scored = match.get("homeScore")
        conceded = match.get("awayScore")
    else:
        team = match.get("awayTeam")
        opponent = match.get("homeTeam")

        scored = match.get("awayScore")
        conceded = match.get("homeScore")

    if (
        scored is None
        or conceded is None
    ):
        return None

    return {
        "date": match.get("date"),
        "utcDate": match.get("utcDate"),
        "opponent": opponent,
        "scored": scored,
        "conceded": conceded,
        "periods": match.get("periods"),
        "hasPeriodData": bool(
            match.get("hasPeriodData")
        ),
        "matchId": match.get("id"),
        "league": match.get("league"),
        "season": match.get("season"),
    }


def add_team_history(games):
    print("=" * 60)
    print("📚 TAKIM GEÇMİŞLERİ")
    print("=" * 60)

    team_games = {}

    # Önce tüm tamamlanmış maçları takımlara dağıt
    for match in games:
        if not match.get("played"):
            continue

        home = match.get("homeTeam")
        away = match.get("awayTeam")

        if home:
            team_games.setdefault(
                normalize_name(home),
                [],
            ).append(
                make_history_record(
                    match,
                    True,
                )
            )

        if away:
            team_games.setdefault(
                normalize_name(away),
                [],
            ).append(
                make_history_record(
                    match,
                    False,
                )
            )

    # Tarihe göre sırala
    for key in team_games:
        team_games[key] = [
            item
            for item in team_games[key]
            if item is not None
        ]

        team_games[key].sort(
            key=lambda x: (
                x.get("utcDate") or ""
            ),
            reverse=True,
        )

    # Her maça, o maçtan ÖNCE oynanan geçmişi ekle
    for match in games:
        home_key = normalize_name(
            match.get("homeTeam")
        )

        away_key = normalize_name(
            match.get("awayTeam")
        )

        current_time = (
            parse_date(
                match.get("utcDate")
            )
        )

        home_history = []
        away_history = []

        if home_key in team_games:
            for history in team_games[
                home_key
            ]:
                history_time = parse_date(
                    history.get("utcDate")
                )

                if not current_time:
                    continue

                if not history_time:
                    continue

                if (
                    history_time < current_time
                ):
                    home_history.append(
                        history
                    )

        if away_key in team_games:
            for history in team_games[
                away_key
            ]:
                history_time = parse_date(
                    history.get("utcDate")
                )

                if not current_time:
                    continue

                if not history_time:
                    continue

                if (
                    history_time < current_time
                ):
                    away_history.append(
                        history
                    )

        # En yeniler önce
        home_history.sort(
            key=lambda x: (
                x.get("utcDate") or ""
            ),
            reverse=True,
        )

        away_history.sort(
            key=lambda x: (
                x.get("utcDate") or ""
            ),
            reverse=True,
        )

        match["homeHistory"] = home_history
        match["awayHistory"] = away_history

        # Eski sistem uyumluluğu
        match["homeLast5"] = (
            home_history[:5]
        )

        match["awayLast5"] = (
            away_history[:5]
        )

    teams_with_history = sum(
        1
        for records in team_games.values()
        if records
    )

    print(
        f"   🏀 Geçmişi oluşan takım: "
        f"{teams_with_history}"
    )

    print(
        "   ℹ️ EuroLeague için 5 maç şartı yok."
    )

    print(
        "   ℹ️ Takımın mevcut sezon içinde "
        "kaç maçı varsa o kadar örnek kullanılır."
    )


# ============================================================
# İSTATİSTİKLER
# ============================================================

def calculate_statistics(games):
    completed = [
        game
        for game in games
        if game.get("played")
    ]

    perioded = [
        game
        for game in games
        if game.get("hasPeriodData")
    ]

    leagues = {}

    for game in games:
        league = game.get("league")

        if league not in leagues:
            leagues[league] = {
                "total": 0,
                "played": 0,
                "periods": 0,
            }

        leagues[league]["total"] += 1

        if game.get("played"):
            leagues[league]["played"] += 1

        if game.get("hasPeriodData"):
            leagues[league]["periods"] += 1

    return {
        "totalMatches": len(games),
        "completedMatches": len(completed),
        "periodMatches": len(perioded),
        "leagues": leagues,
    }


# ============================================================
# ANA JSON
# ============================================================

def save_data(games):
    statistics = calculate_statistics(
        games
    )

    output = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "generatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "settings": {
            "nbaPastDays": NBA_PAST_DAYS,
            "nbaFutureDays": NBA_FUTURE_DAYS,

            "euroLeagueSeason":
                EUROLEAGUE_SEASON,

            "euroLeagueRequiresFiveGames":
                False,

            "euroLeagueHistoryMode":
                "all_available_current_season",

            "periods": [
                "q1",
                "q2",
                "q3",
                "q4",
            ],
        },

        "statistics": statistics,

        "matches": games,
    }

    temp_file = OUTPUT_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(
        temp_file,
        OUTPUT_FILE,
    )

    print("=" * 60)
    print("💾 VERİ KAYDEDİLDİ")
    print("=" * 60)

    print(
        f"📁 {OUTPUT_FILE}"
    )

    print(
        f"🏀 Toplam maç: "
        f"{statistics['totalMatches']}"
    )

    print(
        f"🏁 Tamamlanan: "
        f"{statistics['completedMatches']}"
    )

    print(
        f"⏱️ Periyotlu: "
        f"{statistics['periodMatches']}"
    )

    for league, stats in (
        statistics["leagues"].items()
    ):
        print(
            f"   {league}: "
            f"{stats['total']} maç | "
            f"{stats['played']} tamamlanan | "
            f"{stats['periods']} periyotlu"
        )


# ============================================================
# ANA PROGRAM
# ============================================================

def main():
    print()
    print("=" * 60)
    print("🏀 NBA + EUROLEAGUE BASKETBOL VERİ GÜNCELLEME")
    print("=" * 60)

    print(
        f"📅 Güncelleme zamanı: "
        f"{datetime.now(timezone.utc).isoformat()}"
    )

    # --------------------------------------------------------
    # NBA
    # --------------------------------------------------------

    nba_games = get_nba_games()

    # --------------------------------------------------------
    # EUROLEAGUE
    # --------------------------------------------------------

    euroleague_games = (
        get_euroleague_games()
    )

    # --------------------------------------------------------
    # BİRLEŞTİR
    # --------------------------------------------------------

    games = (
        nba_games
        + euroleague_games
    )

    # ID + lig ile tekilleştir
    unique = {}

    for game in games:
        key = (
            str(game.get("league"))
            + ":"
            + str(game.get("id"))
        )

        unique[key] = game

    games = list(
        unique.values()
    )

    games.sort(
        key=lambda x: (
            x.get("utcDate") or ""
        )
    )

    print()
    print("=" * 60)
    print("📦 TOPLAM")
    print("=" * 60)

    print(
        f"🎯 Toplam maç: {len(games)}"
    )

    # --------------------------------------------------------
    # TAKIM GEÇMİŞLERİ
    # --------------------------------------------------------

    add_team_history(
        games
    )

    # --------------------------------------------------------
    # KAYDET
    # --------------------------------------------------------

    save_data(
        games
    )

    print()
    print("=" * 60)
    print("✅ İŞLEM TAMAMLANDI")
    print("=" * 60)


if __name__ == "__main__":
    main()
