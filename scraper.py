
import os
import json
import time
from datetime import datetime
from statistics import mean

import requests


# ============================================================
# AYARLAR
# ============================================================

API_KEY = os.getenv("API_SPORTS_KEY")

API_BASE = "https://v1.basketball.api-sports.io"

DATA_FILE = "data.json"

TIMEZONE = "Europe/Istanbul"

LAST_GAMES = 5

REQUEST_DELAY = 0.25


# ============================================================
# API KONTROL
# ============================================================

if not API_KEY:
    raise RuntimeError(
        "API_SPORTS_KEY bulunamadı. "
        "GitHub Actions Secrets içine API_SPORTS_KEY ekleyin."
    )


HEADERS = {
    "x-apisports-key": API_KEY
}


# ============================================================
# CACHE
# ============================================================

TEAM_GAMES_CACHE = {}


# ============================================================
# METİN NORMALİZASYONU
# ============================================================

def normalize(text):

    if text is None:
        return ""

    text = str(text).strip().upper()

    replacements = {
        "İ": "I",
        "Ş": "S",
        "Ğ": "G",
        "Ü": "U",
        "Ö": "O",
        "Ç": "C",
        "Â": "A",
        "Ê": "E",
        "Î": "I",
        "Ô": "O",
        "Û": "U",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return " ".join(text.split())


# ============================================================
# API İSTEĞİ
# ============================================================

def api_get(endpoint, params=None):

    try:

        response = requests.get(
            API_BASE + endpoint,
            headers=HEADERS,
            params=params,
            timeout=30
        )

        remaining = response.headers.get(
            "x-ratelimit-requests-remaining"
        )

        if remaining is not None:
            print(
                f"   📊 Kalan API hakkı: {remaining}"
            )

        response.raise_for_status()

        data = response.json()

        time.sleep(REQUEST_DELAY)

        return data

    except requests.RequestException as e:

        print(
            f"   ❌ API hatası: {e}"
        )

        return None

    except ValueError:

        print(
            "   ❌ API geçerli JSON döndürmedi."
        )

        return None


# ============================================================
# LİG FİLTRESİ
# ============================================================

def is_allowed_league(league):

    if not league:
        return False

    name = normalize(
        league.get("name", "")
    )

    country = normalize(
        league.get("country", "")
    )

    # --------------------------------------------------------
    # NBA
    # --------------------------------------------------------

    if name == "NBA":
        return True

    # --------------------------------------------------------
    # EUROLEAGUE
    # --------------------------------------------------------

    if name in {
        "EUROLEAGUE",
        "EURO LEAGUE"
    }:
        return True

    # --------------------------------------------------------
    # TÜRKİYE BSL
    # --------------------------------------------------------

    turkey = country in {
        "TURKEY",
        "TURKIYE"
    }

    bsl_name = name in {
        "BSL",
        "TBSL",
        "SUPER LIG",
        "SUPER LIGI",
        "TURKEY BSL",
        "TURKEY - BSL",
        "TURKIYE BSL"
    }

    if turkey and bsl_name:
        return True

    return False


# ============================================================
# BUGÜNÜN MAÇLARI
# ============================================================

def fetch_today_games():

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    print()
    print(
        "📡 Bugünün basketbol maçları alınıyor..."
    )

    data = api_get(
        "/games",
        {
            "date": today,
            "timezone": TIMEZONE
        }
    )

    if not data:
        return []

    response = data.get(
        "response",
        []
    )

    print(
        f"📦 API toplam "
        f"{len(response)} maç döndürdü."
    )

    games = []

    for game in response:

        league = game.get(
            "league"
        ) or {}

        if not is_allowed_league(
            league
        ):
            continue

        teams = game.get(
            "teams"
        ) or {}

        home = teams.get(
            "home"
        ) or {}

        away = teams.get(
            "away"
        ) or {}

        if not home.get("id"):
            continue

        if not away.get("id"):
            continue

        status = game.get(
            "status"
        ) or {}

        status_short = normalize(
            status.get("short", "")
        )

        # Tamamlanmış / iptal edilmiş maçları
        # bugünün analizine alma.

        if status_short in {
            "FT",
            "AOT",
            "CANC",
            "ABD",
            "AWD",
            "POST",
            "PST"
        }:
            continue

        games.append({
            "id": game.get("id"),

            "date": game.get("date"),

            "timestamp": game.get(
                "timestamp"
            ),

            "league": league.get(
                "name"
            ),

            "country": league.get(
                "country"
            ),

            "league_id": league.get(
                "id"
            ),

            "home": {
                "id": home.get("id"),
                "name": home.get("name"),
                "logo": home.get("logo")
            },

            "away": {
                "id": away.get("id"),
                "name": away.get("name"),
                "logo": away.get("logo")
            },

            "status": status_short
        })

    return games


# ============================================================
# TAKIM GEÇMİŞİ
# ============================================================

def get_team_games(team_id):

    if team_id in TEAM_GAMES_CACHE:
        return TEAM_GAMES_CACHE[team_id]

    print(
        f"   🔎 Takım geçmişi: {team_id}"
    )

    data = api_get(
        "/games",
        {
            "team": team_id,
            "last": 20
        }
    )

    if not data:
        TEAM_GAMES_CACHE[team_id] = []
        return []

    games = data.get(
        "response",
        []
    ) or []

    print(
        f"   📦 {len(games)} geçmiş maç bulundu"
    )

    TEAM_GAMES_CACHE[team_id] = games

    return games


# ============================================================
# MAÇ TAMAMLANMIŞ MI?
# ============================================================

def is_finished(game):

    status = game.get(
        "status"
    ) or {}

    value = normalize(
        status.get("short", "")
    )

    return value in {
        "FT",
        "AOT"
    }


# ============================================================
# SKORLAR
# ============================================================

def get_scores(game):

    scores = game.get(
        "scores"
    ) or {}

    home = scores.get(
        "home"
    )

    away = scores.get(
        "away"
    )

    if isinstance(home, dict):
        home = home.get(
            "total"
        )

    if isinstance(away, dict):
        away = away.get(
            "total"
        )

    try:
        home = int(home)
        away = int(away)
    except:
        return None, None

    return home, away


# ============================================================
# SON 5 EV MAÇI
# ============================================================

def get_last_home_games(team_id):

    games = get_team_games(
        team_id
    )

    result = []

    for game in games:

        if not is_finished(game):
            continue

        teams = game.get(
            "teams"
        ) or {}

        home = teams.get(
            "home"
        ) or {}

        if str(
            home.get("id")
        ) != str(team_id):
            continue

        home_score, away_score = get_scores(
            game
        )

        if home_score is None:
            continue

        if away_score is None:
            continue

        result.append({
            "date": (
                game.get("date")
                or ""
            )[:10],

            "points_for": home_score,

            "points_against": away_score
        })

    result.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    return result[:LAST_GAMES]


# ============================================================
# SON 5 DEPLASMAN MAÇI
# ============================================================

def get_last_away_games(team_id):

    games = get_team_games(
        team_id
    )

    result = []

    for game in games:

        if not is_finished(game):
            continue

        teams = game.get(
            "teams"
        ) or {}

        away = teams.get(
            "away"
        ) or {}

        if str(
            away.get("id")
        ) != str(team_id):
            continue

        home_score, away_score = get_scores(
            game
        )

        if home_score is None:
            continue

        if away_score is None:
            continue

        result.append({
            "date": (
                game.get("date")
                or ""
            )[:10],

            "points_for": away_score,

            "points_against": home_score
        })

    result.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    return result[:LAST_GAMES]


# ============================================================
# GÜVEN
# ============================================================

def calculate_confidence(count):

    if count >= 5:
        return 85

    if count == 4:
        return 80

    if count == 3:
        return 75

    if count == 2:
        return 65

    if count == 1:
        return 55

    return 0


# ============================================================
# MAÇ ANALİZİ
# ============================================================

def analyze_game(game):

    home = game["home"]
    away = game["away"]

    print()
    print(
        f"🏀 {home['name']} - "
        f"{away['name']}"
    )

    print(
        f"   🏆 {game['league']}"
    )

    home_games = get_last_home_games(
        home["id"]
    )

    print(
        f"   🏠 Son 5 ev maçı: "
        f"{len(home_games)}"
    )

    away_games = get_last_away_games(
        away["id"]
    )

    print(
        f"   ✈️ Son 5 deplasman maçı: "
        f"{len(away_games)}"
    )

    if not home_games:
        print(
            "   ⚠️ Ev sahibi geçmişi yok."
        )
        return None

    if not away_games:
        print(
            "   ⚠️ Deplasman geçmişi yok."
        )
        return None

    # --------------------------------------------------------
    # ORTALAMALAR
    # --------------------------------------------------------

    home_for = mean(
        x["points_for"]
        for x in home_games
    )

    home_against = mean(
        x["points_against"]
        for x in home_games
    )

    away_for = mean(
        x["points_for"]
        for x in away_games
    )

    away_against = mean(
        x["points_against"]
        for x in away_games
    )

    # --------------------------------------------------------
    # BEKLENEN SKOR
    # --------------------------------------------------------

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

    first_half = (
        match_total / 2
    )

    quarter_avg = (
        match_total / 4
    )

    games = min(
        len(home_games),
        len(away_games)
    )

    confidence = calculate_confidence(
        games
    )

    print(
        f"   📈 Beklenen skor: "
        f"{expected_home:.1f} - "
        f"{expected_away:.1f}"
    )

    print(
        f"   🏀 Maç toplamı: "
        f"{match_total:.1f}"
    )

    print(
        f"   ⏱️ İlk yarı: "
        f"{first_half:.1f}"
    )

    print(
        f"   📊 Çeyrek ortalaması: "
        f"{quarter_avg:.1f}"
    )

    print(
        f"   🎯 Güven: "
        f"%{confidence}"
    )

    return {
        "id": game["id"],

        "date": game["date"],

        "league": game["league"],

        "country": game["country"],

        "home": home,

        "away": away,

        "status": game["status"],

        "expected_home": round(
            expected_home,
            2
        ),

        "expected_away": round(
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

        "games": games,

        "confidence": confidence
    }


# ============================================================
# DATA.JSON OKU
# ============================================================

def load_data():

    if not os.path.exists(
        DATA_FILE
    ):
        return {}

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, dict):
            return data

    except Exception as e:

        print(
            f"⚠️ data.json okunamadı: {e}"
        )

    return {}


# ============================================================
# DATA.JSON KAYDET
# ============================================================

def save_data(data):

    with open(
        DATA_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# ANA PROGRAM
# ============================================================

def main():

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    print()
    print("=" * 65)
    print("🏀 BASKETBOL ANALİZ SİSTEMİ")
    print("=" * 65)
    print(
        f"📅 Tarih: {today}"
    )
    print(
        "🏆 Ligler: NBA + EuroLeague + Türkiye BSL"
    )
    print(
        "🏠 Ev sahibi: Son 5 ev maçı"
    )
    print(
        "✈️ Deplasman: Son 5 deplasman maçı"
    )
    print("=" * 65)

    games = fetch_today_games()

    print()
    print(
        f"🎯 Uygun liglerden maç: "
        f"{len(games)}"
    )

    if not games:

        print(
            "⚠️ Bugün NBA, EuroLeague "
            "veya Türkiye BSL maçı bulunamadı."
        )

        # Bugünün kaydını boş olarak tut.
        data = load_data()

        data[today] = []

        save_data(data)

        return

    print(
        f"📊 Analiz edilecek maç: "
        f"{len(games)}"
    )

    results = []

    for index, game in enumerate(
        games,
        start=1
    ):

        print()
        print(
            f"[{index}/{len(games)}]"
        )

        result = analyze_game(
            game
        )

        if result:
            results.append(
                result
            )

    # --------------------------------------------------------
    # DATA.JSON
    # --------------------------------------------------------

    data = load_data()

    data[today] = results

    save_data(data)

    print()
    print("=" * 65)

    if results:

        print(
            f"✅ {len(results)} maç analiz edildi."
        )

    else:

        print(
            "⚠️ Analiz üretilebilen maç yok."
        )

    print(
        f"💾 data.json → {today}"
    )

    print("=" * 65)


# ============================================================
# ÇALIŞTIR
# ============================================================

if __name__ == "__main__":
    main()
