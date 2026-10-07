# ============================================================
# BASKETBOL TAHMİN SİSTEMİ
# NBA + EUROLEAGUE
#
# Ana tahmin:
#   Belirlenen barem aralığındaki her 1 puanlık baremin
#   geçmiş maçlarda ÜST / ALT gelme yüzdesini hesaplar.
#
# ÖRNEK:
#   BAREM_MIN = 219.5
#   BAREM_MAX = 227.5
#   BAREM_ADIM = 1.0
#
#   219.5
#   220.5
#   221.5
#   ...
#   227.5
#
# Veri çekme sistemi değiştirilmez.
# basketball.json kullanılır.
# ============================================================

import json
import math
import os
import re
from datetime import datetime, timezone


# ============================================================
# DOSYALAR
# ============================================================

INPUT_FILE = "basketball.json"
OUTPUT_FILE = "predictions.json"


# ============================================================
# BAREM AYARLARI
#
# SADECE BURAYI DEĞİŞTİR
# ============================================================

# Başlangıç baremi
BAREM_MIN = 219.5

# Bitiş baremi
BAREM_MAX = 227.5

# Barem aralığındaki fark
#
# 1.0  -> 219.5, 220.5, 221.5, 222.5...
# 2.0  -> 219.5, 221.5, 223.5, 225.5...
#
BAREM_ADIM = 1.0


# ============================================================
# GEÇMİŞ MAÇ AYARLARI
# ============================================================

MAX_HISTORY = 10

NEWEST_WEIGHT = 1.00
OLDEST_WEIGHT = 0.55

HOME_ADVANTAGE = 2.0

MIN_CONFIDENCE = 50
MAX_CONFIDENCE = 95


# ============================================================
# GENEL YARDIMCI FONKSİYONLAR
# ============================================================

def safe_float(value, default=None):
    try:
        if value is None:
            return default

        if isinstance(value, bool):
            return default

        value = str(value).strip()

        if not value:
            return default

        return float(value)

    except Exception:
        return default


def safe_int(value, default=None):
    try:
        if value is None:
            return default

        if isinstance(value, bool):
            return default

        return int(float(value))

    except Exception:
        return default


def normalize_name(value):
    if value is None:
        return ""

    text = str(value).lower().strip()

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
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def parse_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()

        if not text:
            return None

        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"

            dt = datetime.fromisoformat(text)

        except Exception:
            formats = [
                "%Y-%m-%d",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%d.%m.%Y",
                "%d.%m.%Y %H:%M",
                "%d.%m.%Y %H:%M:%S",
            ]

            dt = None

            for fmt in formats:
                try:
                    dt = datetime.strptime(text, fmt)
                    break
                except Exception:
                    pass

            if dt is None:
                return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def get_match_datetime(match):
    for key in (
        "utcDate",
        "date",
        "datetime",
        "startTime",
        "startDate",
    ):
        value = match.get(key)

        dt = parse_datetime(value)

        if dt:
            return dt

    return None


def get_team_name(match, side):
    if side == "home":
        keys = (
            "homeTeam",
            "home",
            "homeName",
        )
    else:
        keys = (
            "awayTeam",
            "away",
            "awayName",
        )

    for key in keys:
        value = match.get(key)

        if isinstance(value, dict):
            for subkey in (
                "name",
                "shortName",
                "displayName",
                "teamName",
            ):
                if value.get(subkey):
                    return str(value[subkey])

        elif value:
            return str(value)

    return ""


def get_score(match, side):
    if side == "home":
        keys = (
            "homeScore",
            "home_score",
            "homePoints",
        )
    else:
        keys = (
            "awayScore",
            "away_score",
            "awayPoints",
        )

    for key in keys:
        value = safe_int(match.get(key))

        if value is not None:
            return value

    return None


def is_played(match):
    if match.get("played") is True:
        return True

    home = get_score(match, "home")
    away = get_score(match, "away")

    return home is not None and away is not None


def get_league(match):
    value = match.get("league")

    if isinstance(value, dict):
        for key in ("name", "code", "id"):
            if value.get(key) is not None:
                return str(value[key])

    if value is None:
        return ""

    return str(value)


def same_league(a, b):
    la = normalize_name(get_league(a))
    lb = normalize_name(get_league(b))

    if not la or not lb:
        return True

    return la == lb


def match_is_before(history_match, target_match):
    hdt = get_match_datetime(history_match)
    tdt = get_match_datetime(target_match)

    if hdt is None or tdt is None:
        return False

    return hdt < tdt


# ============================================================
# BAREMLERİ OLUŞTUR
# ============================================================

def build_barem_list():
    """
    Örnek:

    219.5 -> 227.5
    adım 1

    sonuç:
    219.5
    220.5
    221.5
    ...
    227.5
    """

    if BAREM_ADIM <= 0:
        raise ValueError("BAREM_ADIM 0'dan büyük olmalıdır.")

    if BAREM_MAX < BAREM_MIN:
        raise ValueError("BAREM_MAX, BAREM_MIN değerinden küçük olamaz.")

    barems = []

    current = float(BAREM_MIN)

    while current <= BAREM_MAX + 0.0001:
        barems.append(round(current, 1))
        current += BAREM_ADIM

    return barems


# ============================================================
# GEÇMİŞ KAYIT
# ============================================================

def make_history_record(match):
    home = get_team_name(match, "home")
    away = get_team_name(match, "away")

    home_score = get_score(match, "home")
    away_score = get_score(match, "away")

    if home_score is None or away_score is None:
        return None

    total = home_score + away_score

    return {
        "id": match.get("id"),
        "date": match.get("date"),
        "utcDate": match.get("utcDate"),
        "homeTeam": home,
        "awayTeam": away,
        "homeScore": home_score,
        "awayScore": away_score,
        "total": total,
        "league": get_league(match),
    }


def sort_newest_first(matches):
    def sort_key(match):
        dt = get_match_datetime(match)

        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)

        return dt

    return sorted(matches, key=sort_key, reverse=True)


# ============================================================
# TAKIM GEÇMİŞİ
# ============================================================

def get_last_10(team_history):
    team_history = sort_newest_first(team_history)

    return team_history[:MAX_HISTORY]


def get_weight(index, count):
    if count <= 1:
        return NEWEST_WEIGHT

    ratio = index / (count - 1)

    return NEWEST_WEIGHT - (
        (NEWEST_WEIGHT - OLDEST_WEIGHT) * ratio
    )


def calculate_team_stats(history):
    if not history:
        return {
            "matches": 0,
            "weightedMatches": 0,
            "scored": 0,
            "conceded": 0,
            "averageScored": 0,
            "averageConceded": 0,
            "averageTotal": 0,
        }

    history = get_last_10(history)

    weighted_scored = 0.0
    weighted_conceded = 0.0
    weighted_total = 0.0
    weight_sum = 0.0

    for index, item in enumerate(history):
        weight = get_weight(index, len(history))

        weighted_scored += item["scored"] * weight
        weighted_conceded += item["conceded"] * weight
        weighted_total += item["total"] * weight

        weight_sum += weight

    if weight_sum <= 0:
        weight_sum = 1

    return {
        "matches": len(history),
        "weightedMatches": round(weight_sum, 3),
        "scored": round(weighted_scored, 2),
        "conceded": round(weighted_conceded, 2),
        "averageScored": round(weighted_scored / weight_sum, 2),
        "averageConceded": round(weighted_conceded / weight_sum, 2),
        "averageTotal": round(weighted_total / weight_sum, 2),
    }


def find_team_history(matches, team_name, target_match):
    normalized_team = normalize_name(team_name)

    history = []

    for match in matches:
        if not is_played(match):
            continue

        if not match_is_before(match, target_match):
            continue

        if not same_league(match, target_match):
            continue

        home = get_team_name(match, "home")
        away = get_team_name(match, "away")

        nhome = normalize_name(home)
        naway = normalize_name(away)

        if normalized_team != nhome and normalized_team != naway:
            continue

        record = make_history_record(match)

        if record is None:
            continue

        if normalized_team == nhome:
            history.append({
                "date": record["date"],
                "team": home,
                "opponent": away,
                "scored": record["homeScore"],
                "conceded": record["awayScore"],
                "total": record["total"],
            })

        elif normalized_team == naway:
            history.append({
                "date": record["date"],
                "team": away,
                "opponent": home,
                "scored": record["awayScore"],
                "conceded": record["homeScore"],
                "total": record["total"],
            })

    return get_last_10(history)


# ============================================================
# BEKLENEN SKOR
# ============================================================

def calculate_expected_score(
    home_stats,
    away_stats,
):
    if home_stats["matches"] == 0:
        home_attack = 0
        home_defense = 0
    else:
        home_attack = home_stats["averageScored"]
        home_defense = home_stats["averageConceded"]

    if away_stats["matches"] == 0:
        away_attack = 0
        away_defense = 0
    else:
        away_attack = away_stats["averageScored"]
        away_defense = away_stats["averageConceded"]

    if home_stats["matches"] == 0 and away_stats["matches"] == 0:
        return 0, 0

    expected_home = (
        (home_attack + away_defense) / 2
    ) + HOME_ADVANTAGE

    expected_away = (
        (away_attack + home_defense) / 2
    )

    expected_home = max(0, expected_home)
    expected_away = max(0, expected_away)

    return (
        round(expected_home, 2),
        round(expected_away, 2),
    )


# ============================================================
# 1X2
# ============================================================

def calculate_1x2(
    expected_home,
    expected_away,
    home_stats,
    away_stats,
):
    difference = expected_home - expected_away

    base = 1 / (1 + math.exp(-difference / 7))

    home_probability = 0.20 + (base * 0.60)
    away_probability = 0.20 + ((1 - base) * 0.60)

    draw_probability = max(
        0.05,
        1 - home_probability - away_probability
    )

    total_probability = (
        home_probability
        + draw_probability
        + away_probability
    )

    home_probability /= total_probability
    draw_probability /= total_probability
    away_probability /= total_probability

    values = {
        "1": home_probability,
        "X": draw_probability,
        "2": away_probability,
    }

    prediction = max(
        values,
        key=values.get
    )

    confidence = values[prediction] * 100

    return {
        "prediction": prediction,
        "confidence": round(confidence, 1),
        "homeWinProbability": round(home_probability * 100, 1),
        "drawProbability": round(draw_probability * 100, 1),
        "awayWinProbability": round(away_probability * 100, 1),
    }


# ============================================================
# BAREM İSTATİSTİĞİ
# ============================================================

def calculate_barem_statistics(
    history,
    barem,
):
    """
    Verilen barem için geçmiş toplam sayıların
    ÜST / ALT oranını hesaplar.

    Örneğin:

    barem = 219.5

    toplam > 219.5 -> ÜST
    toplam < 219.5 -> ALT

    .5 barem olduğu için push oluşmaz.
    """

    if not history:
        return {
            "barem": round(barem, 1),
            "ust": 0,
            "alt": 0,
            "ustPercent": 0,
            "altPercent": 0,
            "confidence": 0,
            "sample": 0,
            "prediction": None,
        }

    ust = 0
    alt = 0

    for item in history:
        total = safe_float(item.get("total"))

        if total is None:
            continue

        if total > barem:
            ust += 1
        elif total < barem:
            alt += 1

    sample = ust + alt

    if sample == 0:
        return {
            "barem": round(barem, 1),
            "ust": 0,
            "alt": 0,
            "ustPercent": 0,
            "altPercent": 0,
            "confidence": 0,
            "sample": 0,
            "prediction": None,
        }

    ust_percent = (ust / sample) * 100
    alt_percent = (alt / sample) * 100

    if ust_percent >= alt_percent:
        prediction = "ÜST"
        confidence = ust_percent
    else:
        prediction = "ALT"
        confidence = alt_percent

    return {
        "barem": round(barem, 1),
        "ust": ust,
        "alt": alt,
        "ustPercent": round(ust_percent, 1),
        "altPercent": round(alt_percent, 1),
        "confidence": round(confidence, 1),
        "sample": sample,
        "prediction": prediction,
    }


# ============================================================
# TÜM BAREMLERİ HESAPLA
# ============================================================

def calculate_all_barems(history, barems):
    results = []

    for barem in barems:
        result = calculate_barem_statistics(
            history,
            barem
        )

        results.append(result)

    return results


# ============================================================
# EN GÜÇLÜ BAREM
# ============================================================

def find_best_barem(barems):
    valid = [
        item
        for item in barems
        if item.get("sample", 0) > 0
        and item.get("prediction")
    ]

    if not valid:
        return None

    # En yüksek güven yüzdesini seç.
    # Eşitlik halinde örneklemi daha yüksek olan kazanır.
    valid.sort(
        key=lambda x: (
            x.get("confidence", 0),
            x.get("sample", 0),
        ),
        reverse=True,
    )

    return valid[0]


# ============================================================
# GERÇEK SONUÇ
# ============================================================

def calculate_actual(match):
    home = get_score(match, "home")
    away = get_score(match, "away")

    if home is None or away is None:
        return {
            "actualTotal": None,
            "actualResult1X2": None,
        }

    total = home + away

    if home > away:
        result_1x2 = "1"
    elif home < away:
        result_1x2 = "2"
    else:
        result_1x2 = "X"

    return {
        "actualTotal": total,
        "actualResult1X2": result_1x2,
    }


# ============================================================
# ANA TAHMİN SONUCU
# ============================================================

def evaluate_main_prediction(
    prediction,
    actual_total,
):
    if actual_total is None:
        return None, None

    best = prediction.get("bestBarem")

    if not best:
        return None, None

    barem = safe_float(best.get("barem"))

    if barem is None:
        return None, None

    if actual_total == barem:
        return "PUSH", None

    actual_prediction = (
        "ÜST"
        if actual_total > barem
        else "ALT"
    )

    success = actual_prediction == best.get("prediction")

    return (
        actual_prediction,
        success,
    )


# ============================================================
# MAÇ TAHMİNİ OLUŞTUR
# ============================================================

def build_prediction_for_match(
    match,
    all_matches,
    barems,
):
    home_team = get_team_name(match, "home")
    away_team = get_team_name(match, "away")

    home_history = find_team_history(
        all_matches,
        home_team,
        match,
    )

    away_history = find_team_history(
        all_matches,
        away_team,
        match,
    )

    combined_history = []

    combined_history.extend(home_history)
    combined_history.extend(away_history)

    # Aynı maçı iki kere saymamak için
    # tarih + rakip + skor kombinasyonu kullan.
    unique_history = {}

    for item in combined_history:
        key = (
            str(item.get("date")),
            normalize_name(item.get("team")),
            normalize_name(item.get("opponent")),
            item.get("scored"),
            item.get("conceded"),
        )

        unique_history[key] = item

    combined_history = list(unique_history.values())

    combined_history = sorted(
        combined_history,
        key=lambda x: (
            parse_datetime(x.get("date"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )

    # En fazla son 10 ortak geçmiş kayıt
    combined_history = combined_history[:MAX_HISTORY]

    home_stats = calculate_team_stats(
        home_history
    )

    away_stats = calculate_team_stats(
        away_history
    )

    expected_home, expected_away = calculate_expected_score(
        home_stats,
        away_stats,
    )

    expected_total = round(
        expected_home + expected_away,
        2,
    )

    # --------------------------------------------------------
    # BAREMLER
    # --------------------------------------------------------

    barem_results = calculate_all_barems(
        combined_history,
        barems,
    )

    best_barem = find_best_barem(
        barem_results
    )

    # --------------------------------------------------------
    # 1X2
    # --------------------------------------------------------

    one_x_two = calculate_1x2(
        expected_home,
        expected_away,
        home_stats,
        away_stats,
    )

    # --------------------------------------------------------
    # GERÇEK SONUÇ
    # --------------------------------------------------------

    actual = calculate_actual(match)

    prediction = None
    confidence = 0

    if best_barem:
        prediction = best_barem["prediction"]
        confidence = best_barem["confidence"]

    result = None
    success = None

    if is_played(match):
        result, success = evaluate_main_prediction(
            {
                "bestBarem": best_barem
            },
            actual["actualTotal"],
        )

    result_1x2 = None
    success_1x2 = None

    if actual["actualResult1X2"] is not None:
        result_1x2 = actual["actualResult1X2"]

        success_1x2 = (
            result_1x2
            == one_x_two["prediction"]
        )

    # --------------------------------------------------------
    # ÇIKTI
    # --------------------------------------------------------

    output = {
        "id": match.get("id"),

        "league": get_league(match),

        "season": match.get("season"),

        "date": match.get("date"),

        "utcDate": match.get("utcDate"),

        "homeTeam": home_team,

        "awayTeam": away_team,

        "homeScore": get_score(match, "home"),

        "awayScore": get_score(match, "away"),

        "played": is_played(match),

        # ----------------------------------------------------
        # ANA TAHMİN
        # ----------------------------------------------------

        "prediction": prediction,

        "line": (
            best_barem["barem"]
            if best_barem
            else None
        ),

        "barem": (
            best_barem["barem"]
            if best_barem
            else None
        ),

        "confidence": round(
            confidence,
            1,
        ),

        # ----------------------------------------------------
        # TÜM BAREMLER
        # ----------------------------------------------------

        "barems": barem_results,

        "bestBarem": best_barem,

        "bestBaremPrediction": (
            best_barem["prediction"]
            if best_barem
            else None
        ),

        "bestBaremConfidence": (
            best_barem["confidence"]
            if best_barem
            else 0
        ),

        "bestBaremUstPercent": (
            best_barem["ustPercent"]
            if best_barem
            else 0
        ),

        "bestBaremAltPercent": (
            best_barem["altPercent"]
            if best_barem
            else 0
        ),

        # ----------------------------------------------------
        # BEKLENEN SKOR
        # ----------------------------------------------------

        "expectedHome": expected_home,

        "expectedAway": expected_away,

        "expectedTotal": expected_total,

        # ----------------------------------------------------
        # 1X2
        # ----------------------------------------------------

        "prediction1X2": one_x_two["prediction"],

        "confidence1X2": one_x_two["confidence"],

        "homeWinProbability": one_x_two[
            "homeWinProbability"
        ],

        "drawProbability": one_x_two[
            "drawProbability"
        ],

        "awayWinProbability": one_x_two[
            "awayWinProbability"
        ],

        # ----------------------------------------------------
        # GERÇEK SONUÇ
        # ----------------------------------------------------

        "actualTotal": actual["actualTotal"],

        "actualResult1X2": actual[
            "actualResult1X2"
        ],

        "result1X2": result_1x2,

        "success1X2": success_1x2,

        "result": result,

        "success": success,

        # ----------------------------------------------------
        # ÖRNEKLEM
        # ----------------------------------------------------

        "homeSample": home_stats["matches"],

        "awaySample": away_stats["matches"],

        "baremSample": len(combined_history),
    }

    return output


# ============================================================
# TÜM TAHMİNLER
# ============================================================

def build_predictions(matches):
    barems = build_barem_list()

    predictions = []

    for match in matches:
        try:
            prediction = build_prediction_for_match(
                match,
                matches,
                barems,
            )

            predictions.append(prediction)

        except Exception as exc:
            print(
                f"⚠️ Tahmin oluşturulamadı "
                f"{match.get('id')}: {exc}"
            )

    return predictions, barems


# ============================================================
# ÖZET HESAPLA
# ============================================================

def calculate_summary(predictions):
    total = len(predictions)

    played = [
        p
        for p in predictions
        if p.get("played") is True
    ]

    upcoming = [
        p
        for p in predictions
        if p.get("played") is not True
    ]

    successful = [
        p
        for p in played
        if p.get("success") is True
    ]

    failed = [
        p
        for p in played
        if p.get("success") is False
    ]

    push = [
        p
        for p in played
        if p.get("result") == "PUSH"
    ]

    main_evaluated = successful + failed

    if main_evaluated:
        main_success_rate = (
            len(successful)
            / len(main_evaluated)
        ) * 100
    else:
        main_success_rate = 0

    # 1X2
    one_x_two_evaluated = [
        p
        for p in predictions
        if p.get("success1X2") is not None
    ]

    one_x_two_success = [
        p
        for p in one_x_two_evaluated
        if p.get("success1X2") is True
    ]

    if one_x_two_evaluated:
        one_x_two_rate = (
            len(one_x_two_success)
            / len(one_x_two_evaluated)
        ) * 100
    else:
        one_x_two_rate = 0

    return {
        "total": total,

        "played": len(played),

        "upcoming": len(upcoming),

        "evaluated": len(main_evaluated),

        "successful": len(successful),

        "failed": len(failed),

        "push": len(push),

        "successRate": round(
            main_success_rate,
            1,
        ),

        "successRateMainPrediction": round(
            main_success_rate,
            1,
        ),

        "oneXTwoEvaluated": len(
            one_x_two_evaluated
        ),

        "oneXTwoSuccessful": len(
            one_x_two_success
        ),

        "oneXTwoSuccessRate": round(
            one_x_two_rate,
            1,
        ),
    }


# ============================================================
# LİG ÖZETLERİ
# ============================================================

def calculate_league_summaries(predictions):
    leagues = {}

    for prediction in predictions:
        league = prediction.get("league") or "Diğer"

        if league not in leagues:
            leagues[league] = []

        leagues[league].append(prediction)

    output = {}

    for league, items in leagues.items():
        output[league] = calculate_summary(items)

    return output


# ============================================================
# JSON KAYDET
# ============================================================

def save_json(data):
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            separators=(",", ":"),
        )


# ============================================================
# KONSOL ÖZETİ
# ============================================================

def print_summary(
    predictions,
    barems,
):
    summary = calculate_summary(
        predictions
    )

    print()
    print("=" * 60)
    print("🏀 BASKETBOL TAHMİN SİSTEMİ")
    print("=" * 60)

    print(
        f"📊 Toplam maç       : {summary['total']}"
    )

    print(
        f"🏁 Oynanmış         : {summary['played']}"
    )

    print(
        f"🔮 Oynanmamış       : {summary['upcoming']}"
    )

    print()
    print("🎯 BAREM ARALIĞI")
    print(
        f"   {BAREM_MIN} → {BAREM_MAX}"
    )

    print(
        f"   Adım: {BAREM_ADIM}"
    )

    print(
        f"   Toplam barem: {len(barems)}"
    )

    print()

    print(
        f"✅ Ana tahmin başarı : "
        f"%{summary['successRate']}"
    )

    print(
        f"🎯 1X2 başarı        : "
        f"%{summary['oneXTwoSuccessRate']}"
    )

    print("=" * 60)

    # İlk birkaç baremi örnek olarak göster
    print()
    print("📈 BAREM ÖRNEKLERİ")

    for barem in barems[:10]:
        print(
            f"   {barem:.1f}"
        )

    if len(barems) > 10:
        print("   ...")

    print()


# ============================================================
# ANA
# ============================================================

def main():
    if not os.path.exists(INPUT_FILE):
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
        matches = data.get("matches", [])

    elif isinstance(data, list):
        matches = data

    else:
        matches = []

    if not isinstance(matches, list):
        matches = []

    print(
        f"📦 Veri içindeki maç sayısı: "
        f"{len(matches)}"
    )

    predictions, barems = build_predictions(
        matches
    )

    summary = calculate_summary(
        predictions
    )

    league_summaries = (
        calculate_league_summaries(
            predictions
        )
    )

    output = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": "basketball.json",

        "settings": {
            "maxHistory": MAX_HISTORY,

            "newestWeight": NEWEST_WEIGHT,

            "oldestWeight": OLDEST_WEIGHT,

            "homeAdvantage": HOME_ADVANTAGE,

            "minConfidence": MIN_CONFIDENCE,

            "maxConfidence": MAX_CONFIDENCE,

            # BAREM AYARLARI
            "baremMin": BAREM_MIN,

            "baremMax": BAREM_MAX,

            "baremAdim": BAREM_ADIM,

            "baremAraliklari": [
                BAREM_MIN,
                BAREM_MAX,
            ],

            "baremler": barems,
        },

        "summary": summary,

        "leagues": league_summaries,

        "predictions": predictions,
    }

    save_json(output)

    print_summary(
        predictions,
        barems,
    )

    print(
        f"💾 Kaydedildi: {OUTPUT_FILE}"
    )

    print(
        f"🔢 Tahmin sayısı: "
        f"{len(predictions)}"
    )


if __name__ == "__main__":
    main()
