import json
from pathlib import Path
from collections import defaultdict


INPUT_FILE = Path("predictions.json")
OUTPUT_FILE = Path("analysis.json")


def load_predictions():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"❌ {INPUT_FILE} bulunamadı."
        )

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    predictions = data.get("predictions", [])

    if not isinstance(predictions, list):
        raise RuntimeError(
            "❌ predictions.json içindeki predictions alanı liste değil."
        )

    return predictions


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def percentage(successful, total):
    if total <= 0:
        return 0.0

    return round(
        successful / total * 100,
        2
    )


def empty_stats():
    return {
        "total": 0,
        "completed": 0,
        "successful": 0,
        "failed": 0,
        "push": 0,
        "successRate": 0.0,
        "averageError": 0.0,
    }


def add_result(stats, prediction, actual_total):
    stats["total"] += 1
    stats["completed"] += 1

    line = safe_float(
        prediction.get("line")
    )

    predicted = str(
        prediction.get("prediction", "")
    ).strip().lower()

    if line is None or actual_total is None:
        return

    difference = abs(
        actual_total - line
    )

    stats.setdefault(
        "_error_sum",
        0.0
    )

    stats["_error_sum"] += difference

    if actual_total == line:
        stats["push"] += 1
        return

    actual_result = (
        "Üst"
        if actual_total > line
        else "Alt"
    )

    if predicted == actual_result.lower():
        stats["successful"] += 1
    else:
        stats["failed"] += 1


def finalize_stats(stats):
    completed_without_push = (
        stats["successful"]
        + stats["failed"]
    )

    stats["successRate"] = percentage(
        stats["successful"],
        completed_without_push
    )

    if stats.get("completed", 0) > 0:
        stats["averageError"] = round(
            stats.get("_error_sum", 0.0)
            / stats["completed"],
            2
        )

    stats.pop(
        "_error_sum",
        None
    )

    return stats


def analyze():
    predictions = load_predictions()

    overall = empty_stats()

    leagues = defaultdict(empty_stats)
    prediction_types = defaultdict(empty_stats)
    line_ranges = defaultdict(empty_stats)

    completed_rows = []

    for prediction in predictions:

        played = prediction.get(
            "played",
            False
        )

        if not played:
            continue

        home_score = safe_int(
            prediction.get("homeScore")
        )

        away_score = safe_int(
            prediction.get("awayScore")
        )

        if (
            home_score is None
            or away_score is None
        ):
            continue

        actual_total = (
            home_score
            + away_score
        )

        line = safe_float(
            prediction.get("line")
        )

        predicted = str(
            prediction.get("prediction", "")
        ).strip()

        if line is None:
            continue

        add_result(
            overall,
            prediction,
            actual_total
        )

        league = (
            prediction.get("league")
            or "Bilinmiyor"
        )

        add_result(
            leagues[league],
            prediction,
            actual_total
        )

        prediction_key = (
            predicted
            if predicted
            else "Bilinmiyor"
        )

        add_result(
            prediction_types[prediction_key],
            prediction,
            actual_total
        )

        # Barem aralıkları
        if line < 140:
            range_name = "<140"
        elif line < 160:
            range_name = "140-159"
        elif line < 180:
            range_name = "160-179"
        elif line < 200:
            range_name = "180-199"
        else:
            range_name = "200+"

        add_result(
            line_ranges[range_name],
            prediction,
            actual_total
        )

        actual_result = (
            "Üst"
            if actual_total > line
            else (
                "Alt"
                if actual_total < line
                else "Push"
            )
        )

        if actual_total == line:
            status = "Push"
            success = None
        else:
            status = (
                "Başarılı"
                if predicted.lower()
                == actual_result.lower()
                else "Başarısız"
            )

            success = (
                status == "Başarılı"
            )

        completed_rows.append({
            "id": prediction.get("id"),
            "league": league,
            "season": prediction.get("season"),
            "date": prediction.get("date"),
            "home": prediction.get("home"),
            "away": prediction.get("away"),
            "prediction": predicted,
            "line": line,
            "expectedTotal": prediction.get(
                "expectedTotal"
            ),
            "homeScore": home_score,
            "awayScore": away_score,
            "actualTotal": actual_total,
            "difference": round(
                actual_total - line,
                2
            ),
            "absoluteError": round(
                abs(actual_total - line),
                2
            ),
            "actualResult": actual_result,
            "status": status,
            "success": success,
        })

    overall = finalize_stats(
        overall
    )

    leagues = {
        league: finalize_stats(stats)
        for league, stats in leagues.items()
    }

    prediction_types = {
        market: finalize_stats(stats)
        for market, stats in prediction_types.items()
    }

    line_ranges = {
        line_range: finalize_stats(stats)
        for line_range, stats in line_ranges.items()
    }

    # En çok yanılan maçlar
    biggest_errors = sorted(
        completed_rows,
        key=lambda x: x["absoluteError"],
        reverse=True
    )[:20]

    # En başarılı tahminler
    closest_predictions = sorted(
        completed_rows,
        key=lambda x: x["absoluteError"]
    )[:20]

    # Üst / Alt ayrımı
    over_stats = prediction_types.get(
        "Üst",
        empty_stats()
    )

    under_stats = prediction_types.get(
        "Alt",
        empty_stats()
    )

    result = {
        "updatedAt": __import__(
            "datetime"
        ).datetime.now(
            __import__(
                "datetime"
            ).timezone.utc
        ).isoformat(),

        "settings": {
            "mainMarket": "Maç Toplam Alt/Üst",
            "analysisPurpose": (
                "Mevcut ana tahminlerin "
                "başarı ve hata analizi"
            ),
            "pushExcludedFromSuccessRate": True,
            "secondaryMarketsExcluded": True,
        },

        "overall": overall,

        "leagues": leagues,

        "predictionTypes": prediction_types,

        "lineRanges": line_ranges,

        "over": over_stats,

        "under": under_stats,

        "biggestErrors": biggest_errors,

        "closestPredictions": closest_predictions,

        "completedMatches": completed_rows,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("=" * 70)
    print("🏀 BASKETBOL TAHMİN ANALİZİ")
    print("=" * 70)

    print()
    print("📊 GENEL")
    print("-" * 70)

    print(
        "Tamamlanan       :",
        overall["completed"]
    )

    print(
        "Başarılı         :",
        overall["successful"]
    )

    print(
        "Başarısız        :",
        overall["failed"]
    )

    print(
        "Push             :",
        overall["push"]
    )

    print(
        "Başarı oranı     :",
        f"%{overall['successRate']}"
    )

    print(
        "Ortalama hata    :",
        overall["averageError"]
    )

    print()
    print("🏆 LİGLER")
    print("-" * 70)

    for league, stats in leagues.items():
        print(
            f"{league}: "
            f"{stats['successful']}/"
            f"{stats['successful'] + stats['failed']} "
            f"→ %{stats['successRate']} "
            f"| Ortalama hata: "
            f"{stats['averageError']}"
        )

    print()
    print("📈 ÜST / ALT")
    print("-" * 70)

    for name in ["Üst", "Alt"]:
        stats = prediction_types.get(
            name
        )

        if not stats:
            continue

        print(
            f"{name}: "
            f"{stats['successful']}/"
            f"{stats['successful'] + stats['failed']} "
            f"→ %{stats['successRate']} "
            f"| Hata: "
            f"{stats['averageError']}"
        )

    print()
    print("🎯 BAREM ARALIKLARI")
    print("-" * 70)

    range_order = [
        "<140",
        "140-159",
        "160-179",
        "180-199",
        "200+",
    ]

    for range_name in range_order:

        stats = line_ranges.get(
            range_name
        )

        if not stats:
            continue

        print(
            f"{range_name}: "
            f"{stats['successful']}/"
            f"{stats['successful'] + stats['failed']} "
            f"→ %{stats['successRate']} "
            f"| Ortalama hata: "
            f"{stats['averageError']}"
        )

    print()
    print("🔥 EN BÜYÜK HATALAR")
    print("-" * 70)

    for row in biggest_errors[:10]:

        print(
            f"{row['home']} - "
            f"{row['away']} | "
            f"Barem: {row['line']} | "
            f"Tahmin: {row['prediction']} | "
            f"Gerçek: {row['actualTotal']} | "
            f"Fark: {row['difference']}"
        )

    print()
    print("📁 Oluşturuldu:", OUTPUT_FILE)
    print("=" * 70)


if __name__ == "__main__":
    analyze()
