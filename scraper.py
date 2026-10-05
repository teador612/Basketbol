import os
import json
import time
from datetime import datetime
from urllib.parse import urlencode

import requests


# ============================================================
# AYARLAR
# ============================================================

API_KEY = os.getenv("API_SPORTS_KEY")

DATA_FILE = "data.json"

DATE = datetime.now().strftime("%Y-%m-%d")

TIMEZONE = "Europe/Istanbul"

LAST_GAMES = 5

REQUEST_DELAY = 0.25

BASKETBALL_BASE = "https://v1.basketball.api-sports.io"
NBA_BASE = "https://v2.nba.api-sports.io"

HEADERS = {
    "x-apisports-key": API_KEY
}


# ============================================================
# KONTROL
# ============================================================

if not API_KEY:
    raise RuntimeError(
        "API_SPORTS_KEY bulunamadı. "
        "GitHub Settings > Secrets and variables > Actions bölümüne ekle."
    )


# ============================================================
# API
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


def api_get(base, endpoint, params=None):
    url = f"{base}{endpoint}"

    if params:
        url += "?" + urlencode(params)

    try:
        response = session.get(
            url,
            timeout=25
        )

        if response.status_code != 200:
            print(
                f"   ❌ API HTTP {response.status_code}: "
                f"{endpoint}"
            )
            return None

        data = response.json()

        time.sleep(REQUEST_DELAY)

        return data

    except Exception as e:
        print(
            f"   ❌ API bağlantı hatası: {e}"
        )

        return None


def remaining_requests(data):
    if not data:
        return None

    errors = data.get("errors")

    if isinstance(errors, dict):
        for key in (
            "requests",
            "requests_remaining",
            "rateLimit"
        ):
            value = errors.get(key)

            if value is not None:
                return value

    return None


# ============================================================
# NORMALİZASYON
# ============================================================

def normalize(text):
    if not text:
        return ""

    text = str(text).lower()

    replacements = {
        "ı": "i",
        "İ": "i",
        "ş": "s",
        "Ş": "s",
        "ğ": "g",
        "Ğ": "g",
        "ü": "u",
        "Ü": "u",
        "ö": "o",
        "Ö": "o",
        "ç": "c",
        "Ç": "c",
        "é": "e",
        "è": "e",
        "ê": "e",
        "á": "a",
        "à": "a",
        "â": "a",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return "".join(
        ch for ch in text
        if ch.isalnum()
    )


# ============================================================
# LİG BULMA
# ============================================================

def find_leagues():
    print()
    print("🔎 API-Basketball ligleri okunuyor...")

    data = api_get(
        BASKETBALL_BASE,
        "/leagues"
    )

    if not data:
        raise RuntimeError(
            "API-Basketball /leagues cevabı alınamadı."
        )

    response = data.get("response", [])

    print(
        f"📚 API'de {len(response)} lig bulundu."
    )

    euroleague = None
    bsl = None

    for item in response:
        league = item.get("league", {})
        country = item.get("country", {})

        league_id = league.get("id")
        name = league.get("name", "")
        country_name = country.get("name", "")

        n_name = normalize(name)
        n_country = normalize(country_name)

        # -----------------------------
        # EUROLEGUE
        # -----------------------------

        if (
            euroleague is None
            and n_name == "euroleague"
            and n_country == "europe"
        ):
            euroleague = {
                "id": league_id,
                "name": name,
                "country": country_name
            }

        # -----------------------------
        # TÜRKİYE BSL
        # -----------------------------

        if (
            bsl is None
            and n_country == "turkey"
            and (
                n_name == "basketbolsuperligi"
                or "basketbolsuperligi" in n_name
            )
        ):
            bsl = {
                "id": league_id,
                "name": name,
                "country": country_name
            }

    print()

    if euroleague:
        print(
            f"✅ EuroLeague bulundu: "
            f"{euroleague['name']} "
            f"(ID: {euroleague['id']})"
        )
    else:
        print(
            "❌ EuroLeague bulunamadı."
        )

    if bsl:
        print(
            f"✅ BSL bulundu: "
            f"{bsl['name']} "
            f"(ID: {bsl['id']})"
        )
    else:
        print(
            "❌ Türkiye Basketbol Süper Ligi bulunamadı."
        )

    return euroleague, bsl


# ============================================================
# BUGÜNKÜ API-BASKETBALL MAÇLARI
# ============================================================

def get_basketball_today(league):
    if not league:
        return []

    data = api_get(
        BASKETBALL_BASE,
        "/games",
        {
            "date": DATE,
            "league": league["id"],
            "timezone": TIMEZONE
        }
    )

    if not data:
        return []

    response = data.get("response", [])

    print(
        f"   📦 {league['name']}: "
        f"{len(response)} maç"
    )

    return response


# ============================================================
# BUGÜNKÜ NBA MAÇLARI
# ============================================================

def get_nba_today():
    print()
    print("🏀 NBA maçları API-NBA'dan alınıyor...")

    # API-Sports NBA dokümantasyonundaki
    # 2026-2027 sezonu = 2026
    data = api_get(
        NBA_BASE,
        "/games",
        {
            "date": DATE,
            "league": "standard",
            "season": "2026"
        }
    )

    if not data:
        print(
            "❌ NBA API cevabı alınamadı."
        )
        return []

    response = data.get("response", [])

    print(
        f"   📦 NBA: {len(response)} maç"
    )

    return response


# ============================================================
# MAÇ FORMATLAMA
# ============================================================

def format_basketball_game(game, source):
    teams = game.get("teams", {})
    scores = game.get("scores", {})

    home = teams.get("home", {})
    away = teams.get("away", {})

    league = game.get("league", {})

    home_id = home.get("id")
    away_id = away.get("id")

    home_name = home.get("name")
    away_name = away.get("name")

    if not home_id or not away_id:
        return None

    home_score = scores.get("home")
    away_score = scores.get("away")

    status = game.get("status", {})

    status_short = status.get("short")

    return {
        "id": game.get("id"),
        "source": source,
        "date": DATE,
        "league": league.get("name"),
        "league_id": league.get("id"),
        "status": status_short,

        "home": {
            "id": home_id,
            "name": home_name
        },

        "away": {
            "id": away_id,
            "name": away_name
        },

        "score": {
            "home": home_score,
            "away": away_score
        }
    }


# ============================================================
# TAMAMLANMIŞ MAÇ KONTROLÜ
# ============================================================

FINISHED_BASKETBALL = {
    "FT",
    "AOT"
}

FINISHED_NBA = {
    "3",
    "FT",
    "AOT"
}


def is_finished(game, source):
    status = game.get("status")

    if source == "NBA":
        return status in FINISHED_NBA

    return status in FINISHED_BASKETBALL


# ============================================================
# TAKIM GEÇMİŞİ - API BASKETBALL
# ============================================================

def get_team_history_basketball(team_id):
    data = api_get(
        BASKETBALL_BASE,
        "/games",
        {
            "team": team_id,
            "last": 30,
            "timezone": TIMEZONE
        }
    )

    if not data:
        return []

    response = data.get("response", [])

    return response


# ============================================================
# TAKIM GEÇMİŞİ - NBA
# ============================================================

def get_team_history_nba(team_id):
    data = api_get(
        NBA_BASE,
        "/games",
        {
            "team": team_id,
            "season": "2026"
        }
    )

    if not data:
        return []

    response = data.get("response", [])

    return response


# ============================================================
# SON 5 EV MAÇI
# ============================================================

def last_home_games(games, team_id, source):
    result = []

    for game in games:
        if not is_finished(game, source):
            continue

        teams = game.get("teams", {})

        home = teams.get("home", {})
        away = teams.get("away", {})

        if home.get("id") != team_id:
            continue

        scores = game.get("scores", {})

        home_score = scores.get("home")

        away_score = scores.get("away")

        if home_score is None or away_score is None:
            continue

        result.append({
            "date": game.get("date"),
            "home": home_score,
            "away": away_score
        })

        if len(result) >= LAST_GAMES:
            break

    return result


# ============================================================
# SON 5 DEPLASMAN MAÇI
# ============================================================

def last_away_games(games, team_id, source):
    result = []

    for game in games:
        if not is_finished(game, source):
            continue

        teams = game.get("teams", {})

        home = teams.get("home", {})
        away = teams.get("away", {})

        if away.get("id") != team_id:
            continue

        scores = game.get("scores", {})

        home_score = scores.get("home")

        away_score = scores.get("away")

        if home_score is None or away_score is None:
            continue

        result.append({
            "date": game.get("date"),
            "home": home_score,
            "away": away_score
        })

        if len(result) >= LAST_GAMES:
            break

    return result


# ============================================================
# ORTALAMA
# ============================================================

def average(values):
    if not values:
        return 0

    return sum(values) / len(values)


# ============================================================
# MAÇ ANALİZİ
# ============================================================

def analyze_match(match):
    source = match["source"]

    home_id = match["home"]["id"]
    away_id = match["away"]["id"]

    home_name = match["home"]["name"]
    away_name = match["away"]["name"]

    print()
    print(
        f"🏀 {home_name} - {away_name}"
    )

    if source == "NBA":
        print("   🏆 NBA")

        home_history = get_team_history_nba(
            home_id
        )

        away_history = get_team_history_nba(
            away_id
        )

    else:
        print(
            f"   🏆 {match['league']}"
        )

        home_history = get_team_history_basketball(
            home_id
        )

        away_history = get_team_history_basketball(
            away_id
        )

    home_games = last_home_games(
        home_history,
        home_id,
        source
    )

    away_games = last_away_games(
        away_history,
        away_id,
        source
    )

    print(
        f"   🏠 Son 5 ev maçı: "
        f"{len(home_games)}"
    )

    print(
        f"   ✈️ Son 5 deplasman maçı: "
        f"{len(away_games)}"
    )

    games = min(
        len(home_games),
        len(away_games)
    )

    if games == 0:
        print(
            "   ⚠️ Kullanılabilir geçmiş veri yok."
        )
        return None

    if games < LAST_GAMES:
        print(
            f"   ⚠️ Tam 5 yerine {games} maç kullanılacak."
        )

    # --------------------------------------------------------
    # EV SAHİBİ
    #
    # PF = attığı sayı
    # PA = yediği sayı
    # --------------------------------------------------------

    home_points_for = [
        x["home"]
        for x in home_games
    ]

    home_points_against = [
        x["away"]
        for x in home_games
    ]

    # --------------------------------------------------------
    # DEPLASMAN
    #
    # PF = attığı sayı
    # PA = yediği sayı
    # --------------------------------------------------------

    away_points_for = [
        x["away"]
        for x in away_games
    ]

    away_points_against = [
        x["home"]
        for x in away_games
    ]

    home_for_avg = average(
        home_points_for
    )

    home_against_avg = average(
        home_points_against
    )

    away_for_avg = average(
        away_points_for
    )

    away_against_avg = average(
        away_points_against
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

    # --------------------------------------------------------
    # GÜVEN
    # --------------------------------------------------------

    confidence_map = {
        5: 85,
        4: 80,
        3: 75,
        2: 65,
        1: 55,
        0: 0
    }

    confidence = confidence_map.get(
        games,
        0
    )

    result = {
        "id": match["id"],
        "source": source,

        "date": DATE,

        "league": match["league"],
        "league_id": match["league_id"],

        "home": home_name,
        "away": away_name,

        "home_team_id": home_id,
        "away_team_id": away_id,

        "games": games,

        "home_for_avg": round(
            home_for_avg,
            2
        ),

        "home_against_avg": round(
            home_against_avg,
            2
        ),

        "away_for_avg": round(
            away_for_avg,
            2
        ),

        "away_against_avg": round(
            away_against_avg,
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

        "confidence": confidence
    }

    print(
        f"   📊 Ev ort: {home_for_avg:.2f} / "
        f"{home_against_avg:.2f}"
    )

    print(
        f"   📊 Dep ort: {away_for_avg:.2f} / "
        f"{away_against_avg:.2f}"
    )

    print(
        f"   🎯 Beklenen skor: "
        f"{expected_home:.2f} - "
        f"{expected_away:.2f}"
    )

    print(
        f"   📈 Toplam: {match_total:.2f}"
    )

    print(
        f"   🌓 İlk yarı: {first_half:.2f}"
    )

    print(
        f"   📊 Çeyrek ort.: {quarter_avg:.2f}"
    )

    print(
        f"   ⭐ Güven: %{confidence}"
    )

    return result


# ============================================================
# DATA.JSON OKU
# ============================================================

def load_data():
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

    except Exception:
        pass

    return {}


# ============================================================
# DATA.JSON YAZ
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
# ANA
# ============================================================

def main():
    print()
    print("=" * 50)
    print("🏀 BASKETBOL ANALİZ SİSTEMİ")
    print("=" * 50)

    print(
        f"📅 Tarih: {DATE}"
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

    print(
        "📐 Hesaplama: Hücum + Rakibin savunması / 2"
    )

    # --------------------------------------------------------
    # LİGLERİ BUL
    # --------------------------------------------------------

    euroleague, bsl = find_leagues()

    # --------------------------------------------------------
    # BUGÜNKÜ MAÇLAR
    # --------------------------------------------------------

    raw_matches = []

    if euroleague:
        raw_matches.extend(
            get_basketball_today(
                euroleague
            )
        )

    if bsl:
        raw_matches.extend(
            get_basketball_today(
                bsl
            )
        )

    nba_matches = get_nba_today()

    # --------------------------------------------------------
    # FORMATLA
    # --------------------------------------------------------

    matches = []

    for game in raw_matches:
        formatted = format_basketball_game(
            game,
            "BASKETBALL"
        )

        if formatted:
            matches.append(
                formatted
            )

    for game in nba_matches:
        formatted = format_basketball_game(
            game,
            "NBA"
        )

        if formatted:
            matches.append(
                formatted
            )

    # --------------------------------------------------------
    # DUPLICATE TEMİZLE
    # --------------------------------------------------------

    unique = {}

    for match in matches:
        key = (
            match["source"],
            match["id"]
        )

        unique[key] = match

    matches = list(
        unique.values()
    )

    print()
    print(
        f"🎯 Toplam uygun maç: "
        f"{len(matches)}"
    )

    if not matches:
        print()
        print(
            "⚠️ Bugün NBA / EuroLeague / BSL "
            "için analiz edilecek maç bulunamadı."
        )

        data = load_data()

        if not data:
            data = {}

        data[DATE] = []

        save_data(data)

        return

    # --------------------------------------------------------
    # ANALİZ
    # --------------------------------------------------------

    results = []

    for index, match in enumerate(
        matches,
        start=1
    ):
        print()
        print(
            f"[{index}/{len(matches)}]"
        )

        result = analyze_match(
            match
        )

        if result:
            results.append(
                result
            )

    # --------------------------------------------------------
    # DATA.JSON
    # --------------------------------------------------------

    data = load_data()

    data[DATE] = results

    save_data(data)

    # --------------------------------------------------------
    # SONUÇ
    # --------------------------------------------------------

    print()
    print("=" * 50)

    if results:
        print(
            f"✅ {len(results)} maç analiz edildi."
        )

    else:
        print(
            "⚠️ Analiz üretilebilen maç yok."
        )

    print(
        f"💾 {DATA_FILE} güncellendi."
    )

    print("=" * 50)


if __name__ == "__main__":
    main()
