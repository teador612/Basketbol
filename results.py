import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


PREDICTIONS_FILE = Path("predictions.json")
OUTPUT_FILE = Path("results.json")


# ============================================================
# YARDIMCI
# ============================================================

def safe_float(value):
    try:
        if value is None:
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def safe_int(value):
    try:
        if value is None:
            return None

        return int(value)

    except (TypeError, ValueError):
        return None


def get_league_name(item):
    league = str(item.get("league", "")).upper()

    if league == "NBA":
        return "NBA"

    if league in (
        "E",
        "E2026",
        "EUROLEAGUE",
        "EUROLEGUE",
        "EUROPE",
    ):
        return "EuroLeague"

    return item.get("league", "Diğer")


def calculate_percentage(successful, total):
    if total <= 0:
        return None

    return round(
        successful / total * 100,
        2,
    )


# ============================================================
# ANA TAHMİN SONUCU
# ============================================================

def evaluate_prediction(item):
    """
    SADECE ANA TAHMİN:

    Maç Toplam Alt/Üst

    Diğer hiçbir market burada başarı hesabına girmez.
    """

    prediction = item.get("prediction")
    line = safe_float(item.get("line"))

    home_score = safe_float(
        item.get("homeScore")
    )

    away_score = safe_float(
        item.get("awayScore")
    )

    played = bool(
        item.get("played")
    )

    if not played:
        return {
            "status": "not_played",
            "prediction": prediction,
            "line": line,
            "actualTotal": None,
            "success": None,
        }

    if (
        prediction not in ("Alt", "Üst")
        or line is None
        or home_score is None
        or away_score is None
    ):
        return {
            "status": "invalid",
            "prediction": prediction,
            "line": line,
            "actualTotal": None,
            "success": None,
        }

    actual_total = (
        home_score + away_score
    )

    # Barem tam eşit ise PUSH.
    if actual_total == line:
        return {
            "status": "push",
            "prediction": prediction,
            "line": line,
            "actualTotal": actual_total,
            "success": None,
        }

    if actual_total > line:
        actual_result = "Üst"
    else:
        actual_result = "Alt"

    success = (
        prediction == actual_result
    )

    return {
        "status": (
            "success"
            if success
            else "failed"
        ),
        "prediction": prediction,
        "line": line,
        "actualTotal": actual_total,
        "actualResult": actual_result,
        "success": success,
    }


# ============================================================
# GENEL İSTATİSTİK
# ============================================================

def calculate_stats(items):
    completed = [
        item
        for item in items
        if item["evaluation"]["status"]
        in (
            "success",
            "failed",
        )
    ]

    successful = [
        item
        for item in completed
        if item["evaluation"]["success"]
        is True
    ]

    failed = [
        item
        for item in completed
        if item["evaluation"]["success"]
        is False
    ]

    pushes = [
        item
        for item in items
        if item["evaluation"]["status"]
        == "push"
    ]

    not_played = [
        item
        for item in items
        if item["evaluation"]["status"]
        == "not_played"
    ]

    invalid = [
        item
        for item in items
        if item["evaluation"]["status"]
        == "invalid"
    ]

    total = len(completed)

    return {
        "totalPredictions": len(items),
        "completed": total,
        "successful": len(successful),
        "failed": len(failed),
        "push": len(pushes),
        "notPlayed": len(not_played),
        "invalid": len(invalid),
        "successRate": calculate_percentage(
            len(successful),
            total,
        ),
    }


# ============================================================
# LİG İSTATİSTİKLERİ
# ============================================================

def calculate_league_stats(items):
    groups = defaultdict(list)

    for item in items:
        league = get_league_name(
            item["prediction"]
        )

        groups[league].append(item)

    result = {}

    for league, league_items in groups.items():
        result[league] = calculate_stats(
            league_items
        )

    return result


# ============================================================
# TARİH İSTATİSTİKLERİ
# ============================================================

def calculate_daily_stats(items):
    groups = defaultdict(list)

    for item in items:
        date = (
            item["prediction"]
            .get("date")
            or "unknown"
        )

        groups[date].append(item)

    result = {}

    for date, date_items in sorted(
        groups.items()
    ):
        result[date] = calculate_stats(
            date_items
        )

    return result


# ============================================================
# TAHMİN DAĞILIMI
# ============================================================

def calculate_prediction_distribution(items):
    result = {
        "Alt": {
            "total": 0,
            "successful": 0,
            "failed": 0,
        },
        "Üst": {
            "total": 0,
            "successful": 0,
            "failed": 0,
        },
    }

    for item in items:
        evaluation = item["evaluation"]

        prediction = evaluation.get(
            "prediction"
        )

        if prediction not in result:
            continue

        status = evaluation.get(
            "status"
        )

        if status == "push":
            continue

        if status not in (
            "success",
            "failed",
        ):
            continue

        result[prediction]["total"] += 1

        if status == "success":
            result[prediction]["successful"] += 1

        elif status == "failed":
            result[prediction]["failed"] += 1

    for prediction in result:
        total = result[prediction]["total"]
        successful = result[prediction]["successful"]

        result[prediction]["successRate"] = (
            calculate_percentage(
                successful,
                total,
            )
        )

    return result


# ============================================================
# SONUÇ KAYITLARI
# ============================================================

def build_result_item(item):
    evaluation = item["evaluation"]

    return {
        "id": item["prediction"].get("id"),

        "league": get_league_name(
            item["prediction"]
        ),

        "season": item["prediction"].get(
            "season"
        ),

        "date": item["prediction"].get(
            "date"
        ),

        "home": item["prediction"].get(
            "home"
        ),

        "away": item["prediction"].get(
            "away"
        ),

        "prediction": evaluation.get(
            "prediction"
        ),

        "line": evaluation.get(
            "line"
        ),

        "homeScore": item["prediction"].get(
            "homeScore"
        ),

        "awayScore": item["prediction"].get(
            "awayScore"
        ),

        "actualTotal": evaluation.get(
            "actualTotal"
        ),

        "actualResult": evaluation.get(
            "actualResult"
        ),

        "status": evaluation.get(
            "status"
        ),

        "success": evaluation.get(
            "success"
        ),
    }


# ============================================================
# DOSYA OKU
# ============================================================

def load_predictions():
    if not PREDICTIONS_FILE.exists():
        raise FileNotFoundError(
            "predictions.json bulunamadı."
        )

    with PREDICTIONS_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:
        return json.load(f)


# ============================================================
# KAYDET
# ============================================================

def save_results(output):
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


# ============================================================
# ANA PROGRAM
# ============================================================

def main():

    print("=" * 70)
    print("🏀 BASKETBOL ANA TAHMİN SONUÇ ANALİZİ")
    print("=" * 70)

    data = load_predictions()

    predictions = data.get(
        "predictions",
        [],
    )

    print()
    print(
        f"📦 Toplam tahmin: {len(predictions)}"
    )

    results = []

    for prediction in predictions:

        evaluation = evaluate_prediction(
            prediction
        )

        result_item = {
            "prediction": prediction,
            "evaluation": evaluation,
        }

        results.append(result_item)

    # ========================================================
    # İSTATİSTİKLER
    # ========================================================

    overall = calculate_stats(
        results
    )

    league_stats = calculate_league_stats(
        results
    )

    daily_stats = calculate_daily_stats(
        results
    )

    distribution = (
        calculate_prediction_distribution(
            results
        )
    )

    # ========================================================
    # ÇIKTI
    # ========================================================

    output = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": "predictions.json",

        "settings": {
            "mainMarket": "Maç Toplam Alt/Üst",

            "successRateOnlyMainPrediction": True,

            "excludedFromMainSuccessRate": [
                "1/X/2",
                "İY Alt/Üst",
                "Q1 Alt/Üst",
                "Q2 Alt/Üst",
                "Q3 Alt/Üst",
                "Q4 Alt/Üst",
            ],

            "pushExcludedFromSuccessRate": True,
        },

        "statistics": {
            "overall": overall,

            "leagues": league_stats,

            "daily": daily_stats,

            "predictionDistribution": distribution,
        },

        "results": [
            build_result_item(item)
            for item in results
        ],
    }

    save_results(output)

    # ========================================================
    # EKRAN
    # ========================================================

    print()
    print("=" * 70)
    print("📊 GENEL BAŞARI")
    print("=" * 70)

    print(
        "Toplam tahmin   :",
        overall["totalPredictions"],
    )

    print(
        "Tamamlanan      :",
        overall["completed"],
    )

    print(
        "✅ Başarılı      :",
        overall["successful"],
    )

    print(
        "❌ Başarısız     :",
        overall["failed"],
    )

    print(
        "⏸️ Push           :",
        overall["push"],
    )

    print(
        "⏳ Oynanmamış    :",
        overall["notPlayed"],
    )

    print(
        "📊 Başarı oranı  :",
        (
            f"%{overall['successRate']}"
            if overall["successRate"]
            is not None
            else "-"
        ),
    )

    # ========================================================
    # LİG
    # ========================================================

    print()
    print("=" * 70)
    print("🏆 LİG BAŞARILARI")
    print("=" * 70)

    for league, stats in league_stats.items():

        rate = stats.get(
            "successRate"
        )

        rate_text = (
            f"%{rate}"
            if rate is not None
            else "-"
        )

        print(
            f"{league}: "
            f"{stats['successful']}/"
            f"{stats['completed']} "
            f"→ {rate_text}"
        )

    # ========================================================
    # ALT / ÜST
    # ========================================================

    print()
    print("=" * 70)
    print("📈 ALT / ÜST DAĞILIMI")
    print("=" * 70)

    for prediction, stats in distribution.items():

        rate = stats.get(
            "successRate"
        )

        rate_text = (
            f"%{rate}"
            if rate is not None
            else "-"
        )

        print(
            f"{prediction}: "
            f"{stats['successful']}/"
            f"{stats['total']} "
            f"→ {rate_text}"
        )

    print()
    print("=" * 70)
    print("✅ results.json oluşturuldu")
    print("=" * 70)


if __name__ == "__main__":
    main()
