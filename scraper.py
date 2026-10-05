import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


# =========================================================
# AYARLAR
# =========================================================

API_BASE = "https://www.sofascore.com/api/v1"

DATA_FILE = "data.json"

TIMEZONE = "Europe/Istanbul"

REQUEST_TIMEOUT = 20

HISTORY_PAGES = 3

MAX_HISTORY_MATCHES = 20


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.sofascore.com/",
}


# =========================================================
# YARDIMCI
# =========================================================

def now_tr():
    return datetime.now(ZoneInfo(TIMEZONE))


def get_today():
    return now_tr().strftime("%Y-%m-%d")


def get_json(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        print(f"HTTP {response.status_code} -> {url}")

        if response.status_code != 200:
            return None

        return response.json()

    except Exception as e:
        print(f"❌ İstek hatası: {e}")
        return None


# =========================================================
# DATA.JSON
# =========================================================

def load_existing_data():

    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

    except Exception as e:
        print(f"⚠️ data.json okunamadı: {e}")

    return {}


def save_data(data):

    temp_file = DATA_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4
        )

    os.replace(temp_file, DATA_FILE)


# =========================================================
# GÜNÜN MAÇLARI
# =========================================================

def get_today_matches():

    today = get_today()

    print("")
    print("=" * 60)
    print("🏀 BASKETBOL SCRAPER")
    print("=" * 60)

    print(f"🇹🇷 Türkiye tarihi : {today}")

    url = (
        f"{API_BASE}/sport/basketball/"
        f"scheduled-events/{today}"
    )

    print(f"🌐 Maç kaynağı:")
    print(url)

    data = get_json(url)

    if not data:
        print("❌ SofaScore verisi alınamadı.")
        return []

    events = data.get("events", [])

    print(f"📦 SofaScore event sayısı: {len(events)}")

    if not events:
        print("⚠️ Bugün için event bulunamadı.")
        return []

    # Durum istatistikleri
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
    print("📊 DURUM DAĞILIMI")

    for status, count in status_counts.items():
        print(f"   {status}: {count}")

    return events


# =========================================================
# TAKIM GEÇMİŞİ
# =========================================================

def get_team_history(team_id):

    matches = []

    if not team_id:
        return matches

    print(f"   📚 Takım geçmişi: {team_id}")

    for page in range(0, HISTORY_PAGES):

        url = (
            f"{API_BASE}/team/"
            f"{team_id}/events/last/{page}"
        )

        data = get_json(url)

        if not data:
            continue

        events = data.get("events", [])

        for event in events:

            status_type = (
                event
                .get("status", {})
                .get("type")
            )

            if status_type != "finished":
                continue

            home_team = event.get("homeTeam", {})
            away_team = event.get("awayTeam", {})

            home_score = event.get("homeScore", {})
            away_score = event.get("awayScore", {})

            home_id = home_team.get("id")
            away_id = away_team.get("id")

            if not home_id or not away_id:
                continue

            home_points = home_score.get("current")
            away_points = away_score.get("current")

            if home_points is None or away_points is None:
                continue

            matches.append({
                "home_id": home_id,
                "away_id": away_id,
                "home_points": float(home_points),
                "away_points": float(away_points),
            })

            if len(matches) >= MAX_HISTORY_MATCHES:
                break

        if len(matches) >= MAX_HISTORY_MATCHES:
            break

        time.sleep(0.15)

    print(f"   ✅ Geçmiş maç: {len(matches)}")

    return matches


# =========================================================
# TAKIM İSTATİSTİĞİ
# =========================================================

def calculate_team_stats(team_id, matches):

    if not matches:
        return None

    total_points = []
    q1_values = []
    q2_values = []
    q3_values = []
    q4_values = []

    for match in matches:

        if match["home_id"] == team_id:

            team_points = match["home_points"]
            opponent_points = match["away_points"]

        elif match["away_id"] == team_id:

            team_points = match["away_points"]
            opponent_points = match["home_points"]

        else:
            continue

        total_points.append(team_points)

        # SofaScore takım geçmiş endpointinde
        # periyot skorları her zaman bulunmayabilir.
        #
        # Bu durumda toplam skor üzerinden
        # dengeli periyot tahmini kullanıyoruz.

        estimated_q1 = team_points * 0.25
        estimated_q2 = team_points * 0.25
        estimated_q3 = team_points * 0.25
        estimated_q4 = team_points * 0.25

        q1_values.append(estimated_q1)
        q2_values.append(estimated_q2)
        q3_values.append(estimated_q3)
        q4_values.append(estimated_q4)

    if not total_points:
        return None

    def avg(values):

        if not values:
            return 0

        return sum(values) / len(values)

    return {
        "games": len(total_points),

        "points": avg(total_points),

        "q1": avg(q1_values),
        "q2": avg(q2_values),
        "q3": avg(q3_values),
        "q4": avg(q4_values),
    }


# =========================================================
# ANALİZ
# =========================================================

def calculate_match_analytics(
    home_stats,
    away_stats
):

    # -----------------------------------------------------
    # TAKIM SAYI ORTALAMALARI
    # -----------------------------------------------------

    home_points = home_stats["points"]
    away_points = away_stats["points"]

    match_total = home_points + away_points

    # -----------------------------------------------------
    # PERİYOT
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # ÖRNEK SAYISI
    # -----------------------------------------------------

    games = min(
        home_stats["games"],
        away_stats["games"]
    )

    # -----------------------------------------------------
    # GÜVEN SKORU
    #
    # Bu gerçek kazanma olasılığı değildir.
    # Veri miktarına göre güven göstergesidir.
    # -----------------------------------------------------

    confidence = min(
        100,
        round(
            (games / 20) * 100,
            1
        )
    )

    return {

        "q1": round(q1, 1),

        "q2": round(q2, 1),

        "q3": round(q3, 1),

        "q4": round(q4, 1),

        "first_half": round(first_half, 1),

        "match_total": round(match_total, 1),

        "exp_home": round(home_points, 1),

        "exp_away": round(away_points, 1),

        "games": games,

        "confidence": confidence
    }


# =========================================================
# MAÇ ANALİZİ
# =========================================================

def analyze_match(event, index):

    home_team = event.get("homeTeam", {})
    away_team = event.get("awayTeam", {})

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

    league_name = (
        event
        .get("tournament", {})
        .get("name", "BASKETBOL")
        .upper()
    )

    start_timestamp = event.get(
        "startTimestamp"
    )

    if start_timestamp:

        try:
            match_time = datetime.fromtimestamp(
                start_timestamp,
                ZoneInfo(TIMEZONE)
            ).strftime("%H:%M")

        except Exception:
            match_time = "--:--"

    else:
        match_time = "--:--"

    print("")
    print(
        f"🏀 [{index}] "
        f"{home_name} - {away_name}"
    )

    print(
        f"   🏆 {league_name} "
        f"⏰ {match_time}"
    )

    if not home_id or not away_id:

        print("   ❌ Takım ID bulunamadı.")

        return None

    # -----------------------------------------------------
    # EV SAHİBİ GEÇMİŞİ
    # -----------------------------------------------------

    home_history = get_team_history(home_id)

    # -----------------------------------------------------
    # DEPLASMAN GEÇMİŞİ
    # -----------------------------------------------------

    away_history = get_team_history(away_id)

    if not home_history:

        print(
            f"   ⚠️ {home_name} geçmişi bulunamadı."
        )

    if not away_history:

        print(
            f"   ⚠️ {away_name} geçmişi bulunamadı."
        )

    # -----------------------------------------------------
    # İKİ TAKIMDA DA HİÇ VERİ YOKSA
    # -----------------------------------------------------

    if not home_history and not away_history:

        print(
            "   ❌ İki takım için de geçmiş veri yok."
        )

        return None

    # Veri yoksa diğer taraftaki mevcut veri
    # kullanılabilir.
    if not home_history:
        home_history = away_history[:]

    if not away_history:
        away_history = home_history[:]

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
            f"   ❌ {home_name} istatistiği oluşturulamadı."
        )

        return None

    if not away_stats:

        print(
            f"   ❌ {away_name} istatistiği oluşturulamadı."
        )

        return None

    analysis = calculate_match_analytics(
        home_stats,
        away_stats
    )

    print(
        f"   📈 Tahmini toplam: "
        f"{analysis['match_total']}"
    )

    print(
        f"   🏠 Ev: {analysis['exp_home']}"
    )

    print(
        f"   ✈️ Dep: {analysis['exp_away']}"
    )

    print(
        f"   📊 Örnek: {analysis['games']}"
    )

    return {
        "id": f"m_{event.get('id', index)}",

        "league": (
            f"{league_name} "
            f"{match_time}"
        ),

        "home": home_name,

        "away": away_name,

        "homeTeamId": home_id,

        "awayTeamId": away_id,

        "analysis": analysis
    }


# =========================================================
# ANA SCRAPER
# =========================================================

def fetch_live_basketball_data():

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

    events = get_today_matches()

    # -----------------------------------------------------
    # API TAMAMEN BOŞSA ESKİ VERİYİ KORU
    # -----------------------------------------------------

    if not events:

        print("")
        print(
            "❌ BUGÜN SOFASCORE'DAN MAÇ ALINAMADI."
        )

        print(
            "⚠️ data.json DEĞİŞTİRİLMEYECEK."
        )

        return

    # -----------------------------------------------------
    # MAÇLARI ANALİZ ET
    # -----------------------------------------------------

    all_matches = []

    skipped = 0

    print("")
    print("=" * 70)
    print("🔎 MAÇLAR ANALİZ EDİLİYOR")
    print("=" * 70)

    for index, event in enumerate(
        events,
        start=1
    ):

        try:

            status = (
                event
                .get("status", {})
                .get("type")
            )

            # İptal edilen / ertelenen maçları alma
            if status in (
                "canceled",
                "postponed",
                "cancelled"
            ):

                skipped += 1

                continue

            result = analyze_match(
                event,
                index
            )

            if result:

                all_matches.append(result)

            else:

                skipped += 1

        except Exception as e:

            skipped += 1

            print(
                f"   ❌ Maç analiz hatası: {e}"
            )

    # -----------------------------------------------------
    # SONUÇ
    # -----------------------------------------------------

    print("")
    print("=" * 70)
    print("📊 SONUÇ")
    print("=" * 70)

    print(
        f"📦 Toplam event : {len(events)}"
    )

    print(
        f"✅ Analiz       : {len(all_matches)}"
    )

    print(
        f"⏭️ Atlanan       : {skipped}"
    )

    # -----------------------------------------------------
    # HİÇ ANALİZ YOKSA ESKİ VERİYİ SİLME
    # -----------------------------------------------------

    if not all_matches:

        print("")
        print(
            "❌ BUGÜN İÇİN HİÇ ANALİZ ÜRETİLEMEDİ."
        )

        print(
            "⚠️ data.json DEĞİŞTİRİLMEYECEK."
        )

        return

    # -----------------------------------------------------
    # SADECE BUGÜNÜ GÜNCELLE
    # ESKİ TARİHLER KORUNUR
    # -----------------------------------------------------

    existing_data[today] = all_matches

    save_data(existing_data)

    print("")
    print("=" * 70)
    print("✅ DATA.JSON GÜNCELLENDİ")
    print("=" * 70)

    print(
        f"📅 Tarih: {today}"
    )

    print(
        f"🏀 Maç: {len(all_matches)}"
    )

    print(
        f"📚 Toplam tarih: "
        f"{len(existing_data)}"
    )

    print(
        f"📁 Dosya: {DATA_FILE}"
    )


# =========================================================
# ÇALIŞTIR
# =========================================================

if __name__ == "__main__":

    fetch_live_basketball_data()
