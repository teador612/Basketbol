import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests


# ============================================================
# AYARLAR
# ============================================================

OUTPUT_FILE = "basketball.json"

REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140 Safari/537.36"
    ),
    "Accept": "application/json",
}


# ============================================================
# NBA
# ============================================================

NBA_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/basketball/nba/scoreboard"
)

NBA_PAST_DAYS = 180
NBA_FUTURE_DAYS = 30


# ============================================================
# EURO LEAGUE
# ============================================================

EUROLEAGUE_URL = (
    "https://api-live.euroleague.net/v2/"
    "competitions/E/seasons/{season}/games"
)

EUROLEAGUE_SEASON = "E2026"


# ============================================================
# EURO CUP
# ============================================================

EUROCUP_URL = (
    "https://api-live.euroleague.net/v2/"
    "competitions/U/seasons/{season}/games"
)

EUROCUP_SEASON = "U2026"


# ============================================================
# EK ESPN LİGLERİ
#
# Bunlar aynı ESPN scoreboard sistemi üzerinden alınır.
# Hata olursa bütün sistemi durdurmaz, sadece o lig atlanır.
# ============================================================

ADDITIONAL_ESPN_LEAGUES = [
    {
        "name": "NBL",
        "slug": "nbl",
        "season": "2026",
        "pastDays": 180,
        "futureDays": 30,
    },
    {
        "name": "NBA G League",
        "slug": "nba-development",
        "season": "2026-27",
        "pastDays": 180,
        "futureDays": 30,
    },
]


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

            if response.status_code in (
                429,
                500,
                502,
                503,
                504,
            ):
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
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_date(value):
    if not value:
        return None

    try:
        text = str(value).strip()

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except Exception:
        return None


def iso_utc(value):
    dt = parse_date(value)

    if dt is None:
        return None

    return dt.isoformat()


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
        "à": "a",
        "ä": "a",
        "â": "a",
        "é": "e",
        "è": "e",
        "ë": "e",
        "ê": "e",
        "í": "i",
        "ì": "i",
        "ï": "i",
        "ó": "o",
        "ò": "o",
        "ô": "o",
        "ú": "u",
        "ù": "u",
        "û": "u",
        "ý": "y",
        "ÿ": "y",
        "ñ": "n",
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new,
        )

    return " ".join(
        text.split()
    )


# ============================================================
# PERİYOTLAR
# ============================================================

def make_periods(
    q1_home=None,
    q1_away=None,
    q2_home=None,
    q2_away=None,
    q3_home=None,
    q3_away=None,
    q4_home=None,
    q4_away=None,
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

    if all(
        value is None
        for value in values
    ):
        return None

    return {
        "q1": {
            "home": q1_home,
            "away": q1_away,
            "total": (
                q1_home + q1_away
                if q1_home is not None
                and q1_away is not None
                else None
            ),
        },
        "q2": {
            "home": q2_home,
            "away": q2_away,
            "total": (
                q2_home + q2_away
                if q2_home is not None
                and q2_away is not None
                else None
            ),
        },
        "q3": {
            "home": q3_home,
            "away": q3_away,
            "total": (
                q3_home + q3_away
                if q3_home is not None
                and q3_away is not None
                else None
            ),
        },
        "q4": {
            "home": q4_home,
            "away": q4_away,
            "total": (
                q4_home + q4_away
                if q4_home is not None
                and q4_away is not None
                else None
            ),
        },
    }


def build_periods_from_euroleague(
    home_side,
    away_side,
):
    if not isinstance(
        home_side,
        dict,
    ):
        return None

    if not isinstance(
        away_side,
        dict,
    ):
        return None

    home_partials = (
        home_side.get("partials")
        or {}
    )

    away_partials = (
        away_side.get("partials")
        or {}
    )

    if not isinstance(
        home_partials,
        dict,
    ):
        return None

    if not isinstance(
        away_partials,
        dict,
    ):
        return None

    return make_periods(
        safe_int(
            home_partials.get("partials1")
        ),
        safe_int(
            away_partials.get("partials1")
        ),
        safe_int(
            home_partials.get("partials2")
        ),
        safe_int(
            away_partials.get("partials2")
        ),
        safe_int(
            home_partials.get("partials3")
        ),
        safe_int(
            away_partials.get("partials3")
        ),
        safe_int(
            home_partials.get("partials4")
        ),
        safe_int(
            away_partials.get("partials4")
        ),
    )


def parse_nba_linescores(team):
    if not isinstance(
        team,
        dict,
    ):
        return None

    linescores = team.get(
        "linescores"
    )

    if not isinstance(
        linescores,
        list,
    ):
        return None

    values = []

    for item in linescores[:4]:
        if not isinstance(
            item,
            dict,
        ):
            values.append(None)
            continue

        values.append(
            safe_int(
                item.get("value")
            )
        )

    while len(values) < 4:
        values.append(None)

    if all(
        value is None
        for value in values
    ):
        return None

    return values


def build_nba_periods(
    home,
    away,
):
    home_scores = parse_nba_linescores(
        home
    )

    away_scores = parse_nba_linescores(
        away
    )

    if not home_scores:
        return None

    if not away_scores:
        return None

    return make_periods(
        home_scores[0],
        away_scores[0],
        home_scores[1],
        away_scores[1],
        home_scores[2],
        away_scores[2],
        home_scores[3],
        away_scores[3],
    )


# ============================================================
# ESPN NORMALIZE
# ============================================================

def normalize_espn_game(
    event,
    league_name,
    season,
):
    if not isinstance(
        event,
        dict,
    ):
        return None

    competitions = (
        event.get("competitions")
        or []
    )

    if not competitions:
        return None

    competition = competitions[0]

    competitors = (
        competition.get(
            "competitors"
        )
        or []
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
        .get("displayName")
        or home.get("team", {})
        .get("shortDisplayName")
    )

    away_team = (
        away.get("team", {})
        .get("displayName")
        or away.get("team", {})
        .get("shortDisplayName")
    )

    if not home_team:
        return None

    if not away_team:
        return None

    status = (
        competition.get(
            "status",
            {},
        )
        .get(
            "type",
            {},
        )
    )

    status_name = (
        status.get("name")
        if isinstance(
            status,
            dict,
        )
        else None
    )

    completed = (
        status_name
        == "STATUS_FINAL"
        or status.get(
            "completed"
        ) is True
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

    utc_date = (
        event.get("date")
        or competition.get("date")
    )

    return {
        "id": str(
            event.get("id")
        ),
        "league": league_name,
        "season": (
            season
            or event.get(
                "season",
                {},
            ).get("slug")
            or event.get(
                "season",
                {},
            ).get("year")
        ),
        "date": date_only(
            utc_date
        ),
        "utcDate": iso_utc(
            utc_date
        ),
        "homeTeam": home_team,
        "awayTeam": away_team,
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
        "hasPeriodData": (
            periods is not None
        ),
        "periods": periods,
        "homeHistory": [],
        "awayHistory": [],
        "homeLast5": [],
        "awayLast5": [],
    }


# ============================================================
# ESPN TEK GÜN
# ============================================================

def get_espn_day(
    date_value,
    league_name,
    league_slug,
    season,
):
    date_text = date_value.strftime(
        "%Y%m%d"
    )

    url = (
        "https://site.api.espn.com/"
        "apis/site/v2/sports/"
        "basketball/"
        f"{league_slug}/scoreboard"
    )

    try:
        data = get_json(
            url,
            params={
                "dates": date_text,
            },
        )

    except Exception as exc:
        print(
            f"   ⚠️ {league_name} "
            f"{date_text}: {exc}"
        )
        return []

    events = (
        data.get("events")
        or []
    )

    games = []

    for event in events:
        game = normalize_espn_game(
            event,
            league_name,
            season,
        )

        if game:
            games.append(game)

    return games


# ============================================================
# ESPN LİGİ TARİH ARALIĞI
# ============================================================

def get_espn_league_games(
    league_name,
    league_slug,
    season,
    past_days,
    future_days,
):
    print()
    print("=" * 60)
    print(
        f"🏀 {league_name}"
    )
    print("=" * 60)

    today = now_utc().date()

    start = (
        today
        - timedelta(
            days=past_days
        )
    )

    end = (
        today
        + timedelta(
            days=future_days
        )
    )

    print(
        f"📅 Tarih aralığı: "
        f"{start} → {end}"
    )

    all_games = []

    current = start

    while current <= end:
        games = get_espn_day(
            current,
            league_name,
            league_slug,
            season,
        )

        all_games.extend(
            games
        )

        current += timedelta(
            days=1
        )

    unique = {}

    for game in all_games:
        game_id = game.get(
            "id"
        )

        if game_id:
            unique[
                f"{league_name}:{game_id}"
            ] = game
        else:
            key = (
                f"{league_name}:"
                f"{game.get('date')}:"
                f"{game.get('homeTeam')}:"
                f"{game.get('awayTeam')}"
            )

            unique[key] = game

    games = list(
        unique.values()
    )

    games.sort(
        key=lambda item: (
            item.get("utcDate")
            or ""
        )
    )

    played = sum(
        1
        for game in games
        if game.get("played")
    )

    periods = sum(
        1
        for game in games
        if game.get(
            "hasPeriodData"
        )
    )

    print(
        f"   📦 Toplam: {len(games)}"
    )

    print(
        f"   🏁 Tamamlanan: {played}"
    )

    print(
        f"   ⏱️ Periyotlu: {periods}"
    )

    return games


# ============================================================
# NBA
# ============================================================

def get_nba_games():
    return get_espn_league_games(
        league_name="NBA",
        league_slug="nba",
        season="2026-27",
        past_days=NBA_PAST_DAYS,
        future_days=NBA_FUTURE_DAYS,
    )


# ============================================================
# EURO LEAGUE / EURO CUP ORTAK
# ============================================================

def extract_euro_games(data):
    if not isinstance(
        data,
        dict,
    ):
        return []

    games = data.get(
        "data"
    )

    if isinstance(
        games,
        list,
    ):
        return games

    if isinstance(
        games,
        dict,
    ):
        nested = games.get(
            "games"
        )

        if isinstance(
            nested,
            list,
        ):
            return nested

    games = data.get(
        "games"
    )

    if isinstance(
        games,
        list,
    ):
        return games

    return []


def normalize_euro_game(
    raw,
    competition_name,
    season,
):
    if not isinstance(
        raw,
        dict,
    ):
        return None

    home = raw.get(
        "local"
    )

    away = raw.get(
        "road"
    )

    if not isinstance(
        home,
        dict,
    ):
        return None

    if not isinstance(
        away,
        dict,
    ):
        return None

    home_club = (
        home.get("club")
        or {}
    )

    away_club = (
        away.get("club")
        or {}
    )

    if not isinstance(
        home_club,
        dict,
    ):
        return None

    if not isinstance(
        away_club,
        dict,
    ):
        return None

    home_name = (
        home_club.get("name")
        or home_club.get(
            "editorialName"
        )
        or home_club.get(
            "abbreviatedName"
        )
    )

    away_name = (
        away_club.get("name")
        or away_club.get(
            "editorialName"
        )
        or away_club.get(
            "abbreviatedName"
        )
    )

    if not home_name:
        return None

    if not away_name:
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

    game_status = str(
        raw.get(
            "gameStatus"
        )
        or ""
    ).lower()

    if (
        home_score is not None
        and away_score is not None
        and (
            "finish" in game_status
            or "final" in game_status
            or "end" in game_status
            or home_score > 0
            or away_score > 0
        )
    ):
        played = True

    periods = None

    if played:
        periods = (
            build_periods_from_euroleague(
                home,
                away,
            )
        )

    return {
        "id": str(
            game_id
        ),
        "league": competition_name,
        "season": season,
        "date": date_only(
            utc_date
        ),
        "utcDate": iso_utc(
            utc_date
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
        "hasPeriodData": (
            periods is not None
        ),
        "periods": periods,
        "homeHistory": [],
        "awayHistory": [],
        "homeLast5": [],
        "awayLast5": [],
        "round": raw.get(
            "round"
        ),
        "roundName": raw.get(
            "roundName"
        ),
        "gameCode": raw.get(
            "gameCode"
        ),
    }


def get_euro_competition_games(
    competition_name,
    competition_code,
    season,
):
    print()
    print("=" * 60)
    print(
        f"🏀 {competition_name}"
    )
    print("=" * 60)

    print(
        f"📅 Sezon: {season}"
    )

    url = (
        "https://api-live.euroleague.net/"
        f"v2/competitions/"
        f"{competition_code}/seasons/"
        f"{season}/games"
    )

    try:
        data = get_json(
            url
        )

    except Exception as exc:
        print(
            f"   ❌ {competition_name}: "
            f"{exc}"
        )
        return []

    raw_games = extract_euro_games(
        data
    )

    print(
        f"   📡 API maçları: "
        f"{len(raw_games)}"
    )

    games = []

    for raw in raw_games:
        game = normalize_euro_game(
            raw,
            competition_name,
            season,
        )

        if game:
            games.append(game)

    unique = {}

    for game in games:
        unique[
            f"{competition_name}:"
            f"{game.get('id')}"
        ] = game

    games = list(
        unique.values()
    )

    games.sort(
        key=lambda item: (
            item.get("utcDate")
            or ""
        )
    )

    played = sum(
        1
        for game in games
        if game.get("played")
    )

    periods = sum(
        1
        for game in games
        if game.get(
            "hasPeriodData"
        )
    )

    print(
        f"   ✅ Kullanılabilir: "
        f"{len(games)}"
    )

    print(
        f"   🏁 Tamamlanan: "
        f"{played}"
    )

    print(
        f"   ⏱️ Periyotlu: "
        f"{periods}"
    )

    return games


def get_euroleague_games():
    return get_euro_competition_games(
        competition_name="EuroLeague",
        competition_code="E",
        season=EUROLEAGUE_SEASON,
    )


def get_eurocup_games():
    return get_euro_competition_games(
        competition_name="EuroCup",
        competition_code="U",
        season=EUROCUP_SEASON,
    )


# ============================================================
# TAKIM GEÇMİŞİ
# ============================================================

def make_history_record(
    match,
    team_is_home,
):
    if not match.get(
        "played"
    ):
        return None

    if team_is_home:
        scored = match.get(
            "homeScore"
        )

        conceded = match.get(
            "awayScore"
        )

        opponent = match.get(
            "awayTeam"
        )

    else:
        scored = match.get(
            "awayScore"
        )

        conceded = match.get(
            "homeScore"
        )

        opponent = match.get(
            "homeTeam"
        )

    if scored is None:
        return None

    if conceded is None:
        return None

    return {
        "date": match.get(
            "date"
        ),
        "utcDate": match.get(
            "utcDate"
        ),
        "opponent": opponent,
        "scored": scored,
        "conceded": conceded,
        "periods": match.get(
            "periods"
        ),
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


def add_team_history(
    games
):
    print()
    print("=" * 60)
    print(
        "📚 TAKIM GEÇMİŞLERİ"
    )
    print("=" * 60)

    team_games = {}

    for match in games:
        if not match.get(
            "played"
        ):
            continue

        home = match.get(
            "homeTeam"
        )

        away = match.get(
            "awayTeam"
        )

        if home:
            key = normalize_name(
                home
            )

            record = make_history_record(
                match,
                True,
            )

            if record:
                team_games.setdefault(
                    key,
                    [],
                ).append(
                    record
                )

        if away:
            key = normalize_name(
                away
            )

            record = make_history_record(
                match,
                False,
            )

            if record:
                team_games.setdefault(
                    key,
                    [],
                ).append(
                    record
                )

    for key in team_games:
        team_games[key].sort(
            key=lambda item: (
                item.get(
                    "utcDate"
                )
                or ""
            ),
            reverse=True,
        )

    for match in games:
        home_key = normalize_name(
            match.get(
                "homeTeam"
            )
        )

        away_key = normalize_name(
            match.get(
                "awayTeam"
            )
        )

        current_time = parse_date(
            match.get(
                "utcDate"
            )
        )

        home_history = []
        away_history = []

        if (
            current_time
            and home_key in team_games
        ):
            for history in team_games[
                home_key
            ]:
                history_time = parse_date(
                    history.get(
                        "utcDate"
                    )
                )

                if not history_time:
                    continue

                if (
                    history_time
                    < current_time
                ):
                    home_history.append(
                        history
                    )

        if (
            current_time
            and away_key in team_games
        ):
            for history in team_games[
                away_key
            ]:
                history_time = parse_date(
                    history.get(
                        "utcDate"
                    )
                )

                if not history_time:
                    continue

                if (
                    history_time
                    < current_time
                ):
                    away_history.append(
                        history
                    )

        home_history.sort(
            key=lambda item: (
                item.get(
                    "utcDate"
                )
                or ""
            ),
            reverse=True,
        )

        away_history.sort(
            key=lambda item: (
                item.get(
                    "utcDate"
                )
                or ""
            ),
            reverse=True,
        )

        # Tüm geçmiş burada tutuluyor.
        # predictions.py son 10'u kullanabilir.
        match[
            "homeHistory"
        ] = home_history

        match[
            "awayHistory"
        ] = away_history

        # Eski sistem uyumluluğu.
        match[
            "homeLast5"
        ] = home_history[:5]

        match[
            "awayLast5"
        ] = away_history[:5]

    teams_with_history = sum(
        1
        for records
        in team_games.values()
        if records
    )

    print(
        f"   🏀 Geçmişi bulunan takım: "
        f"{teams_with_history}"
    )

    print(
        "   ℹ️ Geçmiş maçlar lig bazında "
        "korunuyor."
    )

    print(
        "   ℹ️ Tahmin sistemi son 10 uygun "
        "maçı kullanabilir."
    )


# ============================================================
# İSTATİSTİKLER
# ============================================================

def calculate_statistics(
    games
):
    completed = [
        game
        for game in games
        if game.get(
            "played"
        )
    ]

    perioded = [
        game
        for game in games
        if game.get(
            "hasPeriodData"
        )
    ]

    leagues = {}

    for game in games:
        league = game.get(
            "league"
        )

        if league not in leagues:
            leagues[league] = {
                "total": 0,
                "played": 0,
                "periods": 0,
            }

        leagues[
            league
        ]["total"] += 1

        if game.get(
            "played"
        ):
            leagues[
                league
            ]["played"] += 1

        if game.get(
            "hasPeriodData"
        ):
            leagues[
                league
            ]["periods"] += 1

    return {
        "totalMatches": len(
            games
        ),
        "completedMatches": len(
            completed
        ),
        "periodMatches": len(
            perioded
        ),
        "leagues": leagues,
    }


# ============================================================
# KAYDET
# ============================================================

def save_data(
    games
):
    statistics = (
        calculate_statistics(
            games
        )
    )

    now = datetime.now(
        timezone.utc
    ).isoformat()

    output = {
        "updatedAt": now,
        "generatedAt": now,

        "settings": {
            "nbaPastDays": NBA_PAST_DAYS,
            "nbaFutureDays": NBA_FUTURE_DAYS,

            "euroLeagueSeason":
                EUROLEAGUE_SEASON,

            "euroCupSeason":
                EUROCUP_SEASON,

            "historyMode":
                "all_available_before_match",

            "predictionHistoryLimit":
                10,

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

    output_path = (
        os.path.abspath(
            OUTPUT_FILE
        )
    )

    temp_path = (
        output_path
        + ".tmp"
    )

    with open(
        temp_path,
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
        temp_path,
        output_path,
    )

    print()
    print("=" * 60)
    print(
        "💾 VERİ KAYDEDİLDİ"
    )
    print("=" * 60)

    print(
        f"📁 {output_path}"
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

    print()

    for league, stats in (
        statistics[
            "leagues"
        ].items()
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
    print(
        "🏀 BASKETBOL ÇOKLU LİG VERİ GÜNCELLEME"
    )
    print("=" * 60)

    print(
        f"📅 Güncelleme: "
        f"{now_utc().isoformat()}"
    )

    # --------------------------------------------------------
    # NBA
    # --------------------------------------------------------

    nba_games = get_nba_games()

    # --------------------------------------------------------
    # EURO LEAGUE
    # --------------------------------------------------------

    euroleague_games = (
        get_euroleague_games()
    )

    # --------------------------------------------------------
    # EURO CUP
    # --------------------------------------------------------

    eurocup_games = (
        get_eurocup_games()
    )

    # --------------------------------------------------------
    # EK ESPN LİGLERİ
    # --------------------------------------------------------

    additional_games = []

    for league in (
        ADDITIONAL_ESPN_LEAGUES
    ):
        try:
            games = (
                get_espn_league_games(
                    league_name=league[
                        "name"
                    ],
                    league_slug=league[
                        "slug"
                    ],
                    season=league[
                        "season"
                    ],
                    past_days=league[
                        "pastDays"
                    ],
                    future_days=league[
                        "futureDays"
                    ],
                )
            )

            additional_games.extend(
                games
            )

        except Exception as exc:
            print()
            print(
                f"⚠️ {league['name']} "
                f"alınamadı: {exc}"
            )

            print(
                "   Diğer liglerle devam ediliyor."
            )

    # --------------------------------------------------------
    # BİRLEŞTİR
    # --------------------------------------------------------

    games = (
        nba_games
        + euroleague_games
        + eurocup_games
        + additional_games
    )

    # --------------------------------------------------------
    # TEKRARLARI TEMİZLE
    # --------------------------------------------------------

    unique = {}

    for game in games:
        league = str(
            game.get(
                "league"
            )
        )

        game_id = str(
            game.get(
                "id"
            )
        )

        key = (
            f"{league}:"
            f"{game_id}"
        )

        unique[key] = game

    games = list(
        unique.values()
    )

    # --------------------------------------------------------
    # TARİHE GÖRE SIRALA
    # --------------------------------------------------------

    games.sort(
        key=lambda item: (
            item.get(
                "utcDate"
            )
            or ""
        )
    )

    # --------------------------------------------------------
    # ÖZET
    # --------------------------------------------------------

    print()
    print("=" * 60)
    print(
        "📦 TOPLAM"
    )
    print("=" * 60)

    print(
        f"🎯 Toplam maç: "
        f"{len(games)}"
    )

    league_names = []

    for game in games:
        league = game.get(
            "league"
        )

        if (
            league
            and league not in league_names
        ):
            league_names.append(
                league
            )

    print()
    print(
        "🏆 Ligler:"
    )

    for league in league_names:
        count = sum(
            1
            for game in games
            if game.get(
                "league"
            ) == league
        )

        played = sum(
            1
            for game in games
            if (
                game.get(
                    "league"
                )
                == league
                and game.get(
                    "played"
                )
            )
        )

        print(
            f"   • {league}: "
            f"{count} maç | "
            f"{played} tamamlanan"
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
    print(
        "✅ İŞLEM TAMAMLANDI"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
