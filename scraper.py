import requests
import json
import time
import random
from datetime import datetime
from statistics import mean


# =========================================================
# AYARLAR
# =========================================================

BASE = "https://www.sofascore.com/api/v1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

REQUEST_TIMEOUT = 15

HISTORY_PAGES = 2
MAX_MATCHES_PER_TEAM = 10

# Normal istekler arasındaki bekleme.
# 8-15 saniye ile toplam çekim daha kontrollü olur.
MIN_DELAY = 8
MAX_DELAY = 15

# 403 sonrası bekleme
WAIT_403 = 60

# 429 sonrası bekleme
WAIT_429 = 90

# Ağ hatası sonrası bekleme
WAIT_ERROR = 30


# =========================================================
# CACHE
# =========================================================

TEAM_CACHE = {}

REQUEST_COUNT = 0


# =========================================================
# BEKLEME
# =========================================================

def wait_before_request():

    delay = random.uniform(
        MIN_DELAY,
        MAX_DELAY
    )

    print(
        f"   ⏳ Sonraki istek için "
        f"{delay:.1f} sn bekleniyor..."
    )

    time.sleep(delay)


# =========================================================
# API
# =========================================================

def get_json(url, first_request=False):

    global REQUEST_COUNT

    if not first_request:
        wait_before_request()

    REQUEST_COUNT += 1

    print(
        f"   🌐 API isteği #{REQUEST_COUNT}"
    )

    try:

        response = SESSION.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        status = response.status_code

        print(
            f"   HTTP {status}"
        )

        # -------------------------------------------------
        # BAŞARILI
        # -------------------------------------------------

        if status == 200:

            try:
                return response.json()

            except Exception as e:

                print(
                    f"   ⚠️ JSON okunamadı: {e}"
                )

                return None

        # -------------------------------------------------
        # 403
        # -------------------------------------------------

        if status == 403:

            print(
                "   ⚠️ 403 erişim reddedildi."
            )

            print(
                f"   ⏸️ {WAIT_403} saniye bekleniyor..."
            )

            time.sleep(WAIT_403)

            # Aynı isteği otomatik olarak
            # tekrar tekrar göndermiyoruz.
            return None

        # -------------------------------------------------
        # 429
        # -------------------------------------------------

        if status == 429:

            print(
                "   ⚠️ 429 rate limit."
            )

            print(
                f"   ⏸️ {WAIT_429} saniye bekleniyor..."
            )

            time.sleep(WAIT_429)

            return None

        # -------------------------------------------------
        # DİĞER HTTP HATALARI
        # -------------------------------------------------

        print(
            f"   ⚠️ API {status}: {url}"
        )

        return None

    except requests.Timeout:

        print(
            "   ⚠️ API zaman aşımı."
        )

        print(
            f"   ⏸️ {WAIT_ERROR} saniye bekleniyor..."
        )

        time.sleep(WAIT_ERROR)

        return None

    except requests.RequestException as e:

        print(
            f"   ⚠️ API bağlantı hatası: {e}"
        )

        print(
            f"   ⏸️ {WAIT_ERROR} saniye bekleniyor..."
        )

        time.sleep(WAIT_ERROR)

        return None

    except Exception as e:

        print(
            f"   ⚠️ Beklenmeyen API hatası: {e}"
        )

        return None


# =========================================================
# SAYI
# =========================================================

def safe_mean(values, fallback=0):

    values = [
        float(x)
        for x in values
        if x is not None
    ]

    if not values:
        return fallback

    return mean(values)


# =========================================================
# SKOR
# =========================================================

def get_score_value(score, key):

    value = score.get(key)

    if isinstance(value, (int, float)):
        return float(value)

    return None


# =========================================================
# TAKIM SKORU
# =========================================================

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

    elif away_team.get("id") == team_id:

        score = event.get(
            "awayScore",
            {}
        )

    else:

        return None

    current = (
        get_score_value(
            score,
            "current"
        )
        or
        get_score_value(
            score,
            "display"
        )
    )

    q1 = get_score_value(
        score,
        "period1"
    )

    q2 = get_score_value(
        score,
        "period2"
    )

    q3 = get_score_value(
        score,
        "period3"
    )

    q4 = get_score_value(
        score,
        "period4"
    )

    if current is None:
        return None

    if None in (
        q1,
        q2,
        q3,
        q4
    ):
        return None

    return {
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "q4": q4,
        "total": current,
    }


# =========================================================
# TAKIM GEÇMİŞİ
# =========================================================

def get_last_matches(team_id):

    # -----------------------------------------------------
    # CACHE
    # -----------------------------------------------------

    if team_id in TEAM_CACHE:

        print(
            f"   ♻️ Cache kullanılıyor: "
            f"{team_id}"
        )

        return TEAM_CACHE[team_id]

    print(
        f"   🔎 Takım geçmişi alınıyor: "
        f"{team_id}"
    )

    matches = []

    for page in range(
        HISTORY_PAGES
    ):

        url = (
            f"{BASE}/team/"
            f"{team_id}/events/last/{page}"
        )

        data = get_json(
            url,
            first_request=False
        )

        if not data:

            print(
                f"   ⚠️ Sayfa alınamadı: "
                f"{page}"
            )

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

            # Sadece tamamlanan maçlar
            if status.get("type") != "finished":
                continue

            score = get_team_score(
                event,
                team_id
            )

            if not score:
                continue

            home = event.get(
                "homeTeam",
                {}
            )

            away = event.get(
                "awayTeam",
                {}
            )

            is_home = (
                home.get("id")
                == team_id
            )

            if is_home:

                opponent_score = event.get(
                    "awayScore",
                    {}
                )

            else:

                opponent_score = event.get(
                    "homeScore",
                    {}
                )

            opponent_total = (
                get_score_value(
                    opponent_score,
                    "current"
                )
                or
                get_score_value(
                    opponent_score,
                    "display"
                )
            )

            if opponent_total is None:
                continue

            matches.append({

                "home": is_home,

                "team_total": score[
                    "total"
                ],

                "opponent_total": opponent_total,

                "q1": score["q1"],
                "q2": score["q2"],
                "q3": score["q3"],
                "q4": score["q4"],

            })

            if len(matches) >= MAX_MATCHES_PER_TEAM:

                TEAM_CACHE[team_id] = matches

                print(
                    f"   ✅ {len(matches)} "
                    f"geçerli maç bulundu."
                )

                return matches

    TEAM_CACHE[team_id] = matches

    print(
        f"   📦 Toplam geçmiş: "
        f"{len(matches)} maç"
    )

    return matches


# =========================================================
# TAKIM İSTATİSTİKLERİ
# =========================================================

def calculate_team_stats(matches):

    if not matches:
        return None

    home_matches = [
        m
        for m in matches
        if m["home"]
    ]

    away_matches = [
        m
        for m in matches
        if not m["home"]
    ]

    stats = {

        "games": len(matches),

        "points": safe_mean(
            [
                m["team_total"]
                for m in matches
            ],
            80
        ),

        "allowed": safe_mean(
            [
                m["opponent_total"]
                for m in matches
            ],
            80
        ),

        "q1": safe_mean(
            [
                m["q1"]
                for m in matches
            ],
            20
        ),

        "q2": safe_mean(
            [
                m["q2"]
                for m in matches
            ],
            20
        ),

        "q3": safe_mean(
            [
                m["q3"]
                for m in matches
            ],
            20
        ),

        "q4": safe_mean(
            [
                m["q4"]
                for m in matches
            ],
            20
        ),
    }

    stats["home_points"] = safe_mean(
        [
            m["team_total"]
            for m in home_matches
        ],
        stats["points"]
    )

    stats["home_allowed"] = safe_mean(
        [
            m["opponent_total"]
            for m in home_matches
        ],
        stats["allowed"]
    )

    stats["away_points"] = safe_mean(
        [
            m["team_total"]
            for m in away_matches
        ],
        stats["points"]
    )

    stats["away_allowed"] = safe_mean(
        [
            m["opponent_total"]
            for m in away_matches
        ],
        stats["allowed"]
    )

    return stats


# =========================================================
# PERİYOT TAHMİNİ
# =========================================================

def calculate_period_prediction(
    home_stats,
    away_stats
):

    home_attack = home_stats[
        "points"
    ]

    away_attack = away_stats[
        "points"
    ]

    home_defense = home_stats[
        "allowed"
    ]

    away_defense = away_stats[
        "allowed"
    ]

    home_attack_adj = (
        home_attack * 0.65
        +
        home_stats["home_points"]
        * 0.35
    )

    away_attack_adj = (
        away_attack * 0.65
        +
        away_stats["away_points"]
        * 0.35
    )

    home_defense_adj = (
        home_defense * 0.65
        +
        home_stats["home_allowed"]
        * 0.35
    )

    away_defense_adj = (
        away_defense * 0.65
        +
        away_stats["away_allowed"]
        * 0.35
    )

    expected_home = (
        home_attack_adj * 0.55
        +
        away_defense_adj * 0.45
    )

    expected_away = (
        away_attack_adj * 0.55
        +
        home_defense_adj * 0.45
    )

    home_q = [
        home_stats["q1"],
        home_stats["q2"],
        home_stats["q3"],
        home_stats["q4"],
    ]

    away_q = [
        away_stats["q1"],
        away_stats["q2"],
        away_stats["q3"],
        away_stats["q4"],
    ]

    home_q_total = sum(home_q)

    away_q_total = sum(away_q)

    if home_q_total <= 0:
        home_q_total = 80

    if away_q_total <= 0:
        away_q_total = 80

    home_ratio = (
        expected_home
        /
        home_q_total
    )

    away_ratio = (
        expected_away
        /
        away_q_total
    )

    home_periods = [
        x * home_ratio
        for x in home_q
    ]

    away_periods = [
        x * away_ratio
        for x in away_q
    ]

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

    first_half = q1 + q2

    match_total = (
        expected_home
        +
        expected_away
    )

    return {

        "q1": round(q1, 1),
        "q2": round(q2, 1),
        "q3": round(q3, 1),
        "q4": round(q4, 1),

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
        ),
    }


# =========================================================
# GÜVEN
# =========================================================

def calculate_confidence(
    home_stats,
    away_stats
):

    games = min(
        home_stats["games"],
        away_stats["games"]
    )

    data_score = min(
        games / 10,
        1
    ) * 60

    quality_score = 40

    return round(
        min(
            100,
            data_score
            +
            quality_score
        ),
        1
    )


# =========================================================
# FALLBACK
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
        "away_allowed": 80,
    }


# =========================================================
# ANA SCRAPER
# =========================================================

def run_scraper():

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    print("=" * 60)
    print(
        "🏀 BASKETBOL GERÇEK VERİ ANALİZİ"
    )
    print("=" * 60)

    print(
        f"📅 Tarih: {today}"
    )

    # -----------------------------------------------------
    # BUGÜNÜN MAÇLARI
    # -----------------------------------------------------

    url = (
        f"{BASE}/sport/basketball/"
        f"scheduled-events/{today}"
    )

    print(
        "\n📡 Günün basketbol maçları "
        "alınıyor..."
    )

    data = get_json(
        url,
        first_request=True
    )

    if not data:

        print(
            "❌ Günün maçları alınamadı."
        )

        return

    events = data.get(
        "events",
        []
    )

    print(
        f"🏀 Bulunan maç: "
        f"{len(events)}"
    )

    all_matches = []

    # -----------------------------------------------------
    # MAÇLAR
    # -----------------------------------------------------

    for index, event in enumerate(events):

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

        league = (
            event
            .get(
                "tournament",
                {}
            )
            .get(
                "name",
                "BASKETBOL"
            )
            .upper()
        )

        timestamp = event.get(
            "startTimestamp",
            0
        )

        try:

            time_str = datetime.fromtimestamp(
                timestamp
            ).strftime("%H:%M")

        except Exception:

            time_str = "--:--"

        print("\n" + "-" * 55)

        print(
            f"[{index + 1}/{len(events)}] "
            f"{home_name} - {away_name}"
        )

        print(
            f"   🏆 {league}"
        )

        # -------------------------------------------------
        # EV SAHİBİ
        # -------------------------------------------------

        home_matches = get_last_matches(
            home_id
        )

        # -------------------------------------------------
        # DEPLASMAN
        # -------------------------------------------------

        away_matches = get_last_matches(
            away_id
        )

        home_stats = calculate_team_stats(
            home_matches
        )

        away_stats = calculate_team_stats(
            away_matches
        )

        if not home_stats:

            print(
                "   ⚠️ Ev sahibi geçmişi "
                "bulunamadı."
            )

            home_stats = default_stats()

        if not away_stats:

            print(
                "   ⚠️ Deplasman geçmişi "
                "bulunamadı."
            )

            away_stats = default_stats()

        # -------------------------------------------------
        # ANALİZ
        # -------------------------------------------------

        analysis = calculate_period_prediction(
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

        all_matches.append({

            "id": (
                f"m_"
                f"{event.get('id', index)}"
            ),

            "league": (
                f"{league} "
                f"{time_str}"
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
                    ),
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
                    ),
                }
            }
        })

        print(
            f"   📊 Tahmin: "
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

    # =====================================================
    # DATA.JSON
    # =====================================================

    output = {
        today: all_matches
    }

    with open(
        "data.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=4
        )

    print("\n" + "=" * 60)

    print(
        f"✅ TAMAMLANDI: "
        f"{len(all_matches)} maç"
    )

    print(
        f"📡 Toplam API isteği: "
        f"{REQUEST_COUNT}"
    )

    print(
        f"💾 data.json yazıldı."
    )

    print("=" * 60)


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    run_scraper()
