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
    "E2026",
    "E2025",
]

EUROLEAGUE_BASE_URL = (
    "https://api-live.euroleague.net"
    "/v2/competitions/E/seasons"
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
# TAKIM İSİM NORMALİZASYONU
# ============================================================

TEAM_ALIASES = {
    # FENERBAHÇE
    "fenerbahcetarfinistanbul": "fenerbahce",
    "fenerbahcebekoistanbul": "fenerbahce",
    "fenerbahceistanbul": "fenerbahce",
    "fenerbahce": "fenerbahce",

    # BEŞİKTAŞ
    "besiktasistanbul": "besiktas",
    "besiktasfibabankaistanbul": "besiktas",
    "besiktas": "besiktas",

    # REAL MADRID
    "realmadrid": "realmadrid",
    "realmadridbaloncesto": "realmadrid",

    # OLYMPIACOS
    "olympiacospiraeus": "olympiacos",
    "olympiacos": "olympiacos",

    # PANATHINAIKOS
    "panathinaikosaktorathens": "panathinaikos",
    "panathinaikosathens": "panathinaikos",
    "panathinaikos": "panathinaikos",

    # MILANO
    "armaniolimpiamilan": "olimpiamilano",
    "ea7emporioarmanimeilan": "olimpiamilano",
    "olimpiamilano": "olimpiamilano",
    "olimpiamilan": "olimpiamilano",
    "axarmaniexchangemilan": "olimpiamilano",
    "armanimilan": "olimpiamilano",

    # BASKONIA
    "kosnerbaskoniavitoriagasteiz": "baskonia",
    "baskoniavitoriagasteiz": "baskonia",
    "cazoobaskonia": "baskonia",
    "bitcibaskonia": "baskonia",
    "baskonia": "baskonia",

    # BAYERN
    "fcbayernmunich": "bayernmunich",
    "bayernmunich": "bayernmunich",
    "bayernmunchen": "bayernmunich",

    # MACCABI
    "maccabirapydtelaviv": "maccabitelaviv",
    "maccabiplaykatelaviv": "maccabitelaviv",
    "maccabitelaviv": "maccabitelaviv",

    # HAPOEL
    "hapoelibitelaviv": "hapoeltelaviv",
    "hapoeltelaviv": "hapoeltelaviv",
    "hapoel": "hapoeltelaviv",

    # ZALGIRIS
    "zalgiriskaunas": "zalgiris",
    "zalgiris": "zalgiris",

    # PARTIZAN
    "partizanmozartbetbelgrade": "partizan",
    "partizanbelgrade": "partizan",
    "partizan": "partizan",

    # VALENCIA
    "valenciabasket": "valencia",
    "valencia": "valencia",

    # VIRTUS
    "virtusbologna": "virtusbologna",
    "virtussegafredobologna": "virtusbologna",
    "virtus": "virtusbologna",

    # EFES
    "anadoluefesistanbul": "anadoluefes",
    "anadoluefes": "anadoluefes",

    # ASVEL
    "ldlcasvelvilleurbanne": "asvel",
    "asvelvilleurbanne": "asvel",
    "ldlcasvel": "asvel",
    "asvel": "asvel",

    # CRVENA ZVEZDA
    "crvenazvezdameridianbetbelgrade": "crvenazvezda",
    "crvenazvezdabelgrade": "crvenazvezda",
    "crvenazvezda": "crvenazvezda",

    # DUBAI
    "dubaibasketball": "dubaibasketball",
    "dubai": "dubaibasketball",

    # LONDON
    "londonlions": "londonlions",

    # NBA bazı isim varyasyonları
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

    "sacramentokings": "sacramentokings",

    "charlottehornets": "charlottehornets",

    "utahjazz": "utahjazz",

    "phoenixsuns": "phoenixsuns",
}


def normalize_team_name(name):
    if not name:
        return ""

    text = str(name).strip().lower()

    # Türkçe / özel karakterleri sadeleştir
    text = unicodedata.normalize(
        "NFKD",
        text
    )

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    # Bazı sponsor / gereksiz ifadeleri kaldır
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
        text = text.replace(word, "")

    # Sadece harf/rakam bırak
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
# YARDIMCI
# ============================================================

def now_iso():
    return datetime.now(
        timezone.utc
    ).isoformat()


def safe_int(value):
    try:
        if value is None:
            return None

        return int(
            float(
                str(value).strip()
            )
        )

    except (
        TypeError,
        ValueError
    ):
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
        else:
            dt = dt.astimezone(
                timezone.utc
            )

        return dt

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


def date_key(value):
    dt = parse_date(value)

    if dt is None:
        return datetime.max.replace(
            tzinfo=timezone.utc
        )

    return dt


def reverse_date_key(value):
    dt = parse_date(value)

    if dt is None:
        return datetime.min.replace(
            tzinfo=timezone.utc
        )

    return dt


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
# EUROLEAGUE
# ============================================================

def get_euroleague_games():

    print()
    print("========================================")
    print("🌍 EUROLEAGUE")
    print("========================================")

    all_matches = []

    for season in EUROLEAGUE_SEASONS:

        url = (
            f"{EUROLEAGUE_BASE_URL}/"
            f"{season}/games"
        )

        print()
        print(
            f"📅 EuroLeague sezonu: {season}"
        )

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=60
            )

            print(
                "HTTP:",
                response.status_code
            )

            response.raise_for_status()

            data = response.json()

        except Exception as e:
            print(
                f"❌ {season} hatası:",
                e
            )
            continue

        if isinstance(data, list):
            games = data

        elif isinstance(data, dict):
            games = data.get("data")

            if not isinstance(
                games,
                list
            ):
                games = data.get("games")

            if not isinstance(
                games,
                list
            ):
                games = []

        else:
            games = []

        print(
            f"📦 {season} ham maç:",
            len(games)
        )

        for game in games:

            if not isinstance(
                game,
                dict
            ):
                continue

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
                local_club.get("name")
                or local_club.get(
                    "abbreviatedName"
                )
            )

            away_team = (
                road_club.get("name")
                or road_club.get(
                    "abbreviatedName"
                )
            )

            if not home_team:
                continue

            if not away_team:
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

            if (
                played
                and (
                    home_score is None
                    or away_score is None
                )
            ):
                played = False
                home_score = None
                away_score = None

            all_matches.append({
                "id": game.get("id"),
                "league": "EuroLeague",
                "season": season,
                "date": game.get("date"),
                "utcDate": game.get(
                    "utcDate"
                ),
                "round": game.get(
                    "round"
                ),
                "homeTeam": home_team,
                "awayTeam": away_team,
                "homeScore": home_score,
                "awayScore": away_score,
                "played": played,
                "status": (
                    "finished"
                    if played
                    else "scheduled"
                ),
            })

    # --------------------------------------------------------
    # DUPLICATE TEMİZLE
    # --------------------------------------------------------

    unique = {}

    for match in all_matches:

        season = match.get(
            "season"
        )

        game_id = match.get(
            "id"
        )

        if game_id:
            key = (
                f"{season}:"
                f"{game_id}"
            )
        else:
            key = (
                f"{season}:"
                f"{match.get('date')}:"
                f"{normalize_team_name(match.get('homeTeam'))}:"
                f"{normalize_team_name(match.get('awayTeam'))}"
            )

        unique[key] = match

    matches = list(
        unique.values()
    )

    matches.sort(
        key=lambda x: date_key(
            x.get("date")
        )
    )

    print()
    print(
        "✅ EuroLeague toplam:",
        len(matches)
    )

    finished = sum(
        1
        for x in matches
        if x.get("played")
    )

    print(
        "🏁 EuroLeague oynanan:",
        finished
    )

    return matches


# ============================================================
# NBA - TEK GÜN
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
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

    except Exception as e:
        print(
            f"   ❌ {date_text} NBA hatası:",
            e
        )
        return []

    events = (
        data.get("events")
        or []
    )

    matches = []

    for event in events:

        if not isinstance(
            event,
            dict
        ):
            continue

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

            if not isinstance(
                competitor,
                dict
            ):
                continue

            team = (
                competitor.get(
                    "team"
                )
                or {}
            )

            item = {
                "id": team.get("id"),
                "name": (
                    team.get(
                        "displayName"
                    )
                    or team.get(
                        "shortDisplayName"
                    )
                    or team.get("name")
                ),
                "abbreviation": (
                    team.get(
                        "abbreviation"
                    )
                ),
                "score": safe_int(
                    competitor.get(
                        "score"
                    )
                ),
            }

            side = competitor.get(
                "homeAway"
            )

            if side == "home":
                home = item

            elif side == "away":
                away = item

        if not home or not away:
            continue

        if not home.get("name"):
            continue

        if not away.get("name"):
            continue

        status = (
            event.get("status")
            or {}
        )

        status_type = (
            status.get("type")
            or {}
        )

        state = (
            status_type.get(
                "state"
            )
            or ""
        ).lower()

        completed = bool(
            status_type.get(
                "completed"
            )
        )

        played = (
            completed
            or state == "post"
        )

        home_score = (
            home.get("score")
            if played
            else None
        )

        away_score = (
            away.get("score")
            if played
            else None
        )

        if (
            played
            and (
                home_score is None
                or away_score is None
            )
        ):
            played = False
            home_score = None
            away_score = None

        matches.append({
            "id": event.get("id"),
            "league": "NBA",
            "season": "2026-27",
            "date": event.get("date"),
            "utcDate": event.get(
                "date"
            ),
            "round": None,
            "homeTeam": home["name"],
            "awayTeam": away["name"],
            "homeScore": home_score,
            "awayScore": away_score,
            "played": played,
            "status": (
                "finished"
                if played
                else "scheduled"
            ),
        })

    return matches


# ============================================================
# NBA - TARİH ARALIĞI
# ============================================================

def get_nba_games():

    print()
    print("========================================")
    print("🏀 NBA")
    print("========================================")

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
        f"📅 NBA tarih aralığı: "
        f"{start} → {end}"
    )

    total_days = (
        end - start
    ).days + 1

    all_matches = []

    current = start
    counter = 0

    while current <= end:

        counter += 1

        print(
            f"   NBA gün "
            f"{counter}/{total_days}: "
            f"{current}"
        )

        games = get_nba_day(
            datetime.combine(
                current,
                datetime.min.time(),
                tzinfo=timezone.utc
            )
        )

        all_matches.extend(
            games
        )

        current += timedelta(
            days=1
        )

    unique = {}

    for match in all_matches:

        game_id = match.get(
            "id"
        )

        if game_id:
            key = str(game_id)
        else:
            key = (
                f'{match.get("date")}:'
                f'{normalize_team_name(match.get("homeTeam"))}:'
                f'{normalize_team_name(match.get("awayTeam"))}'
            )

        unique[key] = match

    matches = list(
        unique.values()
    )

    matches.sort(
        key=lambda x: date_key(
            x.get("date")
        )
    )

    print()
    print(
        "🏀 NBA toplam maç:",
        len(matches)
    )

    finished = sum(
        1
        for x in matches
        if x.get("played")
    )

    print(
        "🏁 NBA oynanan:",
        finished
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

    if not team:
        return []

    target = parse_date(
        before_date
    )

    if target is None:
        return []

    target_team = normalize_team_name(
        team
    )

    previous = []

    for match in matches:

        match_team = normalize_team_name(
            match.get("homeTeam")
        )

        if match_team != target_team:
            continue

        if not match.get(
            "played"
        ):
            continue

        home_score = match.get(
            "homeScore"
        )

        away_score = match.get(
            "awayScore"
        )

        if home_score is None:
            continue

        if away_score is None:
            continue

        match_date = match_datetime(
            match
        )

        if match_date is None:
            continue

        if match_date >= target:
            continue

        previous.append(
            match
        )

    previous.sort(
        key=lambda x: reverse_date_key(
            x.get("utcDate")
            or x.get("date")
        ),
        reverse=True
    )

    result = []

    for match in previous[:5]:

        result.append({
            "date": match.get(
                "date"
            ),
            "opponent": match.get(
                "awayTeam"
            ),
            "scored": match.get(
                "homeScore"
            ),
            "conceded": match.get(
                "awayScore"
            ),
        })

    return result


# ============================================================
# SON 5 DEPLASMAN
# ============================================================

def last_five_away(
    matches,
    team,
    before_date
):

    if not team:
        return []

    target = parse_date(
        before_date
    )

    if target is None:
        return []

    target_team = normalize_team_name(
        team
    )

    previous = []

    for match in matches:

        match_team = normalize_team_name(
            match.get("awayTeam")
        )

        if match_team != target_team:
            continue

        if not match.get(
            "played"
        ):
            continue

        home_score = match.get(
            "homeScore"
        )

        away_score = match.get(
            "awayScore"
        )

        if home_score is None:
            continue

        if away_score is None:
            continue

        match_date = match_datetime(
            match
        )

        if match_date is None:
            continue

        if match_date >= target:
            continue

        previous.append(
            match
        )

    previous.sort(
        key=lambda x: reverse_date_key(
            x.get("utcDate")
            or x.get("date")
        ),
        reverse=True
    )

    result = []

    for match in previous[:5]:

        result.append({
            "date": match.get(
                "date"
            ),
            "opponent": match.get(
                "homeTeam"
            ),
            "scored": match.get(
                "awayScore"
            ),
            "conceded": match.get(
                "homeScore"
            ),
        })

    return result


# ============================================================
# SON 5 EKLE
# ============================================================

def add_last_five(matches):

    print()
    print("========================================")
    print("📊 SON 5 VERİLER HESAPLANIYOR")
    print("========================================")

    finished = []

    for match in matches:

        if not match.get(
            "played"
        ):
            continue

        if match.get(
            "homeScore"
        ) is None:
            continue

        if match.get(
            "awayScore"
        ) is None:
            continue

        finished.append(
            match
        )

    print(
        "Geçmişte kullanılabilir maç:",
        len(finished)
    )

    for match in matches:

        home_team = match.get(
            "homeTeam"
        )

        away_team = match.get(
            "awayTeam"
        )

        match["homeLast5"] = (
            last_five_home(
                finished,
                home_team,
                match.get("date")
            )
        )

        match["awayLast5"] = (
            last_five_away(
                finished,
                away_team,
                match.get("date")
            )
        )

    return matches


# ============================================================
# TAKIM VERİ KONTROLÜ
# ============================================================

def print_team_match_debug(matches):

    print()
    print("========================================")
    print("🔎 TAKIM SON 5 KONTROL")
    print("========================================")

    now = datetime.now(
        timezone.utc
    )

    upcoming = []

    for match in matches:

        if match.get("played"):
            continue

        match_date = match_datetime(
            match
        )

        if match_date is None:
            continue

        if match_date < now:
            continue

        home_last5 = (
            match.get(
                "homeLast5"
            )
            or []
        )

        away_last5 = (
            match.get(
                "awayLast5"
            )
            or []
        )

        upcoming.append({
            "date": match_date,
            "match": match,
            "home": home_last5,
            "away": away_last5,
        })

    upcoming.sort(
        key=lambda x: x["date"]
    )

    shown = 0

    for item in upcoming:

        match = item["match"]

        home_last5 = item["home"]
        away_last5 = item["away"]

        if (
            len(home_last5) >= 5
            and len(away_last5) >= 5
        ):
            continue

        print()
        print(
            f'{match.get("league")} | '
            f'{match.get("homeTeam")} - '
            f'{match.get("awayTeam")}'
        )

        print(
            f'   Ev: {len(home_last5)}/5 | '
            f'{normalize_team_name(match.get("homeTeam"))}'
        )

        print(
            f'   Dep: {len(away_last5)}/5 | '
            f'{normalize_team_name(match.get("awayTeam"))}'
        )

        shown += 1

        if shown >= 20:
            break

    print()
    print(
        "Eksik veri gösterilen maç:",
        shown
    )


# ============================================================
# İSTATİSTİK
# ============================================================

def print_statistics(matches):

    print()
    print("========================================")
    print("📊 SONUÇ")
    print("========================================")

    nba = [
        x for x in matches
        if x.get("league") == "NBA"
    ]

    euroleague = [
        x for x in matches
        if x.get("league") == "EuroLeague"
    ]

    nba_finished = sum(
        1
        for x in nba
        if (
            x.get("played")
            and x.get("homeScore") is not None
            and x.get("awayScore") is not None
        )
    )

    euro_finished = sum(
        1
        for x in euroleague
        if (
            x.get("played")
            and x.get("homeScore") is not None
            and x.get("awayScore") is not None
        )
    )

    upcoming = [
        x
        for x in matches
        if not x.get("played")
    ]

    both_5 = 0
    home_5 = 0
    away_5 = 0
    incomplete = 0

    for match in upcoming:

        home_count = len(
            match.get(
                "homeLast5"
            )
            or []
        )

        away_count = len(
            match.get(
                "awayLast5"
            )
            or []
        )

        if home_count >= 5:
            home_5 += 1

        if away_count >= 5:
            away_5 += 1

        if (
            home_count >= 5
            and away_count >= 5
        ):
            both_5 += 1
        else:
            incomplete += 1

    print(
        "Toplam maç:",
        len(matches)
    )

    print(
        "NBA:",
        len(nba)
    )

    print(
        "NBA oynanan:",
        nba_finished
    )

    print(
        "EuroLeague:",
        len(euroleague)
    )

    print(
        "EuroLeague oynanan:",
        euro_finished
    )

    print(
        "Gelecek maç:",
        len(upcoming)
    )

    print(
        "Ev 5/5:",
        home_5
    )

    print(
        "Dep 5/5:",
        away_5
    )

    print(
        "İki taraf 5/5:",
        both_5
    )

    print(
        "Eksik Son 5:",
        incomplete
    )


# ============================================================
# ANA
# ============================================================

def main():

    print()
    print("🏀 BASKETBOL VERİ GÜNCELLEYİCİ")
    print("========================================")

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # VERİLERİ AL
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
    # TEKRARLARI TEMİZLE
    # --------------------------------------------------------

    unique = {}

    for match in matches:

        league = match.get(
            "league"
        )

        game_id = match.get(
            "id"
        )

        if game_id:

            key = (
                f"{league}:"
                f"{game_id}"
            )

        else:

            key = (
                f"{league}:"
                f"{match.get('date')}:"
                f"{normalize_team_name(match.get('homeTeam'))}:"
                f"{normalize_team_name(match.get('awayTeam'))}"
            )

        unique[key] = match

    matches = list(
        unique.values()
    )

    # --------------------------------------------------------
    # TARİHE GÖRE SIRALA
    # --------------------------------------------------------

    matches.sort(
        key=lambda x: date_key(
            x.get("date")
        )
    )

    # --------------------------------------------------------
    # SON 5
    # --------------------------------------------------------

    matches = add_last_five(
        matches
    )

    # --------------------------------------------------------
    # KONTROL
    # --------------------------------------------------------

    print_team_match_debug(
        matches
    )

    print_statistics(
        matches
    )

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    output = {
        "updatedAt": now_iso(),
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
    print("========================================")
    print("✅ BASKETBALL.JSON OLUŞTURULDU")
    print("========================================")
    print(
        "📁",
        OUTPUT
    )
    print(
        "📦 Maç:",
        len(matches)
    )


if __name__ == "__main__":
    main()
