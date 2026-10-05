import os
import json
import requests
from datetime import datetime, timedelta
from statistics import mean
from zoneinfo import ZoneInfo


# =========================================================
# AYARLAR
# =========================================================

DATE = datetime.now(
    ZoneInfo("Europe/Istanbul")
).strftime("%Y-%m-%d")

OUTPUT_FILE = "data.json"

NBA_API_KEY = os.getenv("BALLDONTLIE_API_KEY")

NBA_URL = "https://api.balldontlie.io/v1/games"

EUROLEAGUE_URL = (
    "https://api-live.euroleague.net"
)

EUROLEAGUE_SEASON = "E2026"

TIMEOUT = 30

HEADERS = {}

if NBA_API_KEY:
    HEADERS["Authorization"] = NBA_API_KEY


# =========================================================
# SESSION
# =========================================================

session = requests.Session()

session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
})


# =========================================================
# GENEL HTTP
# =========================================================

def get_json(
    url,
    params=None,
    headers=None
):

    try:

        response = session.get(
            url,
            params=params,
            headers=headers,
            timeout=TIMEOUT
        )

        if response.status_code != 200:

            print(
                f"❌ HTTP {response.status_code}: "
                f"{url}"
            )

            try:
                print(response.text[:500])
            except:
                pass

            return {}

        return response.json()

    except Exception as e:

        print(
            f"❌ Bağlantı hatası: {e}"
        )

        return {}


# =========================================================
# TARİH
# =========================================================

def parse_date(value):

    if not value:
        return None

    value = str(value).strip()

    try:

        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        dt = datetime.fromisoformat(value)

        if dt.tzinfo:

            dt = dt.astimezone(
                ZoneInfo("Europe/Istanbul")
            )

        return dt.date().isoformat()

    except:

        return value[:10]


# =========================================================
# NBA
# =========================================================

def get_nba_games_for_date():

    print()
    print("🏀 NBA maçları alınıyor...")

    if not NBA_API_KEY:

        print(
            "❌ BALLDONTLIE_API_KEY bulunamadı."
        )

        return []

    data = get_json(
        NBA_URL,
        params={
            "dates[]": DATE,
            "per_page": 100
        },
        headers=HEADERS
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

        if not home.get("id"):
            continue

        if not away.get("id"):
            continue

        result.append({
            "id": game.get("id"),

            "league": "NBA",

            "league_id": "nba",

            "season": game.get(
                "season"
            ),

            "home": {
                "id": home.get("id"),
                "name": home.get("full_name")
            },

            "away": {
                "id": away.get("id"),
                "name": away.get("full_name")
            },

            "raw": game
        })

    print(
        f"   📦 NBA: {len(result)} maç"
    )

    return result


# =========================================================
# NBA MAÇ SKORU
# =========================================================

def nba_score(game, team_id):

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
        return None

    if away_score is None:
        return None

    try:

        home_score = float(
            home_score
        )

        away_score = float(
            away_score
        )

    except:

        return None

    if str(
        home.get("id")
    ) == str(team_id):

        return {
            "home": True,
            "for": home_score,
            "against": away_score,
            "date": parse_date(
                game.get("date")
            )
        }

    if str(
        away.get("id")
    ) == str(team_id):

        return {
            "home": False,
            "for": away_score,
            "against": home_score,
            "date": parse_date(
                game.get("date")
            )
        }

    return None


# =========================================================
# NBA TAKIM GEÇMİŞİ
# =========================================================

def get_nba_team_history(
    team_id
):

    end_date = datetime.strptime(
        DATE,
        "%Y-%m-%d"
    )

    start_date = (
        end_date - timedelta(days=120)
    )

    data = get_json(
        NBA_URL,
        params={
            "team_ids[]": team_id,
            "start_date": start_date.strftime(
                "%Y-%m-%d"
            ),
            "end_date": end_date.strftime(
                "%Y-%m-%d"
            ),
            "per_page": 100
        },
        headers=HEADERS
    )

    games = data.get(
        "data",
        []
    )

    result = []

    for game in games:

        score = nba_score(
            game,
            team_id
        )

        if not score:
            continue

        # Henüz oynanmamış maçlar
        if score["for"] == 0 and score["against"] == 0:
            continue

        result.append(score)

    result.sort(
        key=lambda x: x.get("date") or "",
        reverse=True
    )

    return result


# =========================================================
# EUROLEAGUE SEZON MAÇLARI
# =========================================================

def get_euroleague_games():

    print()
    print(
        "🌍 EuroLeague maçları alınıyor..."
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
        f"   📦 Sezon maçları: "
        f"{len(games)}"
    )

    return games


# =========================================================
# EUROLEAGUE TAKIM ADI
# =========================================================

def euro_team_name(
    team
):

    return (
        team.get("name")
        or team.get("clubName")
        or team.get("nameShort")
        or team.get("code")
        or ""
    )


# =========================================================
# EUROLEAGUE ID
# =========================================================

def euro_team_id(
    team
):

    return (
        team.get("clubCode")
        or team.get("code")
        or team.get("id")
    )


# =========================================================
# EUROLEAGUE MAÇTAN TAKIM BİLGİSİ
# =========================================================

def euro_teams(game):

    local = (
        game.get("local")
        or game.get("home")
        or {}
    )

    road = (
        game.get("road")
        or game.get("away")
        or {}
    )

    return local, road


# =========================================================
# EUROLEAGUE MAÇ TARİHİ
# =========================================================

def euro_game_date(
    game
):

    for key in (
        "date",
        "gameDate",
        "startDate",
        "utcDate"
    ):

        value = game.get(key)

        if value:

            parsed = parse_date(
                value
            )

            if parsed:
                return parsed

    return None


# =========================================================
# EUROLEAGUE SKOR
# =========================================================

def euro_score(
    game,
    team_id
):

    local, road = euro_teams(
        game
    )

    local_id = str(
        euro_team_id(local)
    )

    road_id = str(
        euro_team_id(road)
    )

    target_id = str(
        team_id
    )

    # Farklı payload şekillerini destekle
    local_score = (
        local.get("score")
        or local.get("points")
        or local.get("scoreA")
    )

    road_score = (
        road.get("score")
        or road.get("points")
        or road.get("scoreB")
    )

    # Bazı cevaplarda skor doğrudan game içinde
    if local_score is None:

        local_score = (
            game.get("localScore")
            or game.get("homeScore")
        )

    if road_score is None:

        road_score = (
            game.get("roadScore")
            or game.get("awayScore")
        )

    try:

        local_score = float(
            local_score
        )

        road_score = float(
            road_score
        )

    except:

        return None

    if (
        local_id == target_id
    ):

        return {
            "home": True,
            "for": local_score,
            "against": road_score,
            "date": euro_game_date(
                game
            )
        }

    if (
        road_id == target_id
    ):

        return {
            "home": False,
            "for": road_score,
            "against": local_score,
            "date": euro_game_date(
                game
            )
        }

    return None


# =========================================================
# EUROLEAGUE TAKIM GEÇMİŞİ
# =========================================================

def get_euro_team_history(
    team_id,
    games
):

    result = []

    for game in games:

        item = euro_score(
            game,
            team_id
        )

        if not item:
            continue

        if not item.get("date"):
            continue

        # Bugünkü maç / gelecek maç
        if item["date"] >= DATE:
            continue

        result.append(item)

    result.sort(
        key=lambda x: x.get("date") or "",
        reverse=True
    )

    return result


# =========================================================
# SON 5 İÇ / DIŞ SAHA
# =========================================================

def last_5_home(
    history
):

    return [
        x
        for x in history
        if x["home"]
    ][:5]


def last_5_away(
    history
):

    return [
        x
        for x in history
        if not x["home"]
    ][:5]


# =========================================================
# GÜVEN
# =========================================================

def confidence_for(
    games
):

    values = {
        5: 85,
        4: 80,
        3: 75,
        2: 65,
        1: 55,
        0: 0
    }

    return values.get(
        games,
        0
    )


# =========================================================
# MAÇ ANALİZİ
# =========================================================

def analyse_game(
    game,
    euro_games=None
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
        f"\n   🔎 "
        f"{game['home']['name']} "
        f"- "
        f"{game['away']['name']}"
    )

    # -----------------------------------------------------
    # NBA
    # -----------------------------------------------------

    if league == "NBA":

        home_history = (
            get_nba_team_history(
                home_id
            )
        )

        away_history = (
            get_nba_team_history(
                away_id
            )
        )

    # -----------------------------------------------------
    # EUROLEAGUE
    # -----------------------------------------------------

    else:

        home_history = (
            get_euro_team_history(
                home_id,
                euro_games
            )
        )

        away_history = (
            get_euro_team_history(
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
        f"      🏠 Son iç saha: "
        f"{len(home_games)}"
    )

    print(
        f"      ✈️ Son dış saha: "
        f"{len(away_games)}"
    )

    if not home_games:
        print(
            "      ⚠️ Ev sahibi için "
            "iç saha geçmişi yok."
        )
        return None

    if not away_games:
        print(
            "      ⚠️ Deplasman takımı için "
            "dış saha geçmişi yok."
        )
        return None

    # -----------------------------------------------------
    # ORTALAMALAR
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # BEKLENEN SKOR
    # -----------------------------------------------------

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

    confidence = confidence_for(
        sample
    )

    print(
        f"      📊 Beklenen: "
        f"{expected_home:.1f} - "
        f"{expected_away:.1f}"
    )

    print(
        f"      📈 Toplam: "
        f"{match_total:.1f}"
    )

    print(
        f"      🎯 Güven: "
        f"%{confidence}"
    )

    return {

        "id": game.get("id"),

        "league": league,

        "league_id": game.get(
            "league_id"
        ),

        "season": game.get(
            "season"
        ),

        "home": game[
            "home"
        ]["name"],

        "away": game[
            "away"
        ]["name"],

        "home_team_id": home_id,

        "away_team_id": away_id,

        "games": sample,

        "home_for_avg": round(
            home_for,
            2
        ),

        "home_against_avg": round(
            home_against,
            2
        ),

        "away_for_avg": round(
            away_for,
            2
        ),

        "away_against_avg": round(
            away_against,
            2
        ),

        "exp_home": round(
            expected_home,
            2
        ),

        "exp_away": round(
            expected_away,
            2
        ),

        "match_total": round(
            match_total,
            2
        ),

        "quarter_avg": round(
            quarter_avg,
            2
        ),

        "first_half": round(
            first_half,
            2
        ),

        "q1": round(
            quarter_avg,
            2
        ),

        "q2": round(
            quarter_avg,
            2
        ),

        "q3": round(
            quarter_avg,
            2
        ),

        "q4": round(
            quarter_avg,
            2
        ),

        "confidence": confidence,

        "date": DATE
    }


# =========================================================
# EUROLEAGUE BUGÜNÜN MAÇLARI
# =========================================================

def get_euroleague_today():

    all_games = (
        get_euroleague_games()
    )

    result = []

    for game in all_games:

        if (
            euro_game_date(game)
            != DATE
        ):
            continue

        local, road = euro_teams(
            game
        )

        local_id = euro_team_id(
            local
        )

        road_id = euro_team_id(
            road
        )

        if not local_id:
            continue

        if not road_id:
            continue

        result.append({

            "id": game.get(
                "gameCode"
            ) or game.get(
                "id"
            ),

            "league":
                "EuroLeague",

            "league_id": "E",

            "season":
                EUROLEAGUE_SEASON,

            "home": {
                "id": local_id,
                "name": euro_team_name(
                    local
                )
            },

            "away": {
                "id": road_id,
                "name": euro_team_name(
                    road
                )
            },

            "raw": game
        })

    print(
        f"   📦 EuroLeague: "
        f"{len(result)} maç"
    )

    return result, all_games


# =========================================================
# ANA PROGRAM
# =========================================================

def main():

    print("=" * 55)
    print(
        "🏀 NBA + EUROLEAGUE "
        "BASKETBOL ANALİZİ"
    )
    print("=" * 55)

    print(
        f"📅 Tarih: {DATE}"
    )

    # -----------------------------------------------------
    # NBA
    # -----------------------------------------------------

    nba_games = (
        get_nba_games_for_date()
    )

    # -----------------------------------------------------
    # EUROLEAGUE
    # -----------------------------------------------------

    euro_today, euro_all = (
        get_euroleague_today()
    )

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

    for index, game in enumerate(
        all_games,
        1
    ):

        print(
            f"\n[{index}/{len(all_games)}] "
            f"{game['league']}"
        )

        try:

            result = analyse_game(
                game,
                euro_all
            )

            if result:

                results.append(
                    result
                )

        except Exception as e:

            print(
                f"      ❌ Hata: {e}"
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
    ) as file:

        json.dump(
            output,
            file,
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
