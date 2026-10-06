import json
from pathlib import Path
from datetime import datetime, timezone
import math


MAX_HISTORY = 10

NEWEST_WEIGHT = 1.00
OLDEST_WEIGHT = 0.55

HOME_ADVANTAGE = 2.0

INPUT_FILES = [
    Path("basketball.json"),
    Path("data/basketball.json"),
]

OUTPUT_FILE = Path("predictions.json")


def load_input():
    for path in INPUT_FILES:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f), path

    raise FileNotFoundError(
        "basketball.json bulunamadı."
    )


def to_float(value):
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def round_value(value, digits=2):
    if value is None:
        return None
    return round(float(value), digits)


def weighted_average(values):
    valid = []

    for value in values:
        number = to_float(value)
        if number is not None:
            valid.append(number)

    if not valid:
        return None

    if len(valid) == 1:
        return valid[0]

    weights = []

    for index in range(len(valid)):
        progress = index / (len(valid) - 1)

        weight = (
            NEWEST_WEIGHT
            - (
                (NEWEST_WEIGHT - OLDEST_WEIGHT)
                * progress
            )
        )

        weights.append(weight)

    total_weight = sum(weights)

    if total_weight <= 0:
        return None

    return sum(
        value * weight
        for value, weight in zip(valid, weights)
    ) / total_weight


def history_sort_key(item):
    if not isinstance(item, dict):
        return ""

    return str(
        item.get("utcDate")
        or item.get("date")
        or ""
    )


def get_history(match, key):
    history = match.get(key, [])

    if not isinstance(history, list):
        return []

    history = [
        x for x in history
        if isinstance(x, dict)
    ]

    history.sort(
        key=history_sort_key,
        reverse=True
    )

    return history[:MAX_HISTORY]


def match_total(item):
    scored = to_float(
        item.get("scored")
    )

    conceded = to_float(
        item.get("conceded")
    )

    if scored is None or conceded is None:
        return None

    return scored + conceded


def calculate_team_stats(history):
    scored = []
    conceded = []
    totals = []

    for item in history:
        s = to_float(
            item.get("scored")
        )

        c = to_float(
            item.get("conceded")
        )

        t = match_total(item)

        if s is not None:
            scored.append(s)

        if c is not None:
            conceded.append(c)

        if t is not None:
            totals.append(t)

    return {
        "sample": len(totals),

        "scored": weighted_average(
            scored
        ),

        "conceded": weighted_average(
            conceded
        ),

        "total": weighted_average(
            totals
        ),
    }


def calculate_expected_scores(
    home_stats,
    away_stats
):
    hs = home_stats.get("scored")
    hc = home_stats.get("conceded")

    aw = away_stats.get("scored")
    ac = away_stats.get("conceded")

    if any(
        x is None
        for x in [hs, hc, aw, ac]
    ):
        return None

    expected_home = (
        hs + ac
    ) / 2

    expected_away = (
        aw + hc
    ) / 2

    expected_home += HOME_ADVANTAGE

    expected_total = (
        expected_home
        + expected_away
    )

    return {
        "home": round_value(
            expected_home
        ),
        "away": round_value(
            expected_away
        ),
        "total": round_value(
            expected_total
        ),
    }


def calculate_line(
    home_stats,
    away_stats
):
    home_total = home_stats.get("total")
    away_total = away_stats.get("total")

    if (
        home_total is None
        or away_total is None
    ):
        return None

    return round_value(
        (home_total + away_total) / 2
    )


def calculate_over_under(
    expected_total,
    line
):
    if (
        expected_total is None
        or line is None
    ):
        return None

    return (
        "Üst"
        if expected_total > line
        else "Alt"
    )


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

    edge = abs(
        expected_total - line
    )

    edge_score = min(
        25,
        edge * 5
    )

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

    return round_value(
        max(
            50,
            min(95, confidence)
        )
    )


# ============================================================
# 1X2
# ============================================================

def calculate_1x2(
    expected_home,
    expected_away
):
    if (
        expected_home is None
        or expected_away is None
    ):
        return None

    difference = (
        expected_home
        - expected_away
    )

    distance = abs(difference)

    # Skorlar birbirine yakınsa beraberlik ihtimali artar.
    draw_probability = (
        30
        - distance * 2.5
    )

    draw_probability = max(
        10,
        min(
            30,
            draw_probability
        )
    )

    remaining = (
        100
        - draw_probability
    )

    # Home avantajı zaten expected_home
    # içerisinde bulunduğu için burada
    # tekrar eklenmiyor.
    home_share = (
        1
        /
        (
            1
            + math.exp(
                -difference / 3.5
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

    probabilities = {
        "1": home_probability,
        "X": draw_probability,
        "2": away_probability,
    }

    prediction = max(
        probabilities,
        key=probabilities.get
    )

    return {
        "prediction": prediction,

        "confidence": round_value(
            probabilities[prediction]
        ),

        "homeProbability": round_value(
            home_probability
        ),

        "drawProbability": round_value(
            draw_probability
        ),

        "awayProbability": round_value(
            away_probability
        ),
    }


def evaluate_main(
    prediction,
    line,
    home_score,
    away_score
):
    hs = to_float(home_score)
    aw = to_float(away_score)

    if (
        hs is None
        or aw is None
        or line is None
    ):
        return {
            "result": "not_played",
            "success": None,
            "actualTotal": None,
            "actualResult": None,
        }

    actual_total = hs + aw

    if actual_total > line:
        actual = "Üst"
    elif actual_total < line:
        actual = "Alt"
    else:
        actual = "Push"

    if actual == "Push":
        return {
            "result": "push",
            "success": None,
            "actualTotal": round_value(
                actual_total
            ),
            "actualResult": "Push",
        }

    success = (
        prediction == actual
    )

    return {
        "result": (
            "successful"
            if success
            else "failed"
        ),
        "success": success,
        "actualTotal": round_value(
            actual_total
        ),
        "actualResult": actual,
    }


def evaluate_1x2(
    prediction,
    home_score,
    away_score
):
    hs = to_float(home_score)
    aw = to_float(away_score)

    if hs is None or aw is None:
        return {
            "result": "not_played",
            "success": None,
            "actualResult": None,
        }

    if hs > aw:
        actual = "1"
    elif hs < aw:
        actual = "2"
    else:
        actual = "X"

    success = (
        prediction == actual
    )

    return {
        "result": (
            "successful"
            if success
            else "failed"
        ),
        "success": success,
        "actualResult": actual,
    }


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

    home_history = get_history(
        match,
        "homeHistory"
    )

    away_history = get_history(
        match,
        "awayHistory"
    )

    home_stats = calculate_team_stats(
        home_history
    )

    away_stats = calculate_team_stats(
        away_history
    )

    expected = calculate_expected_scores(
        home_stats,
        away_stats
    )

    line = calculate_line(
        home_stats,
        away_stats
    )

    if expected is None or line is None:
        return None

    expected_home = expected["home"]
    expected_away = expected["away"]
    expected_total = expected["total"]

    main_prediction = calculate_over_under(
        expected_total,
        line
    )

    confidence = calculate_confidence(
        expected_total,
        line,
        home_stats["sample"],
        away_stats["sample"]
    )

    # --------------------------------------------------------
    # 1X2
    # --------------------------------------------------------

    one_x_two = calculate_1x2(
        expected_home,
        expected_away
    )

    home_score = match.get(
        "homeScore"
    )

    away_score = match.get(
        "awayScore"
    )

    played = bool(
        match.get("played")
    )

    main_result = {
        "result": "not_played",
        "success": None,
        "actualTotal": None,
        "actualResult": None,
    }

    result_1x2 = {
        "result": "not_played",
        "success": None,
        "actualResult": None,
    }

    if played:

        main_result = evaluate_main(
            main_prediction,
            line,
            home_score,
            away_score
        )

        if one_x_two:
            result_1x2 = evaluate_1x2(
                one_x_two["prediction"],
                home_score,
                away_score
            )

    # --------------------------------------------------------
    # SADECE GEREKLİ VERİLERİ ÇIKTIYA YAZ
    # Geçmiş maç listeleri yazılmıyor.
    # --------------------------------------------------------

    return {
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

        "homeScore": home_score,

        "awayScore": away_score,

        "played": played,

        # ====================================================
        # ANA TAHMİN
        # ====================================================

        "market": "Maç Toplam Alt/Üst",

        "prediction": main_prediction,

        "line": line,

        "barem": line,

        "confidence": confidence,

        "expectedHome": expected_home,

        "expectedAway": expected_away,

        "expectedTotal": expected_total,

        # ====================================================
        # 1X2
        # ====================================================

        "prediction1X2": (
            one_x_two["prediction"]
            if one_x_two
            else None
        ),

        "confidence1X2": (
            one_x_two["confidence"]
            if one_x_two
            else None
        ),

        "homeWinProbability": (
            one_x_two["homeProbability"]
            if one_x_two
            else None
        ),

        "drawProbability": (
            one_x_two["drawProbability"]
            if one_x_two
            else None
        ),

        "awayWinProbability": (
            one_x_two["awayProbability"]
            if one_x_two
            else None
        ),

        "result1X2": result_1x2[
            "result"
        ],

        "success1X2": result_1x2[
            "success"
        ],

        "actualResult1X2": result_1x2[
            "actualResult"
        ],

        # ====================================================
        # ANA SONUÇ
        # ====================================================

        "result": main_result[
            "result"
        ],

        "success": main_result[
            "success"
        ],

        "actualTotal": main_result[
            "actualTotal"
        ],

        "actualResult": main_result[
            "actualResult"
        ],

        # ====================================================
        # ÖRNEKLEM BİLGİSİ
        # ====================================================

        "homeSample": home_stats[
            "sample"
        ],

        "awaySample": away_stats[
            "sample"
        ],
    }


def calculate_statistics(predictions):
    successful = 0
    failed = 0
    push = 0
    not_played = 0

    successful_1x2 = 0
    failed_1x2 = 0

    for item in predictions:

        result = item.get(
            "result"
        )

        if result == "successful":
            successful += 1

        elif result == "failed":
            failed += 1

        elif result == "push":
            push += 1

        else:
            not_played += 1

        result_1x2 = item.get(
            "result1X2"
        )

        if result_1x2 == "successful":
            successful_1x2 += 1

        elif result_1x2 == "failed":
            failed_1x2 += 1

    main_denominator = (
        successful + failed
    )

    x2_denominator = (
        successful_1x2
        + failed_1x2
    )

    main_rate = (
        successful
        / main_denominator
        * 100
        if main_denominator
        else 0
    )

    x2_rate = (
        successful_1x2
        / x2_denominator
        * 100
        if x2_denominator
        else 0
    )

    return {
        "totalPredictions": len(
            predictions
        ),

        "successful": successful,

        "failed": failed,

        "push": push,

        "notPlayed": not_played,

        "successRate": round(
            main_rate,
            2
        ),

        "successful1X2": successful_1x2,

        "failed1X2": failed_1x2,

        "successRate1X2": round(
            x2_rate,
            2
        ),
    }


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

    output = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": str(
            input_path
        ),

        "settings": {
            "historyLimit": MAX_HISTORY,
            "newestWeight": NEWEST_WEIGHT,
            "oldestWeight": OLDEST_WEIGHT,
            "homeAdvantage": HOME_ADVANTAGE,

            "mainMarket":
                "Maç Toplam Alt/Üst",

            "secondaryMarket":
                "1X2",

            "mainSuccessRateOnly":
                True,

            "historyStoredInPrediction":
                False,
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

    print()
    print(
        f"📦 Kaynak maç: {len(matches)}"
    )
    print(
        f"🎯 Tahmin: {len(predictions)}"
    )
    print(
        f"⏭️ Atlanan: {skipped}"
    )

    print()
    print(
        f"🏀 Ana başarı: "
        f"%{statistics['successRate']}"
    )

    print(
        f"🏀 1X2 başarı: "
        f"%{statistics['successRate1X2']}"
    )

    print()
    print(
        f"💾 Kaydedildi: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
