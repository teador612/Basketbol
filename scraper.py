import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from curl_cffi import requests


# =========================================================
# AYARLAR
# =========================================================

API_BASE = "https://api.sofascore.com/api/v1"

DATA_FILE = "data.json"

TIMEZONE = "Europe/Istanbul"

REQUEST_TIMEOUT = 20

HISTORY_PAGES = 3

MAX_HISTORY_MATCHES = 20


# =========================================================
# HTTP SESSION
# =========================================================

session = requests.Session(
    impersonate="chrome"
)

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
    "X-Requested-With": "XMLHttpRequest",
}


# =========================================================
# TARİH
# =========================================================

def get_today():

    return datetime.now(
        ZoneInfo(TIMEZONE)
    ).strftime("%Y-%m-%d")


# =========================================================
# API
# =========================================================

def get_json(url):

    try:

        response = session.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        print(
            f"HTTP {response.status_code} -> {url}"
        )

        if response.status_code != 200:

            print(
                f"⚠️ API cevap kodu: "
                f"{response.status_code}"
            )

            print(
                f"⚠️ Cevap: "
                f"{response.text[:300]}"
            )

            return None

        try:

            return response.json()

        except Exception as e:

            print(
                f"❌ JSON okunamadı: {e}"
            )

            return None

    except Exception as e:

        print(
            f"❌ API bağlantı hatası: {e}"
        )

        return None


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
        ) as file:

            data = json.load(file)

        if isinstance(data, dict):

            return data

    except Exception as e:

        print(
            f"⚠️ data.json okunamadı: {e}"
        )

    return {}


# =========================================================
# DATA.JSON KAYDET
# =========================================================

def save_data(data):

    temp_file = DATA_FILE + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    os.replace(
        temp_file,
        DATA_FILE
    )


# =========================================================
# BUGÜNÜN BASKETBOL MAÇLARI
# =========================================================

def get_today_matches():

    today = get_today()

    url = (
        f"{API_BASE}/sport/basketball/"
        f"scheduled-events/{today}"
    )

    print("")
    print("=" * 70)
    print("🏀 SOFASCORE BASKETBOL")
    print("=" * 70)

    print(
        f"📅 Tarih: {today}"
    )

    print(
        f"🌐 URL: {url}"
    )

    data = get_json(url)

    if not data:

        print(
            "❌ SofaScore'dan veri alınamadı."
        )

        return []

    events = data.get(
        "events",
        []
    )

    print(
        f"📦 Toplam event: {len(events)}"
    )

    if not events:

        print(
            "⚠️ Bugün event bulunamadı."
        )

        return []

    # Durumları göster
    status_counts = {}

    for event in events:

        status = (
            event
            .get("status", {})
            .get("type", "unknown")
        )

        status_counts[status] = (
            status_counts.get(status, 0) + 1
        )

    print("")
    print("📊 MAÇ DURUMLARI")

    for status, count in status_counts.items():

        print(
            f"   {status}: {count}"
        )

    return events


# =========================================================
# TAKIM GEÇMİŞİ
# =========================================================

def get_team_history(team_id):

    if not team_id:

        return []

    matches = []

    print(
        f"   📚 Takım geçmişi ID: {team_id}"
    )

    for page in range(
        HISTORY_PAGES
    ):

        url = (
            f"{API_BASE}/team/"
            f"{team_id}/events/last/{page}"
        )

        data = get_json(url)

        if not data:

            continue

        events = data.get(
            "events",
            []
        )

        for event in events:

            status = (
                event
                .get("status", {})
                .get("type")
            )

            if status != "finished":

                continue

            home_team = event.get(
                "homeTeam",
                {}
            )

            away_team = event.get(
                "awayTeam",
                {}
            )

            home_score = event.get(
                "homeScore",
                {}
            )

            away_score = event.get(
                "awayScore",
                {}
            )

            home_id = home_team.get(
                "id"
            )

            away_id = away_team.get(
                "id"
            )

            home_points = home_score.get(
                "current"
            )

            away_points = away_score.get(
                "current"
            )

            if not home_id:
                continue

            if not away_id:
                continue

            if home_points is None:
                continue

            if away_points is None:
                continue

            matches.append({
                "home_id": home_id,
                "away_id": away_id,
                "home_points": float(
                    home_points
                ),
                "away_points": float(
                    away_points
                ),
                "home_q1": home_score.get(
                    "period1"
                ),
                "away_q1": away_score.get(
                    "period1"
                ),
                "home_q2": home_score.get(
                    "period2"
                ),
                "away_q2": away_score.get(
                    "period2"
                ),
                "home_q3": home_score.get(
                    "period3"
                ),
                "away_q3": away_score.get(
                    "period3"
                ),
                "home_q4": home_score.get(
                    "period4"
                ),
                "away_q4": away_score.get(
                    "period4"
                )
            })

            if len(matches) >= MAX_HISTORY_MATCHES:

                break

        if len(matches) >= MAX_HISTORY_MATCHES:

            break

        time.sleep(0.15)

    print(
        f"   ✅ Geçmiş maç: {len(matches)}"
    )

    return matches


# =========================================================
# TAKIM İSTATİSTİĞİ
# =========================================================

def calculate_team_stats(
    team_id,
    matches
):

    if not matches:

        return None

    points = []

    q1 = []
    q2 = []
    q3 = []
    q4 = []

    for match in matches:

        if match["home_id"] == team_id:

            team_points = match[
                "home_points"
            ]

            tq1 = match["home_q1"]
            tq2 = match["home_q2"]
            tq3 = match["home_q3"]
            tq4 = match["home_q4"]

        elif match["away_id"] == team_id:

            team_points = match[
                "away_points"
            ]

            tq1 = match["away_q1"]
            tq2 = match["away_q2"]
            tq3 = match["away_q3"]
            tq4 = match["away_q4"]

        else:

            continue

        points.append(
            team_points
        )

        if tq1 is not None:
            q1.append(float(tq1))

        if tq2 is not None:
            q2.append(float(tq2))

        if tq3 is not None:
            q3.append(float(tq3))

        if tq4 is not None:
            q4.append(float(tq4))

    if not points:

        return None

    def average(values):

        if not values:

            return 0

        return sum(values) / len(values)

    # Eğer periyot verisi eksikse
    # toplam puandan yaklaşık dağılım
    # kullanılır.

    if not q1:

        q1 = [
            value * 0.25
            for value in points
        ]

    if not q2:

        q2 = [
            value * 0.25
            for value in points
        ]

    if not q3:

        q3 = [
            value * 0.25
            for value in points
        ]

    if not q4:

        q4 = [
            value * 0.25
            for value in points
        ]

    return {

        "games": len(points),

        "points": average(points),

        "q1": average(q1),

        "q2": average(q2),

        "q3": average(q3),

        "q4": average(q4)
    }


# =========================================================
# MAÇ ANALİZİ
# =========================================================

def calculate_analysis(
    home_stats,
    away_stats
):

    home_points = (
        home_stats["points"]
    )

    away_points = (
        away_stats["points"]
    )

    q1 = (
        home_stats["q1"] +
        away_stats["q1"]
    )

    q2 = (
        home_stats["q2"] +
        away_stats["q2"]
    )

    q3 = (
        home_stats["q3"] +
        away_stats["q3"]
    )

    q4 = (
        home_stats["q4"] +
        away_stats["q4"]
    )

    first_half = q1 + q2

    match_total = (
        home_points +
        away_points
    )

    games = min(
        home_stats["games"],
        away_stats["games"]
    )

    confidence = min(
        100,
        round(
            games / 20 * 100,
            1
        )
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
            home_points,
            1
        ),

        "exp_away": round(
            away_points,
            1
        ),

        "games": games,

        "confidence": confidence
    }


# =========================================================
# TEK MAÇ
# =========================================================

def analyze_match(
    event,
    number
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

    home_name = home_team.get(
        "name",
        "Ev Sahibi"
    )

    away_name = away_team.get(
        "name",
        "Deplasman"
    )

    tournament = (
        event
        .get("tournament", {})
        .get("name", "Basketbol")
    )

    timestamp = event.get(
        "startTimestamp"
    )

    if timestamp:

        try:

            match_time = datetime.fromtimestamp(
                timestamp,
                ZoneInfo(TIMEZONE)
            ).strftime("%H:%M")

        except Exception:

            match_time = "--:--"

    else:

        match_time = "--:--"

    print("")
    print(
        f"🏀 [{number}] "
        f"{home_name} - {away_name}"
    )

    print(
        f"   🏆 {tournament}"
    )

    print(
        f"   ⏰ {match_time}"
    )

    if not home_id or not away_id:

        print(
            "   ❌ Takım ID eksik."
        )

        return None

    # -----------------------------------------------------
    # EV SAHİBİ
    # -----------------------------------------------------

    home_history = get_team_history(
        home_id
    )

    # -----------------------------------------------------
    # DEPLASMAN
    # -----------------------------------------------------

    away_history = get_team_history(
        away_id
    )

    if not home_history:

        print(
            f"   ⚠️ {home_name}: "
            f"geçmiş bulunamadı."
        )

    if not away_history:

        print(
            f"   ⚠️ {away_name}: "
            f"geçmiş bulunamadı."
        )

    if (
        not home_history
        and not away_history
    ):

        print(
            "   ❌ İki takımda da veri yok."
        )

        return None

    # Bir tarafın geçmişi yoksa
    # mevcut geçmişi kullan.

    if not home_history:

        home_history = away_history.copy()

    if not away_history:

        away_history = home_history.copy()

    home_stats = calculate_team_stats(
        home_id,
        home_history
    )

    away_stats = calculate_team_stats(
        away_id,
        away_history
    )

    if not home_stats:

        print(
            "   ❌ Ev sahibi analizi yok."
        )

        return None

    if not away_stats:

        print(
            "   ❌ Deplasman analizi yok."
        )

        return None

    analysis = calculate_analysis(
        home_stats,
        away_stats
    )

    print(
        f"   📈 Toplam tahmin: "
        f"{analysis['match_total']}"
    )

    print(
        f"   🏠 Ev: "
        f"{analysis['exp_home']}"
    )

    print(
        f"   ✈️ Dep: "
        f"{analysis['exp_away']}"
    )

    print(
        f"   📊 Örnek: "
        f"{analysis['games']}"
    )

    return {

        "id": str(
            event.get(
                "id",
                number
            )
        ),

        "league": tournament,

        "time": match_time,

        "home": home_name,

        "away": away_name,

        "homeTeamId": home_id,

        "awayTeamId": away_id,

        "analysis": analysis
    }


# =========================================================
# ANA İŞLEM
# =========================================================

def main():

    today = get_today()

    print("")
    print("=" * 70)
    print("🏀 BASKETBOL VERİ GÜNCELLEME")
    print("=" * 70)

    print(
        f"📅 Türkiye tarihi: {today}"
    )

    existing_data = load_existing_data()

    print(
        f"📚 Mevcut tarih sayısı: "
        f"{len(existing_data)}"
    )

    # -----------------------------------------------------
    # MAÇLARI AL
    # -----------------------------------------------------

    events = get_today_matches()

    if not events:

        print("")
        print(
            "❌ BUGÜN MAÇ ALINAMADI."
        )

        print(
            "⚠️ data.json DEĞİŞTİRİLMEYECEK."
        )

        return

    # -----------------------------------------------------
    # ANALİZ
    # -----------------------------------------------------

    results = []

    skipped = 0

    print("")
    print("=" * 70)
    print("🔎 MAÇ ANALİZLERİ")
    print("=" * 70)

    for number, event in enumerate(
        events,
        start=1
    ):

        status = (
            event
            .get("status", {})
            .get("type")
        )

        if status in (
            "canceled",
            "cancelled",
            "postponed"
        ):

            skipped += 1

            continue

        try:

            result = analyze_match(
                event,
                number
            )

            if result:

                results.append(
                    result
                )

            else:

                skipped += 1

        except Exception as e:

            skipped += 1

            print(
                f"   ❌ Hata: {e}"
            )

    # -----------------------------------------------------
    # SONUÇ
    # -----------------------------------------------------

    print("")
    print("=" * 70)
    print("📊 SONUÇ")
    print("=" * 70)

    print(
        f"📦 Event: {len(events)}"
    )

    print(
        f"✅ Analiz: {len(results)}"
    )

    print(
        f"⏭️ Atlanan: {skipped}"
    )

    # -----------------------------------------------------
    # HİÇ VERİ YOKSA ESKİSİNİ KORU
    # -----------------------------------------------------

    if not results:

        print("")
        print(
            "❌ Hiç analiz üretilemedi."
        )

        print(
            "⚠️ data.json korunuyor."
        )

        return

    # -----------------------------------------------------
    # SADECE BUGÜNÜ DEĞİŞTİR
    # -----------------------------------------------------

    existing_data[today] = results

    save_data(
        existing_data
    )

    print("")
    print("=" * 70)
    print("✅ DATA.JSON GÜNCELLENDİ")
    print("=" * 70)

    print(
        f"📅 {today}"
    )

    print(
        f"🏀 {len(results)} maç"
    )

    print(
        f"📚 {len(existing_data)} tarih"
    )


# =========================================================
# BAŞLAT
# =========================================================

if __name__ == "__main__":

    main()
