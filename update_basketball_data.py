import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


# ============================================================
# AYARLAR
# ============================================================

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT = DATA_DIR / "basketball.json"

NBA_HISTORY_DAYS = 400
NBA_FUTURE_DAYS = 30

EUROLEAGUE_SEASONS = [
    "E2025",
    "E2026",
]

EUROLEAGUE_GAMES_URL = (
    "https://api-live.euroleague.net"
    "/v2/competitions/E/seasons/{season}/games"
)

EUROLEAGUE_BOXSCORE_URL = (
    "https://live.euroleague.net/api/Boxscore"
)

ESPN_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/basketball/nba/scoreboard"
)

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
# TAKIM ALIASLARI
# ============================================================

TEAM_ALIASES = {
    "fenerbahcetarfinistanbul": "fenerbahce",
    "fenerbahcebekoistanbul": "fenerbahce",
    "fenerbahceistanbul": "fenerbahce",
    "fenerbahce": "fenerbahce",

    "besiktasistanbul": "besiktas",
    "besiktasfibabankaistanbul": "besiktas",
    "besiktas": "besiktas",

    "realmadrid": "realmadrid",
    "realmadridbaloncesto": "realmadrid",

    "olympiacospiraeus": "olympiacos",
    "olympiacos": "olympiacos",

    "panathinaikosaktorathens": "panathinaikos",
    "panathinaikosathens": "panathinaikos",
    "panathinaikos": "panathinaikos",

    "armaniolimpiamilan": "olimpiamilano",
    "ea7emporioarmanimeilan": "olimpiamilano",
    "olimpiamilano": "olimpiamilano",
    "olimpiamilan": "olimpiamilano",
    "axarmaniexchangemilan": "olimpiamilano",
    "armanimilan": "olimpiamilano",

    "kosnerbaskoniavitoriagasteiz": "baskonia",
    "baskoniavitoriagasteiz": "baskonia",
    "cazoobaskonia": "baskonia",
    "bitcibaskonia": "baskonia",
    "baskonia": "baskonia",

    "fcbayernmunich": "bayernmunich",
    "bayernmunich": "bayernmunich",
    "bayernmunchen": "bayernmunich",

    "maccabirapydtelaviv": "maccabitelaviv",
    "maccabiplaykatelaviv": "maccabitelaviv",
    "maccabitelaviv": "maccabitelaviv",

    "hapoelibitelaviv": "hapoeltelaviv",
    "hapoeltelaviv": "hapoeltelaviv",

    "zalgiriskaunas": "zalgiris",
    "zalgiris": "zalgiris",

    "partizanmozartbetbelgrade": "partizan",
    "partizanbelgrade": "partizan",
    "partizan": "partizan",

    "valenciabasket": "valencia",
    "valencia": "valencia",

    "virtusbologna": "virtusbologna",
    "virtussegafredobologna": "virtusbologna",
    "virtus": "virtusbologna",

    "anadoluefesistanbul": "anadoluefes",
    "anadoluefes": "anadoluefes",

    "ldlcasvelvilleurbanne": "asvel",
    "asvelvilleurbanne": "asvel",
    "ldlcasvel": "asvel",
    "asvel": "asvel",

    "crvenazvezdameridianbetbelgrade": "crvenazvezda",
    "crvenazvezdabelgrade": "crvenazvezda",
    "crvenazvezda": "crvenazvezda",

    "dubaibasketball": "dubaibasketball",
    "dubai": "dubaibasketball",

    "londonlions": "londonlions",

    # NBA
    "losangeleslakers": "losangeleslakers",
    "lalakers": "losangeleslakers",
    "losangelesclippers": "losangelesclippers",
    "laclippers": "losangelesclippers",
    "goldenstatewarriors": "goldenstatewarriors",
    "oklahomacitythunder": "oklahomacitythunder",
    "sanantoniospurs": "sanantoniospurs",
    "newyorkknicks": "newyorkknicks",
    "brooklynnets": "brooklynnets",
    "bostonceltics": "bostonceltics",
    "miamiheat": "miamiheat",
    "chicagobulls": "chicagobulls",
    "clevelandcavaliers": "clevelandcavaliers",
    "milwaukeebucks": "milwaukeebucks",
    "indianapacers": "indianapacers",
    "detroitpistons": "detroitpistons",
    "torontoraptors": "torontoraptors",
    "atlantahawks": "atlantahawks",
    "charlottehornets": "charlottehornets",
    "orlandomagic": "orlandomagic",
    "washingtonwizards": "washingtonwizards",
    "philadelphia76ers": "philadelphia76ers",
    "denvernuggets": "denvernuggets",
    "phoenixsuns": "phoenixsuns",
    "sacramentokings": "sacramentokings",
    "portlandtrailblazers": "portlandtrailblazers",
    "utahjazz": "utahjazz",
    "minnesotatimberwolves": "minnesotatimberwolves",
    "dallasmavericks": "dallasmavericks",
    "houstonrockets": "houstonrockets",
    "memphisgrizzlies": "memphisgrizzlies",
    "neworleanspelicans": "neworleanspelicans",
}


# ============================================================
# NORMALİZASYON
# ============================================================

def normalize_team_name(name):

    if not name:
        return ""

    text = str(name).strip().lower()

    text = unicodedata.normalize(
        "NFKD",
        text
    )

    text = "".join(
        c
        for c in text
        if not unicodedata.combining(c)
    )

    removable = [
        "tarfin",
        "beko",
        "fibabanka",
        "playtika",
        "rapyd",
        "mozartbet",
        "meridianbet",
        "kosner",
        "cazoo",
        "bitci",
        "ea7",
        "emporio",
        "armani",
        "ldlc",
        "segafredo",
    ]

    for word in removable:
        text = text.replace(
            word,
            ""
        )

    text = re.sub(
        r"[^a-z0-9]",
        "",
        text
    )

    return TEAM_ALIASES.get(
        text,
        text
    )


# ============================================================
# YARDIMCILAR
# ============================================================

def safe_int(value):

    try:
        if value is None:
            return None

        return int(
            float(
                str(value).strip()
            )
        )

    except Exception:
        return None


def parse_date(value):

    if not value:
        return None

    try:

        text = str(value).strip()

        if text.endswith("Z"):
            text = (
                text[:-1]
                + "+00:00"
            )

        dt = datetime.fromisoformat(
            text
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except Exception:
        pass

    try:

        dt = datetime.strptime(
            str(value)[:10],
            "%Y-%m-%d"
        )

        return dt.replace(
            tzinfo=timezone.utc
        )

    except Exception:
        return None


def match_datetime(match):

    return (
        parse_date(
            match.get("utcDate")
        )
        or parse_date(
            match.get("date")
        )
    )


# ============================================================
# PERİYOT OBJESİ
# ============================================================

def empty_periods():

    return {
        "q1": {
            "scored": None,
            "conceded": None
        },
        "q2": {
            "scored": None,
            "conceded": None
        },
        "q3": {
            "scored": None,
            "conceded": None
        },
        "q4": {
            "scored": None,
            "conceded": None
        }
    }


def build_periods(
    home_values,
    away_values
):

    periods = empty_periods()

    count = min(
        len(home_values),
        len(away_values),
        4
    )

    for i in range(count):

        home_score = safe_int(
            home_values[i]
        )

        away_score = safe_int(
            away_values[i]
        )

        if (
            home_score is None
            or away_score is None
        ):
            continue

        key = f"q{i + 1}"

        periods[key] = {
            "scored": home_score,
            "conceded": away_score
        }

    return periods


# ============================================================
# ESPN PERİYOT
# ============================================================

def extract_espn_linescores(
    competitor
):

    linescores = (
        competitor.get(
            "linescores"
        )
        or []
    )

    values = []

    for item in linescores:

        value = (
            item.get("value")
        )

        if value is None:
            value = (
                item.get(
                    "displayValue"
                )
            )

        value = safe_int(
            value
        )

        if value is not None:
            values.append(
                value
            )

    return values


# ============================================================
# NBA
# ============================================================

def get_nba_day(date_value):

    date_text = date_value.strftime(
        "%Y%m%d"
    )

    try:

        response = requests.get(
            ESPN_URL,
            params={
                "dates": date_text,
                "limit": 100,
            },
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

    except Exception:
        return []

    matches = []

    for event in (
        data.get("events")
        or []
    ):

        competitions = (
            event.get(
                "competitions"
            )
            or []
        )

        if not competitions:
            continue

        competition = competitions[0]

        competitors = (
            competition.get(
                "competitors"
            )
            or []
        )

        home = None
        away = None

        for competitor in competitors:

            team = (
                competitor.get(
                    "team"
                )
                or {}
            )

            item = {
                "name": (
                    team.get(
                        "displayName"
                    )
                    or team.get(
                        "shortDisplayName"
                    )
                    or team.get("name")
                ),
                "score": safe_int(
                    competitor.get(
                        "score"
                    )
                ),
                "linescores": (
                    competitor.get(
                        "linescores"
                    )
                    or []
                )
            }

            if competitor.get(
                "homeAway"
            ) == "home":

                home = item

            elif competitor.get(
                "homeAway"
            ) == "away":

                away = item

        if not home or not away:
            continue

        status = (
            event.get("status")
            or {}
        )

        status_type = (
            status.get("type")
            or {}
        )

        played = bool(
            status_type.get(
                "completed"
            )
        ) or (
            str(
                status_type.get(
                    "state"
                )
                or ""
            ).lower()
            == "post"
        )

        home_score = (
            home["score"]
            if played
            else None
        )

        away_score = (
            away["score"]
            if played
            else None
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

        period_count = sum(
            1
            for q in periods.values()
            if q["scored"] is not None
        )

        has_period_data = (
            period_count >= 4
        )

        matches.append({

            "id": event.get("id"),

            "league": "NBA",

            "season": "2026-27",

            "date": event.get(
                "date"
            ),

            "utcDate": event.get(
                "date"
            ),

            "homeTeam": home["name"],

            "awayTeam": away["name"],

            "homeScore": home_score,

            "awayScore": away_score,

            "played": played,

            "hasPeriodData": (
                has_period_data
            ),

            "periods": periods,

            "status": (
                "finished"
                if played
                else "scheduled"
            )
        })

    return matches


def get_nba_games():

    print()
    print("=" * 60)
    print("🏀 NBA")
    print("=" * 60)

    today = datetime.now(
        timezone.utc
    ).date()

    start = (
        today
        - timedelta(
            days=NBA_HISTORY_DAYS
        )
    )

    end = (
        today
        + timedelta(
            days=NBA_FUTURE_DAYS
        )
    )

    print(
        f"📅 {start} → {end}"
    )

    all_matches = []

    current = start

    while current <= end:

        day_matches = get_nba_day(
            datetime.combine(
                current,
                datetime.min.time(),
                tzinfo=timezone.utc
            )
        )

        all_matches.extend(
            day_matches
        )

        current += timedelta(
            days=1
        )

    unique = {}

    for match in all_matches:

        key = (
            str(
                match.get("id")
            )
            if match.get("id")
            else
            f'{match.get("date")}:'
            f'{normalize_team_name(match.get("homeTeam"))}:'
            f'{normalize_team_name(match.get("awayTeam"))}'
        )

        unique[key] = match

    matches = list(
        unique.values()
    )

    print(
        f"✅ Toplam: {len(matches)}"
    )

    print(
        "🏁 Oynanan:",
        sum(
            1
            for x in matches
            if x.get("played")
        )
    )

    print(
        "⏱️ Periyot verili:",
        sum(
            1
            for x in matches
            if x.get(
                "hasPeriodData"
            )
        )
    )

    return matches


# ============================================================
# EUROLEAGUE BOXSCORE
# ============================================================

def get_euroleague_periods(
    season,
    game_code
):

    periods = empty_periods()

    if not game_code:
        return periods

    try:

        response = requests.get(
            EUROLEAGUE_BOXSCORE_URL,
            params={
                "gamecode": game_code,
                "seasoncode": season,
            },
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        data = response.json()

    except Exception:
        return periods

    # --------------------------------------------------------
    # Farklı API yapılarında ByQuarter aranır
    # --------------------------------------------------------

    by_quarter = (
        data.get(
            "ByQuarter"
        )
        or data.get(
            "byQuarter"
        )
        or data.get(
            "byquarter"
        )
    )

    if not by_quarter:
        return periods

    home_values = []
    away_values = []

    # Liste yapısı
    if isinstance(
        by_quarter,
        list
    ):

        for item in by_quarter:

            if not isinstance(
                item,
                dict
            ):
                continue

            home_value = (
                item.get("local")
                or item.get("home")
                or item.get("localScore")
                or item.get("homeScore")
            )

            away_value = (
                item.get("road")
                or item.get("away")
                or item.get("roadScore")
                or item.get("awayScore")
            )

            home_value = safe_int(
                home_value
            )

            away_value = safe_int(
                away_value
            )

            if (
                home_value is not None
                and away_value is not None
            ):

                home_values.append(
                    home_value
                )

                away_values.append(
                    away_value
                )

    # Dict yapısı
    elif isinstance(
        by_quarter,
        dict
    ):

        possible_keys = [
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
        ]

        for key in possible_keys:

            item = by_quarter.get(
                key
            )

            if not isinstance(
                item,
                dict
            ):
                continue

            home_value = (
                item.get("local")
                or item.get("home")
                or item.get("localScore")
                or item.get("homeScore")
            )

            away_value = (
                item.get("road")
                or item.get("away")
                or item.get("roadScore")
                or item.get("awayScore")
            )

            home_value = safe_int(
                home_value
            )

            away_value = safe_int(
                away_value
            )

            if (
                home_value is not None
                and away_value is not None
            ):

                home_values.append(
                    home_value
                )

                away_values.append(
                    away_value
                )

    return build_periods(
        home_values,
        away_values
    )


# ============================================================
# EUROLEAGUE
# ============================================================

def get_euroleague_games():

    print()
    print("=" * 60)
    print("🌍 EUROLEAGUE")
    print("=" * 60)

    all_matches = []

    for season in EUROLEAGUE_SEASONS:

        url = (
            EUROLEAGUE_GAMES_URL.format(
                season=season
            )
        )

        print(
            f"\n📅 {season}"
        )

        try:

            response = requests.get(
                url,
                headers=HEADERS,
                timeout=60
            )

            response.raise_for_status()

            data = response.json()

        except Exception as e:

            print(
                f"❌ {season}: {e}"
            )

            continue

        games = (
            data.get("data")
            if isinstance(
                data,
                dict
            )
            else data
        )

        if not isinstance(
            games,
            list
        ):
            games = []

        print(
            f"   Maç: {len(games)}"
        )

        for game in games:

            local = (
                game.get("local")
                or {}
            )

            road = (
                game.get("road")
                or {}
            )

            local_club = (
                local.get("club")
                or {}
            )

            road_club = (
                road.get("club")
                or {}
            )

            home_team = (
                local_club.get(
                    "name"
                )
                or local_club.get(
                    "abbreviatedName"
                )
            )

            away_team = (
                road_club.get(
                    "name"
                )
                or road_club.get(
                    "abbreviatedName"
                )
            )

            if not home_team or not away_team:
                continue

            played = bool(
                game.get("played")
            )

            home_score = (
                safe_int(
                    local.get("score")
                )
                if played
                else None
            )

            away_score = (
                safe_int(
                    road.get("score")
                )
                if played
                else None
            )

            periods = empty_periods()

            # gameCode per-game Boxscore için gereklidir
            game_code = (
                game.get("gameCode")
                or game.get("gamecode")
            )

            if played and game_code:

                periods = get_euroleague_periods(
                    season,
                    game_code
                )

            has_period_data = all(
                periods[q]["scored"] is not None
                for q in [
                    "q1",
                    "q2",
                    "q3",
                    "q4"
                ]
            )

            all_matches.append({

                "id": game.get("id"),

                "gameCode": game_code,

                "league": "EuroLeague",

                "season": season,

                "date": game.get(
                    "date"
                ),

                "utcDate": game.get(
                    "utcDate"
                ),

                "homeTeam": home_team,

                "awayTeam": away_team,

                "homeScore": home_score,

                "awayScore": away_score,

                "played": played,

                "hasPeriodData": (
                    has_period_data
                ),

                "periods": periods,

                "status": (
                    "finished"
                    if played
                    else "scheduled"
                )
            })

    unique = {}

    for match in all_matches:

        key = (
            f'{match.get("season")}:'
            f'{match.get("id") or match.get("gameCode")}'
        )

        unique[key] = match

    matches = list(
        unique.values()
    )

    print(
        f"✅ Toplam: {len(matches)}"
    )

    print(
        "🏁 Oynanan:",
        sum(
            1
            for x in matches
            if x.get("played")
        )
    )

    print(
        "⏱️ Periyot verili:",
        sum(
            1
            for x in matches
            if x.get(
                "hasPeriodData"
            )
        )
    )

    return matches


# ============================================================
# SON 5 EV
# ============================================================

def last_five_home(
    matches,
    team,
    before_date
):

    target = parse_date(
        before_date
    )

    if not target:
        return []

    normalized = normalize_team_name(
        team
    )

    previous = []

    for match in matches:

        if normalize_team_name(
            match.get("homeTeam")
        ) != normalized:
            continue

        if not match.get("played"):
            continue

        if match.get("homeScore") is None:
            continue

        if match.get("awayScore") is None:
            continue

        game_date = match_datetime(
            match
        )

        if not game_date or game_date >= target:
            continue

        previous.append(
            match
        )

    previous.sort(
        key=lambda x: (
            match_datetime(x)
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True
    )

    result = []

    for x in previous[:5]:

        periods = x.get(
            "periods"
        ) or empty_periods()

        result.append({

            "date": x.get("date"),

            "opponent": x.get(
                "awayTeam"
            ),

            "scored": x.get(
                "homeScore"
            ),

            "conceded": x.get(
                "awayScore"
            ),

            "periods": periods,

            "hasPeriodData": x.get(
                "hasPeriodData",
                False
            )
        })

    return result


# ============================================================
# SON 5 DEP
# ============================================================

def last_five_away(
    matches,
    team,
    before_date
):

    target = parse_date(
        before_date
    )

    if not target:
        return []

    normalized = normalize_team_name(
        team
    )

    previous = []

    for match in matches:

        if normalize_team_name(
            match.get("awayTeam")
        ) != normalized:
            continue

        if not match.get("played"):
            continue

        if match.get("homeScore") is None:
            continue

        if match.get("awayScore") is None:
            continue

        game_date = match_datetime(
            match
        )

        if not game_date or game_date >= target:
            continue

        previous.append(
            match
        )

    previous.sort(
        key=lambda x: (
            match_datetime(x)
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True
    )

    result = []

    for x in previous[:5]:

        periods = x.get(
            "periods"
        ) or empty_periods()

        result.append({

            "date": x.get("date"),

            "opponent": x.get(
                "homeTeam"
            ),

            "scored": x.get(
                "awayScore"
            ),

            "conceded": x.get(
                "homeScore"
            ),

            "periods": periods,

            "hasPeriodData": x.get(
                "hasPeriodData",
                False
            )
        })

    return result


# ============================================================
# SON 5 EKLE
# ============================================================

def add_last_five(matches):

    finished = [
        x
        for x in matches
        if (
            x.get("played")
            and x.get("homeScore") is not None
            and x.get("awayScore") is not None
        )
    ]

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


# ============================================================
# PERİYOT ÖZETİ
# ============================================================

def period_summary(matches):

    finished = [
        x
        for x in matches
        if x.get("played")
    ]

    with_periods = [
        x
        for x in finished
        if x.get(
            "hasPeriodData"
        )
    ]

    print()
    print("=" * 60)
    print("⏱️ PERİYOT VERİ KONTROLÜ")
    print("=" * 60)

    print(
        f"Tamamlanan maç: "
        f"{len(finished)}"
    )

    print(
        f"Periyot verisi olan: "
        f"{len(with_periods)}"
    )

    print(
        f"Periyot verisi olmayan: "
        f"{len(finished) - len(with_periods)}"
    )

    # İlk birkaç örnek
    for match in with_periods[:5]:

        periods = match.get(
            "periods"
        )

        print()
        print(
            f"{match.get('homeTeam')} - "
            f"{match.get('awayTeam')}"
        )

        print(
            "   "
            f"Q1: {periods['q1']['scored']}-"
            f"{periods['q1']['conceded']} | "
            f"Q2: {periods['q2']['scored']}-"
            f"{periods['q2']['conceded']} | "
            f"Q3: {periods['q3']['scored']}-"
            f"{periods['q3']['conceded']} | "
            f"Q4: {periods['q4']['scored']}-"
            f"{periods['q4']['conceded']}"
        )


# ============================================================
# ANA
# ============================================================

def main():

    print()
    print("=" * 65)
    print("🏀 NBA + EUROLEAGUE BASKETBOL VERİ SİSTEMİ")
    print("=" * 65)

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # KAYNAKLAR
    # --------------------------------------------------------

    euroleague = (
        get_euroleague_games()
    )

    nba = (
        get_nba_games()
    )

    matches = (
        euroleague
        + nba
    )

    # --------------------------------------------------------
    # DUPLICATE
    # --------------------------------------------------------

    unique = {}

    for match in matches:

        league = match.get(
            "league"
        )

        key = (
            f"{league}:"
            f"{match.get('id') or match.get('gameCode')}:"
            f"{match.get('date')}"
        )

        unique[key] = match

    matches = list(
        unique.values()
    )

    # --------------------------------------------------------
    # TARİH SIRASI
    # --------------------------------------------------------

    matches.sort(
        key=lambda x: (
            match_datetime(x)
            or datetime.max.replace(
                tzinfo=timezone.utc
            )
        )
    )

    # --------------------------------------------------------
    # SON 5
    # --------------------------------------------------------

    matches = add_last_five(
        matches
    )

    # --------------------------------------------------------
    # PERİYOT KONTROLÜ
    # --------------------------------------------------------

    period_summary(
        matches
    )

    # --------------------------------------------------------
    # ÖZET
    # --------------------------------------------------------

    upcoming = [
        x
        for x in matches
        if not x.get("played")
    ]

    full_5 = sum(
        1
        for x in upcoming
        if (
            len(
                x.get("homeLast5")
                or []
            ) == 5
            and
            len(
                x.get("awayLast5")
                or []
            ) == 5
        )
    )

    print()
    print("=" * 60)
    print("📊 GENEL ÖZET")
    print("=" * 60)

    print(
        f"Toplam maç: {len(matches)}"
    )

    print(
        f"Tamamlanan: "
        f"{sum(x.get('played', False) for x in matches)}"
    )

    print(
        f"Yaklaşan: {len(upcoming)}"
    )

    print(
        f"Yaklaşan 5/5: {full_5}"
    )

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    output = {

        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "total": len(matches),

        "nba": sum(
            1
            for x in matches
            if x.get("league") == "NBA"
        ),

        "nbaFinished": sum(
            1
            for x in matches
            if (
                x.get("league") == "NBA"
                and x.get("played")
            )
        ),

        "nbaPeriodData": sum(
            1
            for x in matches
            if (
                x.get("league") == "NBA"
                and x.get("hasPeriodData")
            )
        ),

        "euroleague": sum(
            1
            for x in matches
            if x.get("league") == "EuroLeague"
        ),

        "euroleagueFinished": sum(
            1
            for x in matches
            if (
                x.get("league") == "EuroLeague"
                and x.get("played")
            )
        ),

        "euroleaguePeriodData": sum(
            1
            for x in matches
            if (
                x.get("league") == "EuroLeague"
                and x.get("hasPeriodData")
            )
        ),

        "matches": matches,
    }

    with OUTPUT.open(
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
    print("=" * 65)
    print("✅ BASKETBOL VERİLERİ GÜNCELLENDİ")
    print("=" * 65)

    print(
        f"📁 {OUTPUT}"
    )


if __name__ == "__main__":
    main()
