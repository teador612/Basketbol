import json
import math
from pathlib import Path
from statistics import mean


INPUT_FILE = Path("basketball.json")
OUTPUT_FILE = Path("predictions.json")

MAX_HISTORY = 5
LINE_STEP = 5


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def safe_float(value):
    try:
        if value is None:
            return None

        number = float(value)

        if math.isnan(number) or math.isinf(number):
            return None

        return number

    except (TypeError, ValueError):
        return None


def safe_int(value):
    try:
        if value is None:
            return None

        return int(value)

    except (TypeError, ValueError):
        return None


def average(values):
    values = [
        safe_float(value)
        for value in values
        if safe_float(value) is not None
    ]

    if not values:
        return None

    return mean(values)


def round_number(value, digits=2):
    value = safe_float(value)

    if value is None:
        return None

    return round(value, digits)


def round_line(value):
    """
    Barem 5'in katına yuvarlanır.

    Örnek:
    157 -> 155
    158 -> 160
    162 -> 160
    """

    value = safe_float(value)

    if value is None:
        return None

    return int(round(value / LINE_STEP) * LINE_STEP)


def clamp(value, minimum=50, maximum=95):
    value = safe_float(value)

    if value is None:
        return None

    return round(max(minimum, min(maximum, value)), 1)


# ============================================================
# GEÇMİŞ MAÇLAR
# ============================================================

def get_home_history(match):
    history = match.get("homeHistory", [])

    if not isinstance(history, list):
        return []

    return history[:MAX_HISTORY]


def get_away_history(match):
    history = match.get("awayHistory", [])

    if not isinstance(history, list):
        return []

    return history[:MAX_HISTORY]


# ============================================================
# MAÇ TOPLAMLARI
# ============================================================

def history_match_total(item):
    scored = safe_float(item.get("scored"))
    conceded = safe_float(item.get("conceded"))

    if scored is None or conceded is None:
        return None

    return scored + conceded


def get_history_totals(history):
    totals = []

    for item in history:
        total = history_match_total(item)

        if total is not None:
            totals.append(total)

    return totals


# ============================================================
# ANA BAREM HESABI
# ============================================================

def calculate_main_line(home_history, away_history):
    """
    Ana barem:

    Ev takımının son 5 ev maçı toplam ortalaması
    +
    Deplasman takımının son 5 deplasman maçı toplam ortalaması

    iki takımın ortalaması alınır.

    Böylece iki tarafın mevcut gol/puan üretim seviyesine
    göre maç toplam baremi oluşturulur.
    """

    home_totals = get_history_totals(home_history)
    away_totals = get_history_totals(away_history)

    home_average = average(home_totals)
    away_average = average(away_totals)

    values = []

    if home_average is not None:
        values.append(home_average)

    if away_average is not None:
        values.append(away_average)

    if not values:
        return {
            "homeAverage": None,
            "awayAverage": None,
            "rawAverage": None,
            "line": None,
        }

    raw_average = average(values)

    return {
        "homeAverage": round_number(home_average),
        "awayAverage": round_number(away_average),
        "rawAverage": round_number(raw_average),
        "line": round_line(raw_average),
    }


# ============================================================
# BEKLENEN MAÇ TOPLAMI
# ============================================================

def calculate_expected_total(match):
    """
    Beklenen toplam:

    Ev takımının attığı ortalama
    +
    Ev takımının yediği ortalama
    +
    Deplasman takımının attığı ortalama
    +
    Deplasman takımının yediği ortalama

    iki takımın beklenen skorları üzerinden hesaplanır.
    """

    home_history = get_home_history(match)
    away_history = get_away_history(match)

    home_scored = average([
        safe_float(item.get("scored"))
        for item in home_history
        if safe_float(item.get("scored")) is not None
    ])

    home_conceded = average([
        safe_float(item.get("conceded"))
        for item in home_history
        if safe_float(item.get("conceded")) is not None
    ])

    away_scored = average([
        safe_float(item.get("scored"))
        for item in away_history
        if safe_float(item.get("scored")) is not None
    ])

    away_conceded = average([
        safe_float(item.get("conceded"))
        for item in away_history
        if safe_float(item.get("conceded")) is not None
    ])

    expected_home_values = []

    if home_scored is not None:
        expected_home_values.append(home_scored)

    if away_conceded is not None:
        expected_home_values.append(away_conceded)

    expected_away_values = []

    if away_scored is not None:
        expected_away_values.append(away_scored)

    if home_conceded is not None:
        expected_away_values.append(home_conceded)

    expected_home = average(expected_home_values)
    expected_away = average(expected_away_values)

    expected_total = None

    if expected_home is not None and expected_away is not None:
        expected_total = expected_home + expected_away
    elif expected_home is not None:
        expected_total = expected_home
    elif expected_away is not None:
        expected_total = expected_away

    return {
        "expectedHome": round_number(expected_home),
        "expectedAway": round_number(expected_away),
        "expectedTotal": round_number(expected_total),
    }


# ============================================================
# ALT / ÜST
# ============================================================

def calculate_over_under(line, expected_total):
    if line is None or expected_total is None:
        return {
            "prediction": None,
            "confidence": None,
            "difference": None,
        }

    difference = expected_total - line

    if difference > 0:
        prediction = "Üst"
    elif difference < 0:
        prediction = "Alt"
    else:
        prediction = "Üst"

    # Fark büyüdükçe güven yükselir.
    confidence = 50 + abs(difference) * 8

    return {
        "prediction": prediction,
        "confidence": clamp(confidence),
        "difference": round_number(difference),
    }


# ============================================================
# ANA TAHMİN
# ============================================================

def calculate_main_prediction(match):
    home_history = get_home_history(match)
    away_history = get_away_history(match)

    barem = calculate_main_line(
        home_history,
        away_history,
    )

    expected = calculate_expected_total(match)

    result = calculate_over_under(
        barem["line"],
        expected["expectedTotal"],
    )

    return {
        # ANA TAHMİN
        "prediction": result["prediction"],

        # ANA BAREM
        "line": barem["line"],

        # HESAPLAMALAR
        "expectedTotal": expected["expectedTotal"],
        "expectedHome": expected["expectedHome"],
        "expectedAway": expected["expectedAway"],

        # GEÇMİŞ ORTALAMALARI
        "homeAverageTotal": barem["homeAverage"],
        "awayAverageTotal": barem["awayAverage"],
        "rawAverageTotal": barem["rawAverage"],

        # GÜVEN
        "confidence": result["confidence"],
        "difference": result["difference"],

        # ANA MARKET
        "market": "Maç Toplam",
    }


# ============================================================
# PERİYOT VERİLERİ
# ============================================================

def get_period_total(item, period):
    periods = item.get("periods", {})

    if not isinstance(periods, dict):
        return None

    data = periods.get(period)

    if not isinstance(data, dict):
        return None

    total = safe_float(data.get("total"))

    if total is not None:
        return total

    home = safe_float(data.get("home"))
    away = safe_float(data.get("away"))

    if home is None or away is None:
        return None

    return home + away


def calculate_period_market(history, period):
    totals = []

    for item in history:
        total = get_period_total(item, period)

        if total is not None:
            totals.append(total)

    if not totals:
        return None

    raw_average = average(totals)
    line = round_line(raw_average)

    return {
        "line": line,
        "average": round_number(raw_average),
        "sample": len(totals),
    }


# ============================================================
# İLK YARI
# ============================================================

def get_first_half_total(item):
    q1 = get_period_total(item, "q1")
    q2 = get_period_total(item, "q2")

    if q1 is None or q2 is None:
        return None

    return q1 + q2


def calculate_first_half_market(history):
    totals = []

    for item in history:
        total = get_first_half_total(item)

        if total is not None:
            totals.append(total)

    if not totals:
        return None

    raw_average = average(totals)
    line = round_line(raw_average)

    if raw_average > line:
        prediction = "Üst"
    else:
        prediction = "Alt"

    difference = raw_average - line

    return {
        "prediction": prediction,
        "line": line,
        "average": round_number(raw_average),
        "difference": round_number(difference),
        "confidence": clamp(50 + abs(difference) * 8),
        "sample": len(totals),
        "market": "İY Toplam",
    }


# ============================================================
# DÖNEM MARKETLERİ
# ============================================================

def calculate_period_predictions(home_history, away_history):
    results = {}

    for period in ("q1", "q2", "q3", "q4"):

        home_market = calculate_period_market(
            home_history,
            period,
        )

        away_market = calculate_period_market(
            away_history,
            period,
        )

        averages = []

        if home_market and home_market.get("average") is not None:
            averages.append(home_market["average"])

        if away_market and away_market.get("average") is not None:
            averages.append(away_market["average"])

        if not averages:
            results[period] = None
            continue

        raw_average = average(averages)
        line = round_line(raw_average)

        if raw_average > line:
            prediction = "Üst"
        else:
            prediction = "Alt"

        difference = raw_average - line

        results[period] = {
            "prediction": prediction,
            "line": line,
            "average": round_number(raw_average),
            "difference": round_number(difference),
            "confidence": clamp(50 + abs(difference) * 8),
            "homeAverage": (
                home_market["average"]
                if home_market
                else None
            ),
            "awayAverage": (
                away_market["average"]
                if away_market
                else None
            ),
            "market": period.upper(),
        }

    return results


# ============================================================
# MAÇ TAHMİNİ
# ============================================================

def predict_match(match):
    home_history = get_home_history(match)
    away_history = get_away_history(match)

    # --------------------------------------------------------
    # ANA TAHMİN
    # --------------------------------------------------------

    main = calculate_main_prediction(match)

    # --------------------------------------------------------
    # İLK YARI
    # --------------------------------------------------------

    combined_history = []

    # Ev + deplasman geçmişini ayrı ayrı değerlendiriyoruz.
    combined_history.extend(home_history)
    combined_history.extend(away_history)

    first_half = calculate_first_half_market(
        combined_history
    )

    # --------------------------------------------------------
    # Q1-Q4
    # --------------------------------------------------------

    periods = calculate_period_predictions(
        home_history,
        away_history,
    )

    # --------------------------------------------------------
    # SONUÇ
    # --------------------------------------------------------

    result = {
        "id": match.get("id"),
        "league": match.get("league"),
        "season": match.get("season"),

        "date": match.get("date"),
        "utcDate": match.get("utcDate"),

        "home": match.get("homeTeam"),
        "away": match.get("awayTeam"),

        # ====================================================
        # ANA TAHMİN
        # ====================================================

        "prediction": main["prediction"],
        "market": main["market"],
        "line": main["line"],
        "confidence": main["confidence"],

        "expectedTotal": main["expectedTotal"],
        "expectedHome": main["expectedHome"],
        "expectedAway": main["expectedAway"],

        "homeAverageTotal": main["homeAverageTotal"],
        "awayAverageTotal": main["awayAverageTotal"],
        "rawAverageTotal": main["rawAverageTotal"],

        "difference": main["difference"],

        # ====================================================
        # ÖRNEKLEM
        # ====================================================

        "homeSample": len(home_history),
        "awaySample": len(away_history),

        "homeLast5": home_history,
        "awayLast5": away_history,

        # ====================================================
        # DİĞER MARKETLER
        # ====================================================

        "firstHalfTotal": first_half,

        "q1": periods.get("q1"),
        "q2": periods.get("q2"),
        "q3": periods.get("q3"),
        "q4": periods.get("q4"),

        # ====================================================
        # SONUÇ
        # ====================================================

        "played": bool(match.get("played")),

        "homeScore": match.get("homeScore"),
        "awayScore": match.get("awayScore"),

        "result": None,
        "success": None,
    }

    # --------------------------------------------------------
    # OYNANMIŞ MAÇ İSE ANA TAHMİNİ DEĞERLENDİR
    # --------------------------------------------------------

    home_score = safe_float(match.get("homeScore"))
    away_score = safe_float(match.get("awayScore"))

    if (
        match.get("played")
        and home_score is not None
        and away_score is not None
        and main["line"] is not None
        and main["prediction"] is not None
    ):
        actual_total = home_score + away_score

        if actual_total > main["line"]:
            actual_result = "Üst"
        elif actual_total < main["line"]:
            actual_result = "Alt"
        else:
            actual_result = "Push"

        if actual_result == "Push":
            success = None
        else:
            success = (
                actual_result == main["prediction"]
            )

        result["result"] = actual_result
        result["actualTotal"] = actual_total
        result["success"] = success

    return result


# ============================================================
# VERİ OKU
# ============================================================

def load_data():
    possible_files = [
        Path("basketball.json"),
        Path("data/basketball.json"),
    ]

    for file in possible_files:
        if file.exists():
            with file.open(
                "r",
                encoding="utf-8",
            ) as f:
                return json.load(f)

    raise FileNotFoundError(
        "basketball.json bulunamadı."
    )


# ============================================================
# KAYDET
# ============================================================

def save_predictions(predictions, source):
    completed = [
        item
        for item in predictions
        if item.get("success") is not None
    ]

    successful = [
        item
        for item in completed
        if item.get("success") is True
    ]

    failed = [
        item
        for item in completed
        if item.get("success") is False
    ]

    success_rate = None

    if completed:
        success_rate = (
            len(successful)
            / len(completed)
            * 100
        )

    output = {
        "updatedAt": source.get(
            "updatedAt"
        ),

        "generatedAt": __import__(
            "datetime"
        ).datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),

        "settings": {
            "maxHistory": MAX_HISTORY,
            "lineStep": LINE_STEP,

            # ANA MARKET
            "mainMarket": "Maç Toplam Alt/Üst",

            # ANA BAŞARI ORANI
            "mainSuccessRateIncludes": [
                "Maç Toplam Alt/Üst"
            ],

            "mainSuccessRateExcludes": [
                "1/X/2",
                "İY Alt/Üst",
                "Q1 Alt/Üst",
                "Q2 Alt/Üst",
                "Q3 Alt/Üst",
                "Q4 Alt/Üst",
            ],

            "euroLeagueRequiresFiveGames": False,
        },

        "statistics": {
            "totalPredictions": len(predictions),
            "completed": len(completed),
            "successful": len(successful),
            "failed": len(failed),
            "push": len([
                item
                for item in predictions
                if item.get("result") == "Push"
            ]),
            "successRate": (
                round(success_rate, 2)
                if success_rate is not None
                else None
            ),
        },

        "predictions": predictions,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2,
        )

    return output


# ============================================================
# ANA PROGRAM
# ============================================================

def main():
    print("=" * 70)
    print("🏀 BASKETBOL ANA TAHMİN SİSTEMİ")
    print("=" * 70)

    print()
    print("🎯 ANA MARKET: MAÇ TOPLAM ALT/ÜST")
    print("📚 Geçmiş: maksimum 5 maç")
    print("📊 Eksik geçmiş maçları kullanılabilir")
    print("🏀 EuroLeague: mevcut sezon E2026")
    print()

    source = load_data()

    matches = source.get("matches", [])

    print(
        f"📦 Toplam maç: {len(matches)}"
    )

    predictions = []

    for match in matches:

        prediction = predict_match(match)

        # Tahmin oluşturulamayan kayıtları da
        # tamamen kaybetmemek için listeye ekliyoruz.
        predictions.append(prediction)

    output = save_predictions(
        predictions,
        source,
    )

    print()
    print("=" * 70)
    print("📊 SONUÇ")
    print("=" * 70)

    print(
        "Toplam tahmin       :",
        output["statistics"]["totalPredictions"],
    )

    print(
        "Tamamlanan          :",
        output["statistics"]["completed"],
    )

    print(
        "Başarılı            :",
        output["statistics"]["successful"],
    )

    print(
        "Başarısız           :",
        output["statistics"]["failed"],
    )

    print(
        "Push                :",
        output["statistics"]["push"],
    )

    print(
        "Ana başarı oranı    :",
        output["statistics"]["successRate"],
    )

    print()
    print("=" * 70)
    print("✅ predictions.json oluşturuldu")
    print("=" * 70)


if __name__ == "__main__":
    main()
