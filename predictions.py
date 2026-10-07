# ============================================================
# BASKETBOL TAHMİN SİSTEMİ
# NBA + EUROLEAGUE
#
# Veri kaynağı:
# basketball.json
#
# Mantık:
# - Veri çekme sistemine dokunmaz.
# - Kullanıcının belirlediği baremleri analiz eder.
# - Her barem için ÜST / ALT yüzdesi hesaplar.
# - En yüksek güvenilir seçeneği ana tahmin yapar.
# - 1X2 tahmini ayrıca hesaplanır.
# - Geçmiş maçlar predictions.json içine yazılmaz.
# ============================================================

import json
import math
import os
from datetime import datetime, timezone


INPUT_FILE = "basketball.json"
OUTPUT_FILE = "predictions.json"


# ============================================================
# AYARLAR
# ============================================================

# Buraya istediğin barem aralıklarını yazabilirsin.
#
# Örnek:
# 210.5 - 219.5 aralığındaki baremler:
# 210.5
# 211.5
# ...
# 219.5
#
# Sistem bu baremlerin tamamını tek tek analiz eder.
#
BAREM_ARALIKLARI = [
    (180.5, 189.5),
    (190.5, 199.5),
    (200.5, 209.5),
    (210.5, 219.5),
    (220.5, 229.5),
    (230.5, 239.5),
    (240.5, 249.5),
]


# Bir aralıkta minimum kaç geçmiş maç olmalı?
MIN_SAMPLE = 5


# Ana tahmin için minimum başarı yüzdesi.
MIN_CONFIDENCE = 70


# Her takım için kullanılacak maksimum geçmiş maç.
MAX_HISTORY = 10


# Yeni maçlara daha fazla ağırlık verilir.
NEWEST_WEIGHT = 1.00
OLDEST_WEIGHT = 0.55


# Ev sahibi avantajı.
HOME_ADVANTAGE = 2.0


# ============================================================
# DOSYA OKUMA
# ============================================================

def load_json(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dosya bulunamadı: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def safe_float(value):
    try:
        if value is None:
            return None

        if isinstance(value, str):
            value = value.replace(",", ".").strip()

        return float(value)
    except Exception:
        return None


def safe_int(value):
    try:
        if value is None:
            return None

        return int(float(value))
    except Exception:
        return None


def normalize_team(name):
    if not name:
        return ""

    name = str(name).lower().strip()

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
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    return " ".join(name.split())


def is_played(match):
    if match.get("played") is True:
        return True

    home = safe_int(match.get("homeScore"))
    away = safe_int(match.get("awayScore"))

    return home is not None and away is not None


def total_score(match):
    home = safe_int(match.get("homeScore"))
    away = safe_int(match.get("awayScore"))

    if home is None or away is None:
        return None

    return home + away


def result_1x2(match):
    home = safe_int(match.get("homeScore"))
    away = safe_int(match.get("awayScore"))

    if home is None or away is None:
        return None

    if home > away:
        return "1"

    if home < away:
        return "2"

    return "X"


def round_barem(value):
    """
    Barem değerini .5 hassasiyetinde tutar.
    """

    return round(value * 2) / 2


def generate_barems():
    """
    Kullanıcının verdiği aralıklardan baremleri üretir.
    """

    result = []

    for start, end in BAREM_ARALIKLARI:

        start = safe_float(start)
        end = safe_float(end)

        if start is None or end is None:
            continue

        if end < start:
            start, end = end, start

        current = start

        while current <= end + 0.001:

            barem = round_barem(current)

            if barem not in result:
                result.append(barem)

            current += 1.0

    return sorted(result)


BAREMS = generate_barems()


# ============================================================
# TARİH SIRALAMA
# ============================================================

def date_value(match):
    value = match.get("utcDate") or match.get("date")

    if not value:
        return 0

    try:
        text = str(value)

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        return datetime.fromisoformat(text).timestamp()

    except Exception:
        return 0


# ============================================================
# GEÇMİŞ MAÇLARI HAZIRLA
# ============================================================

def prepare_history(matches):
    history = []

    for match in matches:

        if not is_played(match):
            continue

        total = total_score(match)

        if total is None:
            continue

        home = normalize_team(match.get("homeTeam"))
        away = normalize_team(match.get("awayTeam"))

        if not home or not away:
            continue

        history.append({
            "homeTeam": home,
            "awayTeam": away,
            "homeScore": safe_int(match.get("homeScore")),
            "awayScore": safe_int(match.get("awayScore")),
            "total": total,
            "result": result_1x2(match),
            "date": date_value(match),
        })

    history.sort(key=lambda x: x["date"])

    return history


# ============================================================
# TAKIM GEÇMİŞİ
# ============================================================

def get_team_history(team, history):
    team = normalize_team(team)

    result = []

    for match in history:

        if match["homeTeam"] == team:
            result.append({
                **match,
                "teamHome": True,
                "teamScore": match["homeScore"],
                "opponentScore": match["awayScore"],
            })

        elif match["awayTeam"] == team:
            result.append({
                **match,
                "teamHome": False,
                "teamScore": match["awayScore"],
                "opponentScore": match["homeScore"],
            })

    result.sort(key=lambda x: x["date"], reverse=True)

    return result[:MAX_HISTORY]


# ============================================================
# AĞIRLIK
# ============================================================

def calculate_weight(index, total):
    if total <= 1:
        return NEWEST_WEIGHT

    ratio = index / (total - 1)

    return (
        NEWEST_WEIGHT
        - (NEWEST_WEIGHT - OLDEST_WEIGHT) * ratio
    )


# ============================================================
# TAKIM ORTALAMALARI
# ============================================================

def team_statistics(team, history):
    games = get_team_history(team, history)

    if not games:
        return {
            "sample": 0,
            "pointsFor": None,
            "pointsAgainst": None,
            "totalAverage": None,
            "weightedPointsFor": None,
            "weightedPointsAgainst": None,
            "weightedTotal": None,
        }

    total_weight = 0
    points_for = 0
    points_against = 0
    totals = 0

    weighted_points_for = 0
    weighted_points_against = 0
    weighted_total = 0

    for index, game in enumerate(games):

        weight = calculate_weight(
            index,
            len(games)
        )

        pf = game["teamScore"]
        pa = game["opponentScore"]

        if pf is None or pa is None:
            continue

        game_total = pf + pa

        points_for += pf
        points_against += pa
        totals += game_total

        weighted_points_for += pf * weight
        weighted_points_against += pa * weight
        weighted_total += game_total * weight

        total_weight += weight

    if total_weight == 0:
        return {
            "sample": 0,
            "pointsFor": None,
            "pointsAgainst": None,
            "totalAverage": None,
            "weightedPointsFor": None,
            "weightedPointsAgainst": None,
            "weightedTotal": None,
        }

    return {
        "sample": len(games),

        "pointsFor": points_for / len(games),

        "pointsAgainst": points_against / len(games),

        "totalAverage": totals / len(games),

        "weightedPointsFor":
            weighted_points_for / total_weight,

        "weightedPointsAgainst":
            weighted_points_against / total_weight,

        "weightedTotal":
            weighted_total / total_weight,
    }


# ============================================================
# BEKLENEN SKOR
# ============================================================

def calculate_expected_scores(
    home_team,
    away_team,
    history
):

    home_stats = team_statistics(
        home_team,
        history
    )

    away_stats = team_statistics(
        away_team,
        history
    )

    if (
        home_stats["sample"] == 0
        or away_stats["sample"] == 0
    ):
        return None

    # Ev takımının hücum gücü
    home_attack = home_stats["weightedPointsFor"]

    # Ev takımının savunma yediği sayı
    home_defense = home_stats["weightedPointsAgainst"]

    # Deplasman hücumu
    away_attack = away_stats["weightedPointsFor"]

    # Deplasman savunması
    away_defense = away_stats["weightedPointsAgainst"]

    # Ev takımının beklenen sayısı
    expected_home = (
        (home_attack + away_defense) / 2
        + HOME_ADVANTAGE
    )

    # Deplasman beklenen sayısı
    expected_away = (
        (away_attack + home_defense) / 2
    )

    expected_total = (
        expected_home + expected_away
    )

    return {
        "expectedHome": round(expected_home, 2),
        "expectedAway": round(expected_away, 2),
        "expectedTotal": round(expected_total, 2),

        "homeSample": home_stats["sample"],
        "awaySample": away_stats["sample"],
    }


# ============================================================
# BAREM İÇİN ÜST / ALT ANALİZİ
# ============================================================

def analyze_barem(
    barem,
    home_team,
    away_team,
    history
):

    home_team = normalize_team(home_team)
    away_team = normalize_team(away_team)

    relevant = []

    # Öncelikle iki takımın geçmiş maçları.
    #
    # Ev takımının geçmişleri
    home_history = get_team_history(
        home_team,
        history
    )

    # Deplasman takımının geçmişleri
    away_history = get_team_history(
        away_team,
        history
    )

    # İki takımın geçmiş maçlarını birleştir.
    combined = []

    combined.extend(home_history)
    combined.extend(away_history)

    # Aynı maçı iki kere sayma.
    seen = set()

    for game in combined:

        key = (
            game["date"],
            game["homeTeam"],
            game["awayTeam"]
        )

        if key in seen:
            continue

        seen.add(key)

        if game["total"] is not None:
            relevant.append(game)

    # En yeni maçlar önce.
    relevant.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    # Son 20 maç yeterli.
    relevant = relevant[:20]

    if len(relevant) < MIN_SAMPLE:
        return {
            "barem": barem,
            "sample": len(relevant),
            "ust": None,
            "alt": None,
            "prediction": None,
            "confidence": None,
        }

    ust_weight = 0
    alt_weight = 0
    total_weight = 0

    for index, game in enumerate(relevant):

        weight = calculate_weight(
            index,
            len(relevant)
        )

        total = game["total"]

        if total > barem:
            ust_weight += weight

        elif total < barem:
            alt_weight += weight

        # Eşitlikte hiçbir tarafa yazmıyoruz.
        else:
            pass

        total_weight += weight

    if total_weight <= 0:
        return {
            "barem": barem,
            "sample": len(relevant),
            "ust": None,
            "alt": None,
            "prediction": None,
            "confidence": None,
        }

    ust_percent = (
        ust_weight / total_weight
    ) * 100

    alt_percent = (
        alt_weight / total_weight
    ) * 100

    if ust_percent >= alt_percent:
        prediction = "ÜST"
        confidence = ust_percent
    else:
        prediction = "ALT"
        confidence = alt_percent

    return {
        "barem": barem,
        "sample": len(relevant),

        "ust": round(ust_percent, 2),
        "alt": round(alt_percent, 2),

        "prediction": prediction,
        "confidence": round(confidence, 2),
    }


# ============================================================
# TÜM BAREMLERİ ANALİZ ET
# ============================================================

def analyze_all_barems(
    home_team,
    away_team,
    history
):

    analyses = []

    for barem in BAREMS:

        result = analyze_barem(
            barem,
            home_team,
            away_team,
            history
        )

        analyses.append(result)

    return analyses


# ============================================================
# ANA TAHMİNİ SEÇ
# ============================================================

def select_main_prediction(
    barem_results,
    expected_total=None
):

    valid = [
        x
        for x in barem_results
        if x["prediction"] is not None
        and x["confidence"] is not None
    ]

    if not valid:
        return None

    # Önce minimum güven sınırını geçenler.
    strong = [
        x
        for x in valid
        if x["confidence"] >= MIN_CONFIDENCE
    ]

    if strong:
        valid = strong

    # Beklenen toplam skora en yakın baremleri
    # öncelikli değerlendir.
    if expected_total is not None:

        for item in valid:

            item["_distance"] = abs(
                item["barem"] - expected_total
            )

        valid.sort(
            key=lambda x: (
                -x["confidence"],
                x["_distance"]
            )
        )

    else:

        valid.sort(
            key=lambda x: -x["confidence"]
        )

    selected = valid[0]

    return {
        "barem": selected["barem"],
        "prediction": selected["prediction"],
        "confidence": selected["confidence"],
        "ust": selected["ust"],
        "alt": selected["alt"],
        "sample": selected["sample"],
    }


# ============================================================
# 1X2 TAHMİNİ
# ============================================================

def calculate_1x2(
    home_team,
    away_team,
    history
):

    home_games = get_team_history(
        home_team,
        history
    )

    away_games = get_team_history(
        away_team,
        history
    )

    if (
        len(home_games) < MIN_SAMPLE
        or len(away_games) < MIN_SAMPLE
    ):
        return {
            "prediction": None,
            "confidence": None,
            "home": None,
            "draw": None,
            "away": None,
        }

    home_w = 0
    draw_w = 0
    away_w = 0

    total_home_weight = 0
    total_away_weight = 0

    # Ev takımının geçmiş performansı
    for index, game in enumerate(home_games):

        weight = calculate_weight(
            index,
            len(home_games)
        )

        if game["teamScore"] > game["opponentScore"]:
            home_w += weight

        elif game["teamScore"] == game["opponentScore"]:
            draw_w += weight

        else:
            away_w += weight

        total_home_weight += weight

    # Deplasman takımının geçmiş performansı
    for index, game in enumerate(away_games):

        weight = calculate_weight(
            index,
            len(away_games)
        )

        if game["teamScore"] > game["opponentScore"]:
            away_w += weight

        elif game["teamScore"] == game["opponentScore"]:
            draw_w += weight

        else:
            home_w += weight

        total_away_weight += weight

    total = (
        home_w +
        draw_w +
        away_w
    )

    if total <= 0:
        return {
            "prediction": None,
            "confidence": None,
            "home": None,
            "draw": None,
            "away": None,
        }

    home_probability = (
        home_w / total
    ) * 100

    draw_probability = (
        draw_w / total
    ) * 100

    away_probability = (
        away_w / total
    ) * 100

    probabilities = {
        "1": home_probability,
        "X": draw_probability,
        "2": away_probability,
    }

    prediction = max(
        probabilities,
        key=probabilities.get
    )

    confidence = probabilities[prediction]

    return {
        "prediction": prediction,
        "confidence": round(confidence, 2),

        "home": round(home_probability, 2),
        "draw": round(draw_probability, 2),
        "away": round(away_probability, 2),
    }


# ============================================================
# MAÇ TAHMİNİ
# ============================================================

def predict_match(
    match,
    history
):

    home_team_raw = match.get("homeTeam")
    away_team_raw = match.get("awayTeam")

    home_team = normalize_team(
        home_team_raw
    )

    away_team = normalize_team(
        away_team_raw
    )

    expected = calculate_expected_scores(
        home_team,
        away_team,
        history
    )

    if expected is None:
        return None

    barem_results = analyze_all_barems(
        home_team,
        away_team,
        history
    )

    main_prediction = select_main_prediction(
        barem_results,
        expected["expectedTotal"]
    )

    prediction_1x2 = calculate_1x2(
        home_team,
        away_team,
        history
    )

    if main_prediction is None:
        return None

    return {
        "id": match.get("id"),

        "league": match.get("league"),

        "season": match.get("season"),

        "date": match.get("date"),

        "utcDate": match.get("utcDate"),

        "homeTeam": home_team_raw,

        "awayTeam": away_team_raw,

        # ====================================================
        # ANA TAHMİN
        # ====================================================

        "prediction": main_prediction["prediction"],

        "line": main_prediction["barem"],

        "barem": main_prediction["barem"],

        "confidence": main_prediction["confidence"],

        "ustPercent": main_prediction["ust"],

        "altPercent": main_prediction["alt"],

        # ====================================================
        # TÜM BAREMLER
        # ====================================================

        "barems": barem_results,

        # ====================================================
        # MODEL BEKLENTİSİ
        # ====================================================

        "expectedHome": expected["expectedHome"],

        "expectedAway": expected["expectedAway"],

        "expectedTotal": expected["expectedTotal"],

        # ====================================================
        # ÖRNEK SAYISI
        # ====================================================

        "homeSample": expected["homeSample"],

        "awaySample": expected["awaySample"],

        # ====================================================
        # 1X2
        # ====================================================

        "prediction1X2":
            prediction_1x2["prediction"],

        "confidence1X2":
            prediction_1x2["confidence"],

        "homeWinProbability":
            prediction_1x2["home"],

        "drawProbability":
            prediction_1x2["draw"],

        "awayWinProbability":
            prediction_1x2["away"],

        # ====================================================
        # MAÇ SONUCU
        # ====================================================

        "played": is_played(match),

        "homeScore": safe_int(
            match.get("homeScore")
        ),

        "awayScore": safe_int(
            match.get("awayScore")
        ),
    }


# ============================================================
# ANA FONKSİYON
# ============================================================

def main():

    print("=" * 70)
    print("🏀 BASKETBOL BAREM ANALİZİ")
    print("=" * 70)

    print()

    print("📁 Veri:", INPUT_FILE)

    print(
        "🎯 Barem sayısı:",
        len(BAREMS)
    )

    print(
        "📊 Barem aralıkları:",
        BAREM_ARALIKLARI
    )

    print(
        "📈 Minimum güven:",
        f"%{MIN_CONFIDENCE}"
    )

    print(
        "📚 Minimum örnek:",
        MIN_SAMPLE
    )

    print()

    data = load_json(INPUT_FILE)

    matches = data.get("matches", [])

    if not isinstance(matches, list):
        raise RuntimeError(
            "basketball.json içindeki matches dizisi bulunamadı."
        )

    print(
        "🏀 Toplam maç:",
        len(matches)
    )

    history = prepare_history(
        matches
    )

    print(
        "📚 Oynanmış geçmiş maç:",
        len(history)
    )

    # Gelecek / oynanmamış maçlar
    upcoming = [
        match
        for match in matches
        if not is_played(match)
    ]

    print(
        "🔮 Oynanmamış maç:",
        len(upcoming)
    )

    print()

    predictions = []

    skipped = 0

    for match in upcoming:

        prediction = predict_match(
            match,
            history
        )

        if prediction is None:
            skipped += 1
            continue

        predictions.append(
            prediction
        )

    # Tarihe göre sırala
    predictions.sort(
        key=lambda x: (
            str(x.get("date") or ""),
            str(x.get("homeTeam") or "")
        )
    )

    output = {
        "updatedAt":
            datetime.now(timezone.utc).isoformat(),

        "source":
            INPUT_FILE,

        "baremAraliklari":
            BAREM_ARALIKLARI,

        "baremler":
            BAREMS,

        "minConfidence":
            MIN_CONFIDENCE,

        "minSample":
            MIN_SAMPLE,

        "totalMatches":
            len(predictions),

        "predictions":
            predictions,
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            separators=(",", ":")
        )

    print()
    print("=" * 70)
    print("✅ TAHMİNLER OLUŞTURULDU")
    print("=" * 70)

    print(
        "🎯 Tahmin bulunan:",
        len(predictions)
    )

    print(
        "⏭️ Tahmin oluşturulamayan:",
        skipped
    )

    print(
        "📁 Dosya:",
        OUTPUT_FILE
    )

    print()

    # İlk birkaç tahmini terminalde göster
    for item in predictions[:10]:

        print(
            f"🏀 {item['homeTeam']} - "
            f"{item['awayTeam']}"
        )

        print(
            f"   🎯 {item['barem']} "
            f"{item['prediction']} "
            f"%{item['confidence']}"
        )

        print(
            f"   📊 ÜST %{item['ustPercent']} "
            f"| ALT %{item['altPercent']}"
        )

        print(
            f"   🔢 Beklenen toplam: "
            f"{item['expectedTotal']}"
        )

        print()


if __name__ == "__main__":
    main()
