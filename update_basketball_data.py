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
    "hapoel": "hapoeltelaviv",

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
# TAKIM NORMALİZASYONU
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
# GENEL YARDIMCILAR
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
    print("🌍 EUROLEAGUE VERİLERİ")
    print("=" * 60)

    all_matches = []

    for season in EUROLEAGUE_SEASONS:

        url = (
            f"{EUROLEAGUE_BASE_URL}/"
            f"{season}/games"
        )

        print(
            f"\n📅 Sezon: {season}"
        )

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=60
            )

            print(
                f"   HTTP: {response.status_code}"
            )

            response.raise_for_status()

            data = response.json()

        except Exception as e:
            print(
                f"   ❌ Hata: {e}"
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
            f"   📦 Maç: {len(games)}"
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

    finished = sum(
        1
        for match in matches
        if match.get("played")
    )

    print(
        f"\n✅ EuroLeague toplam: {len(matches)}"
    )

    print(
        f"🏁 EuroLeague oynanan: {finished}"
    )

    return matches


# ============================================================
# NBA TEK GÜN
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
            f"   ❌ {date_text}: {e}"
        )
        return []

    events = (
        data.get("events")
        or []
    )

    matches = []

    for event in events:

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
                    or team.get(
                        "name"
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

        state = str(
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
# NBA TARİH ARALIĞI
# ============================================================

def get_nba_games():

    print()
    print("=" * 60)
    print("🏀 NBA VERİLERİ")
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
        f"📅 Aralık: {start} → {end}"
    )

    all_matches = []

    current = start

    while current <= end:

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

    finished = sum(
        1
        for match in matches
        if match.get("played")
    )

    print(
        f"\n🏀 NBA toplam: {len(matches)}"
    )

    print(
        f"🏁 NBA oynanan: {finished}"
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

    normalized_team = normalize_team_name(
        team
    )

    previous = []

    for match in matches:

        if normalize_team_name(
            match.get("homeTeam")
        ) != normalized_team:
            continue

        if not match.get("played"):
            continue

        if match.get("homeScore") is None:
            continue

        if match.get("awayScore") is None:
            continue

        match_date = match_datetime(
            match
        )

        if not match_date:
            continue

        if match_date >= target:
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
            "date": match.get("date"),
            "opponent": match.get(
                "awayTeam"
            ),
            "scored": match.get(
                "homeScore"
            ),
            "conceded": match.get(
                "awayScore"
            ),
        }
        for match in previous[:5]
    ]


# ============================================================
# SON 5 DEPLASMAN
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

    normalized_team = normalize_team_name(
        team
    )

    previous = []

    for match in matches:

        if normalize_team_name(
            match.get("awayTeam")
        ) != normalized_team:
            continue

        if not match.get("played"):
            continue

        if match.get("homeScore") is None:
            continue

        if match.get("awayScore") is None:
            continue

        match_date = match_datetime(
            match
        )

        if not match_date:
            continue

        if match_date >= target:
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
            "date": match.get("date"),
            "opponent": match.get(
                "homeTeam"
            ),
            "scored": match.get(
                "awayScore"
            ),
            "conceded": match.get(
                "homeScore"
            ),
        }
        for match in previous[:5]
    ]


# ============================================================
# SON 5 VERİLERİNİ EKLE
# ============================================================

def add_last_five(matches):

    print()
    print("=" * 60)
    print("📊 SON 5 VERİLER HESAPLANIYOR")
    print("=" * 60)

    finished = [
        match
        for match in matches
        if (
            match.get("played")
            and match.get("homeScore") is not None
            and match.get("awayScore") is not None
        )
    ]

    print(
        f"🏁 Kullanılabilir geçmiş maç: "
        f"{len(finished)}"
    )

    for match in matches:

        match["homeLast5"] = (
            last_five_home(
                finished,
                match.get("homeTeam"),
                match.get("date")
            )
        )

        match["awayLast5"] = (
            last_five_away(
                finished,
                match.get("awayTeam"),
                match.get("date")
            )
        )

    return matches


# ============================================================
# EKSİK MAÇLARI DETAYLI GÖSTER
# ============================================================

def print_missing_matches(matches):

    print()
    print("=" * 70)
    print("🔎 EKSİK SON 5 DETAYLI KONTROL")
    print("=" * 70)

    now = datetime.now(
        timezone.utc
    )

    missing = []

    for match in matches:

        if match.get("played"):
            continue

        match_date = match_datetime(
            match
        )

        if not match_date:
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

        if (
            len(home_last5) == 5
            and len(away_last5) == 5
        ):
            continue

        missing.append({
            "date": match_date,
            "match": match,
            "home": home_last5,
            "away": away_last5,
        })

    missing.sort(
        key=lambda x: x["date"]
    )

    print(
        f"\n⚠️ Eksik maç: {len(missing)}"
    )

    for index, item in enumerate(
        missing,
        1
    ):

        match = item["match"]

        home_last5 = item["home"]
        away_last5 = item["away"]

        home_name = match.get(
            "homeTeam"
        )

        away_name = match.get(
            "awayTeam"
        )

        print()
        print("-" * 70)

        print(
            f"{index}. "
            f"{match.get('league')}"
        )

        print(
            f"   🏀 {home_name} - {away_name}"
        )

        print(
            f"   📅 {match.get('date')}"
        )

        print(
            f"   🏠 EV: "
            f"{len(home_last5)}/5"
        )

        print(
            f"      Normalized: "
            f"{normalize_team_name(home_name)}"
        )

        if home_last5:

            for game in home_last5:

                print(
                    f"      {game.get('date')} | "
                    f"{game.get('scored')}-"
                    f"{game.get('conceded')} | "
                    f"{game.get('opponent')}"
                )

        else:

            print(
                "      ❌ Geçmiş ev maçı yok"
            )

        print(
            f"   ✈️ DEP: "
            f"{len(away_last5)}/5"
        )

        print(
            f"      Normalized: "
            f"{normalize_team_name(away_name)}"
        )

        if away_last5:

            for game in away_last5:

                print(
                    f"      {game.get('date')} | "
                    f"{game.get('scored')}-"
                    f"{game.get('conceded')} | "
                    f"{game.get('opponent')}"
                )

        else:

            print(
                "      ❌ Geçmiş deplasman maçı yok"
            )

    print()
    print("=" * 70)
    print("🔎 EKSİK MAÇ ANALİZİ TAMAMLANDI")
    print("=" * 70)


# ============================================================
# ÖZET
# ============================================================

def print_summary(matches):

    upcoming = [
        match
        for match in matches
        if not match.get("played")
    ]

    full = 0
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

        if (
            home_count == 5
            and away_count == 5
        ):
            full += 1
        else:
            incomplete += 1

    total = (
        full
        + incomplete
    )

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
    print("🏀 NBA + EUROLEAGUE BASKETBOL VERİ SİSTEMİ")
    print("=" * 60)

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # VERİLER
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
    # DUPLICATE TEMİZLE
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
    # TARİH SIRASI
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
    # EKSİKLERİ GÖSTER
    # --------------------------------------------------------

    print_missing_matches(
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
            for match in matches
            if match.get("league") == "NBA"
        ),

        "nbaFinished": sum(
            1
            for match in matches
            if (
                match.get("league") == "NBA"
                and match.get("played")
            )
        ),

        "euroleague": sum(
            1
            for match in matches
            if match.get("league") == "EuroLeague"
        ),

        "euroleagueFinished": sum(
            1
            for match in matches
            if (
                match.get("league") == "EuroLeague"
                and match.get("played")
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
    print("✅ VERİ GÜNCELLENDİ")
    print("=" * 60)

    print(
        f"📁 {OUTPUT}"
    )

    print(
        f"📦 Toplam maç: {len(matches)}"
    )


if __name__ == "__main__":
    main()
