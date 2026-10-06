import json
import math
import os
from datetime import datetime, timezone


# ============================================================
# AYARLAR
# ============================================================

INPUT_FILE = "basketball.json"
OUTPUT_FILE = "predictions.json"

MAX_HISTORY = 5

# Ana sonuç tahmini için beraberlik toleransı
DRAW_TOLERANCE = 2.0

# Barem yuvarlama adımı
LINE_STEP = 5

# Güven sınırları
MIN_CONFIDENCE = 50
MAX_CONFIDENCE = 95


# ============================================================
# GENEL YARDIMCILAR
# ============================================================

def safe_float(value):
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value):
    if value is None:
        return None

    try:
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

    return sum(values) / len(values)


def clamp(value, minimum, maximum):
    return max(
        minimum,
        min(maximum, value)
    )


def round_line(value, step=LINE_STEP):
    """
    Barem değerini 5'in katına yuvarlar.

    Örnek:
    162.3 -> 160
    163.1 -> 165
    167.8 -> 170
    """

    if value is None:
        return None

    return round(
        value / step
    ) * step


def confidence_from_difference(
    difference,
    sample_size,
):
    """
    Fark büyüdükçe güven artar.

    Örnek:
    Beklenen ev = 86
    Beklenen deplasman = 74

    Fark = 12

    Güven yükselir.
    """

    if difference is None:
        return None

    diff = abs(
        float(difference)
    )

    sample_factor = min(
        1.0,
        sample_size / MAX_HISTORY
    )

    confidence = (
        50
        + diff * 3.0
        + sample_factor * 10
    )

    return round(
        clamp(
            confidence,
            MIN_CONFIDENCE,
            MAX_CONFIDENCE,
        ),
        1,
    )


# ============================================================
# GEÇMİŞ MAÇLARI SEÇ
# ============================================================

def get_home_history(match):
    """
    Ev sahibi takımın yalnızca EVİNDE oynadığı
    geçmiş maçlarını kullanır.

    basketball.json içindeki homeHistory:
    - date
    - opponent
    - scored
    - conceded
    - periods
    """

    history = match.get(
        "homeHistory"
    )

    if not isinstance(history, list):
        return []

    valid = []

    for item in history:
        if not isinstance(item, dict):
            continue

        scored = safe_float(
            item.get("scored")
        )

        conceded = safe_float(
            item.get("conceded")
        )

        if scored is None or conceded is None:
            continue

        valid.append(item)

    return valid[:MAX_HISTORY]


def get_away_history(match):
    """
    Deplasman takımının yalnızca DEPLASMANDA oynadığı
    geçmiş maçlarını kullanır.
    """

    history = match.get(
        "awayHistory"
    )

    if not isinstance(history, list):
        return []

    valid = []

    for item in history:
        if not isinstance(item, dict):
            continue

        scored = safe_float(
            item.get("scored")
        )

        conceded = safe_float(
            item.get("conceded")
        )

        if scored is None or conceded is None:
            continue

        valid.append(item)

    return valid[:MAX_HISTORY]


# ============================================================
# ANA SAYI ORTALAMALARI
# ============================================================

def calculate_basic_averages(
    home_history,
    away_history,
):
    """
    Ev takımının ev performansı:

        ev attığı
        ev yediği

    Deplasman takımının deplasman performansı:

        deplasmanda attığı
        deplasmanda yediği
    """

    home_scored = average([
        item.get("scored")
        for item in home_history
    ])

    home_conceded = average([
        item.get("conceded")
        for item in home_history
    ])

    away_scored = average([
        item.get("scored")
        for item in away_history
    ])

    away_conceded = average([
        item.get("conceded")
        for item in away_history
    ])

    return {
        "homeScored": home_scored,
        "homeConceded": home_conceded,
        "awayScored": away_scored,
        "awayConceded": away_conceded,
    }


# ============================================================
# BEKLENEN SKOR
# ============================================================

def calculate_expected_score(
    averages,
):
    """
    Beklenen ev sahibi:

        (ev sahibinin evde attığı
         +
         deplasmanın deplasmanda yediği)
        / 2

    Beklenen deplasman:

        (deplasmanın deplasmanda attığı
         +
         ev sahibinin evde yediği)
        / 2
    """

    home_scored = averages.get(
        "homeScored"
    )

    home_conceded = averages.get(
        "homeConceded"
    )

    away_scored = averages.get(
        "awayScored"
    )

    away_conceded = averages.get(
        "awayConceded"
    )

    values = [
        home_scored,
        home_conceded,
        away_scored,
        away_conceded,
    ]

    if any(
        value is None
        for value in values
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
        "home": round(
            expected_home,
            2,
        ),
        "away": round(
            expected_away,
            2,
        ),
        "total": round(
            expected_total,
            2,
        ),
    }


# ============================================================
# 1 / X / 2
# ============================================================

def calculate_main_prediction(
    expected,
    sample_size,
):
    if not expected:
        return None

    home = expected.get(
        "home"
    )

    away = expected.get(
        "away"
    )

    if home is None or away is None:
        return None

    difference = (
        home - away
    )

    if abs(difference) <= DRAW_TOLERANCE:
        prediction = "X"
    elif difference > 0:
        prediction = "1"
    else:
        prediction = "2"

    confidence = confidence_from_difference(
        difference,
        sample_size,
    )

    return {
        "prediction": prediction,
        "expectedHome": round(
            home,
            2,
        ),
        "expectedAway": round(
            away,
            2,
        ),
        "difference": round(
            difference,
            2,
        ),
        "confidence": confidence,
    }


# ============================================================
# ALT / ÜST ANA HESAP
# ============================================================

def calculate_over_under(
    expected_total,
    historical_total,
    sample_size,
):
    """
    Kullanıcının istediği sistem:

    1. Geçmiş ev/deplasman verilerinden
       beklenen toplam sayı bulunur.

    2. Geçmiş toplam ortalaması bulunur.

    3. Barem 5'in katına yuvarlanır.

    4. Beklenen toplam baremin üzerindeyse ÜST,
       altındaysa ALT.

    Eşitse:
       beklenen toplam ile barem aynı olduğundan
       yönsel avantaj oluşmaz.
    """

    if expected_total is None:
        return None

    if historical_total is None:
        historical_total = expected_total

    line = round_line(
        historical_total
    )

    if line is None:
        return None

    difference = (
        expected_total
        - line
    )

    if difference > 0:
        prediction = "ÜST"
    elif difference < 0:
        prediction = "ALT"
    else:
        # Eşitlik durumunda iki ondalık
        # seviyesinde bakıyoruz.
        if expected_total >= historical_total:
            prediction = "ÜST"
        else:
            prediction = "ALT"

    confidence = (
        50
        + abs(difference) * 4
        + min(
            sample_size,
            MAX_HISTORY,
        ) * 1.5
    )

    confidence = round(
        clamp(
            confidence,
            MIN_CONFIDENCE,
            MAX_CONFIDENCE,
        ),
        1,
    )

    return {
        "prediction": prediction,
        "line": line,
        "expectedTotal": round(
            expected_total,
            2,
        ),
        "historicalAverage": round(
            historical_total,
            2,
        ),
        "difference": round(
            difference,
            2,
        ),
        "confidence": confidence,
        "sampleSize": sample_size,
    }


# ============================================================
# MAÇ TOPLAMI ALT / ÜST
# ============================================================

def calculate_match_total(
    home_history,
    away_history,
    expected,
):
    if not expected:
        return None

    home_totals = []

    for item in home_history:
        scored = safe_float(
            item.get("scored")
        )

        conceded = safe_float(
            item.get("conceded")
        )

        if (
            scored is not None
            and conceded is not None
        ):
            home_totals.append(
                scored + conceded
            )

    away_totals = []

    for item in away_history:
        scored = safe_float(
            item.get("scored")
        )

        conceded = safe_float(
            item.get("conceded")
        )

        if (
            scored is not None
            and conceded is not None
        ):
            away_totals.append(
                scored + conceded
            )

    historical_values = (
        home_totals
        + away_totals
    )

    historical_average = average(
        historical_values
    )

    sample_size = min(
        len(home_history),
        MAX_HISTORY,
    )

    sample_size_away = min(
        len(away_history),
        MAX_HISTORY,
    )

    usable_sample = (
        sample_size
        + sample_size_away
    )

    return calculate_over_under(
        expected_total=expected.get(
            "total"
        ),
        historical_total=historical_average,
        sample_size=usable_sample,
    )


# ============================================================
# PERİYOT DEĞERİ
# ============================================================

def get_period_value(
    history_item,
    period,
    side,
):
    periods = history_item.get(
        "periods"
    )

    if not isinstance(
        periods,
        dict,
    ):
        return None

    period_data = periods.get(
        period
    )

    if not isinstance(
        period_data,
        dict,
    ):
        return None

    value = period_data.get(
        side
    )

    return safe_float(
        value
    )


# ============================================================
# PERİYOT ORTALAMALARI
# ============================================================

def calculate_period_averages(
    home_history,
    away_history,
    period,
):
    """
    Her periyot için:

    Ev takımının kendi ev maçlarındaki
    o periyotta attığı / yediği

    Deplasman takımının kendi deplasman
    maçlarındaki o periyotta attığı / yediği
    """

    home_scored_values = []
    home_conceded_values = []

    away_scored_values = []
    away_conceded_values = []

    for item in home_history:
        periods = item.get(
            "periods"
        )

        if not isinstance(
            periods,
            dict,
        ):
            continue

        data = periods.get(
            period
        )

        if not isinstance(
            data,
            dict,
        ):
            continue

        home_value = safe_float(
            data.get("home")
        )

        away_value = safe_float(
            data.get("away")
        )

        if (
            home_value is not None
            and away_value is not None
        ):
            home_scored_values.append(
                home_value
            )

            home_conceded_values.append(
                away_value
            )

    for item in away_history:
        periods = item.get(
            "periods"
        )

        if not isinstance(
            periods,
            dict,
        ):
            continue

        data = periods.get(
            period
        )

        if not isinstance(
            data,
            dict,
        ):
            continue

        home_value = safe_float(
            data.get("home")
        )

        away_value = safe_float(
            data.get("away")
        )

        if (
            home_value is not None
            and away_value is not None
        ):
            away_scored_values.append(
                away_value
            )

            away_conceded_values.append(
                home_value
            )

    return {
        "homeScored": average(
            home_scored_values
        ),
        "homeConceded": average(
            home_conceded_values
        ),
        "awayScored": average(
            away_scored_values
        ),
        "awayConceded": average(
            away_conceded_values
        ),
        "homeSamples": len(
            home_scored_values
        ),
        "awaySamples": len(
            away_scored_values
        ),
    }


# ============================================================
# PERİYOT BEKLENEN SKOR
# ============================================================

def calculate_period_expected(
    averages,
):
    home_scored = averages.get(
        "homeScored"
    )

    home_conceded = averages.get(
        "homeConceded"
    )

    away_scored = averages.get(
        "awayScored"
    )

    away_conceded = averages.get(
        "awayConceded"
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
        "home": round(
            expected_home,
            2,
        ),
        "away": round(
            expected_away,
            2,
        ),
        "total": round(
            expected_total,
            2,
        ),
    }


# ============================================================
# PERİYOT ALT / ÜST
# ============================================================

def calculate_period_total(
    home_history,
    away_history,
    period,
):
    averages = calculate_period_averages(
        home_history,
        away_history,
        period,
    )

    expected = calculate_period_expected(
        averages
    )

    if not expected:
        return None

    historical_totals = []

    # Ev takımının evindeki periyot toplamları
    for item in home_history:
        periods = item.get(
            "periods"
        )

        if not isinstance(
            periods,
            dict,
        ):
            continue

        data = periods.get(
            period
        )

        if not isinstance(
            data,
            dict,
        ):
            continue

        home_value = safe_float(
            data.get("home")
        )

        away_value = safe_float(
            data.get("away")
        )

        if (
            home_value is not None
            and away_value is not None
        ):
            historical_totals.append(
                home_value
                + away_value
            )

    # Deplasman takımının deplasman
    # periyot toplamları
    for item in away_history:
        periods = item.get(
            "periods"
        )

        if not isinstance(
            periods,
            dict,
        ):
            continue

        data = periods.get(
            period
        )

        if not isinstance(
            data,
            dict,
        ):
            continue

        home_value = safe_float(
            data.get("home")
        )

        away_value = safe_float(
            data.get("away")
        )

        if (
            home_value is not None
            and away_value is not None
        ):
            historical_totals.append(
                home_value
                + away_value
            )

    historical_average = average(
        historical_totals
    )

    if historical_average is None:
        return None

    sample_size = (
        averages["homeSamples"]
        + averages["awaySamples"]
    )

    result = calculate_over_under(
        expected_total=expected["total"],
        historical_total=historical_average,
        sample_size=sample_size,
    )

    if not result:
        return None

    result["expectedHome"] = expected[
        "home"
    ]

    result["expectedAway"] = expected[
        "away"
    ]

    result["homeSamples"] = averages[
        "homeSamples"
    ]

    result["awaySamples"] = averages[
        "awaySamples"
    ]

    return result


# ============================================================
# İLK YARI
# ============================================================

def build_first_half_history(
    history,
):
    """
    Q1 + Q2 toplamlarını kullanır.

    Her maç için:

    Ev:
        Q1 home + Q2 home
        Q1 away + Q2 away

    Deplasman:
        aynı maçtaki Q1/Q2
    """

    result = []

    for item in history:
        periods = item.get(
            "periods"
        )

        if not isinstance(
            periods,
            dict,
        ):
            continue

        q1 = periods.get(
            "q1"
        )

        q2 = periods.get(
            "q2"
        )

        if not isinstance(
            q1,
            dict,
        ):
            continue

        if not isinstance(
            q2,
            dict,
        ):
            continue

        q1_home = safe_float(
            q1.get("home")
        )

        q1_away = safe_float(
            q1.get("away")
        )

        q2_home = safe_float(
            q2.get("home")
        )

        q2_away = safe_float(
            q2.get("away")
        )

        if None in (
            q1_home,
            q1_away,
            q2_home,
            q2_away,
        ):
            continue

        result.append({
            "home": q1_home + q2_home,
            "away": q1_away + q2_away,
        })

    return result


def calculate_first_half_total(
    home_history,
    away_history,
):
    home_values = build_first_half_history(
        home_history
    )

    away_values = build_first_half_history(
        away_history
    )

    if not home_values:
        return None

    if not away_values:
        return None

    home_scored = average([
        item["home"]
        for item in home_values
    ])

    home_conceded = average([
        item["away"]
        for item in home_values
    ])

    away_scored = average([
        item["away"]
        for item in away_values
    ])

    away_conceded = average([
        item["home"]
        for item in away_values
    ])

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

    historical_totals = []

    for item in home_values:
        historical_totals.append(
            item["home"]
            + item["away"]
        )

    for item in away_values:
        historical_totals.append(
            item["home"]
            + item["away"]
        )

    historical_average = average(
        historical_totals
    )

    if historical_average is None:
        return None

    sample_size = (
        len(home_values)
        + len(away_values)
    )

    result = calculate_over_under(
        expected_total=expected_total,
        historical_total=historical_average,
        sample_size=sample_size,
    )

    if not result:
        return None

    result["expectedHome"] = round(
        expected_home,
        2,
    )

    result["expectedAway"] = round(
        expected_away,
        2,
    )

    result["homeSamples"] = len(
        home_values
    )

    result["awaySamples"] = len(
        away_values
    )

    return result


# ============================================================
# TAKIM ÖZETİ
# ============================================================

def build_team_summary(
    home_history,
    away_history,
):
    averages = calculate_basic_averages(
        home_history,
        away_history,
    )

    return {
        "homeTeamHomeGames": len(
            home_history
        ),
        "awayTeamAwayGames": len(
            away_history
        ),

        "homeTeamHomeScored":
            round_or_none(
                averages.get(
                    "homeScored"
                )
            ),

        "homeTeamHomeConceded":
            round_or_none(
                averages.get(
                    "homeConceded"
                )
            ),

        "awayTeamAwayScored":
            round_or_none(
                averages.get(
                    "awayScored"
                )
            ),

        "awayTeamAwayConceded":
            round_or_none(
                averages.get(
                    "awayConceded"
                )
            ),
    }


def round_or_none(value):
    if value is None:
        return None

    return round(
        float(value),
        2,
    )


# ============================================================
# MAÇ TAHMİNİ
# ============================================================

def predict_match(match):
    home_history = get_home_history(
        match
    )

    away_history = get_away_history(
        match
    )

    # İki tarafta da en az bir örnek
    # yoksa tahmin üretme.
    if not home_history:
        return None

    if not away_history:
        return None

    averages = calculate_basic_averages(
        home_history,
        away_history,
    )

    expected = calculate_expected_score(
        averages
    )

    if not expected:
        return None

    sample_size = (
        len(home_history)
        + len(away_history)
    )

    main_prediction = calculate_main_prediction(
        expected,
        sample_size,
    )

    match_total = calculate_match_total(
        home_history,
        away_history,
        expected,
    )

    first_half = calculate_first_half_total(
        home_history,
        away_history,
    )

    periods = {}

    for period in (
        "q1",
        "q2",
        "q3",
        "q4",
    ):
        result = calculate_period_total(
            home_history,
            away_history,
            period,
        )

        if result:
            periods[period] = result

    return {
        "matchId": match.get(
            "id"
        ),

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

        "homeTeam": match.get(
            "homeTeam"
        ),

        "awayTeam": match.get(
            "awayTeam"
        ),

        "sample": {
            "home": len(
                home_history
            ),
            "away": len(
                away_history
            ),
            "total": sample_size,
        },

        "teamAverages": build_team_summary(
            home_history,
            away_history,
        ),

        "expectedScore": {
            "home": expected["home"],
            "away": expected["away"],
            "total": expected["total"],
        },

        "mainPrediction": main_prediction,

        "totals": {
            "match": match_total,
            "firstHalf": first_half,
            "periods": periods,
        },
    }


# ============================================================
# DOSYA OKU
# ============================================================

def load_data():
    if not os.path.exists(
        INPUT_FILE
    ):
        raise FileNotFoundError(
            f"{INPUT_FILE} bulunamadı."
        )

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    if isinstance(data, dict):
        matches = data.get(
            "matches"
        )

        if isinstance(
            matches,
            list,
        ):
            return data, matches

    if isinstance(data, list):
        return {
            "matches": data
        }, data

    raise RuntimeError(
        "basketball.json içinde "
        "'matches' listesi bulunamadı."
    )


# ============================================================
# KAYDET
# ============================================================

def save_predictions(
    source_data,
    predictions,
):
    leagues = {}

    for item in predictions:
        league = item.get(
            "league"
        )

        if league not in leagues:
            leagues[league] = 0

        leagues[league] += 1

    output = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "sourceUpdatedAt":
            source_data.get(
                "updatedAt"
            ),

        "settings": {
            "maxHistory":
                MAX_HISTORY,

            "drawTolerance":
                DRAW_TOLERANCE,

            "lineStep":
                LINE_STEP,

            "historyMethod":
                "home-only-and-away-only",

            "overUnderMethod":
                "average-scored-and-conceded",
        },

        "statistics": {
            "totalPredictions":
                len(predictions),

            "leagues":
                leagues,
        },

        "predictions": predictions,
    }

    temp_file = (
        OUTPUT_FILE
        + ".tmp"
    )

    with open(
        temp_file,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=2,
        )

    os.replace(
        temp_file,
        OUTPUT_FILE
    )


# ============================================================
# ANA PROGRAM
# ============================================================

def main():
    print()
    print("=" * 70)
    print("🏀 BASKETBOL TAHMİN SİSTEMİ")
    print("=" * 70)

    print(
        f"📂 Kaynak: {INPUT_FILE}"
    )

    source_data, matches = load_data()

    print(
        f"📦 Toplam maç: {len(matches)}"
    )

    predictions = []

    skipped = 0

    for index, match in enumerate(
        matches,
        start=1,
    ):
        prediction = predict_match(
            match
        )

        if prediction is None:
            skipped += 1
            continue

        predictions.append(
            prediction
        )

    save_predictions(
        source_data,
        predictions,
    )

    print()
    print("=" * 70)
    print("📊 SONUÇ")
    print("=" * 70)

    print(
        f"🎯 Tahmin oluşturulan: "
        f"{len(predictions)}"
    )

    print(
        f"⏭️ Yeterli veri olmayan: "
        f"{skipped}"
    )

    league_counts = {}

    for item in predictions:
        league = item.get(
            "league"
        )

        league_counts[league] = (
            league_counts.get(
                league,
                0
            )
            + 1
        )

    for league, count in sorted(
        league_counts.items()
    ):
        print(
            f"   {league}: {count} tahmin"
        )

    # --------------------------------------------------------
    # ÖRNEK
    # --------------------------------------------------------

    if predictions:
        example = predictions[0]

        print()
        print("=" * 70)
        print("🔎 ÖRNEK TAHMİN")
        print("=" * 70)

        print(
            f"🏀 "
            f"{example.get('homeTeam')} "
            f"- "
            f"{example.get('awayTeam')}"
        )

        main = example.get(
            "mainPrediction"
        )

        if main:
            print(
                f"🎯 Ana tahmin: "
                f"{main.get('prediction')}"
            )

            print(
                f"   Beklenen skor: "
                f"{main.get('expectedHome')} - "
                f"{main.get('expectedAway')}"
            )

        totals = example.get(
            "totals",
            {}
        )

        match_total = totals.get(
            "match"
        )

        if match_total:
            print(
                f"📈 Maç Alt/Üst: "
                f"{match_total.get('prediction')} "
                f"{match_total.get('line')}"
            )

        first_half = totals.get(
            "firstHalf"
        )

        if first_half:
            print(
                f"⏱️ İY Alt/Üst: "
                f"{first_half.get('prediction')} "
                f"{first_half.get('line')}"
            )

        period_totals = totals.get(
            "periods",
            {}
        )

        for period in (
            "q1",
            "q2",
            "q3",
            "q4",
        ):
            item = period_totals.get(
                period
            )

            if item:
                print(
                    f"   {period.upper()} "
                    f"Alt/Üst: "
                    f"{item.get('prediction')} "
                    f"{item.get('line')}"
                )

    print()
    print("=" * 70)
    print(
        f"💾 {OUTPUT_FILE} oluşturuldu."
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
