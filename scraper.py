import json
import os
import time
from datetime import datetime, timezone
from statistics import mean

import requests


BASE = "https://www.sofascore.com/api/v1"

REQUEST_TIMEOUT = 15
HISTORY_PAGES = 2
MAX_MATCHES_PER_TEAM = 10


SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
})


# =========================================================
# GENEL
# =========================================================

def get_json(url):
    try:
        r = SESSION.get(url, timeout=REQUEST_TIMEOUT)

        if r.status_code != 200:
            print(f"HTTP {r.status_code}: {url}")
            return None

        return r.json()

    except Exception as e:
        print(f"İstek hatası: {e}")
        return None


def safe_mean(values, default=0):
    values = [
        float(x)
        for x in values
        if x is not None
    ]

    if not values:
        return default

    return mean(values)


def number(value, default=0):
    try:
        return float(value)
    except Exception:
        return default


def round_value(value):
    return round(float(value), 1)


# =========================================================
# SKOR OKUMA
# =========================================================

def get_score_value(score, key):
    if not isinstance(score, dict):
        return 0

    value = score.get(key)

    if isinstance(value, dict):
        value = value.get("current")

    return number(value, 0)


def get_team_score(event, side):
    score = event.get("homeScore" if side == "home" else "awayScore")

    if not isinstance(score, dict):
        return {
            "total": 0,
            "q1": 0,
            "q2": 0,
            "q3": 0,
            "q4": 0,
        }

    return {
        "total": get_score_value(score, "current"),

        "q1": get_score_value(score, "period1"),

        "q2": get_score_value(score, "period2"),

        "q3": get_score_value(score, "period3"),

        "q4": get_score_value(score, "period4"),
    }


# =========================================================
# TAKIM GEÇMİŞ MAÇLARI
# =========================================================

def get_last_matches(team_id):

    all_matches = []

    for page in range(HISTORY_PAGES):

        url = (
            f"{BASE}/team/{team_id}/events/last/"
            f"{page + 1}"
        )

        data = get_json(url)

        if not data:
            continue

        events = data.get("events", [])

        if not events:
            continue

        all_matches.extend(events)

    # Aynı maçı iki kez alma
    unique = {}

    for event in all_matches:

        event_id = event.get("id")

        if event_id:
            unique[event_id] = event

    matches = []

    for event in unique.values():

        status = event.get("status", {})

        if status.get("type") != "finished":
            continue

        matches.append(event)

    matches.sort(
        key=lambda x: x.get("startTimestamp", 0),
        reverse=True
    )

    return matches[:MAX_MATCHES_PER_TEAM]


# =========================================================
# TAKIM İSTATİSTİKLERİ
# =========================================================

def calculate_team_stats(team_id):

    events = get_last_matches(team_id)

    if not events:

        return {
            "games": 0,

            "scored": 0,
            "conceded": 0,

            "q1_scored": 0,
            "q2_scored": 0,
            "q3_scored": 0,
            "q4_scored": 0,

            "q1_conceded": 0,
            "q2_conceded": 0,
            "q3_conceded": 0,
            "q4_conceded": 0,

            "home_scored": 0,
            "home_conceded": 0,

            "away_scored": 0,
            "away_conceded": 0,
        }

    scored = []
    conceded = []

    q1_scored = []
    q2_scored = []
    q3_scored = []
    q4_scored = []

    q1_conceded = []
    q2_conceded = []
    q3_conceded = []
    q4_conceded = []

    home_scored = []
    home_conceded = []

    away_scored = []
    away_conceded = []

    for event in events:

        home_team = event.get("homeTeam", {})
        away_team = event.get("awayTeam", {})

        home_id = home_team.get("id")
        away_id = away_team.get("id")

        home = get_team_score(event, "home")
        away = get_team_score(event, "away")

        if home_id == team_id:

            my = home
            opp = away

            is_home = True

        elif away_id == team_id:

            my = away
            opp = home

            is_home = False

        else:
            continue

        scored.append(my["total"])
        conceded.append(opp["total"])

        q1_scored.append(my["q1"])
        q2_scored.append(my["q2"])
        q3_scored.append(my["q3"])
        q4_scored.append(my["q4"])

        q1_conceded.append(opp["q1"])
        q2_conceded.append(opp["q2"])
        q3_conceded.append(opp["q3"])
        q4_conceded.append(opp["q4"])

        if is_home:

            home_scored.append(my["total"])
            home_conceded.append(opp["total"])

        else:

            away_scored.append(my["total"])
            away_conceded.append(opp["total"])

    games = len(scored)

    return {

        "games": games,

        "scored": safe_mean(scored),
        "conceded": safe_mean(conceded),

        "q1_scored": safe_mean(q1_scored),
        "q2_scored": safe_mean(q2_scored),
        "q3_scored": safe_mean(q3_scored),
        "q4_scored": safe_mean(q4_scored),

        "q1_conceded": safe_mean(q1_conceded),
        "q2_conceded": safe_mean(q2_conceded),
        "q3_conceded": safe_mean(q3_conceded),
        "q4_conceded": safe_mean(q4_conceded),

        "home_scored": safe_mean(home_scored),
        "home_conceded": safe_mean(home_conceded),

        "away_scored": safe_mean(away_scored),
        "away_conceded": safe_mean(away_conceded),
    }


# =========================================================
# PERİYOT TAHMİNİ
# =========================================================

def calculate_period_prediction(home_stats, away_stats):

    home_q1 = (
        home_stats["q1_scored"]
        + away_stats["q1_conceded"]
    ) / 2

    away_q1 = (
        away_stats["q1_scored"]
        + home_stats["q1_conceded"]
    ) / 2


    home_q2 = (
        home_stats["q2_scored"]
        + away_stats["q2_conceded"]
    ) / 2

    away_q2 = (
        away_stats["q2_scored"]
        + home_stats["q2_conceded"]
    ) / 2


    home_q3 = (
        home_stats["q3_scored"]
        + away_stats["q3_conceded"]
    ) / 2

    away_q3 = (
        away_stats["q3_scored"]
        + home_stats["q3_conceded"]
    ) / 2


    home_q4 = (
        home_stats["q4_scored"]
        + away_stats["q4_conceded"]
    ) / 2

    away_q4 = (
        away_stats["q4_scored"]
        + home_stats["q4_conceded"]
    ) / 2


    first_half = (
        home_q1
        + away_q1
        + home_q2
        + away_q2
    )


    second_half = (
        home_q3
        + away_q3
        + home_q4
        + away_q4
    )


    match_total = first_half + second_half


    # Genel takım ortalamasıyla küçük dengeleme
    general_home = (
        home_stats["scored"]
        + away_stats["conceded"]
    ) / 2

    general_away = (
        away_stats["scored"]
        + home_stats["conceded"]
    ) / 2


    exp_home = (
        home_q1
        + home_q2
        + home_q3
        + home_q4
    )

    exp_away = (
        away_q1
        + away_q2
        + away_q3
        + away_q4
    )


    # Periyot verisi eksikse genel ortalamaya yaklaş
    if exp_home <= 0:
        exp_home = general_home

    if exp_away <= 0:
        exp_away = general_away


    match_total = exp_home + exp_away

    return {

        "q1": round_value(home_q1 + away_q1),

        "q2": round_value(home_q2 + away_q2),

        "q3": round_value(home_q3 + away_q3),

        "q4": round_value(home_q4 + away_q4),

        "first_half": round_value(first_half),

        "match_total": round_value(match_total),

        "exp_home": round_value(exp_home),

        "exp_away": round_value(exp_away),
    }


# =========================================================
# GÜVEN SKORU
# =========================================================

def calculate_confidence(home_stats, away_stats):

    games_home = home_stats["games"]
    games_away = away_stats["games"]

    games = min(games_home, games_away)

    if games <= 0:
        return 0

    # Veri miktarı
    sample_score = min(games / 10, 1) * 70

    # İki takımın da yeterli geçmişi olması
    balance_score = 30

    confidence = sample_score + balance_score

    return round(min(100, confidence), 1)


# =========================================================
# BUGÜNÜN MAÇLARI
# =========================================================

def get_today_matches():

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    # SofaScore günlük event endpoint
    url = (
        f"{BASE}/sport/basketball/scheduled-events/"
        f"{today}"
    )

    data = get_json(url)

    if not data:
        return []

    return data.get("events", [])


# =========================================================
# MEVCUT DATA.JSON
# =========================================================

def load_existing_data():

    if not os.path.exists("data.json"):
        return {}

    try:

        with open(
            "data.json",
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

        if isinstance(data, dict):
            return data

        return {}

    except Exception as e:

        print(f"data.json okunamadı: {e}")

        return {}


def save_data(data):

    temp_file = "data.json.tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=4
        )

    os.replace(
        temp_file,
        "data.json"
    )


# =========================================================
# ANA SCRAPER
# =========================================================

def run_scraper():

    today = datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")

    print("=" * 50)
    print("🏀 BASKETBOL ANALİZ SCRAPER")
    print("=" * 50)

    print(f"📅 Tarih: {today}")

    events = get_today_matches()

    if not events:

        print("❌ Bugünün maçları alınamadı.")

        print(
            "⚠️ Mevcut data.json KORUNDU."
        )

        return

    print(
        f"🏀 Bulunan toplam event: {len(events)}"
    )

    all_matches = []

    for event in events:

        try:

            status = event.get(
                "status",
                {}
            )

            # Sadece gerçekten oynanmamış
            # veya başlamamış basketbol maçları
            # analiz edilir.
            if status.get("type") not in (
                "notstarted",
                "inprogress",
                "finished",
            ):
                continue


            home_team = event.get(
                "homeTeam",
                {}
            )

            away_team = event.get(
                "awayTeam",
                {}
            )

            home_id = home_team.get("id")
            away_id = away_team.get("id")

            home_name = home_team.get(
                "name",
                "Ev Sahibi"
            )

            away_name = away_team.get(
                "name",
                "Deplasman"
            )

            if not home_id or not away_id:
                continue


            print(
                f"\n🏀 {home_name} - {away_name}"
            )

            print("  📊 Ev sahibi geçmişi...")

            home_stats = calculate_team_stats(
                home_id
            )

            print(
                f"     {home_stats['games']} maç"
            )

            print("  📊 Deplasman geçmişi...")

            away_stats = calculate_team_stats(
                away_id
            )

            print(
                f"     {away_stats['games']} maç"
            )


            if (
                home_stats["games"] == 0
                or away_stats["games"] == 0
            ):

                print(
                    "  ⚠️ Yeterli geçmiş bulunamadı."
                )

                continue


            prediction = calculate_period_prediction(
                home_stats,
                away_stats
            )


            confidence = calculate_confidence(
                home_stats,
                away_stats
            )


            league = (
                event
                .get("tournament", {})
                .get("name", "Basketbol")
            )


            match = {

                "id": event.get("id"),

                "home": home_name,

                "away": away_name,

                "league": league,

                "timestamp": event.get(
                    "startTimestamp"
                ),

                "analysis": {

                    "q1": prediction["q1"],

                    "q2": prediction["q2"],

                    "q3": prediction["q3"],

                    "q4": prediction["q4"],

                    "first_half": prediction[
                        "first_half"
                    ],

                    "match_total": prediction[
                        "match_total"
                    ],

                    "exp_home": prediction[
                        "exp_home"
                    ],

                    "exp_away": prediction[
                        "exp_away"
                    ],

                    "confidence": confidence,

                },

                "stats": {

                    "home_games":
                        home_stats["games"],

                    "away_games":
                        away_stats["games"],

                    "home_scored":
                        round_value(
                            home_stats["scored"]
                        ),

                    "home_conceded":
                        round_value(
                            home_stats["conceded"]
                        ),

                    "away_scored":
                        round_value(
                            away_stats["scored"]
                        ),

                    "away_conceded":
                        round_value(
                            away_stats["conceded"]
                        ),
                }
            }


            all_matches.append(match)

            print(
                f"  🎯 Toplam: "
                f"{prediction['match_total']}"
            )

            print(
                f"  🏠 Ev: "
                f"{prediction['exp_home']}"
            )

            print(
                f"  ✈️ Dep: "
                f"{prediction['exp_away']}"
            )

            print(
                f"  🔒 Güven: "
                f"%{confidence}"
            )


            # API'yi gereksiz zorlamamak için
            time.sleep(0.15)


        except Exception as e:

            print(
                f"  ❌ Maç analiz hatası: {e}"
            )

            continue


    print()
    print("=" * 50)

    if not all_matches:

        print(
            "❌ Analiz edilebilecek maç bulunamadı."
        )

        print(
            "⚠️ data.json değiştirilmiyor."
        )

        return


    # =====================================================
    # KRİTİK NOKTA:
    # ESKİ TARİHLERİ SİLME
    # =====================================================

    existing_data = load_existing_data()

    existing_data[today] = all_matches

    save_data(existing_data)


    print(
        f"✅ Bugün kaydedildi: {len(all_matches)} maç"
    )

    print(
        f"📚 Toplam tarih: {len(existing_data)}"
    )

    print(
        "💾 data.json başarıyla güncellendi."
    )

    print("=" * 50)


if __name__ == "__main__":
    run_scraper()
