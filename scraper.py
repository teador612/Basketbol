import requests
import json
import time
import os
from datetime import datetime

BASE_URL = "https://www.sofascore.com/api/v1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

DATA_FILE = "data.json"

REQUEST_TIMEOUT = 15
MAX_HISTORY_MATCHES = 10
HISTORY_PAGES = 3


session = requests.Session()
session.headers.update(HEADERS)


# =========================================================
# API
# =========================================================

def get_json(url):
    try:
        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            return response.json()

        print(
            f"API HATASI: {response.status_code} -> {url}"
        )

    except Exception as e:
        print(
            f"API BAĞLANTI HATASI: {e}"
        )

    return None


# =========================================================
# DATA.JSON
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

    except Exception as e:
        print(
            f"data.json okunamadı: {e}"
        )

    return {}


def save_data(data):

    temp_file = DATA_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4
        )

    os.replace(
        temp_file,
        DATA_FILE
    )


# =========================================================
# SCORE
# =========================================================

def get_score_number(score, *keys):

    if not isinstance(score, dict):
        return None

    for key in keys:

        value = score.get(key)

        if isinstance(value, (int, float)):
            return float(value)

    return None


def get_team_score(event, team_id):

    home_team = event.get(
        "homeTeam",
        {}
    )

    away_team = event.get(
        "awayTeam",
        {}
    )

    if home_team.get("id") == team_id:

        score = event.get(
            "homeScore",
            {}
        )

        opponent_score = event.get(
            "awayScore",
            {}
        )

        is_home = True

    elif away_team.get("id") == team_id:

        score = event.get(
            "awayScore",
            {}
        )

        opponent_score = event.get(
            "homeScore",
            {}
        )

        is_home = False

    else:
        return None

    total = get_score_number(
        score,
        "current",
        "display"
    )

    opponent_total = get_score_number(
        opponent_score,
        "current",
        "display"
    )

    q1 = get_score_number(
        score,
        "period1"
    )

    q2 = get_score_number(
        score,
        "period2"
    )

    q3 = get_score_number(
        score,
        "period3"
    )

    q4 = get_score_number(
        score,
        "period4"
    )

    if total is None:
        return None

    if opponent_total is None:
        return None

    # Periyot bilgisi olmayan maçları
    # tahmin geçmişine dahil etmiyoruz.
    if None in (
        q1,
        q2,
        q3,
        q4
    ):
        return None

    return {
        "home": is_home,
        "total": total,
        "opponent_total": opponent_total,
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "q4": q4
    }


# =========================================================
# TEAM HISTORY
# =========================================================

def get_team_last_matches(team_id):

    matches = []

    for page in range(
        HISTORY_PAGES
    ):

        url = (
            f"{BASE_URL}/team/"
            f"{team_id}/events/last/"
            f"{page}"
        )

        data = get_json(url)

        if not data:
            continue

        events = data.get(
            "events",
            []
        )

        for event in events:

            status = event.get(
                "status",
                {}
            )

            # SADECE TAMAMLANMIŞ MAÇ
            if status.get("type") != "finished":
                continue

            score = get_team_score(
                event,
                team_id
            )

            if not score:
                continue

            matches.append(score)

            if len(matches) >= MAX_HISTORY_MATCHES:
                return matches

        time.sleep(0.10)

    return matches


# =========================================================
# TEAM STATISTICS
# =========================================================

def average(values, fallback=0):

    values = [
        float(v)
        for v in values
        if v is not None
    ]

    if not values:
        return fallback

    return sum(values) / len(values)


def team_statistics(matches):

    if not matches:
        return None

    home_matches = [
        m for m in matches
        if m["home"]
    ]

    away_matches = [
        m for m in matches
        if not m["home"]
    ]

    stats = {

        "games": len(matches),

        "points": average(
            [
                m["total"]
                for m in matches
            ],
            80
        ),

        "allowed": average(
            [
                m["opponent_total"]
                for m in matches
            ],
            80
        ),

        "q1": average(
            [
                m["q1"]
                for m in matches
            ],
            20
        ),

        "q2": average(
            [
                m["q2"]
                for m in matches
            ],
            20
        ),

        "q3": average(
            [
                m["q3"]
                for m in matches
            ],
            20
        ),

        "q4": average(
            [
                m["q4"]
                for m in matches
            ],
            20
        )
    }

    stats["home_points"] = average(
        [
            m["total"]
            for m in home_matches
        ],
        stats["points"]
    )

    stats["home_allowed"] = average(
        [
            m["opponent_total"]
            for m in home_matches
        ],
        stats["allowed"]
    )

    stats["away_points"] = average(
        [
            m["total"]
            for m in away_matches
        ],
        stats["points"]
    )

    stats["away_allowed"] = average(
        [
            m["opponent_total"]
            for m in away_matches
        ],
        stats["allowed"]
    )

    return stats


# =========================================================
# DEFAULT STATS
# =========================================================

def default_stats():

    return {

        "games": 0,

        "points": 80,
        "allowed": 80,

        "q1": 20,
        "q2": 20,
        "q3": 20,
        "q4": 20,

        "home_points": 80,
        "home_allowed": 80,

        "away_points": 80,
        "away_allowed": 80
    }


# =========================================================
# MATCH MODEL
# =========================================================

def calculate_prediction(
    home,
    away
):

    # -----------------------------------------
    # EV SAHİBİ HÜCUM
    # -----------------------------------------

    home_attack = (
        home["points"] * 0.65
        +
        home["home_points"] * 0.35
    )

    # -----------------------------------------
    # DEPLASMAN SAVUNMASI
    # -----------------------------------------

    away_defense = (
        away["allowed"] * 0.65
        +
        away["away_allowed"] * 0.35
    )

    # -----------------------------------------
    # DEPLASMAN HÜCUM
    # -----------------------------------------

    away_attack = (
        away["points"] * 0.65
        +
        away["away_points"] * 0.35
    )

    # -----------------------------------------
    # EV SAHİBİ SAVUNMASI
    # -----------------------------------------

    home_defense = (
        home["allowed"] * 0.65
        +
        home["home_allowed"] * 0.35
    )

    # -----------------------------------------
    # BEKLENEN SKOR
    # -----------------------------------------

    expected_home = (
        home_attack * 0.55
        +
        away_defense * 0.45
    )

    expected_away = (
        away_attack * 0.55
        +
        home_defense * 0.45
    )

    # -----------------------------------------
    # PERİYOTLAR
    # -----------------------------------------

    home_q = [
        home["q1"],
        home["q2"],
        home["q3"],
        home["q4"]
    ]

    away_q = [
        away["q1"],
        away["q2"],
        away["q3"],
        away["q4"]
    ]

    home_q_total = sum(
        home_q
    )

    away_q_total = sum(
        away_q
    )

    if home_q_total <= 0:
        home_q_total = 80

    if away_q_total <= 0:
        away_q_total = 80

    home_factor = (
        expected_home /
        home_q_total
    )

    away_factor = (
        expected_away /
        away_q_total
    )

    home_periods = [
        q * home_factor
        for q in home_q
    ]

    away_periods = [
        q * away_factor
        for q in away_q
    ]

    # BURASI ÖNEMLİ:
    # Q3 = Q3 + Q3
    # Q4 = Q4 + Q4

    q1 = (
        home_periods[0]
        +
        away_periods[0]
    )

    q2 = (
        home_periods[1]
        +
        away_periods[1]
    )

    q3 = (
        home_periods[2]
        +
        away_periods[2]
    )

    q4 = (
        home_periods[3]
        +
        away_periods[3]
    )

    first_half = (
        q1 + q2
    )

    match_total = (
        expected_home
        +
        expected_away
    )

    return {

        "q1": round(
            q1,
            1
        ),

        "q2": round(
            q2,
            1
        ),

        "q3": round(
            q3,
            1
        ),

        "q4": round(
            q4,
            1
        ),

        "first_half": round(
            first_half,
            1
        ),

        "match_total": round(
            match_total,
            1
        ),

        "exp_home": round(
            expected_home,
            1
        ),

        "exp_away": round(
            expected_away,
            1
        )
    }


# =========================================================
# CONFIDENCE
# =========================================================

def calculate_confidence(
    home,
    away
):

    games = min(
        home["games"],
        away["games"]
    )

    if games <= 0:
        return 25

    if games >= 10:
        return 85

    return round(
        30 + (
            games * 5.5
        )
    )


# =========================================================
# TODAY'S MATCHES
# =========================================================

def get_today_matches(
    date_string
):

    url = (
        f"{BASE_URL}/sport/"
        f"basketball/"
        f"scheduled-events/"
        f"{date_string}"
    )

    data = get_json(
        url
    )

    if not data:
        return []

    return data.get(
        "events",
        []
    )


# =========================================================
# MAIN
# =========================================================

def run_scraper():

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    print()
    print("=" * 70)
    print("🏀 BASKETBOL ANALİZ MOTORU")
    print("=" * 70)
    print(
        f"📅 Gün: {today}"
    )

    # -----------------------------------------
    # ESKİ DATA.JSON'U YÜKLE
    # -----------------------------------------

    all_data = load_existing_data()

    print(
        f"📁 Mevcut tarih sayısı: "
        f"{len(all_data)}"
    )

    # -----------------------------------------
    # BUGÜNÜN MAÇLARI
    # -----------------------------------------

    events = get_today_matches(
        today
    )

    print(
        f"🏀 Bugünün bulunan maçı: "
        f"{len(events)}"
    )

    if not events:

        print(
            "⚠️ Bugünün maçları alınamadı."
        )

        # ÖNEMLİ:
        # Eski data.json'u silmiyoruz.
        return

    today_matches = []

    # -----------------------------------------
    # MAÇLAR
    # -----------------------------------------

    for index, event in enumerate(
        events,
        start=1
    ):

        home_team = event.get(
            "homeTeam",
            {}
        )

        away_team = event.get(
            "awayTeam",
            {}
        )

        home_id = home_team.get(
            "id"
        )

        away_id = away_team.get(
            "id"
        )

        if not home_id or not away_id:
            continue

        home_name = home_team.get(
            "name",
            "Ev Sahibi"
        )

        away_name = away_team.get(
            "name",
            "Deplasman"
        )

        tournament = event.get(
            "tournament",
            {}
        )

        league = tournament.get(
            "name",
            "BASKETBOL"
        )

        timestamp = event.get(
            "startTimestamp"
        )

        if timestamp:

            try:

                match_time = datetime.fromtimestamp(
                    timestamp
                ).strftime(
                    "%H:%M"
                )

            except Exception:

                match_time = "--:--"

        else:

            match_time = "--:--"

        print()
        print(
            f"🔎 [{index}] "
            f"{home_name} - "
            f"{away_name}"
        )

        # -------------------------------------
        # EV TAKIMI
        # -------------------------------------

        home_history = get_team_last_matches(
            home_id
        )

        home_stats = team_statistics(
            home_history
        )

        if not home_stats:

            home_stats = default_stats()

        # -------------------------------------
        # DEPLASMAN TAKIMI
        # -------------------------------------

        away_history = get_team_last_matches(
            away_id
        )

        away_stats = team_statistics(
            away_history
        )

        if not away_stats:

            away_stats = default_stats()

        # -------------------------------------
        # TAHMİN
        # -------------------------------------

        analysis = calculate_prediction(
            home_stats,
            away_stats
        )

        confidence = calculate_confidence(
            home_stats,
            away_stats
        )

        analysis["confidence"] = confidence

        analysis["home_games"] = (
            home_stats["games"]
        )

        analysis["away_games"] = (
            away_stats["games"]
        )

        # -------------------------------------
        # JSON KAYDI
        # -------------------------------------

        today_matches.append({

            "id": f"m_{event.get('id', index)}",

            "eventId": event.get(
                "id"
            ),

            "league": (
                f"{league} "
                f"{match_time}"
            ),

            "home": home_name,

            "away": away_name,

            "homeId": home_id,

            "awayId": away_id,

            "analysis": analysis,

            "stats": {

                "home": {

                    "games":
                        home_stats["games"],

                    "points": round(
                        home_stats["points"],
                        1
                    ),

                    "allowed": round(
                        home_stats["allowed"],
                        1
                    )
                },

                "away": {

                    "games":
                        away_stats["games"],

                    "points": round(
                        away_stats["points"],
                        1
                    ),

                    "allowed": round(
                        away_stats["allowed"],
                        1
                    )
                }
            }
        })

        print(
            f"   📊 "
            f"{analysis['exp_home']} - "
            f"{analysis['exp_away']}"
        )

        print(
            f"   🎯 Toplam: "
            f"{analysis['match_total']}"
        )

        print(
            f"   📈 Güven: "
            f"%{confidence}"
        )

    # -----------------------------------------
    # BUGÜNÜ GÜNCELLE
    # -----------------------------------------

    all_data[today] = today_matches

    # -----------------------------------------
    # TÜM TARİHLERİ KORU
    # -----------------------------------------

    save_data(
        all_data
    )

    print()
    print("=" * 70)
    print(
        f"✅ Bugün kaydedildi: "
        f"{len(today_matches)} maç"
    )

    print(
        f"📅 Data.json tarih sayısı: "
        f"{len(all_data)}"
    )

    print(
        "💾 Eski tarihler korunuyor."
    )

    print("=" * 70)


if __name__ == "__main__":
    run_scraper()
