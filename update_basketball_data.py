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
OUTPUT_FILE = DATA_DIR / "basketball.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)

NBA_HISTORY_DAYS = 180
NBA_FUTURE_DAYS = 30

EUROLEAGUE_SEASONS = [
    "E2025",
    "E2026",
]

EUROLEAGUE_PERIOD_SCAN_LIMIT = 250

REQUEST_TIMEOUT = 30
EURO_DELAY = 0.4

RETRY_DELAYS = [
    3,
    8,
    15,
    30,
]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}


session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def safe_int(value):
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        match = re.search(
            r"-?\d+",
            str(value)
        )

        if not match:
            return None

        return int(match.group())

    except Exception:
        return None


def parse_date(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ]

    try:
        return datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except Exception:
        pass

    for fmt in formats:
        try:
            return datetime.strptime(
                text,
                fmt
            )
        except Exception:
            pass

    return None


def match_datetime(game):
    keys = [
        "utcDate",
        "date",
        "startDate",
        "gameDate",
        "Date",
        "GameDate",
        "StartDate",
    ]

    for key in keys:
        value = game.get(key)

        dt = parse_date(value)

        if dt:
            return dt

    return None


def get_value(obj, *keys):
    if not isinstance(obj, dict):
        return None

    for key in keys:
        if key in obj and obj[key] is not None:
            return obj[key]

    lowered = {
        str(k).lower(): v
        for k, v in obj.items()
    }

    for key in keys:
        value = lowered.get(
            str(key).lower()
        )

        if value is not None:
            return value

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


def has_period_data(periods):
    if not isinstance(periods, dict):
        return False

    for quarter in ["q1", "q2", "q3", "q4"]:
        item = periods.get(quarter)

        if not isinstance(item, dict):
            continue

        if (
            item.get("scored") is not None
            and item.get("conceded") is not None
        ):
            return True

    return False


def build_periods(home_scores, away_scores):
    periods = empty_periods()

    count = min(
        len(home_scores),
        len(away_scores),
        4,
    )

    for i in range(count):
        home = safe_int(home_scores[i])
        away = safe_int(away_scores[i])

        if home is None or away is None:
            continue

        periods[f"q{i + 1}"] = {
            "scored": home,
            "conceded": away,
        }

    return periods


def sort_completed(games):
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


# ============================================================
# HTTP
# ============================================================

def get_json(url, params=None):
    last_error = None

    for attempt in range(5):
        try:
            response = session.get(
                url,
                params=params,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 429:
                if attempt >= len(RETRY_DELAYS):
                    break

                wait = RETRY_DELAYS[attempt]

                print(
                    f"   ⚠️ 429 → {wait} sn"
                )

                time.sleep(wait)
                continue

            response.raise_for_status()

            return response.json()

        except Exception as exc:
            last_error = exc

            if attempt >= len(RETRY_DELAYS):
                break

            wait = RETRY_DELAYS[attempt]

            print(
                f"   ⚠️ {exc} → {wait} sn"
            )

            time.sleep(wait)

    raise last_error


# ============================================================
# EUROLeague
# ============================================================

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


def extract_side(game, side):
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
        *keys
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
        "id",
        "Id",
    )

    home_name, home_score = extract_side(
        game,
        "home"
    )

    away_name, away_score = extract_side(
        game,
        "away"
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
            f"euroleague-{season_code}-"
            f"{game_code}"
        ),
        "sourceId": str(game_code),
        "gameCode": safe_int(game_code),
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


def get_euroleague_games_api(season_code):
    url = (
        "https://api-live.euroleague.net/"
        "v2/competitions/E/"
        f"seasons/{season_code}/games"
    )

    return get_json(url)


def get_euroleague_games_feed(season_code):
    url = (
        "https://feeds.incrowdsports.com/"
        "provider/euroleague-feeds/v2/"
        "competitions/E/"
        f"seasons/{season_code}/games"
    )

    return get_json(url)


def get_euroleague_games():
    print()
    print("=" * 60)
    print("🏀 EUROLEAGUE")
    print("=" * 60)

    all_games = []

    for season_code in EUROLEAGUE_SEASONS:
        print()
        print(f"📅 {season_code}")

        raw_games = []

        try:
            data = get_euroleague_games_api(
                season_code
            )

            raw_games = extract_games_list(data)

            print(
                f"   📡 api-live: {len(raw_games)}"
            )

        except Exception as exc:
            print(
                f"   ⚠️ api-live: {exc}"
            )

        if not raw_games:
            try:
                data = get_euroleague_games_feed(
                    season_code
                )

                raw_games = extract_games_list(data)

                print(
                    f"   📡 feeds: {len(raw_games)}"
                )

            except Exception as exc:
                print(
                    f"   ❌ feeds: {exc}"
                )

        season_games = []

        for raw in raw_games:
            game = normalize_euroleague_game(
                raw,
                season_code
            )

            if game:
                season_games.append(game)

        print(
            f"   ✅ Kullanılabilir: "
            f"{len(season_games)}"
        )

        all_games.extend(season_games)

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

            if home is not None and away is not None:
                home_scores.append(home)
                away_scores.append(away)

        if len(home_scores) >= 4:
            home_q = []
            away_q = []

            previous_home = 0
            previous_away = 0

            for i in range(4):
                home_q.append(
                    home_scores[i] - previous_home
                )

                away_q.append(
                    away_scores[i] - previous_away
                )

                previous_home = home_scores[i]
                previous_away = away_scores[i]

            periods = build_periods(
                home_q,
                away_q
            )

            if has_period_data(periods):
                return periods

    by_quarter = get_value(
        data,
        "ByQuarter",
        "byQuarter",
        "byquarter",
    )

    if isinstance(by_quarter, list):
        home_scores = []
        away_scores = []

        for item in by_quarter:
            if not isinstance(item, dict):
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

            if home is not None and away is not None:
                home_scores.append(home)
                away_scores.append(away)

        if len(home_scores) >= 4:
            periods = build_periods(
                home_scores[:4],
                away_scores[:4]
            )

            if has_period_data(periods):
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

    for attempt in range(5):
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
                if attempt >= len(RETRY_DELAYS):
                    return empty_periods()

                wait = RETRY_DELAYS[attempt]

                print(
                    f"   ⚠️ Boxscore 429 "
                    f"→ {wait} sn"
                )

                time.sleep(wait)
                continue

            response.raise_for_status()

            return extract_boxscore_periods(
                response.json()
            )

        except Exception as exc:
            if attempt >= len(RETRY_DELAYS):
                print(
                    f"   ⚠️ Boxscore "
                    f"{season_code}/{game_code}: "
                    f"{exc}"
                )

                return empty_periods()

            time.sleep(
                RETRY_DELAYS[attempt]
            )

    return empty_periods()


def add_euroleague_periods(games):
    print()
    print("=" * 60)
    print("⏱️ EUROLEAGUE PERİYOTLARI")
    print("=" * 60)

    completed = [
        g
        for g in games
        if g.get("played")
        and g.get("gameCode")
    ]

    completed.sort(
        key=lambda g: (
            match_datetime(g)
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True
    )

    scan_games = completed[
        :EUROLEAGUE_PERIOD_SCAN_LIMIT
    ]

    completed_count = len(completed)
    scan_count = len(scan_games)

    print(
        f"Tamamlanan: {completed_count}"
    )

    print(
        f"Periyot için taranacak: "
        f"{scan_count}"
    )

    found = 0

    for index, game in enumerate(
        scan_games,
        1
    ):
        periods = get_euroleague_periods(
            game.get("season"),
            game.get("gameCode")
        )

        if has_period_data(periods):
            game["periods"] = periods
            game["hasPeriodData"] = True
            found += 1

        if index % 25 == 0:
            print(
                f"   {index}/{scan_count} "
                f"→ {found} periyotlu"
            )

        time.sleep(EURO_DELAY)

    print()
    print(
        f"✅ Periyotlu: {found}"
    )

    return games


# ============================================================
# NBA
# ============================================================

def extract_espn_linescores(team):
    if not isinstance(team, dict):
        return []

    linescores = team.get("linescores")

    if not isinstance(linescores, list):
        return []

    result = []

    for item in linescores:
        if not isinstance(item, dict):
            continue

        value = safe_int(
            item.get("value")
        )

        if value is None:
            value = safe_int(
                item.get("displayValue")
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
        - timedelta(days=NBA_HISTORY_DAYS)
    )

    end_date = (
        today
        + timedelta(days=NBA_FUTURE_DAYS)
    )

    print(
        f"📅 {start_date} → {end_date}"
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
            "basketball/nba/"
            "scoreboard"
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

            current += timedelta(days=1)
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
                side = team.get("homeAway")

                if side == "home":
                    home = team

                elif side == "away":
                    away = team

            if not home or not away:
                continue

            home_team_data = home.get(
                "team",
                {}
            )

            away_team_data = away.get(
                "team",
                {}
            )

            home_team = (
                home_team_data.get(
                    "displayName"
                )
                or
                home_team_data.get(
                    "name"
                )
            )

            away_team = (
                away_team_data.get(
                    "displayName"
                )
                or
                away_team_data.get(
                    "name"
                )
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
                status == "STATUS_FINAL"
                and home_score is not None
                and away_score is not None
            )

            home_q = extract_espn_linescores(
                home
            )

            away_q = extract_espn_linescores(
                away
            )

            periods = build_periods(
                home_q,
                away_q
            )

            all_games.append({
                "id": f"nba-{event.get('id')}",
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
                "date": event.get("date"),
                "utcDate": event.get("date"),
                "homeTeam": home_team,
                "awayTeam": away_team,
                "homeScore": home_score,
                "awayScore": away_score,
                "played": played,
                "status": status,
                "hasPeriodData": has_period_data(
                    periods
                ),
                "periods": periods,
            })

        current += timedelta(days=1)

    total_count = len(all_games)

    played_count = sum(
        1
        for g in all_games
        if g.get("played")
    )

    period_count = sum(
        1
        for g in all_games
        if g.get("hasPeriodData")
    )

    print(
        f"✅ Toplam: {total_count}"
    )

    print(
        f"🏁 Oynanan: {played_count}"
    )

    print(
        f"⏱️ Periyotlu: {period_count}"
    )

    return all_games


# ============================================================
# SON 5 EV MAÇI
# ============================================================

def last_five_home(games, team):
    result = []

    for game in sort_completed(games):
        if game.get("homeTeam") != team:
            continue

        result.append({
            "date": game.get("date"),
            "opponent": game.get("awayTeam"),
            "scored": game.get("homeScore"),
            "conceded": game.get("awayScore"),
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
# SON 5 DEPLASMAN MAÇI
# ============================================================

def last_five_away(games, team):
    result = []

    for game in sort_completed(games):
        if game.get("awayTeam") != team:
            continue

        result.append({
            "date": game.get("date"),
            "opponent": game.get("homeTeam"),
            "scored": game.get("awayScore"),
            "conceded": game.get("homeScore"),
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


def add_last_five(games):
    completed = [
        g
        for g in games
        if g.get("played")
    ]

    for game in games:
        home_team = game.get(
            "homeTeam"
        )

        away_team = game.get(
            "awayTeam"
        )

        game["homeLast5"] = last_five_home(
            completed,
            home_team
        )

        game["awayLast5"] = last_five_away(
            completed,
            away_team
        )

    return games


# ============================================================
# KONTROL
# ============================================================

def print_period_summary(games):
    print()
    print("=" * 60)
    print("📊 PERİYOT KONTROLÜ")
    print("=" * 60)

    completed = [
        g
        for g in games
        if g.get("played")
    ]

    period_games = [
        g
        for g in completed
        if g.get("hasPeriodData")
    ]

    completed_count = len(completed)
    period_count = len(period_games)
    no_period_count = (
        completed_count
        - period_count
    )

    print(
        f"Tamamlanan: {completed_count}"
    )

    print(
        f"Periyotlu: {period_count}"
    )

    print(
        f"Periyotsuz: {no_period_count}"
    )

    for game in period_games[:3]:
        print()
        print(
            f"{game.get('homeTeam')} - "
            f"{game.get('awayTeam')}"
        )

        periods = game.get(
            "periods",
            {}
        )

        for quarter in [
            "q1",
            "q2",
            "q3",
            "q4",
        ]:
            item = periods.get(
                quarter,
                {}
            )

            print(
                f"   {quarter.upper()}: "
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
    # EUROLeague
    # --------------------------------------------------------

    euro_games = get_euroleague_games()

    euro_games = add_euroleague_periods(
        euro_games
    )

    # --------------------------------------------------------
    # NBA
    # --------------------------------------------------------

    nba_games = get_nba_games()

    # --------------------------------------------------------
    # BİRLEŞTİR
    # --------------------------------------------------------

    games = (
        euro_games
        + nba_games
    )

    # --------------------------------------------------------
    # TARİH SIRASI
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
    # KONTROL
    # --------------------------------------------------------

    print_period_summary(
        games
    )

    # --------------------------------------------------------
    # SAYILAR
    # --------------------------------------------------------

    total_count = len(games)

    played_count = sum(
        1
        for g in games
        if g.get("played")
    )

    period_count = sum(
        1
        for g in games
        if g.get("hasPeriodData")
    )

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    output = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": {
            "nba": "ESPN NBA Scoreboard",
            "euroleague": "EuroLeague API",
        },

        "settings": {
            "nbaHistoryDays": NBA_HISTORY_DAYS,
            "nbaFutureDays": NBA_FUTURE_DAYS,
            "euroleagueSeasons": (
                EUROLEAGUE_SEASONS
            ),
        },

        "totalMatches": total_count,
        "playedMatches": played_count,
        "periodMatches": period_count,

        "matches": games,
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2
        )

    print()
    print("=" * 60)
    print("✅ TAMAMLANDI")
    print("=" * 60)

    print(
        f"📁 {OUTPUT_FILE}"
    )

    print(
        f"🏀 Toplam: {total_count}"
    )

    print(
        f"🏁 Oynanan: {played_count}"
    )

    print(
        f"⏱️ Periyotlu: {period_count}"
    )


if __name__ == "__main__":
    main()
