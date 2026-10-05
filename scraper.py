import os
import json
import time
from datetime import datetime, timedelta
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
# KONTROL
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
# SADECE BU LİGLER
# ============================================================

ALLOWED_LEAGUES = {
    "NBA",
    "EUROLEAGUE",
    "EURO LEAGUE",
    "BASKETBALL EUROLEAGUE",
    "TURKIYE BSL",
    "TURKEY BSL",
    "BSL",
    "TBSL",
    "SUPER LIG",
    "SUPER LIGI",
    "TURKEY - BSL",
    "TÜRKIYE BSL",
}


# ============================================================
# CACHE
# ============================================================

TEAM_GAMES_CACHE = {}

LEAGUE_CACHE = {}


# ============================================================
# YARDIMCI
# ============================================================

def normalize(text):
    if text is None:
        return ""

    text = str(text).strip().upper()

    replacements = {
        "İ": "I",
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


def is_allowed_league(league):
    if not league:
        return False

    name = normalize(
        league.get("name")
        or league.get("league")
        or ""
    )

    country = normalize(
        league.get("country")
        or ""
    )

    # --------------------------------------------------------
    # NBA
    # --------------------------------------------------------

    if name == "NBA":
        return True

    # --------------------------------------------------------
    # EUROLEAGUE
    # --------------------------------------------------------

    compact = name.replace(" ", "")

    if compact == "EUROLEAGUE":
        return True

    # --------------------------------------------------------
    # TÜRKİYE BSL
    # --------------------------------------------------------

    if (
        name in {
            "BSL",
            "TBSL",
            "SUPER LIG",
            "SUPER LIGI",
            "TURKEY BSL",
            "TURKIYE BSL",
            "TURKEY - BSL",
        }
        and (
            "TURKEY" in country
            or "TURKIYE" in country
            or "TÜRKIYE" in country
            or country == ""
        )
    ):
        return True

    return False


def safe_int(value):
    try:
        return int(value)
    except Exception:
        return None


# ============================================================
# API
# ============================================================

def api_get(endpoint, params=None):
    url = API_BASE + endpoint

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=30
        )

        remaining = response.headers.get(
            "x-ratelimit-requests-remaining"
        )

        if remaining is not None:
            print(f"   📊 Kalan API hakkı: {remaining}")

        response.raise_for_status()

        data = response.json()

        time.sleep(REQUEST_DELAY)

        return data

    except requests.RequestException as e:
        print(f"   ❌ API hatası: {e}")
        return None

    except ValueError:
        print("   ❌ API geçerli JSON döndürmedi.")
        return None


# ============================================================
# BUGÜNÜN MAÇLARI
# ============================================================

def fetch_today_games():

    today = datetime.now().strftime("%Y-%m-%d")

    print()
    print("📡 Bugünün basketbol maçları alınıyor...")

    data = api_get(
        "/games",
        {
            "date": today,
            "timezone": TIMEZONE
        }
    )

    if not data:
        return []

    response = data.get("response", [])

    print(f"📦 API toplam {len(response)} maç döndürdü.")

    allowed = []

    for game in response:

        league = game.get("league") or {}

        league_name = league.get("name", "")
        country = league.get("country", "")

        if not is_allowed_league(league):
            continue

        teams = game.get("teams") or {}

        home = teams.get("home") or {}
        away = teams.get("away") or {}

        if not home.get("id") or not away.get("id"):
            continue

        status = game.get("status") or {}

        status_short = str(
            status.get("short") or ""
        ).upper()

        # Tamamlanmış eski maçları bugünkü analizden çıkar.
        if status_short in {
            "FT",
            "AOT",
            "CANC",
            "ABD",
            "AWD",
            "POST",
            "PST",
        }:
            continue

        allowed.append({
            "id": game.get("id"),

            "date": game.get("date"),

            "timestamp": game.get("timestamp"),

            "timezone": game.get("timezone"),

            "league_id": league.get("id"),

            "league": league_name,

            "country": country,

            "home": {
                "id": home.get("id"),
                "name": home.get("name"),
                "logo": home.get("logo"),
            },

            "away": {
                "id": away.get("id"),
                "name": away.get("name"),
                "logo": away.get("logo"),
            },

            "status": status_short,
        })

    return allowed


# ============================================================
# TAKIM MAÇLARI
# ============================================================

def get_team_games(team_id):

    if team_id in TEAM_GAMES_CACHE:
        return TEAM_GAMES_CACHE[team_id]

    print(f"   🔎 Takım geçmişi: {team_id}")

    # --------------------------------------------------------
    # Önce team endpoint
    # --------------------------------------------------------

    data = api_get(
        "/games",
        {
            "team": team_id,
            "last": 100
        }
    )

    games = []

    if data:
        games = data.get("response", []) or []

    print(f"   📦 {len(games)} geçmiş maç bulundu.")

    # --------------------------------------------------------
    # API team= bazen boş dönebiliyor.
    # Bu durumda son günleri tarıyoruz.
    # --------------------------------------------------------

    if not games:

        print("   🔄 Alternatif geçmiş maç araması başlıyor...")

        found = {}

        today = datetime.now()

        # Son 120 gün
        for i in range(0, 120):

            day = today - timedelta(days=i)

            date_string = day.strftime("%Y-%m-%d")

            data = api_get(
                "/games",
                {
                    "date": date_string,
                    "timezone": TIMEZONE
                }
            )

            if not data:
                continue

            for game in data.get("response", []) or []:

                teams = game.get("teams") or {}

                home = teams.get("home") or {}
                away = teams.get("away") or {}

                if (
                    str(home.get("id")) == str(team_id)
                    or
                    str(away.get("id")) == str(team_id)
                ):
                    found[str(game.get("id"))] = game

            if len(found) >= 15:
                break

        games = list(found.values())

        print(
            f"   📦 Alternatif aramada "
            f"{len(games)} maç bulundu."
        )

    TEAM_GAMES_CACHE[team_id] = games

    return games


# ============================================================
# MAÇ TAMAMLANDI MI?
# ============================================================

def is_finished(game):

    status = game.get("status") or {}

    short = str(
        status.get("short") or ""
    ).upper()

    return short in {
        "FT",
        "AOT"
    }


# ============================================================
# TARİH
# ============================================================

def game_date(game):

    value = game.get("date")

    if not value:
        return ""

    try:
        return value[:10]
    except Exception:
        return ""


# ============================================================
# SKOR
# ============================================================

def get_scores(game):

    scores = game.get("scores") or {}

    home_score = scores.get("home")
    away_score = scores.get("away")

    if isinstance(home_score, dict):
        home_score = home_score.get("total")

    if isinstance(away_score, dict):
        away_score = away_score.get("total")

    home_score = safe_int(home_score)
    away_score = safe_int(away_score)

    if home_score is None or away_score is None:
        return None, None

    return home_score, away_score


# ============================================================
# SON 5 EV MAÇI
# ============================================================

def get_last_home_games(team_id):

    games = get_team_games(team_id)

    result = []

    for game in games:

        if not is_finished(game):
            continue

        teams = game.get("teams") or {}

        home = teams.get("home") or {}

        if str(home.get("id")) != str(team_id):
            continue

        home_score, away_score = get_scores(game)

        if home_score is None or away_score is None:
            continue

        result.append({
            "date": game_date(game),
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

    games = get_team_games(team_id)

    result = []

    for game in games:

        if not is_finished(game):
            continue

        teams = game.get("teams") or {}

        away = teams.get("away") or {}

        if str(away.get("id")) != str(team_id):
            continue

        home_score, away_score = get_scores(game)

        if home_score is None or away_score is None:
            continue

        result.append({
            "date": game_date(game),
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

def calculate_confidence(sample_count):

    if sample_count >= 5:
        return 85

    if sample_count == 4:
        return 80

    if sample_count == 3:
        return 75

    if sample_count == 2:
        return 65

    if sample_count == 1:
        return 55

    return 0


# ============================================================
# MAÇ ANALİZİ
# ============================================================

def analyze_game(game):

    home = game["home"]
    away = game["away"]

    home_id = home["id"]
    away_id = away["id"]

    print()
    print(
        f"[ANALİZ] {home['name']} - {away['name']}"
    )

    print(
        f"   🏆 {game['league']} "
        f"({game['country']})"
    )

    # --------------------------------------------------------
    # HOME
    # --------------------------------------------------------

    home_games = get_last_home_games(home_id)

    print(
        f"   🏠 Son {LAST_GAMES} ev maçı: "
        f"{len(home_games)}"
    )

    # --------------------------------------------------------
    # AWAY
    # --------------------------------------------------------

    away_games = get_last_away_games(away_id)

    print(
        f"   ✈️ Son {LAST_GAMES} deplasman maçı: "
        f"{len(away_games)}"
    )

    if not home_games or not away_games:

        print("   ⚠️ Yeterli veri yok.")

        return None

    # --------------------------------------------------------
    # ORTALAMALAR
    # --------------------------------------------------------

    home_for_avg = mean(
        x["points_for"]
        for x in home_games
    )

    home_against_avg = mean(
        x["points_against"]
        for x in home_games
    )

    away_for_avg = mean(
        x["points_for"]
        for x in away_games
    )

    away_against_avg = mean(
        x["points_against"]
        for x in away_games
    )

    # --------------------------------------------------------
    # BEKLENEN SKOR
    # --------------------------------------------------------

    expected_home = (
        home_for_avg +
        away_against_avg
    ) / 2

    expected_away = (
        away_for_avg +
        home_against_avg
    ) / 2

    match_total = (
        expected_home +
        expected_away
    )

    quarter_avg = match_total / 4

    first_half = match_total / 2

    sample_count = min(
        len(home_games),
        len(away_games)
    )

    confidence = calculate_confidence(
        sample_count
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

        "games": sample_count,

        "confidence": confidence,

        "home_sample": home_games,

        "away_sample": away_games
    }


# ============================================================
# DATA.JSON
# ============================================================

def load_existing_data():

    if not os.path.exists(DATA_FILE):
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
# ANA
# ============================================================

def main():

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    print()
    print("=" * 65)
    print("🏀 BASKETBOL ANALİZ SİSTEMİ")
    print("=" * 65)
    print(f"📅 Tarih: {today}")
    print(
        "🏆 Ligler: "
        "NBA + EuroLeague + Türkiye BSL"
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
        f"🎯 NBA + EuroLeague + BSL: "
        f"{len(games)} maç"
    )

    if not games:

        print(
            "⚠️ Bugün analiz edilecek "
            "uygun maç bulunamadı."
        )

        return

    results = []

    print(
        f"📊 Analiz edilecek maç: "
        f"{len(games)}"
    )

    for index, game in enumerate(
        games,
        start=1
    ):

        print()
        print(
            f"[{index}/{len(games)}] "
            f"{game['home']['name']} - "
            f"{game['away']['name']}"
        )

        result = analyze_game(game)

        if result:
            results.append(result)

    print()
    print("=" * 65)
    print(
        f"✅ Analiz tamamlandı: "
        f"{len(results)} maç"
    )
    print("=" * 65)

    existing = load_existing_data()

    existing[today] = results

    save_data(existing)

    print(
        f"💾 data.json güncellendi: "
        f"{today}"
    )


if __name__ == "__main__":
    main()
