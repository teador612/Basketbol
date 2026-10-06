import json
from pathlib import Path
from datetime import datetime, timezone
import math


# ============================================================
# AYARLAR
# ============================================================

MAX_HISTORY = 10

# En yeni maç 1.00, en eski maç 0.55 ağırlık alır.
NEWEST_WEIGHT = 1.00
OLDEST_WEIGHT = 0.55

# Ev sahibi avantajı
HOME_ADVANTAGE = 2.0

INPUT_FILES = [
    Path("basketball.json"),
    Path("data/basketball.json"),
]

OUTPUT_FILE = Path("predictions.json")


# ============================================================
# DOSYA OKUMA
# ============================================================

def load_input():
    for path in INPUT_FILES:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f), path

    raise FileNotFoundError(
        "basketball.json bulunamadı. "
        "Kontrol edilen yollar: "
        + ", ".join(str(x) for x in INPUT_FILES)
    )


# ============================================================
# SAYI YARDIMCILARI
# ============================================================

def to_float(value):
    try:
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def round_value(value, digits=2):
    if value is None:
        return None

    return round(float(value), digits)


def weighted_average(values):
    """
    values:
        [en yeni, ..., en eski]

    En yeni maça daha yüksek ağırlık verir.
    """

    valid = []

    for value in values:
        number = to_float(value)

        if number is not None:
            valid.append(number)

    if not valid:
        return None

    count = len(valid)

    if count == 1:
        return valid[0]

    weights = []

    for index in range(count):
        if count == 1:
            weight = NEWEST_WEIGHT
        else:
            progress = index / (count - 1)

            weight = (
                NEWEST_WEIGHT
                - (
                    (NEWEST_WEIGHT - OLDEST_WEIGHT)
                    * progress
                )
            )

        weights.append(weight)

    weighted_sum = sum(
        value * weight
        for value, weight in zip(valid, weights)
    )

    weight_sum = sum(weights)

    if weight_sum == 0:
        return None

    return weighted_sum / weight_sum


def simple_average(values):
    valid = []

    for value in values:
        number = to_float(value)

        if number is not None:
            valid.append(number)

    if not valid:
        return None

    return sum(valid) / len(valid)


# ============================================================
# PERİYOT
# ============================================================

def period_total(period):
    if not isinstance(period, dict):
        return None

    home = to_float(period.get("home"))
    away = to_float(period.get("away"))

    if home is None or away is None:
        return None

    return home + away


def get_period_value(periods, key):
    if not isinstance(periods, dict):
        return None

    period = periods.get(key)

    if not isinstance(period, dict):
        return None

    return period_total(period)


# ============================================================
# MAÇ TOPLAMI
# ============================================================

def match_total_from_history(item):
    if not isinstance(item, dict):
        return None

    scored = to_float(item.get("scored"))
    conceded = to_float(item.get("conceded"))

    if scored is None or conceded is None:
        return None

    return scored + conceded


# ============================================================
# TARİH
# ============================================================

def history_sort_key(item):
    if not isinstance(item, dict):
        return ""

    value = (
        item.get("utcDate")
        or item.get("date")
        or ""
    )

    return str(value)


# ============================================================
# SON 10 EV MAÇI
# ============================================================

def get_home_history(match):
    history = match.get("homeHistory", [])

    if not isinstance(history, list):
        return []

    history = [
        item
        for item in history
        if isinstance(item, dict)
    ]

    history.sort(
        key=history_sort_key,
        reverse=True
    )

    return history[:MAX_HISTORY]


# ============================================================
# SON 10 DEPLASMAN MAÇI
# ============================================================

def get_away_history(match):
    history = match.get("awayHistory", [])

    if not isinstance(history, list):
        return []

    history = [
        item
        for item in history
        if isinstance(item, dict)
    ]

    history.sort(
        key=history_sort_key,
        reverse=True
    )

    return history[:MAX_HISTORY]


# ============================================================
# TAKIM İSTATİSTİKLERİ
# ============================================================

def calculate_team_stats(history):
    scored = []
    conceded = []
    totals = []

    for item in history:
        scored_value = to_float(
            item.get("scored")
        )

        conceded_value = to_float(
            item.get("conceded")
        )

        total_value = match_total_from_history(
            item
        )

        if scored_value is not None:
            scored.append(scored_value)

        if conceded_value is not None:
            conceded.append(conceded_value)

        if total_value is not None:
            totals.append(total_value)

    return {
        "sample": len(totals),

        "scoredAverage": weighted_average(
            scored
        ),

        "concededAverage": weighted_average(
            conceded
        ),

        "totalAverage": weighted_average(
            totals
        ),

        "scoredSimpleAverage": simple_average(
            scored
        ),

        "concededSimpleAverage": simple_average(
            conceded
        ),

        "totalSimpleAverage": simple_average(
            totals
        ),
    }


# ============================================================
# BEKLENEN TAKIM SAYILARI
# ============================================================

def calculate_expected_scores(
    home_stats,
    away_stats
):
    home_scored = home_stats.get(
        "scoredAverage"
    )

    home_conceded = home_stats.get(
        "concededAverage"
    )

    away_scored = away_stats.get(
        "scoredAverage"
    )

    away_conceded = away_stats.get(
        "concededAverage"
    )

    if (
        home_scored is None
        or home_conceded is None
        or away_scored is None
        or away_conceded is None
    ):
        return None

    # Ev takımının hücumu
    # + rakibin savunmada verdiği sayı
    expected_home = (
        home_scored
        + away_conceded
    ) / 2

    # Deplasman hücumu
    # + ev sahibinin savunmada verdiği sayı
    expected_away = (
        away_scored
        + home_conceded
    ) / 2

    # Ev sahibi avantajı
    expected_home += HOME_ADVANTAGE

    expected_total = (
        expected_home
        + expected_away
    )

    return {
        "home": round_value(
            expected_home,
            2
        ),

        "away": round_value(
            expected_away,
            2
        ),

        "total": round_value(
            expected_total,
            2
        ),
    }


# ============================================================
# ANA MAÇ BAREMİ
# ============================================================

def calculate_main_line(
    home_stats,
    away_stats
):
    home_total = home_stats.get(
        "totalAverage"
    )

    away_total = away_stats.get(
        "totalAverage"
    )

    if (
        home_total is None
        or away_total is None
    ):
        return None

    line = (
        home_total
        + away_total
    ) / 2

    return round_value(
        line,
        2
    )


# ============================================================
# ALT / ÜST
# ============================================================

def calculate_over_under(
    expected_total,
    line
):
    if (
        expected_total is None
        or line is None
    ):
        return None

    if expected_total > line:
        return "Üst"

    if expected_total < line:
        return "Alt"

    return "Üst"


# ============================================================
# ALT / ÜST GÜVEN
# ============================================================

def calculate_confidence(
    expected_total,
    line,
    home_sample,
    away_sample
):
    if (
        expected_total is None
        or line is None
    ):
        return None

    difference = abs(
        expected_total - line
    )

    # Barem farkı
    edge_score = min(
        25,
        difference * 5
    )

    # Örneklem
    sample = min(
        home_sample,
        away_sample
    )

    sample_score = min(
        10,
        sample
    )

    confidence = (
        55
        + edge_score
        + sample_score
    )

    confidence = max(
        50,
        min(
            95,
            confidence
        )
    )

    return round_value(
        confidence,
        2
    )


# ============================================================
# 1X2 HESAPLAMA
# ============================================================

def calculate_1x2(
    expected_home,
    expected_away,
    home_stats,
    away_stats
):
    if (
        expected_home is None
        or expected_away is None
    ):
        return None

    home_scored = home_stats.get(
        "scoredAverage"
    )

    home_conceded = home_stats.get(
        "concededAverage"
    )

    away_scored = away_stats.get(
        "scoredAverage"
    )

    away_conceded = away_stats.get(
        "concededAverage"
    )

    if any(
        value is None
        for value in [
            home_scored,
            home_conceded,
            away_scored,
            away_conceded,
        ]
    ):
        return None

    # Hücum + savunma dengesi
    home_strength = (
        home_scored
        + (100 - home_conceded)
    )

    away_strength = (
        away_scored
        + (100 - away_conceded)
    )

    # Beklenen skor farkı ana belirleyici
    score_difference = (
        expected_home
        - expected_away
    )

    # Basit güç farkı
    strength_difference = (
        home_strength
        - away_strength
    )

    combined_difference = (
        score_difference * 2
        + strength_difference * 0.05
    )

    # Beraberlik ihtimali:
    # skorlar birbirine ne kadar yakınsa
    # beraberlik ihtimali o kadar yüksek.
    closeness = abs(
        expected_home
        - expected_away
    )

    draw_probability = (
        32
        - closeness * 3.2
    )

    draw_probability = max(
        10,
        min(
            32,
            draw_probability
        )
    )

    remaining = (
        100
        - draw_probability
    )

    # Lojistik dağılım
    home_share = (
        1
        / (
            1
            + math.exp(
                -combined_difference / 4
            )
        )
    )

    home_probability = (
        remaining
        * home_share
    )

    away_probability = (
        remaining
        - home_probability
    )

    # Güvenlik için normalize et
    total_probability = (
        home_probability
        + draw_probability
        + away_probability
    )

    if total_probability <= 0:
        return None

    home_probability = (
        home_probability
        / total_probability
        * 100
    )

    draw_probability = (
        draw_probability
        / total_probability
        * 100
    )

    away_probability = (
        away_probability
        / total_probability
        * 100
    )

    probabilities = {
        "1": home_probability,
        "X": draw_probability,
        "2": away_probability,
    }

    prediction = max(
        probabilities,
        key=probabilities.get
    )

    confidence = probabilities[
        prediction
    ]

    return {
        "prediction": prediction,

        "confidence": round_value(
            confidence,
            2
        ),

        "homeProbability": round_value(
            home_probability,
            2
        ),

        "drawProbability": round_value(
            draw_probability,
            2
        ),

        "awayProbability": round_value(
            away_probability,
            2
        ),

        "expectedHome": round_value(
            expected_home,
            2
        ),

        "expectedAway": round_value(
            expected_away,
            2
        ),
    }


# ============================================================
# PERİYOT İSTATİSTİKLERİ
# ============================================================

def calculate_period_prediction(
    histories,
    period_key
):
    values = []

    for item in histories:
        periods = item.get(
            "periods"
        )

        value = get_period_value(
            periods,
            period_key
        )

        if value is not None:
            values.append(value)

    if not values:
        return None

    average_value = weighted_average(
        values
    )

    return {
        "line": round_value(
            average_value,
            2
        ),

        "average": round_value(
            average_value,
            2
        ),

        "prediction": None,

        "sample": len(values),
    }


# ============================================================
# İLK YARI
# ============================================================

def calculate_first_half(
    home_history,
    away_history
):
    values = []

    combined = (
        home_history
        + away_history
    )

    for item in combined:
        periods = item.get(
            "periods"
        )

        q1 = get_period_value(
            periods,
            "q1"
        )

        q2 = get_period_value(
            periods,
            "q2"
        )

        if (
            q1 is not None
            and q2 is not None
        ):
            values.append(
                q1 + q2
            )

    if not values:
        return None

    average_value = weighted_average(
        values
    )

    return {
        "line": round_value(
            average_value,
            2
        ),

        "average": round_value(
            average_value,
            2
        ),

        "prediction": None,

        "sample": len(values),
    }


# ============================================================
# PERİYOT TAHMİNLERİ
# ============================================================

def build_period_predictions(
    home_history,
    away_history
):
    combined = (
        home_history
        + away_history
    )

    result = {}

    first_half = calculate_first_half(
        home_history,
        away_history
    )

    if first_half is not None:
        result["firstHalfTotal"] = (
            first_half
        )

    for key in [
        "q1",
        "q2",
        "q3",
        "q4",
    ]:
        prediction = (
            calculate_period_prediction(
                combined,
                key
            )
        )

        if prediction is not None:
            result[key] = prediction

    return result


# ============================================================
# OYNANMIŞ MAÇ SONUCU
# ============================================================

def evaluate_main_prediction(
    prediction,
    line,
    home_score,
    away_score
):
    hs = to_float(home_score)
    aws = to_float(away_score)

    if (
        hs is None
        or aws is None
        or line is None
    ):
        return {
            "result": "not_played",
            "success": None,
            "actualTotal": None,
            "actualResult": None,
        }

    actual_total = (
        hs + aws
    )

    if actual_total > line:
        actual_result = "Üst"

    elif actual_total < line:
        actual_result = "Alt"

    else:
        actual_result = "Push"

    if actual_result == "Push":
        success = None
        result = "push"

    else:
        success = (
            prediction
            == actual_result
        )

        result = (
            "successful"
            if success
            else "failed"
        )

    return {
        "result": result,

        "success": success,

        "actualTotal": round_value(
            actual_total,
            2
        ),

        "actualResult": actual_result,
    }


# ============================================================
# 1X2 SONUCU
# ============================================================

def evaluate_1x2(
    prediction,
    home_score,
    away_score
):
    hs = to_float(home_score)
    aws = to_float(away_score)

    if (
        hs is None
        or aws is None
    ):
        return {
            "result": "not_played",
            "success": None,
            "actualResult": None,
        }

    if hs > aws:
        actual = "1"

    elif hs < aws:
        actual = "2"

    else:
        actual = "X"

    return {
        "result": (
            "successful"
            if prediction == actual
            else "failed"
        ),

        "success": (
            prediction == actual
        ),

        "actualResult": actual,
    }


# ============================================================
# TAHMİN OLUŞTUR
# ============================================================

def build_prediction(match):
    home = (
        match.get("homeTeam")
        or match.get("home")
        or ""
    )

    away = (
        match.get("awayTeam")
        or match.get("away")
        or ""
    )

    home_history = get_home_history(
        match
    )

    away_history = get_away_history(
        match
    )

    home_stats = calculate_team_stats(
        home_history
    )

    away_stats = calculate_team_stats(
        away_history
    )

    # --------------------------------------------------------
    # ANA BAREM
    # --------------------------------------------------------

    line = calculate_main_line(
        home_stats,
        away_stats
    )

    # --------------------------------------------------------
    # BEKLENEN SKOR
    # --------------------------------------------------------

    expected = calculate_expected_scores(
        home_stats,
        away_stats
    )

    if (
        line is None
        or expected is None
    ):
        return None

    expected_home = expected.get(
        "home"
    )

    expected_away = expected.get(
        "away"
    )

    expected_total = expected.get(
        "total"
    )

    # --------------------------------------------------------
    # ANA ALT / ÜST
    # --------------------------------------------------------

    prediction = calculate_over_under(
        expected_total,
        line
    )

    if prediction is None:
        return None

    confidence = calculate_confidence(
        expected_total,
        line,
        home_stats.get("sample", 0),
        away_stats.get("sample", 0)
    )

    # --------------------------------------------------------
    # 1X2
    # --------------------------------------------------------

    prediction_1x2 = calculate_1x2(
        expected_home,
        expected_away,
        home_stats,
        away_stats
    )

    # --------------------------------------------------------
    # MAÇ SONUCU
    # --------------------------------------------------------

    home_score = (
        match.get("homeScore")
    )

    away_score = (
        match.get("awayScore")
    )

    played = bool(
        match.get("played")
    )

    evaluation = {
        "result": "not_played",
        "success": None,
        "actualTotal": None,
        "actualResult": None,
    }

    evaluation_1x2 = {
        "result": "not_played",
        "success": None,
        "actualResult": None,
    }

    if played:
        evaluation = evaluate_main_prediction(
            prediction,
            line,
            home_score,
            away_score
        )

        if prediction_1x2 is not None:
            evaluation_1x2 = evaluate_1x2(
                prediction_1x2["prediction"],
                home_score,
                away_score
            )

    # --------------------------------------------------------
    # PERİYOTLAR
    # --------------------------------------------------------

    periods = build_period_predictions(
        home_history,
        away_history
    )

    # --------------------------------------------------------
    # ANA KAYIT
    # --------------------------------------------------------

    record = {
        "id": match.get("id"),

        "league": match.get(
            "league"
        ),

        "season": match.get(
            "season"
        ),

        "date": match.get(
            "date"
        ),

        "utcDate": match.get(
            "utcDate"
        ),

        "home": home,

        "away": away,

        # ====================================================
        # ANA MARKET
        # ====================================================

        "market": "Maç Toplam",

        "prediction": prediction,

        "line": line,

        "confidence": confidence,

        "expectedHome": expected_home,

        "expectedAway": expected_away,

        "expectedTotal": expected_total,

        # ====================================================
        # 1X2
        # ====================================================

        "prediction1X2": (
            prediction_1x2.get(
                "prediction"
            )
            if prediction_1x2
            else None
        ),

        "confidence1X2": (
            prediction_1x2.get(
                "confidence"
            )
            if prediction_1x2
            else None
        ),

        "homeWinProbability": (
            prediction_1x2.get(
                "homeProbability"
            )
            if prediction_1x2
            else None
        ),

        "drawProbability": (
            prediction_1x2.get(
                "drawProbability"
            )
            if prediction_1x2
            else None
        ),

        "awayWinProbability": (
            prediction_1x2.get(
                "awayProbability"
            )
            if prediction_1x2
            else None
        ),

        "result1X2": evaluation_1x2.get(
            "result"
        ),

        "success1X2": evaluation_1x2.get(
            "success"
        ),

        "actualResult1X2": evaluation_1x2.get(
            "actualResult"
        ),

        # ====================================================
        # İSTATİSTİK
        # ====================================================

        "homeSample": home_stats.get(
            "sample"
        ),

        "awaySample": away_stats.get(
            "sample"
        ),

        "homeScoredAverage": round_value(
            home_stats.get(
                "scoredAverage"
            ),
            2
        ),

        "homeConcededAverage": round_value(
            home_stats.get(
                "concededAverage"
            ),
            2
        ),

        "homeTotalAverage": round_value(
            home_stats.get(
                "totalAverage"
            ),
            2
        ),

        "awayScoredAverage": round_value(
            away_stats.get(
                "scoredAverage"
            ),
            2
        ),

        "awayConcededAverage": round_value(
            away_stats.get(
                "concededAverage"
            ),
            2
        ),

        "awayTotalAverage": round_value(
            away_stats.get(
                "totalAverage"
            ),
            2
        ),

        # ====================================================
        # SON 10 MAÇ
        # ====================================================

        "homeLast10": home_history,

        "awayLast10": away_history,

        # Eski arayüz uyumluluğu
        "homeLast5": home_history[:5],

        "awayLast5": away_history[:5],

        # ====================================================
        # PERİYOTLAR
        # ====================================================

        "firstHalfTotal": periods.get(
            "firstHalfTotal"
        ),

        "q1": periods.get(
            "q1"
        ),

        "q2": periods.get(
            "q2"
        ),

        "q3": periods.get(
            "q3"
        ),

        "q4": periods.get(
            "q4"
        ),

        # ====================================================
        # MAÇ SONUCU
        # ====================================================

        "played": played,

        "homeScore": home_score,

        "awayScore": away_score,

        "result": evaluation.get(
            "result"
        ),

        "success": evaluation.get(
            "success"
        ),

        "actualTotal": evaluation.get(
            "actualTotal"
        ),

        "actualResult": evaluation.get(
            "actualResult"
        ),
    }

    return record


# ============================================================
# İSTATİSTİKLER
# ============================================================

def calculate_statistics(predictions):
    total = len(predictions)

    completed = 0
    successful = 0
    failed = 0
    push = 0
    not_played = 0

    completed_1x2 = 0
    successful_1x2 = 0
    failed_1x2 = 0

    for item in predictions:

        # ====================================================
        # ANA MARKET
        # ====================================================

        result = item.get(
            "result"
        )

        if result == "successful":
            completed += 1
            successful += 1

        elif result == "failed":
            completed += 1
            failed += 1

        elif result == "push":
            completed += 1
            push += 1

        else:
            not_played += 1

        # ====================================================
        # 1X2
        # ====================================================

        result_1x2 = item.get(
            "result1X2"
        )

        if result_1x2 == "successful":
            completed_1x2 += 1
            successful_1x2 += 1

        elif result_1x2 == "failed":
            completed_1x2 += 1
            failed_1x2 += 1

    # ========================================================
    # ANA BAŞARI
    # ========================================================

    denominator = (
        successful
        + failed
    )

    if denominator > 0:
        success_rate = (
            successful
            / denominator
            * 100
        )
    else:
        success_rate = 0

    # ========================================================
    # 1X2 BAŞARI
    # ========================================================

    denominator_1x2 = (
        successful_1x2
        + failed_1x2
    )

    if denominator_1x2 > 0:
        success_rate_1x2 = (
            successful_1x2
            / denominator_1x2
            * 100
        )
    else:
        success_rate_1x2 = 0

    return {
        # Ana market
        "totalPredictions": total,

        "completed": completed,

        "successful": successful,

        "failed": failed,

        "push": push,

        "notPlayed": not_played,

        "successRate": round(
            success_rate,
            2
        ),

        # 1X2 ayrı
        "completed1X2": completed_1x2,

        "successful1X2": successful_1x2,

        "failed1X2": failed_1x2,

        "successRate1X2": round(
            success_rate_1x2,
            2
        ),
    }


# ============================================================
# ANA
# ============================================================

def main():

    print("=" * 70)
    print("🏀 BASKETBOL TAHMİNLERİ")
    print("=" * 70)

    data, input_path = load_input()

    matches = data.get(
        "matches",
        []
    )

    predictions = []

    skipped = 0

    for match in matches:

        if not isinstance(match, dict):
            skipped += 1
            continue

        prediction = build_prediction(
            match
        )

        if prediction is None:
            skipped += 1
            continue

        predictions.append(
            prediction
        )

    statistics = calculate_statistics(
        predictions
    )

    # ========================================================
    # ÇIKTI
    # ========================================================

    output = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": str(
            input_path
        ),

        "settings": {

            "mainMarket":
                "Maç Toplam Alt/Üst",

            "secondaryMarket":
                "1X2",

            "historyLimit":
                MAX_HISTORY,

            "historyWeight":
                "Yeni maçlar daha yüksek ağırlıklı",

            "newestWeight":
                NEWEST_WEIGHT,

            "oldestWeight":
                OLDEST_WEIGHT,

            "homeAdvantage":
                HOME_ADVANTAGE,

            "homeHistory":
                "Son 10 ev maçı",

            "awayHistory":
                "Son 10 deplasman maçı",

            "lineRounding":
                False,

            "exactCalculatedLine":
                True,

            "minimumDifference":
                0,

            "mainSuccessRateOnly":
                True,

            "mainSuccessRateMarket":
                "Maç Toplam Alt/Üst",

            "oneXTwoSeparate":
                True,

            "excludedFromMainSuccessRate": [
                "1/X/2",
                "İY",
                "Q1",
                "Q2",
                "Q3",
                "Q4"
            ],

            "pushExcludedFromSuccessRate":
                True,
        },

        "statistics": statistics,

        "predictions": predictions,
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    # ========================================================
    # EKRAN
    # ========================================================

    print()

    print(
        f"📦 Kaynak maç: "
        f"{len(matches)}"
    )

    print(
        f"🎯 Tahmin: "
        f"{len(predictions)}"
    )

    print(
        f"⏭️ Atlanan: "
        f"{skipped}"
    )

    print()

    print(
        "🏀 ANA MARKET"
    )

    print(
        f"🏁 Tamamlanan: "
        f"{statistics['completed']}"
    )

    print(
        f"✅ Başarılı: "
        f"{statistics['successful']}"
    )

    print(
        f"❌ Başarısız: "
        f"{statistics['failed']}"
    )

    print(
        f"🟡 Push: "
        f"{statistics['push']}"
    )

    print(
        f"⏳ Oynanmamış: "
        f"{statistics['notPlayed']}"
    )

    print(
        f"📈 Ana başarı: "
        f"%{statistics['successRate']}"
    )

    print()

    print(
        "🏀 1X2"
    )

    print(
        f"🏁 Tamamlanan: "
        f"{statistics['completed1X2']}"
    )

    print(
        f"✅ Başarılı: "
        f"{statistics['successful1X2']}"
    )

    print(
        f"❌ Başarısız: "
        f"{statistics['failed1X2']}"
    )

    print(
        f"📈 1X2 başarı: "
        f"%{statistics['successRate1X2']}"
    )

    print()

    print(
        f"💾 Kaydedildi: "
        f"{OUTPUT_FILE}"
    )

    print()

    print("=" * 70)
    print("✅ TAHMİNLER TAMAMLANDI")
    print("=" * 70)


if __name__ == "__main__":
    main()
