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
        char
        for char in text
        if not unicodedata.combining(char)
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


def date_key(value):
    dt = parse_date(value)

    if dt is None:
        return datetime.max.replace(
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
    print("=" * 60)
    print("🌍 EUROLEAGUE")
    print("=" * 60)

    all_matches = []

    for season in EUROLEAGUE_SEASONS:

        url = (
            f"{EUROLEAGUE_BASE_URL}/"
            f"{season}/games"
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

        if isinstance(data, list):
            games = data

        elif isinstance(data, dict):

            games = data.get(
                "data"
            )

            if not isinstance(
                games,
                list
            ):
                games = data.get(
                    "games"
                )

            if not isinstance(
                games,
                list
            ):
                games = []

        else:
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

    unique = {}

    for match in all_matches:

        game_id = match.get(
            "id"
        )

        if game_id:

            key = (
                f'{match.get("season")}:'
                f'{game_id}'
            )

        else:

            key = (
                f'{match.get("season")}:'
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

    return matches


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

        competitors = (
            competitions[0].get(
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
            "utcDate": event.get("date"),
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

        all_matches.extend(
            get_nba_day(
                datetime.combine(
                    current,
                    datetime.min.time(),
                    tzinfo=timezone.utc
                )
            )
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

    matches.sort(
        key=lambda x: date_key(
            x.get("date")
        )
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

    return matches


# ============================================================
# SON 5
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

    return [
        {
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
        }
        for x in previous[:5]
    ]


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

    return [
        {
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
        }
        for x in previous[:5]
    ]


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

    print()
    print(
        f"📊 Geçmiş maç sayısı: {len(finished)}"
    )

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
# EKSİK MAÇ TEŞHİSİ
# ============================================================

def diagnose_missing(matches):

    now = datetime.now(
        timezone.utc
    )

    finished = [
        x
        for x in matches
        if (
            x.get("played")
            and x.get("homeScore") is not None
            and x.get("awayScore") is not None
        )
    ]

    missing = []

    for match in matches:

        if match.get("played"):
            continue

        game_date = match_datetime(
            match
        )

        if not game_date or game_date < now:
            continue

        home_last5 = (
            match.get("homeLast5")
            or []
        )

        away_last5 = (
            match.get("awayLast5")
            or []
        )

        if (
            len(home_last5) == 5
            and len(away_last5) == 5
        ):
            continue

        missing.append(
            match
        )

    missing.sort(
        key=lambda x: match_datetime(x)
    )

    print()
    print("=" * 75)
    print("🔎 5/5 OLMAYAN MAÇLAR")
    print("=" * 75)

    print(
        f"Toplam: {len(missing)}"
    )

    for index, match in enumerate(
        missing,
        1
    ):

        game_date = match_datetime(
            match
        )

        home_name = match.get(
            "homeTeam"
        )

        away_name = match.get(
            "awayTeam"
        )

        home_key = normalize_team_name(
            home_name
        )

        away_key = normalize_team_name(
            away_name
        )

        # Kaynakta bulunan tüm ev maçları
        home_history = []

        # Kaynakta bulunan tüm deplasman maçları
        away_history = []

        for game in finished:

            game_date_history = match_datetime(
                game
            )

            if not game_date_history:
                continue

            if game_date_history >= game_date:
                continue

            if normalize_team_name(
                game.get("homeTeam")
            ) == home_key:

                home_history.append(
                    game
                )

            if normalize_team_name(
                game.get("awayTeam")
            ) == away_key:

                away_history.append(
                    game
                )

        home_history.sort(
            key=lambda x: match_datetime(x),
            reverse=True
        )

        away_history.sort(
            key=lambda x: match_datetime(x),
            reverse=True
        )

        home_used = (
            match.get("homeLast5")
            or []
        )

        away_used = (
            match.get("awayLast5")
            or []
        )

        print()
        print(
            f"{index}. "
            f"{home_name} - {away_name}"
        )

        print(
            f"   📅 {match.get('date')}"
        )

        if len(home_used) < 5:

            print(
                f"   🏠 EV "
                f"{len(home_used)}/5 "
                f"| Kaynak: "
                f"{len(home_history)}"
            )

            print(
                f"      Anahtar: {home_key}"
            )

        if len(away_used) < 5:

            print(
                f"   ✈️ DEP "
                f"{len(away_used)}/5 "
                f"| Kaynak: "
                f"{len(away_history)}"
            )

            print(
                f"      Anahtar: {away_key}"
            )

    print()
    print("=" * 75)
    print("📊 TEŞHİS TAMAMLANDI")
    print("=" * 75)


# ============================================================
# ÖZET
# ============================================================

def print_summary(matches):

    upcoming = [
        x
        for x in matches
        if not x.get("played")
    ]

    full = 0
    incomplete = 0

    for match in upcoming:

        home_count = len(
            match.get("homeLast5")
            or []
        )

        away_count = len(
            match.get("awayLast5")
            or []
        )

        if (
            home_count == 5
            and away_count == 5
        ):
            full += 1
        else:
            incomplete += 1

    total = full + incomplete

    rate = (
        full / total * 100
        if total
        else 0
    )

    print()
    print("=" * 60)
    print("📊 ÖZET")
    print("=" * 60)

    print(
        f"Tam 5/5: {full}"
    )

    print(
        f"Eksik: {incomplete}"
    )

    print(
        f"5/5 oranı: %{rate:.1f}"
    )


# ============================================================
# ANA
# ============================================================

def main():

    print()
    print("=" * 60)
    print("🏀 NBA + EUROLEAGUE BASKETBOL ANALİZİ")
    print("=" * 60)

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

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
    # TEŞHİS
    # --------------------------------------------------------

    diagnose_missing(
        matches
    )

    # --------------------------------------------------------
    # ÖZET
    # --------------------------------------------------------

    print_summary(
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
    print("=" * 60)
    print("✅ VERİ + TEŞHİS TAMAMLANDI")
    print("=" * 60)

    print(
        f"📁 {OUTPUT}"
    )


if __name__ == "__main__":
    main()
