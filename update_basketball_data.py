import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


# ============================================================
# AYARLAR
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = DATA_DIR / "basketball.json"

# ------------------------------------------------------------
# GEÇMİŞ / GELECEK
# ------------------------------------------------------------

NBA_HISTORY_DAYS = 180
NBA_FUTURE_DAYS = 30

EUROLEAGUE_HISTORY_DAYS = 120
EUROLEAGUE_FUTURE_DAYS = 30

# ------------------------------------------------------------
# HTTP
# ------------------------------------------------------------

REQUEST_TIMEOUT = 30

EURO_LIVE_DELAY = 0.40

EURO_RETRY_DELAYS = [
    3,
    8,
    15,
    30,
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}

EUROLEAGUE_SEASONS = [
    "E2025",
    "E2026",
]


# ============================================================
# TAKIM ALIAS
# ============================================================

TEAM_ALIASES = {
    "real madrid": "real madrid",
    "real madrid baloncesto": "real madrid",

    "barcelona": "barcelona",
    "fc barcelona": "barcelona",

    "olympiacos": "olympiacos",
    "olympiacos piraeus": "olympiacos",

    "panathinaikos": "panathinaikos",
    "panathinaikos bc": "panathinaikos",

    "fenerbahce": "fenerbahce",
    "fenerbahce beko": "fenerbahce",

    "anadolu efes": "anadolu efes",
    "efes": "anadolu efes",

    "maccabi tel aviv": "maccabi tel aviv",
    "maccabi playtika tel aviv": "maccabi tel aviv",

    "partizan": "partizan",
    "partizan belgrade": "partizan",

    "crvena zvezda": "crvena zvezda",
    "red star": "crvena zvezda",

    "bayern munich": "bayern munich",
    "fc bayern munich": "bayern munich",

    "asvel": "asvel",
    "lyon villeurbanne": "asvel",
    "ldlc asvel": "asvel",

    "monaco": "monaco",
    "as monaco": "monaco",

    "zalgiris": "zalgiris",
    "zalgiris kaunas": "zalgiris",

    "virtus bologna": "virtus bologna",
    "virtus segafredo bologna": "virtus bologna",

    "olimpia milano": "olimpia milano",
    "ea7 milan": "olimpia milano",
    "armani milan": "olimpia milano",

    "baskonia": "baskonia",
    "baskonia vitoria": "baskonia",

    "paris basketball": "paris basketball",
    "paris": "paris basketball",

    "valencia basket": "valencia",
    "valencia": "valencia",

    "dubai basketball": "dubai",
    "dubai": "dubai",

    "gran canaria": "gran canaria",
}


# ============================================================
# SESSION
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# YARDIMCILAR
# ============================================================

def safe_int(value):
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        text = str(value).strip()

        if not text:
            return None

        match = re.search(r"-?\d+", text)

        if not match:
            return None

        return int(match.group())
    except Exception:
        return None


def normalize_team_name(name):
    if not name:
        return ""

    text = str(name).lower().strip()

    replacements = {
        "ı": "i",
        "ş": "s",
        "ğ": "g",
        "ü": "u",
        "ö": "o",
        "ç": "c",
    }

    for a, b in replacements.items():
        text = text.replace(a, b)

    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return TEAM_ALIASES.get(
        text,
        text,
    )


def parse_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except Exception:
        pass

    formats = [
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                text,
                fmt,
            )
        except Exception:
            continue

    return None


def match_datetime(match):
    for key in [
        "utcDate",
        "date",
        "startDate",
        "gameDate",
        "Date",
    ]:
        value = match.get(key)

        dt = parse_date(value)

        if dt:
            return dt

    return None


def empty_periods():
    return {
        "q1": {
            "scored": None,
            "conceded": None,
        },
        "q2": {
            "scored": None,
            "conceded": None,
        },
        "q3": {
            "scored": None,
            "conceded": None,
        },
        "q4": {
            "scored": None,
            "conceded": None,
        },
    }


def build_periods(home_scores, away_scores):
    periods = empty_periods()

    if not home_scores or not away_scores:
        return periods

    count = min(
        len(home_scores),
        len(away_scores),
        4,
    )

    for i in range(count):
        hs = safe_int(home_scores[i])
        aws = safe_int(away_scores[i])

        if hs is None or aws is None:
            continue

        periods[f"q{i + 1}"] = {
            "scored": hs,
            "conceded": aws,
        }

    return periods


def has_period_data(periods):
    if not isinstance(periods, dict):
        return False

    for q in [
        "q1",
        "q2",
        "q3",
        "q4",
    ]:
        item = periods.get(q)

        if not isinstance(item, dict):
            continue

        if (
            item.get("scored") is not None
            and item.get("conceded") is not None
        ):
            return True

    return False


def get_value(obj, *keys):
    if not isinstance(obj, dict):
        return None

    for key in keys:
        if key in obj:
            value = obj[key]

            if value is not None:
                return value

    lower_map = {
        str(k).lower(): v
        for k, v in obj.items()
    }

    for key in keys:
        value = lower_map.get(
            str(key).lower()
        )

        if value is not None:
            return value

    return None


# ============================================================
# HTTP JSON
# ============================================================

def get_json(
    url,
    params=None,
    retries=4,
):
    last_error = None

    for attempt in range(retries):

        try:

            response = session.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 429:

                wait = EURO_RETRY_DELAYS[
                    min(
                        attempt,
                        len(EURO_RETRY_DELAYS) - 1,
                    )
                ]

                print(
                    f"   ⚠️ 429 → "
                    f"{wait} sn bekleniyor..."
                )

                time.sleep(wait)

                continue

            response.raise_for_status()

            return response.json()

        except Exception as exc:

            last_error = exc

            if attempt < retries - 1:

                wait = 2 * (
                    attempt + 1
                )

                print(
                    f"   ⚠️ İstek hatası: "
                    f"{exc}"
                )

                time.sleep(wait)

    raise last_error


# ============================================================
# EUROLeague
# ============================================================

def extract_team_name(obj):
    if not isinstance(obj, dict):
        return None

    value = get_value(
        obj,
        "name",
        "Name",
        "teamName",
        "TeamName",
        "clubPermanentName",
        "ClubPermanentName",
        "shortName",
        "ShortName",
    )

    if isinstance(value, dict):
        return extract_team_name(value)

    if value:
        return str(value)

    return None


def extract_score(obj):
    if not isinstance(obj, dict):
        return None

    value = get_value(
        obj,
        "score",
        "Score",
        "points",
        "Points",
        "total",
        "Total",
    )

    if isinstance(value, dict):
        value = get_value(
            value,
            "score",
            "Score",
            "points",
            "Points",
            "total",
            "Total",
        )

    return safe_int(value)


def extract_team_side(game, side):

    if side == "home":
        keys = [
            "home",
            "Home",
            "local",
            "Local",
            "homeTeam",
            "HomeTeam",
        ]
    else:
        keys = [
            "away",
            "Away",
            "road",
            "Road",
            "awayTeam",
            "AwayTeam",
        ]

    value = get_value(
        game,
        *keys,
    )

    if isinstance(value, dict):

        return (
            extract_team_name(value),
            extract_score(value),
        )

    return None, None


def normalize_euroleague_game(
    game,
    season_code,
):
    if not isinstance(game, dict):
        return None

    game_code = get_value(
        game,
        "code",
        "Code",
        "gameCode",
        "GameCode",
    )

    if game_code is None:
        game_code = get_value(
            game,
            "id",
            "Id",
        )

    home_name, home_score = (
        extract_team_side(
            game,
            "home",
        )
    )

    away_name, away_score = (
        extract_team_side(
            game,
            "away",
        )
    )

    if not home_name:

        home_name = get_value(
            game,
            "homeName",
            "HomeName",
            "localName",
            "LocalName",
        )

    if not away_name:

        away_name = get_value(
            game,
            "awayName",
            "AwayName",
            "roadName",
            "RoadName",
        )

    if home_score is None:

        home_score = safe_int(
            get_value(
                game,
                "homeScore",
                "HomeScore",
                "localScore",
                "LocalScore",
            )
        )

    if away_score is None:

        away_score = safe_int(
            get_value(
                game,
                "awayScore",
                "AwayScore",
                "roadScore",
                "RoadScore",
            )
        )

    if not home_name or not away_name:
        return None

    game_id = str(
        get_value(
            game,
            "id",
            "Id",
        )
        or game_code
    )

    date_value = get_value(
        game,
        "date",
        "Date",
        "gameDate",
        "GameDate",
        "startDate",
        "StartDate",
    )

    utc_date = get_value(
        game,
        "utcDate",
        "UtcDate",
        "startDate",
        "StartDate",
        "date",
        "Date",
    )

    status = get_value(
        game,
        "status",
        "Status",
        "gameStatus",
        "GameStatus",
    )

    played = (
        home_score is not None
        and away_score is not None
    )

    return {
        "id": (
            f"euroleague-"
            f"{season_code}-"
            f"{game_id}"
        ),
        "sourceId": game_id,
        "gameCode": safe_int(
            game_code
        ),
        "league": "EuroLeague",
        "season": season_code,
        "date": date_value,
        "utcDate": utc_date,
        "homeTeam": str(home_name),
        "awayTeam": str(away_name),
        "homeScore": home_score,
        "awayScore": away_score,
        "played": played,
        "status": status,
        "hasPeriodData": False,
        "periods": empty_periods(),
    }


def get_euroleague_games_api(
    season_code,
):
    url = (
        "https://api-live.euroleague.net/"
        "v2/competitions/E/"
        f"seasons/{season_code}/games"
    )

    return get_json(
        url,
        retries=4,
    )


def get_euroleague_games_feed(
    season_code,
):
    url = (
        "https://feeds.incrowdsports.com/"
        "provider/euroleague-feeds/v2/"
        "competitions/E/"
        f"seasons/{season_code}/games"
    )

    return get_json(
        url,
        retries=4,
    )


def extract_games_list(data):

    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        return []

    for key in [
        "data",
        "games",
        "Games",
        "items",
        "Items",
    ]:

        value = data.get(key)

        if isinstance(value, list):
            return value

    return []


def get_euroleague_games():

    print()
    print("=" * 60)
    print("🏀 EUROLEAGUE")
    print("=" * 60)

    now = datetime.now(
        timezone.utc
    )

    min_date = now - timedelta(
        days=EUROLEAGUE_HISTORY_DAYS
    )

    max_date = now + timedelta(
        days=EUROLEAGUE_FUTURE_DAYS
    )

    print(
        f"📅 {min_date.date()} → "
        f"{max_date.date()}"
    )

    all_games = []

    for season_code in EUROLEAGUE_SEASONS:

        print()
        print(
            f"📅 {season_code}"
        )

        raw_games = []

        # ----------------------------------------------------
        # API
        # ----------------------------------------------------

        try:

            data = get_euroleague_games_api(
                season_code
            )

            raw_games = extract_games_list(
                data
            )

            print(
                f"   📡 api-live: "
                f"{len(raw_games)}"
            )

        except Exception as exc:

            print(
                f"   ⚠️ api-live: "
                f"{exc}"
            )

        # ----------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------

        if not raw_games:

            try:

                data = get_euroleague_games_feed(
                    season_code
                )

                raw_games = extract_games_list(
                    data
                )

                print(
                    f"   📡 feeds: "
                    f"{len(raw_games)}"
                )

            except Exception as exc:

                print(
                    f"   ❌ feeds: "
                    f"{exc}"
                )

        season_games = []

        for raw in raw_games:

            game = normalize_euroleague_game(
                raw,
                season_code,
            )

            if not game:
                continue

            dt = match_datetime(
                game
            )

            if dt:

                if (
                    dt < min_date
                    or dt > max_date
                ):
                    continue

            season_games.append(
                game
            )

        print(
            f"   ✅ Kullanılabilir: "
            f"{len(season_games)}"
        )

        all_games.extend(
            season_games
        )

    print()
    print(
        f"🏀 EuroLeague toplam: "
        f"{len(all_games)}"
    )

    return all_games


# ============================================================
# EUROLeague BOXSCORE
# ============================================================

def extract_boxscore_periods(data):

    if not isinstance(data, dict):
        return empty_periods()

    # --------------------------------------------------------
    # EndOfQuarter
    # --------------------------------------------------------

    end_q = get_value(
        data,
        "EndOfQuarter",
        "endOfQuarter",
    )

    if isinstance(end_q, list):

        home_scores = []
        away_scores = []

        for item in end_q:

            if not isinstance(item, dict):
                continue

            home = safe_int(
                get_value(
                    item,
                    "HomeScore",
                    "homeScore",
                    "LocalScore",
                    "localScore",
                    "Home",
                    "home",
                    "Local",
                    "local",
                )
            )

            away = safe_int(
                get_value(
                    item,
                    "AwayScore",
                    "awayScore",
                    "RoadScore",
                    "roadScore",
                    "Away",
                    "away",
                    "Road",
                    "road",
                )
            )

            if (
                home is not None
                and away is not None
            ):

                home_scores.append(
                    home
                )

                away_scores.append(
                    away
                )

        if (
            len(home_scores) >= 4
            and len(away_scores) >= 4
        ):

            qh = []
            qa = []

            prev_h = 0
            prev_a = 0

            for i in range(4):

                qh.append(
                    home_scores[i]
                    - prev_h
                )

                qa.append(
                    away_scores[i]
                    - prev_a
                )

                prev_h = home_scores[i]
                prev_a = away_scores[i]

            periods = build_periods(
                qh,
                qa,
            )

            if has_period_data(
                periods
            ):
                return periods

    # --------------------------------------------------------
    # ByQuarter
    # --------------------------------------------------------

    by_quarter = get_value(
        data,
        "ByQuarter",
        "byQuarter",
        "byquarter",
    )

    if isinstance(
        by_quarter,
        list,
    ):

        home_scores = []
        away_scores = []

        for item in by_quarter:

            if not isinstance(
                item,
                dict,
            ):
                continue

            home = safe_int(
                get_value(
                    item,
                    "Home",
                    "home",
                    "Local",
                    "local",
                    "HomeScore",
                    "homeScore",
                    "LocalScore",
                    "localScore",
                )
            )

            away = safe_int(
                get_value(
                    item,
                    "Away",
                    "away",
                    "Road",
                    "road",
                    "AwayScore",
                    "awayScore",
                    "RoadScore",
                    "roadScore",
                )
            )

            if (
                home is not None
                and away is not None
            ):

                home_scores.append(
                    home
                )

                away_scores.append(
                    away
                )

        if len(home_scores) >= 4:

            periods = build_periods(
                home_scores[:4],
                away_scores[:4],
            )

            if has_period_data(
                periods
            ):
                return periods

    return empty_periods()


def get_euroleague_periods(
    season_code,
    game_code,
):

    if not game_code:
        return empty_periods()

    url = (
        "https://live.euroleague.net/"
        "api/Boxscore"
    )

    for attempt in range(
        len(EURO_RETRY_DELAYS) + 1
    ):

        try:

            response = session.get(
                url,
                params={
                    "gamecode": game_code,
                    "seasoncode": season_code,
                },
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 429:

                if (
                    attempt
                    >= len(EURO_RETRY_DELAYS)
                ):
                    return empty_periods()

                wait = EURO_RETRY_DELAYS[
                    attempt
                ]

                print(
                    f"   ⚠️ Boxscore 429 "
                    f"→ {wait} sn"
                )

                time.sleep(wait)

                continue

            response.raise_for_status()

            data = response.json()

            return extract_boxscore_periods(
                data
            )

        except Exception as exc:

            if (
                attempt
                >= len(EURO_RETRY_DELAYS)
            ):

                print(
                    f"   ⚠️ Boxscore: "
                    f"{season_code}/"
                    f"{game_code} "
                    f"{exc}"
                )

                return empty_periods()

            wait = EURO_RETRY_DELAYS[
                attempt
            ]

            time.sleep(wait)

    return empty_periods()


# ============================================================
# SADECE İHTİYAÇ OLAN EUROLeague BOXSCORE'LARI
# ============================================================

def add_euroleague_periods(
    games
):

    print()
    print("=" * 60)
    print(
        "⏱️ EUROLEAGUE PERİYOTLARI"
    )
    print("=" * 60)

    completed = [
        g
        for g in games
        if g.get("played")
        and g.get("gameCode")
    ]

    # En yeni maçlardan başla.
    completed.sort(
        key=lambda g: (
            match_datetime(g)
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # Burada bütün geçmiş maçları istemiyoruz.
    #
    # Her takımın son 5 ev/deplasmanını oluşturabilmek
    # için en yeni maçlardan sınırlı sayıda Boxscore
    # yeterli olacaktır.
    #
    # EuroLeague'de takım başına yaklaşık 5-8 maç
    # tampon bırakıyoruz.
    # --------------------------------------------------------

    target_games = completed[
        :250
    ]

    print(
        f"Tamamlanan: "
        f"{len(completed)}"
    )

    print(
        f"Periyot için taranacak: "
        f"{len(target_games)}"
    )

    found = 0

    for index, game in enumerate(
        target_games,
        1,
    ):

        if game.get(
            "hasPeriodData"
        ):
            found += 1
            continue

        periods = get_euroleague_periods(
            game.get("season"),
            game.get("gameCode"),
        )

        if has_period_data(
            periods
        ):

            game["periods"] = periods
            game["hasPeriodData"] = True

            found += 1

        if index % 25 == 0:

            print(
                f"   {index}/"
                f"{len(target_games)} "
                f"→ {found} periyotlu"
            )

        time.sleep(
            EURO_LIVE_DELAY
        )

    print()
    print(
        f"✅ Periyotlu: "
        f"{found}"
    )

    return games


# ============================================================
# NBA
# ============================================================

def extract_espn_linescores(
    team_data
):

    if not isinstance(
        team_data,
        dict,
    ):
        return []

    linescores = team_data.get(
        "linescores"
    )

    if not isinstance(
        linescores,
        list,
    ):
        return []

    result = []

    for item in linescores:

        if not isinstance(
            item,
            dict,
        ):
            continue

        value = safe_int(
            item.get("value")
        )

        if value is None:

            value = safe_int(
                item.get(
                    "displayValue"
                )
            )

        if value is not None:
            result.append(value)

    return result


def get_nba_games():

    print()
    print("=" * 60)
    print("🏀 NBA")
    print("=" * 60)

    today = datetime.now(
        timezone.utc
    ).date()

    start_date = (
        today
        - timedelta(
            days=NBA_HISTORY_DAYS
        )
    )

    end_date = (
        today
        + timedelta(
            days=NBA_FUTURE_DAYS
        )
    )

    print(
        f"📅 {start_date} → "
        f"{end_date}"
    )

    all_games = []

    current = start_date

    while current <= end_date:

        date_string = current.strftime(
            "%Y%m%d"
        )

        url = (
            "https://site.api.espn.com/"
            "apis/site/v2/sports/"
            "basketball/nba/scoreboard"
        )

        try:

            response = session.get(
                url,
                params={
                    "dates": date_string
                },
                timeout=REQUEST_TIMEOUT,
            )

            response.raise_for_status()

            data = response.json()

        except Exception as exc:

            print(
                f"   ⚠️ {date_string}: "
                f"{exc}"
            )

            current += timedelta(
                days=1
            )

            continue

        events = data.get(
            "events",
            []
        )

        for event in events:

            competitions = event.get(
                "competitions",
                []
            )

            if not competitions:
                continue

            competition = competitions[0]

            competitors = competition.get(
                "competitors",
                []
            )

            if len(competitors) < 2:
                continue

            home = None
            away = None

            for team in competitors:

                if (
                    team.get("homeAway")
                    == "home"
                ):
                    home = team

                elif (
                    team.get("homeAway")
                    == "away"
                ):
                    away = team

            if not home or not away:
                continue

            home_team = (
                home
                .get("team", {})
                .get("displayName")
                or home
                .get("team", {})
                .get("name")
            )

            away_team = (
                away
                .get("team", {})
                .get("displayName")
                or away
                .get("team", {})
                .get("name")
            )

            home_score = safe_int(
                home.get("score")
            )

            away_score = safe_int(
                away.get("score")
            )

            status = (
                event
                .get("status", {})
                .get("type", {})
                .get("name")
            )

            played = (
                status
                == "STATUS_FINAL"
                and home_score is not None
                and away_score is not None
            )

            home_q = (
                extract_espn_linescores(
                    home
                )
            )

            away_q = (
                extract_espn_linescores(
                    away
                )
            )

            periods = build_periods(
                home_q,
                away_q,
            )

            all_games.append({
                "id": (
                    f"nba-"
                    f"{event.get('id')}"
                ),
                "sourceId": str(
                    event.get("id")
                ),
                "gameCode": None,
                "league": "NBA",
                "season": (
                    event
                    .get("season", {})
                    .get("slug")
                ),
                "date": event.get(
                    "date"
                ),
                "utcDate": event.get(
                    "date"
                ),
                "homeTeam": home_team,
                "awayTeam": away_team,
                "homeScore": home_score,
                "awayScore": away_score,
                "played": played,
                "status": status,
                "hasPeriodData": (
                    has_period_data(
                        periods
                    )
                ),
                "periods": periods,
            })

        current += timedelta(
            days=1
        )

    print(
        f"✅ Toplam: "
        f"{len(all_games)}"
    )

    print(
        f"🏁 Oynanan: "
        f"{sum(1 for g in all_games if g.get('played'))}"
    )

    print(
        f"⏱️ Periyotlu: "
        f"{sum(1 for g in all_games if g.get('hasPeriodData'))}"
    )

    return all_games


# ============================================================
# SON 5 EV
# ============================================================

def sort_completed(
    games
):

    return sorted(
        [
            g
            for g in games
            if g.get("played")
        ],
        key=lambda g: (
            match_datetime(g)
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True,
    )


def last_five_home(
    games,
    team,
):

    target = normalize_team_name(
        team
    )

    result = []

    for game in sort_completed(
        games
    ):

        if normalize_team_name(
            game.get("homeTeam")
        ) != target:
            continue

        result.append({
            "date": game.get(
                "date"
            ),
            "opponent": game.get(
                "awayTeam"
            ),
            "scored": game.get(
                "homeScore"
            ),
            "conceded": game.get(
                "awayScore"
            ),
            "periods": game.get(
                "periods",
                empty_periods()
            ),
            "hasPeriodData": game.get(
                "hasPeriodData",
                False
            ),
        })

        if len(result) >= 5:
            break

    return result


# ============================================================
# SON 5 DEPLASMAN
# ============================================================

def last_five_away(
    games,
    team,
):

    target = normalize_team_name(
        team
    )

    result = []

    for game in sort_completed(
        games
    ):

        if normalize_team_name(
            game.get("awayTeam")
        ) != target:
            continue

        result.append({
            "date": game.get(
                "date"
            ),
            "opponent": game.get(
                "homeTeam"
            ),
            "scored": game.get(
                "awayScore"
            ),
            "conceded": game.get(
                "homeScore"
            ),
            "periods": game.get(
                "periods",
                empty_periods()
            ),
            "hasPeriodData": game.get(
                "hasPeriodData",
                False
            ),
        })

        if len(result) >= 5:
            break

    return result


# ============================================================
# SON 5'İ EKLE
# ============================================================

def add_last_five(
    games
):

    completed = [
        g
        for g in games
        if g.get("played")
    ]

    for game in games:

        game["homeLast5"] = (
            last_five_home(
                completed,
                game.get(
                    "homeTeam"
                ),
            )
        )

        game["awayLast5"] = (
            last_five_away(
                completed,
                game.get(
                    "awayTeam"
                ),
            )
        )

    return games


# ============================================================
# ÖZET
# ============================================================

def print_summary(
    games
):

    completed = [
        g
        for g in games
        if g.get("played")
    ]

    periods = [
        g
        for g in completed
        if g.get("hasPeriodData")
    ]

    print()
    print("=" * 60)
    print(
        "📊 PERİYOT KONTROLÜ"
    )
    print("=" * 60)

    print(
        f"Tamamlanan: "
        f"{len(completed)}"
    )

    print(
        f"Periyotlu: "
        f"{len(periods)}"
    )

    print(
        f"Periyotsuz: "
        f"{len(completed) - len(periods)}"
    )

    print()

    for game in periods[:3]:

        p = game.get(
            "periods",
            {}
        )

        print(
            f"{game.get('homeTeam')} - "
            f"{game.get('awayTeam')}"
        )

        for q in [
            "q1",
            "q2",
            "q3",
            "q4",
        ]:

            item = p.get(
                q,
                {}
            )

            print(
                f"   {q.upper()}: "
                f"{item.get('scored')}-"
                f"{item.get('conceded')}"
            )


# ============================================================
# ANA
# ============================================================

def main():

    print()
    print("=" * 60)
    print(
        "🏀 NBA + EUROLEAGUE "
        "BASKETBOL VERİ GÜNCELLEME"
    )
    print("=" * 60)

    print(
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    # --------------------------------------------------------
    # EUROLEAGUE
    # --------------------------------------------------------

    euro_games = (
        get_euroleague_games()
    )

    euro_games = (
        add_euroleague_periods(
            euro_games
        )
    )

    # --------------------------------------------------------
    # NBA
    # --------------------------------------------------------

    nba_games = (
        get_nba_games()
    )

    # --------------------------------------------------------
    # BİRLEŞTİR
    # --------------------------------------------------------

    games = (
        euro_games
        + nba_games
    )

    # --------------------------------------------------------
    # SIRALA
    # --------------------------------------------------------

    games.sort(
        key=lambda g: (
            match_datetime(g)
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        )
    )

    # --------------------------------------------------------
    # SON 5
    # --------------------------------------------------------

    games = add_last_five(
        games
    )

    # --------------------------------------------------------
    # ÖZET
    # --------------------------------------------------------

    print_summary(
        games
    )

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    output = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": {
            "nba": (
                "ESPN NBA Scoreboard"
            ),
            "euroleague": (
                "EuroLeague API"
            ),
        },

        "settings": {
            "nbaHistoryDays": (
                NBA_HISTORY_DAYS
            ),
            "nbaFutureDays": (
                NBA_FUTURE_DAYS
            ),
            "euroleagueHistoryDays": (
                EUROLEAGUE_HISTORY_DAYS
            ),
            "euroleagueFutureDays": (
                EUROLEAGUE_FUTURE_DAYS
            ),
        },

        "totalMatches": len(
            games
        ),

        "playedMatches": sum(
            1
            for g in games
            if g.get("played")
        ),

        "periodMatches": sum(
            1
            for g in games
            if g.get(
                "hasPeriodData"
            )
        ),

        "matches": games,
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("=" * 60)
    print("✅ TAMAMLANDI")
    print("=" * 60)

    print(
        f"📁 {OUTPUT_FILE}"
    )

    print(
        f"🏀 Toplam: "
        f"{len(games)}"
    )

    print(
        f"🏁 Oynanan: "
        f"{sum(1 for g in games if g.get('played'))}"
    )

    print(
        f"⏱️ Periyotlu: "
        f"{sum(1 for g in games if g.get('hasPeriodData'))}"
    )


if __name__ == "__main__":
    main()
