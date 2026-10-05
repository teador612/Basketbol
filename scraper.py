import os
import json
import requests
from datetime import datetime, timedelta
from statistics import mean
from zoneinfo import ZoneInfo


# =========================================================
# AYARLAR
# =========================================================

TZ = ZoneInfo("Europe/Istanbul")

TODAY = datetime.now(TZ).date()
DATE = TODAY.isoformat()

OUTPUT_FILE = "data.json"

BALLDONTLIE_KEY = os.getenv("BALLDONTLIE_API_KEY")

NBA_URL = "https://api.balldontlie.io/v1/games"

EUROLEAGUE_URL = (
    "https://api-live.euroleague.net"
)

EUROLEAGUE_SEASON = "E2026"

TIMEOUT = 30


# =========================================================
# HTTP
# =========================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
})


def get_json(url, params=None, headers=None):

    try:

        r = session.get(
            url,
            params=params,
            headers=headers,
            timeout=TIMEOUT
        )

        if r.status_code != 200:

            print(
                f"❌ HTTP {r.status_code}: {url}"
            )

            print(r.text[:500])

            return {}

        return r.json()

    except Exception as e:

        print(
            f"❌ Bağlantı hatası: {e}"
        )

        return {}


# =========================================================
# TARİH PARSE
# =========================================================

def parse_any_date(value):

    if value is None:
        return None

    if isinstance(value, dict):

        for key in (
            "start",
            "date",
            "gameDate",
            "utcDate",
            "localDate"
        ):

            if value.get(key):
                value = value[key]
                break

    value = str(value).strip()

    if not value:
        return None

    # YYYY-MM-DD direkt
    if len(value) >= 10:

        first10 = value[:10]

        if (
            first10[4:5] == "-"
            and first10[7:8] == "-"
        ):

            try:
                datetime.strptime(
                    first10,
                    "%Y-%m-%d"
                )

                return first10

            except:
                pass

    # ISO tarih
    try:

        v = value

        if v.endswith("Z"):
            v = v[:-1] + "+00:00"

        dt = datetime.fromisoformat(v)

        if dt.tzinfo:

            dt = dt.astimezone(TZ)

        return dt.date().isoformat()

    except:
        pass

    return None


# =========================================================
# NBA
# =========================================================

def nba_headers():

    return {
        "Authorization": BALLDONTLIE_KEY
    }


def get_nba_today():

    print()
    print("🏀 NBA maçları alınıyor...")

    if not BALLDONTLIE_KEY:

        print(
            "❌ BALLDONTLIE_API_KEY bulunamadı."
        )

        return []

    # Önce doğrudan bugünü dene
    data = get_json(
        NBA_URL,
        params={
            "dates[]": DATE,
            "per_page": 100
        },
        headers=nba_headers()
    )

    games = data.get("data", [])

    result = []

    for game in games:

        game_date = parse_any_date(
            game.get("date")
        )

        if game_date != DATE:
            continue

        home = game.get(
            "home_team",
            {}
        )

        away = game.get(
            "visitor_team",
            {}
        )

        if not home.get("id"):
            continue

        if not away.get("id"):
            continue

        result.append({
            "id": game.get("id"),

            "league": "NBA",

            "league_id": "NBA",

            "season": game.get(
                "season"
            ),

            "home": {
                "id": home.get("id"),
                "name": home.get(
                    "full_name"
                )
            },

            "away": {
                "id": away.get("id"),
                "name": away.get(
                    "full_name"
                )
            },

            "raw": game
        })

    print(
        f"   📦 NBA: {len(result)} maç"
    )

    return result


# =========================================================
# NBA TAKIM GEÇMİŞİ
# =========================================================

def get_nba_history(team_id):

    end_date = TODAY

    start_date = (
        end_date -
        timedelta(days=180)
    )

    data = get_json(
        NBA_URL,
        params={
            "team_ids[]": team_id,
            "start_date":
                start_date.isoformat(),
            "end_date":
                end_date.isoformat(),
            "per_page": 100
        },
        headers=nba_headers()
    )

    games = data.get(
        "data",
        []
    )

    result = []

    for game in games:

        home = game.get(
            "home_team",
            {}
        )

        away = game.get(
            "visitor_team",
            {}
        )

        home_score = game.get(
            "home_team_score"
        )

        away_score = game.get(
            "visitor_team_score"
        )

        if home_score is None:
            continue

        if away_score is None:
            continue

        try:

            home_score = float(
                home_score
            )

            away_score = float(
                away_score
            )

        except:

            continue

        # Henüz oynanmamış maç
        if (
            home_score == 0
            and away_score == 0
        ):
            continue

        game_date = parse_any_date(
            game.get("date")
        )

        if not game_date:
            continue

        if (
            str(home.get("id"))
            == str(team_id)
        ):

            result.append({
                "home": True,
                "for": home_score,
                "against": away_score,
                "date": game_date
            })

        elif (
            str(away.get("id"))
            == str(team_id)
        ):

            result.append({
                "home": False,
                "for": away_score,
                "against": home_score,
                "date": game_date
            })

    result.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    return result


# =========================================================
# EUROLEAGUE TÜM SEZON
# =========================================================

def get_euroleague_all():

    print()
    print(
        "🌍 EuroLeague sezon verisi alınıyor..."
    )

    url = (
        f"{EUROLEAGUE_URL}"
        f"/v2/competitions/E"
        f"/seasons/{EUROLEAGUE_SEASON}"
        f"/games"
    )

    data = get_json(url)

    games = data.get(
        "data",
        []
    )

    print(
        f"   📦 EuroLeague sezon maçları: "
        f"{len(games)}"
    )

    return games


# =========================================================
# EUROLEAGUE TAKIM
# =========================================================

def euro_home(game):

    return (
        game.get("local")
        or game.get("home")
        or game.get("homeTeam")
        or {}
    )


def euro_away(game):

    return (
        game.get("road")
        or game.get("away")
        or game.get("awayTeam")
        or {}
    )


def euro_team_id(team):

    for key in (
        "clubCode",
        "code",
        "id",
        "teamCode"
    ):

        if team.get(key) is not None:
            return team.get(key)

    return None


def euro_team_name(team):

    for key in (
        "name",
        "clubName",
        "nameShort",
        "teamName"
    ):

        if team.get(key):
            return str(
                team.get(key)
            )

    return ""


# =========================================================
# EUROLEAGUE TARİH
# =========================================================

def euro_date(game):

    # Öncelikle olası tarih alanlarını dene
    keys = (
        "date",
        "gameDate",
        "startDate",
        "utcDate",
        "localDate"
    )

    for key in keys:

        value = game.get(key)

        parsed = parse_any_date(
            value
        )

        if parsed:
            return parsed

    # Bazı payloadlarda nested
    for parent in (
        "date",
        "start",
        "game"
    ):

        obj = game.get(parent)

        if isinstance(obj, dict):

            for key in keys:

                parsed = parse_any_date(
                    obj.get(key)
                )

                if parsed:
                    return parsed

    return None


# =========================================================
# EUROLEAGUE BUGÜN
# =========================================================

def get_euroleague_today(
    all_games
):

    result = []

    for game in all_games:

        d = euro_date(game)

        if d != DATE:
            continue

        home = euro_home(game)
        away = euro_away(game)

        home_id = euro_team_id(
            home
        )

        away_id = euro_team_id(
            away
        )

        if not home_id:
            continue

        if not away_id:
            continue

        result.append({
            "id":
                game.get("gameCode")
                or game.get("id"),

            "league":
                "EuroLeague",

            "league_id":
                "E",

            "season":
                EUROLEAGUE_SEASON,

            "home": {
                "id": home_id,
                "name": euro_team_name(
                    home
                )
            },

            "away": {
                "id": away_id,
                "name": euro_team_name(
                    away
                )
            },

            "raw": game
        })

    print(
        f"   📦 EuroLeague bugün: "
        f"{len(result)} maç"
    )

    return result


# =========================================================
# EUROLEAGUE SKOR
# =========================================================

def euro_points(obj):

    if not isinstance(obj, dict):
        return None

    for key in (
        "score",
        "points",
        "total"
    ):

        value = obj.get(key)

        if value is not None:

            try:
                return float(value)
            except:
                pass

    return None


def euro_game_score(
    game,
    team_id
):

    home = euro_home(game)
    away = euro_away(game)

    home_id = euro_team_id(
        home
    )

    away_id = euro_team_id(
        away
    )

    # Takım skorlarını mümkün olan
    # bütün payload şekillerinden bul
    home_score = euro_points(
        home
    )

    away_score = euro_points(
        away
    )

    if home_score is None:

        home_score = (
            game.get("homeScore")
            or game.get("localScore")
        )

    if away_score is None:

        away_score = (
            game.get("awayScore")
            or game.get("roadScore")
        )

    try:

        home_score = float(
            home_score
        )

        away_score = float(
            away_score
        )

    except:

        return None

    d = euro_date(game)

    if not d:
        return None

    if (
        str(home_id)
        == str(team_id)
    ):

        return {
            "home": True,
            "for": home_score,
            "against": away_score,
            "date": d
        }

    if (
        str(away_id)
        == str(team_id)
    ):

        return {
            "home": False,
            "for": away_score,
            "against": home_score,
            "date": d
        }

    return None


# =========================================================
# EUROLEAGUE TAKIM GEÇMİŞİ
# =========================================================

def get_euro_history(
    team_id,
    all_games
):

    result = []

    for game in all_games:

        item = euro_game_score(
            game,
            team_id
        )

        if not item:
            continue

        # Bugünkü / gelecek maçları
        # geçmiş hesabına katma
        if item["date"] >= DATE:
            continue

        # 0-0 oynanmamış kayıt
        if (
            item["for"] == 0
            and item["against"] == 0
        ):
            continue

        result.append(item)

    result.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    return result


# =========================================================
# SON 5
# =========================================================

def last_5_home(history):

    return [
        x
        for x in history
        if x["home"]
    ][:5]


def last_5_away(history):

    return [
        x
        for x in history
        if not x["home"]
    ][:5]


# =========================================================
# ANALİZ
# =========================================================

def analyse(
    game,
    euro_games
):

    league = game[
        "league"
    ]

    home_id = game[
        "home"
    ]["id"]

    away_id = game[
        "away"
    ]["id"]

    print(
        f"\n🔎 "
        f"{game['home']['name']} "
        f"- "
        f"{game['away']['name']}"
    )

    if league == "NBA":

        home_history = (
            get_nba_history(
                home_id
            )
        )

        away_history = (
            get_nba_history(
                away_id
            )
        )

    else:

        home_history = (
            get_euro_history(
                home_id,
                euro_games
            )
        )

        away_history = (
            get_euro_history(
                away_id,
                euro_games
            )
        )

    home_games = last_5_home(
        home_history
    )

    away_games = last_5_away(
        away_history
    )

    print(
        f"   🏠 İç saha geçmişi: "
        f"{len(home_games)}"
    )

    print(
        f"   ✈️ Dış saha geçmişi: "
        f"{len(away_games)}"
    )

    if not home_games:
        print(
            "   ⚠️ Ev sahibi için veri yok."
        )
        return None

    if not away_games:
        print(
            "   ⚠️ Deplasman için veri yok."
        )
        return None

    home_for = mean(
        x["for"]
        for x in home_games
    )

    home_against = mean(
        x["against"]
        for x in home_games
    )

    away_for = mean(
        x["for"]
        for x in away_games
    )

    away_against = mean(
        x["against"]
        for x in away_games
    )

    expected_home = (
        home_for +
        away_against
    ) / 2

    expected_away = (
        away_for +
        home_against
    ) / 2

    match_total = (
        expected_home +
        expected_away
    )

    quarter_avg = (
        match_total / 4
    )

    first_half = (
        match_total / 2
    )

    sample = min(
        len(home_games),
        len(away_games)
    )

    confidence = {
        5: 85,
        4: 80,
        3: 75,
        2: 65,
        1: 55,
        0: 0
    }.get(
        sample,
        0
    )

    print(
        f"   📊 Beklenen skor: "
        f"{expected_home:.1f} - "
        f"{expected_away:.1f}"
    )

    print(
        f"   📈 Maç toplamı: "
        f"{match_total:.1f}"
    )

    print(
        f"   🎯 Güven: "
        f"%{confidence}"
    )

    return {

        "id":
            game.get("id"),

        "league":
            league,

        "league_id":
            game.get("league_id"),

        "season":
            game.get("season"),

        "home":
            game["home"]["name"],

        "away":
            game["away"]["name"],

        "home_team_id":
            home_id,

        "away_team_id":
            away_id,

        "games":
            sample,

        "home_for_avg":
            round(home_for, 2),

        "home_against_avg":
            round(home_against, 2),

        "away_for_avg":
            round(away_for, 2),

        "away_against_avg":
            round(away_against, 2),

        "exp_home":
            round(expected_home, 2),

        "exp_away":
            round(expected_away, 2),

        "match_total":
            round(match_total, 2),

        "quarter_avg":
            round(quarter_avg, 2),

        "first_half":
            round(first_half, 2),

        "q1":
            round(quarter_avg, 2),

        "q2":
            round(quarter_avg, 2),

        "q3":
            round(quarter_avg, 2),

        "q4":
            round(quarter_avg, 2),

        "confidence":
            confidence,

        "date":
            DATE
    }


# =========================================================
# ANA
# =========================================================

def main():

    print("=" * 55)

    print(
        "🏀 NBA + EUROLEAGUE "
        "BASKETBOL ANALİZİ"
    )

    print("=" * 55)

    print(
        f"📅 Türkiye tarihi: {DATE}"
    )

    # -----------------------------------------------------
    # NBA
    # -----------------------------------------------------

    nba_games = (
        get_nba_today()
    )

    # -----------------------------------------------------
    # EUROLEAGUE
    # -----------------------------------------------------

    euro_all = (
        get_euroleague_all()
    )

    euro_today = (
        get_euroleague_today(
            euro_all
        )
    )

    # -----------------------------------------------------
    # BİRLEŞTİR
    # -----------------------------------------------------

    all_games = (
        nba_games +
        euro_today
    )

    print()
    print(
        f"🎯 Toplam maç: "
        f"{len(all_games)}"
    )

    results = []

    for i, game in enumerate(
        all_games,
        1
    ):

        print(
            f"\n[{i}/{len(all_games)}] "
            f"{game['league']}"
        )

        try:

            result = analyse(
                game,
                euro_all
            )

            if result:
                results.append(
                    result
                )

        except Exception as e:

            print(
                f"❌ Analiz hatası: {e}"
            )

    # -----------------------------------------------------
    # JSON
    # -----------------------------------------------------

    output = {
        DATE: results
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

    print()
    print("=" * 55)

    print(
        f"✅ {len(results)} maç analiz edildi."
    )

    print(
        f"📁 {OUTPUT_FILE}"
    )

    print("=" * 55)


if __name__ == "__main__":
    main()
