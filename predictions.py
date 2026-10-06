import json
from pathlib import Path
from datetime import datetime, timezone


# ============================================================
# AYARLAR
# ============================================================

MAX_HISTORY = 5

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


def average(values):
    values = [
        to_float(x)
        for x in values
        if to_float(x) is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def round_value(value, digits=2):
    if value is None:
        return None

    return round(float(value), digits)


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
    scored = to_float(item.get("scored"))
    conceded = to_float(item.get("conceded"))

    if scored is None or conceded is None:
        return None

    return scored + conceded


# ============================================================
# TARİH SIRALAMA
# ============================================================

def history_sort_key(item):
    value = (
        item.get("utcDate")
        or item.get("date")
        or ""
    )

    return str(value)


# ============================================================
# SON 5 EV / DEPLASMAN
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
# TEMEL İSTATİSTİKLER
# ============================================================

def calculate_team_stats(history):
    scored = []
    conceded = []
    totals = []

    for item in history:

        s = to_float(item.get("scored"))
        c = to_float(item.get("conceded"))

        if s is not None:
            scored.append(s)

        if c is not None:
            conceded.append(c)

        total = match_total_from_history(item)

        if total is not None:
            totals.append(total)

    return {
        "sample": len(totals),
        "scoredAverage": average(scored),
        "concededAverage": average(conceded),
        "totalAverage": average(totals),
    }


# ============================================================
# ANA MAÇ BAREMİ
# ============================================================
#
# ÖNEMLİ:
#
# Burada artık 5'in katına yuvarlama YOK.
#
# Ev takımının son 5 EV maç toplam ortalaması
# ile deplasman takımının son 5 DEPLASMAN maç
# toplam ortalaması alınır.
#
# İkisinin ortalaması doğrudan barem olur.
#
# Örnek:
#
# Ev = 211.4
# Dep = 218.2
#
# (211.4 + 218.2) / 2 = 214.8
#
# Barem = 214.8
#
# ============================================================

def calculate_main_line(home_stats, away_stats):

    home_total_avg = home_stats.get(
        "totalAverage"
    )

    away_total_avg = away_stats.get(
        "totalAverage"
    )

    if (
        home_total_avg is None
        or away_total_avg is None
    ):
        return None

    line = (
        home_total_avg
        + away_total_avg
    ) / 2

    return round_value(line, 2)


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

    expected_home = (
        home_scored
        + away_conceded
    ) / 2

    expected_away = (
        away_scored
        + home_conceded
    ) / 2

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

    # Tam eşitlik durumunda
    # yön seçmek yerine Üst veriyoruz.
    # Gerçek maçta eşitlik Push olacaktır.
    return "Üst"


# ============================================================
# GÜVEN
# ============================================================

def calculate_confidence(
    expected_total,
    line
):

    if (
        expected_total is None
        or line is None
    ):
        return None

    difference = abs(
        expected_total - line
    )

    confidence = 50 + (
        difference * 8
    )

    confidence = max(
        50,
        min(95, confidence)
    )

    return round_value(
        confidence,
        2
    )


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

    avg = average(values)

    return {
        "line": round_value(
            avg,
            2
        ),
        "average": round_value(
            avg,
            2
        ),
        "prediction": None,
        "sample": len(values),
    }


def calculate_first_half(
    home_history,
    away_history
):

    values = []

    for item in (
        home_history
        + away_history
    ):

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

    avg = average(values)

    return {
        "line": round_value(
            avg,
            2
        ),
        "average": round_value(
            avg,
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

    actual_total = hs + aws

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
            prediction == actual_result
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
    # Ana barem
    # --------------------------------------------------------

    line = calculate_main_line(
        home_stats,
        away_stats
    )

    # --------------------------------------------------------
    # Beklenen skor
    # --------------------------------------------------------

    expected = calculate_expected_scores(
        home_stats,
        away_stats
    )

    if line is None or expected is None:
        return None

    expected_total = expected.get(
        "total"
    )

    prediction = calculate_over_under(
        expected_total,
        line
    )

    if prediction is None:
        return None

    confidence = calculate_confidence(
        expected_total,
        line
    )

    # --------------------------------------------------------
    # Sonuç
    # --------------------------------------------------------

    home_score = match.get(
        "homeScore"
    )

    away_score = match.get(
        "awayScore"
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

    if played:
        evaluation = evaluate_main_prediction(
            prediction,
            line,
            home_score,
            away_score
        )

    # --------------------------------------------------------
    # Periyotlar
    # --------------------------------------------------------

    periods = build_period_predictions(
        home_history,
        away_history
    )

    # --------------------------------------------------------
    # Ana kayıt
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
        # ANA TAHMİN
        # ====================================================

        "market": "Maç Toplam",

        "prediction": prediction,

        # ARTIK YUVARLAMA YOK
        "line": line,

        "confidence": confidence,

        "expectedHome": expected.get(
            "home"
        ),

        "expectedAway": expected.get(
            "away"
        ),

        "expectedTotal": expected_total,

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
        # GEÇMİŞ
        # ====================================================

        "homeLast5": home_history,

        "awayLast5": away_history,

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

    for item in predictions:

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

    return {
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

    output = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": str(
            input_path
        ),

        "settings": {
            "mainMarket": "Maç Toplam Alt/Üst",

            "historyLimit": MAX_HISTORY,

            "homeHistory": (
                "Son 5 ev maçı"
            ),

            "awayHistory": (
                "Son 5 deplasman maçı"
            ),

            "lineRounding": False,

            "lineStep": None,

            "exactCalculatedLine": True,

            "minimumDifference": 0,

            "allAvailableHistory": False,

            "mainSuccessRateOnly": True,

            "excludedFromMainSuccessRate": [
                "1/X/2",
                "İY",
                "Q1",
                "Q2",
                "Q3",
                "Q4"
            ],

            "pushExcludedFromSuccessRate": True,
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
        f"🏆 Tamamlanan: "
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
        f"📈 Başarı: "
        f"%{statistics['successRate']}"
    )

    print()
    print(
        f"💾 Kaydedildi: "
        f"{OUTPUT_FILE}"
    )

    print()
    print("=" * 70)
    print(
        "✅ TAHMİNLER TAMAMLANDI"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
