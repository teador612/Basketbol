import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


# =========================================================
# AYARLAR
# =========================================================

API_KEY = os.getenv("API_SPORTS_KEY")

API_BASE = "https://v1.basketball.api-sports.io"

DATA_FILE = "data.json"

TIMEZONE = "Europe/Istanbul"

REQUEST_TIMEOUT = 20

LAST_HOME_AWAY_GAMES = 5

REQUEST_DELAY = 0.25

# API kotasını koru
MIN_REMAINING_REQUESTS = 5


# =========================================================
# SADECE İSTEDİĞİMİZ LİGLER
# =========================================================
#
# API-Basketball league ID'leri
#
# NBA          = 12
# EuroLeague   = 120
# Türkiye BSL  = 40
#
# Not:
# API'deki ID farklılıklarını önlemek için aşağıdaki
# isim kontrolü de ayrıca yapılmaktadır.
#

ALLOWED_LEAGUE_IDS = {
    12,    # NBA
    120,   # EuroLeague
    40     # Türkiye BSL
}


ALLOWED_LEAGUE_NAMES = {
    "NBA",
    "Euroleague",
    "EuroLeague",
    "BSL",
    "TBSL",
    "Super Lig",
    "Super Ligi"
}


# =========================================================
# API KONTROL
# =========================================================

if not API_KEY:

    raise RuntimeError(
        "API_SPORTS_KEY bulunamadı. "
        "GitHub Actions Secrets içine "
        "API_SPORTS_KEY ekleyin."
    )


HEADERS = {
    "x-apisports-key": API_KEY
}


SESSION = requests.Session()

SESSION.headers.update(
    HEADERS
)


DAILY_REMAINING = None


# Aynı takımın geçmişini aynı çalışma içinde
# tekrar tekrar API'den çekmemek için
TEAM_CACHE = {}


# =========================================================
# TARİH
# =========================================================

def now_tr():

    return datetime.now(
        ZoneInfo(TIMEZONE)
    )


def get_today():

    return now_tr().strftime(
        "%Y-%m-%d"
    )


# =========================================================
# API
# =========================================================

def get_json(
    endpoint,
    params=None
):

    global DAILY_REMAINING

    url = f"{API_BASE}/{endpoint}"

    try:

        response = SESSION.get(
            url,
            params=params or {},
            timeout=REQUEST_TIMEOUT
        )

        remaining = response.headers.get(
            "x-ratelimit-requests-remaining"
        )

        if remaining is not None:

            try:

                DAILY_REMAINING = int(
                    remaining
                )

                print(
                    f"   📊 Kalan API hakkı: "
                    f"{DAILY_REMAINING}"
                )

            except Exception:
                pass


        if response.status_code == 429:

            print(
                "   🛑 API rate limit: 429"
            )

            return None


        if response.status_code != 200:

            print(
                f"   ❌ HTTP "
                f"{response.status_code}"
            )

            try:

                print(
                    response.text[:500]
                )

            except Exception:
                pass

            return None


        return response.json()


    except requests.RequestException as e:

        print(
            f"   ❌ API bağlantı hatası: "
            f"{e}"
        )

        return None


# =========================================================
# KOTA
# =========================================================

def can_make_request():

    if DAILY_REMAINING is None:

        return True


    if DAILY_REMAINING <= MIN_REMAINING_REQUESTS:

        print(
            f"🛑 API kotası korunuyor. "
            f"Kalan: {DAILY_REMAINING}"
        )

        return False


    return True


# =========================================================
# DATA.JSON OKU
# =========================================================

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


        return {}


    except Exception as e:

        print(
            f"⚠️ data.json okunamadı: "
            f"{e}"
        )

        return {}


# =========================================================
# DATA.JSON KAYDET
# =========================================================

def save_data(data):

    temp_file = (
        DATA_FILE + ".tmp"
    )


    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


    os.replace(
        temp_file,
        DATA_FILE
    )


# =========================================================
# LİG KONTROLÜ
# =========================================================

def is_allowed_league(
    game
):

    league = game.get(
        "league",
        {}
    )

    league_id = league.get(
        "id"
    )

    league_name = str(
        league.get(
            "name",
            ""
        )
    ).strip()


    # Önce ID kontrolü
    if league_id in ALLOWED_LEAGUE_IDS:

        return True


    # İsim kontrolü
    if league_name in ALLOWED_LEAGUE_NAMES:

        return True


    return False


# =========================================================
# TAKIM GEÇMİŞİ
# =========================================================

def get_team_games(
    team_id
):

    team_key = str(
        team_id
    )


    if team_key in TEAM_CACHE:

        return TEAM_CACHE[
            team_key
        ]


    if not can_make_request():

        return []


    print(
        f"   🔎 Takım geçmişi: "
        f"{team_id}"
    )


    data = get_json(
        "games",
        params={
            "team": team_id
        }
    )


    if not data:

        TEAM_CACHE[
            team_key
        ] = []

        return []


    games = data.get(
        "response",
        []
    )


    TEAM_CACHE[
        team_key
    ] = games


    time.sleep(
        REQUEST_DELAY
    )


    print(
        f"   📦 {len(games)} "
        f"geçmiş maç bulundu"
    )


    return games


# =========================================================
# SON 5 EV MAÇI
# =========================================================

def get_last_home_games(
    team_id
):

    games = get_team_games(
        team_id
    )


    result = []


    for game in games:

        status = (
            game
            .get("status", {})
            .get("short")
        )


        # Sadece tamamlanmış maçlar
        if status not in (
            "FT",
            "AOT"
        ):

            continue


        teams = game.get(
            "teams",
            {}
        )


        home = teams.get(
            "home",
            {}
        )


        away = teams.get(
            "away",
            {}
        )


        scores = game.get(
            "scores",
            {}
        )


        home_score = (
            scores
            .get("home", {})
            .get("total")
        )


        away_score = (
            scores
            .get("away", {})
            .get("total")
        )


        # Takım ev sahibi olmalı
        if str(
            home.get("id")
        ) != str(team_id):

            continue


        if (
            home_score is None
            or away_score is None
        ):

            continue


        result.append({

            "date":
                game.get(
                    "date",
                    {}
                ).get(
                    "start"
                ),

            "points_for":
                float(
                    home_score
                ),

            "points_against":
                float(
                    away_score
                )

        })


    # En yeni maçtan eskiye
    result.sort(
        key=lambda x:
            x["date"] or "",
        reverse=True
    )


    return result[
        :LAST_HOME_AWAY_GAMES
    ]


# =========================================================
# SON 5 DEPLASMAN MAÇI
# =========================================================

def get_last_away_games(
    team_id
):

    games = get_team_games(
        team_id
    )


    result = []


    for game in games:

        status = (
            game
            .get("status", {})
            .get("short")
        )


        if status not in (
            "FT",
            "AOT"
        ):

            continue


        teams = game.get(
            "teams",
            {}
        )


        home = teams.get(
            "home",
            {}
        )


        away = teams.get(
            "away",
            {}
        )


        scores = game.get(
            "scores",
            {}
        )


        home_score = (
            scores
            .get("home", {})
            .get("total")
        )


        away_score = (
            scores
            .get("away", {})
            .get("total")
        )


        # Takım deplasman takımı olmalı
        if str(
            away.get("id")
        ) != str(team_id):

            continue


        if (
            home_score is None
            or away_score is None
        ):

            continue


        result.append({

            "date":
                game.get(
                    "date",
                    {}
                ).get(
                    "start"
                ),

            "points_for":
                float(
                    away_score
                ),

            "points_against":
                float(
                    home_score
                )

        })


    result.sort(
        key=lambda x:
            x["date"] or "",
        reverse=True
    )


    return result[
        :LAST_HOME_AWAY_GAMES
    ]


# =========================================================
# ORTALAMA
# =========================================================

def calculate_average(
    games
):

    if not games:

        return {
            "points_for": 0.0,
            "points_against": 0.0,
            "games": 0
        }


    points_for = [

        game["points_for"]

        for game in games

    ]


    points_against = [

        game["points_against"]

        for game in games

    ]


    return {

        "points_for":
            sum(points_for)
            / len(points_for),

        "points_against":
            sum(points_against)
            / len(points_against),

        "games":
            len(games)

    }


# =========================================================
# ANALİZ
# =========================================================

def calculate_analysis(
    home_stats,
    away_stats
):

    # Ev sahibinin evde attığı
    home_attack = (
        home_stats["points_for"]
    )


    # Ev sahibinin evde yediği
    home_defense = (
        home_stats["points_against"]
    )


    # Deplasmanın deplasmanda attığı
    away_attack = (
        away_stats["points_for"]
    )


    # Deplasmanın deplasmanda yediği
    away_defense = (
        away_stats["points_against"]
    )


    # Beklenen ev sahibi sayısı
    expected_home = (
        home_attack
        + away_defense
    ) / 2


    # Beklenen deplasman sayısı
    expected_away = (
        away_attack
        + home_defense
    ) / 2


    # Maç toplamı
    match_total = (
        expected_home
        + expected_away
    )


    # Çeyrek ortalaması
    quarter_average = (
        match_total / 4
    )


    # İlk yarı
    first_half = (
        match_total / 2
    )


    # Kullanılan örneklem
    games_used = min(
        home_stats["games"],
        away_stats["games"]
    )


    # Veri yeterliliğine göre
    # güven seviyesi
    if games_used >= 5:

        confidence = 85.0

    elif games_used == 4:

        confidence = 80.0

    elif games_used == 3:

        confidence = 75.0

    elif games_used == 2:

        confidence = 65.0

    elif games_used == 1:

        confidence = 55.0

    else:

        confidence = 0.0


    return {

        "q1":
            round(
                quarter_average,
                1
            ),

        "q2":
            round(
                quarter_average,
                1
            ),

        "q3":
            round(
                quarter_average,
                1
            ),

        "q4":
            round(
                quarter_average,
                1
            ),

        "first_half":
            round(
                first_half,
                1
            ),

        "match_total":
            round(
                match_total,
                1
            ),

        "exp_home":
            round(
                expected_home,
                1
            ),

        "exp_away":
            round(
                expected_away,
                1
            ),

        "games":
            games_used,

        "confidence":
            confidence

    }


# =========================================================
# SAAT
# =========================================================

def format_game_time(
    game
):

    game_date = (
        game
        .get("date", {})
        .get("start")
    )


    if not game_date:

        return "--:--"


    try:

        dt = datetime.fromisoformat(
            game_date.replace(
                "Z",
                "+00:00"
            )
        )


        dt_tr = dt.astimezone(
            ZoneInfo(TIMEZONE)
        )


        return dt_tr.strftime(
            "%H:%M"
        )


    except Exception:

        return "--:--"


# =========================================================
# BUGÜNÜN MAÇLARI
# =========================================================

def fetch_today_games():

    today = get_today()


    print("")
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


    # -----------------------------------------------------
    # BUGÜNÜN TÜM MAÇLARI
    # -----------------------------------------------------

    if not can_make_request():

        print(
            "❌ API kotası yetersiz."
        )

        return


    data = get_json(
        "games",
        params={
            "date": today,
            "timezone": TIMEZONE
        }
    )


    if not data:

        print(
            "❌ Günün maçları alınamadı."
        )

        return


    all_games = data.get(
        "response",
        []
    )


    print(
        f"📦 API toplam "
        f"{len(all_games)} maç döndürdü."
    )


    # -----------------------------------------------------
    # SADECE İSTEDİĞİMİZ LİGLER
    # -----------------------------------------------------

    selected_games = []


    for game in all_games:

        if not is_allowed_league(
            game
        ):

            continue


        selected_games.append(
            game
        )


    print(
        f"🎯 NBA + EuroLeague + BSL: "
        f"{len(selected_games)} maç"
    )


    # -----------------------------------------------------
    # SADECE ANALİZ EDİLEBİLECEK DURUMLAR
    # -----------------------------------------------------

    valid_games = []


    for game in selected_games:

        status = (
            game
            .get("status", {})
            .get("short")
        )


        if status in (
            "NS",
            "1Q",
            "2Q",
            "HT",
            "3Q",
            "4Q",
            "OT"
        ):

            valid_games.append(
                game
            )


    print(
        f"📊 Analiz edilecek maç: "
        f"{len(valid_games)}"
    )


    if not valid_games:

        print(
            "ℹ️ Bugün analiz edilecek "
            "maç yok."
        )

        return


    analyzed_matches = []


    # -----------------------------------------------------
    # MAÇLAR
    # -----------------------------------------------------

    for index, game in enumerate(
        valid_games,
        start=1
    ):

        teams = game.get(
            "teams",
            {}
        )


        home = teams.get(
            "home",
            {}
        )


        away = teams.get(
            "away",
            {}
        )


        home_id = home.get(
            "id"
        )


        away_id = away.get(
            "id"
        )


        if not home_id or not away_id:

            continue


        home_name = home.get(
            "name",
            "Ev Sahibi"
        )


        away_name = away.get(
            "name",
            "Deplasman"
        )


        league = game.get(
            "league",
            {}
        )


        league_name = league.get(
            "name",
            "Basketbol"
        )


        country_name = league.get(
            "country",
            ""
        )


        print("")
        print(
            f"[{index}/{len(valid_games)}] "
            f"{home_name} - {away_name}"
        )


        print(
            f"   🏆 {league_name}"
        )


        # -------------------------------------------------
        # EV SAHİBİNİN SON 5 EV MAÇI
        # -------------------------------------------------

        home_games = get_last_home_games(
            home_id
        )


        print(
            f"   🏠 Son 5 ev maçı: "
            f"{len(home_games)}"
        )


        # -------------------------------------------------
        # DEPLASMANIN SON 5 DEPLASMAN MAÇI
        # -------------------------------------------------

        away_games = get_last_away_games(
            away_id
        )


        print(
            f"   ✈️ Son 5 deplasman maçı: "
            f"{len(away_games)}"
        )


        # İki tarafın da geçmişi
        # yoksa tahmin üretme
        if (
            not home_games
            or not away_games
        ):

            print(
                "   ⚠️ Yeterli veri yok."
            )

            continue


        home_stats = calculate_average(
            home_games
        )


        away_stats = calculate_average(
            away_games
        )


        analysis = calculate_analysis(
            home_stats,
            away_stats
        )


        time_str = format_game_time(
            game
        )


        league_display = league_name


        if country_name:

            league_display = (
                f"{country_name} - "
                f"{league_name}"
            )


        analyzed_matches.append({

            "id":
                f"m_{game.get('id')}",

            "gameId":
                game.get("id"),

            "league":
                league_display,

            "time":
                time_str,

            "home":
                home_name,

            "away":
                away_name,

            "homeTeamId":
                home_id,

            "awayTeamId":
                away_id,

            "analysis":
                analysis

        })


        print(
            f"   📈 Beklenen skor: "
            f"{analysis['exp_home']} - "
            f"{analysis['exp_away']}"
        )


        print(
            f"   🔢 Maç toplamı: "
            f"{analysis['match_total']}"
        )


        print(
            f"   📊 Örneklem: "
            f"{analysis['games']} + "
            f"{analysis['games']}"
        )


    # -----------------------------------------------------
    # KAYDET
    # -----------------------------------------------------

    if not analyzed_matches:

        print("")
        print(
            "⚠️ Analiz üretilebilen maç yok."
        )

        return


    existing_data = load_existing_data()


    # Eski tarihler korunur
    existing_data[
        today
    ] = analyzed_matches


    save_data(
        existing_data
    )


    print("")
    print("=" * 65)
    print(
        f"✅ {len(analyzed_matches)} maç "
        f"data.json'a kaydedildi."
    )


    if DAILY_REMAINING is not None:

        print(
            f"📊 Kalan API hakkı: "
            f"{DAILY_REMAINING}"
        )


    print("=" * 65)


# =========================================================
# ÇALIŞTIR
# =========================================================

if __name__ == "__main__":

    fetch_today_games()
