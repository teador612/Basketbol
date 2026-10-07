# ============================================================
# BASKETBOL TAHMİN SİSTEMİ
# NBA + EUROLEAGUE
#
# ANA MANTIK:
# ------------------------------------------------------------
# SABİT / YAPAY BAREM KULLANILMAZ.
#
# Her maç için:
#
#   1. Takımların son maçları analiz edilir.
#   2. Beklenen ev sahibi skoru hesaplanır.
#   3. Beklenen deplasman skoru hesaplanır.
#   4. Beklenen toplam sayı bulunur.
#   5. Takımların geçmiş toplam skorlarından doğal referans
#      çizgisi hesaplanır.
#   6. Beklenen toplam > doğal referans ise ÜST
#      Beklenen toplam < doğal referans ise ALT
#
# ÖRNEK:
#
#   Beklenen toplam : 175.2
#   Doğal referans  : 173.8
#
#   Tahmin: ÜST 173.8
#
# Artık:
#
#   219.5
#   220.5
#   221.5
#   ...
#
# gibi sabit yapay baremler kullanılmaz.
#
# BAŞLAMAMIŞ / CANLI MAÇLAR:
#   played = False
#   result = None
#   success = None
#
# SADECE MAÇ BİTTİKTEN SONRA:
#   success = True / False
#   result = ÜST / ALT / PUSH
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
# GEÇMİŞ MAÇ AYARLARI
# ============================================================

MAX_HISTORY = 10

NEWEST_WEIGHT = 1.00
OLDEST_WEIGHT = 0.55

HOME_ADVANTAGE = 2.0

MIN_CONFIDENCE = 50
MAX_CONFIDENCE = 95

# Beklenen toplam ile doğal referans arasındaki farkın
# güven hesabında kullanılacak minimum farkı.
#
# Örneğin:
# fark = 1.5 sayı
#
# Bu değer doğrudan tahmin kararını değiştirmez.
# Sadece confidence hesabında kullanılır.
MIN_SIGNAL_DIFFERENCE = 0.5


# ============================================================
# YARDIMCI FONKSİYONLAR
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
                    dt = datetime.strptime(
                        text,
                        fmt
                    )
                    break

                except Exception:
                    pass

            if dt is None:
                return None

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

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


# ============================================================
# MAÇ DURUMU
# ============================================================

def get_status_value(match):

    for key in (
        "status",
        "matchStatus",
        "gameStatus",
        "state",
        "phase",
    ):

        value = match.get(key)

        if value is None:
            continue

        if isinstance(value, dict):

            for subkey in (
                "name",
                "status",
                "state",
                "type",
                "code",
            ):

                if value.get(subkey) is not None:
                    return str(
                        value[subkey]
                    )

        else:
            return str(value)

    return ""


def normalize_status(value):
    return normalize_name(value).replace(
        " ",
        "_"
    )


def is_final_status(match):

    status = normalize_status(
        get_status_value(match)
    )

    final_statuses = {
        "finished",
        "final",
        "completed",
        "complete",
        "ended",
        "end",
        "ft",
        "post",
        "closed",
        "game_finished",
        "match_finished",
        "finished_game",
    }

    return status in final_statuses


def is_live_status(match):

    status = normalize_status(
        get_status_value(match)
    )

    live_statuses = {
        "live",
        "in_progress",
        "inprogress",
        "playing",
        "ongoing",
        "started",
        "halftime",
        "half_time",
        "period_1",
        "period_2",
        "period_3",
        "period_4",
        "q1",
        "q2",
        "q3",
        "q4",
        "ot",
        "overtime",
    }

    return status in live_statuses


def is_explicitly_unstarted(match):

    status = normalize_status(
        get_status_value(match)
    )

    unstarted_statuses = {
        "scheduled",
        "not_started",
        "notstarted",
        "upcoming",
        "pre_match",
        "prematch",
        "pending",
        "fixture",
        "created",
        "not_played",
        "notplayed",
        "postponed",
        "cancelled",
        "canceled",
    }

    return status in unstarted_statuses


def has_real_final_score(match):

    home = get_score(
        match,
        "home"
    )

    away = get_score(
        match,
        "away"
    )

    if home is None or away is None:
        return False

    return True


def is_match_finished(match):

    if is_explicitly_unstarted(match):
        return False

    if is_live_status(match):
        return False

    if is_final_status(match):
        return has_real_final_score(match)

    if match.get("played") is True:
        return has_real_final_score(match)

    match_dt = get_match_datetime(match)

    if match_dt is None:
        return False

    now = datetime.now(
        timezone.utc
    )

    if match_dt > now:
        return False

    return has_real_final_score(match)


def is_played(match):
    return is_match_finished(match)


# ============================================================
# TAKIM / SKOR
# ============================================================

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
                    return str(
                        value[subkey]
                    )

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

        value = safe_int(
            match.get(key)
        )

        if value is not None:
            return value

    return None


def get_league(match):

    value = match.get("league")

    if isinstance(value, dict):

        for key in (
            "name",
            "code",
            "id",
        ):

            if value.get(key) is not None:
                return str(
                    value[key]
                )

    if value is None:
        return ""

    return str(value)


def same_league(a, b):

    la = normalize_name(
        get_league(a)
    )

    lb = normalize_name(
        get_league(b)
    )

    if not la or not lb:
        return True

    return la == lb


def match_is_before(
    history_match,
    target_match
):

    hdt = get_match_datetime(
        history_match
    )

    tdt = get_match_datetime(
        target_match
    )

    if hdt is None or tdt is None:
        return False

    return hdt < tdt


# ============================================================
# GEÇMİŞ KAYDI
# ============================================================

def make_history_record(match):

    if not is_match_finished(match):
        return None

    home = get_team_name(
        match,
        "home"
    )

    away = get_team_name(
        match,
        "away"
    )

    home_score = get_score(
        match,
        "home"
    )

    away_score = get_score(
        match,
        "away"
    )

    if (
        home_score is None
        or away_score is None
    ):
        return None

    total = (
        home_score
        + away_score
    )

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

        dt = get_match_datetime(
            match
        )

        if dt is None:

            return datetime.min.replace(
                tzinfo=timezone.utc
            )

        return dt

    return sorted(
        matches,
        key=sort_key,
        reverse=True,
    )


# ============================================================
# TAKIM GEÇMİŞİ
# ============================================================

def get_last_10(team_history):

    team_history = sort_newest_first(
        team_history
    )

    return team_history[:MAX_HISTORY]


def get_weight(index, count):

    if count <= 1:
        return NEWEST_WEIGHT

    ratio = index / (
        count - 1
    )

    return (
        NEWEST_WEIGHT
        - (
            (
                NEWEST_WEIGHT
                - OLDEST_WEIGHT
            )
            * ratio
        )
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

    history = get_last_10(
        history
    )

    weighted_scored = 0.0
    weighted_conceded = 0.0
    weighted_total = 0.0

    weight_sum = 0.0

    for index, item in enumerate(
        history
    ):

        weight = get_weight(
            index,
            len(history)
        )

        weighted_scored += (
            item["scored"]
            * weight
        )

        weighted_conceded += (
            item["conceded"]
            * weight
        )

        weighted_total += (
            item["total"]
            * weight
        )

        weight_sum += weight

    if weight_sum <= 0:
        weight_sum = 1

    return {
        "matches": len(history),

        "weightedMatches": round(
            weight_sum,
            3
        ),

        "scored": round(
            weighted_scored,
            2
        ),

        "conceded": round(
            weighted_conceded,
            2
        ),

        "averageScored": round(
            weighted_scored
            / weight_sum,
            2
        ),

        "averageConceded": round(
            weighted_conceded
            / weight_sum,
            2
        ),

        "averageTotal": round(
            weighted_total
            / weight_sum,
            2
        ),
    }


def find_team_history(
    matches,
    team_name,
    target_match
):

    normalized_team = normalize_name(
        team_name
    )

    history = []

    for match in matches:

        if not is_match_finished(
            match
        ):
            continue

        if not match_is_before(
            match,
            target_match
        ):
            continue

        if not same_league(
            match,
            target_match
        ):
            continue

        home = get_team_name(
            match,
            "home"
        )

        away = get_team_name(
            match,
            "away"
        )

        nhome = normalize_name(
            home
        )

        naway = normalize_name(
            away
        )

        if (
            normalized_team != nhome
            and normalized_team != naway
        ):
            continue

        record = make_history_record(
            match
        )

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

    return get_last_10(
        history
    )


# ============================================================
# BEKLENEN SKOR
# ============================================================

def calculate_expected_score(
    home_stats,
    away_stats
):

    if home_stats["matches"] == 0:

        home_attack = 0
        home_defense = 0

    else:

        home_attack = (
            home_stats["averageScored"]
        )

        home_defense = (
            home_stats["averageConceded"]
        )

    if away_stats["matches"] == 0:

        away_attack = 0
        away_defense = 0

    else:

        away_attack = (
            away_stats["averageScored"]
        )

        away_defense = (
            away_stats["averageConceded"]
        )

    if (
        home_stats["matches"] == 0
        and away_stats["matches"] == 0
    ):

        return 0, 0

    expected_home = (
        (
            home_attack
            + away_defense
        )
        / 2
    ) + HOME_ADVANTAGE

    expected_away = (
        (
            away_attack
            + home_defense
        )
        / 2
    )

    expected_home = max(
        0,
        expected_home
    )

    expected_away = max(
        0,
        expected_away
    )

    return (
        round(
            expected_home,
            2
        ),
        round(
            expected_away,
            2
        ),
    )


# ============================================================
# 1X2
# ============================================================

def calculate_1x2(
    expected_home,
    expected_away,
    home_stats,
    away_stats
):

    difference = (
        expected_home
        - expected_away
    )

    base = 1 / (
        1
        + math.exp(
            -difference / 7
        )
    )

    home_probability = (
        0.20
        + (
            base
            * 0.60
        )
    )

    away_probability = (
        0.20
        + (
            (1 - base)
            * 0.60
        )
    )

    draw_probability = max(
        0.05,
        1
        - home_probability
        - away_probability
    )

    total_probability = (
        home_probability
        + draw_probability
        + away_probability
    )

    home_probability /= (
        total_probability
    )

    draw_probability /= (
        total_probability
    )

    away_probability /= (
        total_probability
    )

    values = {
        "1": home_probability,
        "X": draw_probability,
        "2": away_probability,
    }

    prediction = max(
        values,
        key=values.get
    )

    confidence = (
        values[prediction]
        * 100
    )

    return {
        "prediction": prediction,

        "confidence": round(
            confidence,
            1
        ),

        "homeWinProbability": round(
            home_probability * 100,
            1
        ),

        "drawProbability": round(
            draw_probability * 100,
            1
        ),

        "awayWinProbability": round(
            away_probability * 100,
            1
        ),
    }


# ============================================================
# DOĞAL REFERANS ÇİZGİSİ
# ============================================================
#
# ARTIK YAPAY BAREM YOK.
#
# Referans:
#   Takımların son MAX_HISTORY maçındaki toplam skorlar
#   ağırlıklı olarak değerlendirilir.
#
# Örnek:
#
#   166
#   174
#   171
#   179
#   176
#   ...
#
# ağırlıklı ortalama:
#
#   173.8
#
# Bu maçın doğal referansıdır.
#
# Burada 219.5 gibi dışarıdan seçilmiş bir sayı yoktur.
# ============================================================

def calculate_natural_reference(
    history
):

    if not history:
        return None

    valid = []

    ordered = sort_history_records(
        history
    )

    ordered = ordered[:MAX_HISTORY]

    weighted_total = 0.0
    weight_sum = 0.0

    for index, item in enumerate(
        ordered
    ):

        total = safe_float(
            item.get("total")
        )

        if total is None:
            continue

        valid.append(total)

        weight = get_weight(
            index,
            len(ordered)
        )

        weighted_total += (
            total
            * weight
        )

        weight_sum += weight

    if weight_sum <= 0:
        return None

    average = (
        weighted_total
        / weight_sum
    )

    # Standart sapma / dağılım.
    if len(valid) >= 2:

        mean = sum(valid) / len(valid)

        variance = sum(
            (
                value - mean
            ) ** 2
            for value in valid
        ) / len(valid)

        stddev = math.sqrt(
            variance
        )

    else:

        stddev = 0.0

    return {
        "average": round(
            average,
            2
        ),

        "sample": len(valid),

        "stddev": round(
            stddev,
            2
        ),

        "min": round(
            min(valid),
            2
        ) if valid else None,

        "max": round(
            max(valid),
            2
        ) if valid else None,
    }


def sort_history_records(
    history
):

    def key(item):

        dt = parse_datetime(
            item.get("date")
        )

        if dt is None:

            dt = parse_datetime(
                item.get("utcDate")
            )

        if dt is None:

            return datetime.min.replace(
                tzinfo=timezone.utc
            )

        return dt

    return sorted(
        history,
        key=key,
        reverse=True
    )


# ============================================================
# DOĞAL REFERANSA GÖRE ALT / ÜST
# ============================================================

def calculate_natural_prediction(
    expected_total,
    reference
):

    if (
        expected_total is None
        or reference is None
    ):
        return {
            "prediction": None,
            "confidence": 0,
            "difference": None,
            "direction": None,
        }

    reference_average = safe_float(
        reference.get("average")
    )

    if reference_average is None:
        return {
            "prediction": None,
            "confidence": 0,
            "difference": None,
            "direction": None,
        }

    difference = (
        expected_total
        - reference_average
    )

    # Çok küçük farklarda yön güvenilmez.
    if abs(difference) < MIN_SIGNAL_DIFFERENCE:

        return {
            "prediction": None,
            "confidence": 50.0,
            "difference": round(
                difference,
                2
            ),
            "direction": "PUSH",
        }

    if difference > 0:

        prediction = "ÜST"

    else:

        prediction = "ALT"

    # Standart sapma güveni yumuşatmak için kullanılır.
    stddev = safe_float(
        reference.get("stddev"),
        0
    )

    if stddev is None or stddev <= 0:
        stddev = 10.0

    signal_strength = (
        abs(difference)
        / stddev
    )

    # Güven:
    #
    # küçük fark  -> düşük
    # orta fark    -> orta
    # büyük fark   -> yüksek
    #
    confidence = (
        50
        + (
            signal_strength
            * 18
        )
    )

    confidence = max(
        MIN_CONFIDENCE,
        min(
            MAX_CONFIDENCE,
            confidence
        )
    )

    return {
        "prediction": prediction,

        "confidence": round(
            confidence,
            1
        ),

        "difference": round(
            difference,
            2
        ),

        "direction": prediction,
    }


# ============================================================
# GERÇEK SONUÇ
# ============================================================

def calculate_actual(match):

    if not is_match_finished(
        match
    ):

        return {
            "actualTotal": None,
            "actualResult1X2": None,
        }

    home = get_score(
        match,
        "home"
    )

    away = get_score(
        match,
        "away"
    )

    if home is None or away is None:

        return {
            "actualTotal": None,
            "actualResult1X2": None,
        }

    total = (
        home
        + away
    )

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
    actual_total
):

    if actual_total is None:
        return None, None

    best = prediction.get(
        "bestBarem"
    )

    if not best:
        return None, None

    reference = safe_float(
        best.get("barem")
    )

    if reference is None:
        return None, None

    # Referans çizgisine tam eşit ise PUSH.
    if abs(
        actual_total
        - reference
    ) < 0.01:

        return "PUSH", None

    actual_prediction = (
        "ÜST"
        if actual_total > reference
        else "ALT"
    )

    predicted = best.get(
        "prediction"
    )

    if not predicted:
        return (
            actual_prediction,
            None
        )

    success = (
        actual_prediction
        == predicted
    )

    return (
        actual_prediction,
        success,
    )


# ============================================================
# MAÇ TAHMİNİ OLUŞTUR
# ============================================================

def build_prediction_for_match(
    match,
    all_matches
):

    home_team = get_team_name(
        match,
        "home"
    )

    away_team = get_team_name(
        match,
        "away"
    )

    # --------------------------------------------------------
    # TAKIM GEÇMİŞLERİ
    # --------------------------------------------------------

    home_history = find_team_history(
        all_matches,
        home_team,
        match
    )

    away_history = find_team_history(
        all_matches,
        away_team,
        match
    )

    # --------------------------------------------------------
    # BİRLEŞTİRİLMİŞ GEÇMİŞ
    # --------------------------------------------------------

    combined_history = []

    combined_history.extend(
        home_history
    )

    combined_history.extend(
        away_history
    )

    unique_history = {}

    for item in combined_history:

        key = (
            str(
                item.get("date")
            ),

            normalize_name(
                item.get("team")
            ),

            normalize_name(
                item.get("opponent")
            ),

            item.get("scored"),

            item.get("conceded"),
        )

        unique_history[key] = item

    combined_history = list(
        unique_history.values()
    )

    combined_history = sort_history_records(
        combined_history
    )

    combined_history = (
        combined_history[:MAX_HISTORY]
    )

    # --------------------------------------------------------
    # TAKIM İSTATİSTİKLERİ
    # --------------------------------------------------------

    home_stats = calculate_team_stats(
        home_history
    )

    away_stats = calculate_team_stats(
        away_history
    )

    # --------------------------------------------------------
    # BEKLENEN SKOR
    # --------------------------------------------------------

    (
        expected_home,
        expected_away
    ) = calculate_expected_score(
        home_stats,
        away_stats
    )

    expected_total = round(
        expected_home
        + expected_away,
        2
    )

    # --------------------------------------------------------
    # DOĞAL REFERANS
    # --------------------------------------------------------

    natural_reference = (
        calculate_natural_reference(
            combined_history
        )
    )

    # --------------------------------------------------------
    # ANA ALT / ÜST TAHMİNİ
    # --------------------------------------------------------

    natural_prediction = (
        calculate_natural_prediction(
            expected_total,
            natural_reference
        )
    )

    reference_line = None

    if natural_reference:

        reference_line = safe_float(
            natural_reference.get(
                "average"
            )
        )

    prediction = (
        natural_prediction.get(
            "prediction"
        )
    )

    confidence = (
        natural_prediction.get(
            "confidence",
            0
        )
    )

    # --------------------------------------------------------
    # GERİYE UYUMLULUK
    # --------------------------------------------------------
    #
    # Eski HTML bestBarem / barem / line okuyorsa çalışmaya
    # devam etsin.
    #
    # Fakat burada artık yapay barem yok.
    # Bu değer doğal referans çizgisidir.
    # --------------------------------------------------------

    best_barem = None

    if reference_line is not None:

        best_barem = {

            "barem": round(
                reference_line,
                2
            ),

            "ust": None,

            "alt": None,

            "ustPercent": None,

            "altPercent": None,

            "confidence": round(
                confidence,
                1
            ),

            "sample": (
                natural_reference.get(
                    "sample",
                    0
                )
                if natural_reference
                else 0
            ),

            "prediction": prediction,

            "expectedTotal":
                expected_total,

            "difference":
                natural_prediction.get(
                    "difference"
                ),

            "stddev":
                natural_reference.get(
                    "stddev"
                ),

            "type":
                "natural_reference",
        }

    # --------------------------------------------------------
    # 1X2
    # --------------------------------------------------------

    one_x_two = calculate_1x2(
        expected_home,
        expected_away,
        home_stats,
        away_stats
    )

    # --------------------------------------------------------
    # MAÇ DURUMU
    # --------------------------------------------------------

    finished = is_match_finished(
        match
    )

    live = is_live_status(
        match
    )

    match_dt = get_match_datetime(
        match
    )

    unstarted = (
        is_explicitly_unstarted(
            match
        )
        or (
            not finished
            and not live
            and match_dt is not None
            and match_dt
            > datetime.now(
                timezone.utc
            )
        )
    )

    # --------------------------------------------------------
    # GERÇEK SONUÇ
    # --------------------------------------------------------

    actual = calculate_actual(
        match
    )

    # --------------------------------------------------------
    # SADECE BİTMİŞ MAÇTA ANA SONUÇ
    # --------------------------------------------------------

    result = None
    success = None

    if finished:

        (
            result,
            success
        ) = evaluate_main_prediction(
            {
                "bestBarem":
                    best_barem
            },
            actual[
                "actualTotal"
            ]
        )

    # --------------------------------------------------------
    # 1X2 SADECE BİTMİŞ MAÇTA
    # --------------------------------------------------------

    result_1x2 = None
    success_1x2 = None

    if (
        finished
        and actual[
            "actualResult1X2"
        ] is not None
    ):

        result_1x2 = actual[
            "actualResult1X2"
        ]

        success_1x2 = (
            result_1x2
            == one_x_two[
                "prediction"
            ]
        )

    # --------------------------------------------------------
    # DURUM
    # --------------------------------------------------------

    if finished:

        status = "finished"

    elif live:

        status = "live"

    else:

        status = "scheduled"

    # --------------------------------------------------------
    # ÇIKTI
    # --------------------------------------------------------

    output = {

        "id":
            match.get("id"),

        "league":
            get_league(match),

        "season":
            match.get("season"),

        "date":
            match.get("date"),

        "utcDate":
            match.get("utcDate"),

        "homeTeam":
            home_team,

        "awayTeam":
            away_team,

        "homeScore":
            get_score(
                match,
                "home"
            ),

        "awayScore":
            get_score(
                match,
                "away"
            ),

        # ----------------------------------------------------
        # DURUM
        # ----------------------------------------------------

        "status":
            status,

        "isLive":
            live,

        "isFinished":
            finished,

        "isUnstarted":
            unstarted,

        "played":
            finished,

        # ----------------------------------------------------
        # ANA TAHMİN
        # ----------------------------------------------------

        "prediction":
            prediction,

        # Eski frontend uyumluluğu.
        # Artık yapay barem değil.
        "line":
            reference_line,

        "barem":
            reference_line,

        "confidence":
            round(
                confidence,
                1
            ),

        # ----------------------------------------------------
        # DOĞAL REFERANS
        # ----------------------------------------------------

        "referenceType":
            "natural_history_average",

        "naturalReference":
            reference_line,

        "naturalReferenceAverage":
            (
                natural_reference.get(
                    "average"
                )
                if natural_reference
                else None
            ),

        "naturalReferenceStdDev":
            (
                natural_reference.get(
                    "stddev"
                )
                if natural_reference
                else None
            ),

        "naturalReferenceMin":
            (
                natural_reference.get(
                    "min"
                )
                if natural_reference
                else None
            ),

        "naturalReferenceMax":
            (
                natural_reference.get(
                    "max"
                )
                if natural_reference
                else None
            ),

        "predictionDifference":
            natural_prediction.get(
                "difference"
            ),

        # ----------------------------------------------------
        # GERİYE UYUMLULUK
        # ----------------------------------------------------

        "bestBarem":
            best_barem,

        "bestBaremPrediction":
            (
                best_barem.get(
                    "prediction"
                )
                if best_barem
                else None
            ),

        "bestBaremConfidence":
            (
                best_barem.get(
                    "confidence"
                )
                if best_barem
                else 0
            ),

        "bestBaremUstPercent":
            None,

        "bestBaremAltPercent":
            None,

        # ----------------------------------------------------
        # ESKİ BAREM LİSTESİ YOK
        # ----------------------------------------------------
        #
        # Frontend'de barems alanı kontrol ediliyorsa boş liste
        # döndürülür.
        #
        # Böylece eski JS hata vermez.
        # ----------------------------------------------------

        "barems":
            [],

        # ----------------------------------------------------
        # BEKLENEN SKOR
        # ----------------------------------------------------

        "expectedHome":
            expected_home,

        "expectedAway":
            expected_away,

        "expectedTotal":
            expected_total,

        # ----------------------------------------------------
        # 1X2
        # ----------------------------------------------------

        "prediction1X2":
            one_x_two[
                "prediction"
            ],

        "confidence1X2":
            one_x_two[
                "confidence"
            ],

        "homeWinProbability":
            one_x_two[
                "homeWinProbability"
            ],

        "drawProbability":
            one_x_two[
                "drawProbability"
            ],

        "awayWinProbability":
            one_x_two[
                "awayWinProbability"
            ],

        # ----------------------------------------------------
        # GERÇEK SONUÇ
        # ----------------------------------------------------

        "actualTotal":
            actual[
                "actualTotal"
            ],

        "actualResult1X2":
            actual[
                "actualResult1X2"
            ],

        "result1X2":
            result_1x2,

        "success1X2":
            success_1x2,

        "result":
            result,

        "success":
            success,

        # ----------------------------------------------------
        # ÖRNEKLEM
        # ----------------------------------------------------

        "homeSample":
            home_stats[
                "matches"
            ],

        "awaySample":
            away_stats[
                "matches"
            ],

        "baremSample":
            (
                natural_reference.get(
                    "sample",
                    0
                )
                if natural_reference
                else 0
            ),
    }

    return output


# ============================================================
# TÜM TAHMİNLER
# ============================================================

def build_predictions(matches):

    predictions = []

    for match in matches:

        try:

            prediction = (
                build_prediction_for_match(
                    match,
                    matches
                )
            )

            predictions.append(
                prediction
            )

        except Exception as exc:

            print(
                f"⚠️ Tahmin oluşturulamadı "
                f"{match.get('id')}: {exc}"
            )

    return predictions


# ============================================================
# ÖZET
# ============================================================

def calculate_summary(
    predictions
):

    total = len(
        predictions
    )

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

    main_evaluated = (
        successful
        + failed
    )

    if main_evaluated:

        main_success_rate = (
            len(successful)
            / len(main_evaluated)
        ) * 100

    else:

        main_success_rate = 0

    # --------------------------------------------------------
    # 1X2
    # --------------------------------------------------------

    one_x_two_evaluated = [

        p

        for p in predictions

        if p.get(
            "success1X2"
        ) is not None
    ]

    one_x_two_success = [

        p

        for p in one_x_two_evaluated

        if p.get(
            "success1X2"
        ) is True
    ]

    if one_x_two_evaluated:

        one_x_two_rate = (

            len(
                one_x_two_success
            )

            / len(
                one_x_two_evaluated
            )

        ) * 100

    else:

        one_x_two_rate = 0

    return {

        "total":
            total,

        "played":
            len(played),

        "upcoming":
            len(upcoming),

        "evaluated":
            len(main_evaluated),

        "successful":
            len(successful),

        "failed":
            len(failed),

        "push":
            len(push),

        "successRate":
            round(
                main_success_rate,
                1
            ),

        "successRateMainPrediction":
            round(
                main_success_rate,
                1
            ),

        "oneXTwoEvaluated":
            len(
                one_x_two_evaluated
            ),

        "oneXTwoSuccessful":
            len(
                one_x_two_success
            ),

        "oneXTwoSuccessRate":
            round(
                one_x_two_rate,
                1
            ),
    }


# ============================================================
# LİG ÖZETLERİ
# ============================================================

def calculate_league_summaries(
    predictions
):

    leagues = {}

    for prediction in predictions:

        league = (
            prediction.get(
                "league"
            )
            or "Diğer"
        )

        if league not in leagues:

            leagues[league] = []

        leagues[league].append(
            prediction
        )

    output = {}

    for league, items in leagues.items():

        output[league] = (
            calculate_summary(
                items
            )
        )

    return output


# ============================================================
# JSON KAYDET
# ============================================================

def save_json(data):

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            separators=(
                ",",
                ":"
            )
        )


# ============================================================
# KONSOL ÖZETİ
# ============================================================

def print_summary(
    predictions
):

    summary = (
        calculate_summary(
            predictions
        )
    )

    print()

    print(
        "=" * 60
    )

    print(
        "🏀 BASKETBOL TAHMİN SİSTEMİ"
    )

    print(
        "=" * 60
    )

    print(
        f"📊 Toplam maç       : "
        f"{summary['total']}"
    )

    print(
        f"🏁 Oynanmış         : "
        f"{summary['played']}"
    )

    print(
        f"🔮 Oynanmamış       : "
        f"{summary['upcoming']}"
    )

    print()

    print(
        "📐 BAREM SİSTEMİ"
    )

    print(
        "   Sabit yapay barem: YOK"
    )

    print(
        "   Referans: Son maçların "
        "doğal toplam ortalaması"
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

    print(
        "=" * 60
    )

    print()


# ============================================================
# ANA
# ============================================================

def main():

    if not os.path.exists(
        INPUT_FILE
    ):

        raise FileNotFoundError(
            f"{INPUT_FILE} bulunamadı."
        )

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    if isinstance(
        data,
        dict
    ):

        matches = data.get(
            "matches",
            []
        )

    elif isinstance(
        data,
        list
    ):

        matches = data

    else:

        matches = []

    if not isinstance(
        matches,
        list
    ):

        matches = []

    print(
        f"📦 Veri içindeki maç sayısı: "
        f"{len(matches)}"
    )

    predictions = (
        build_predictions(
            matches
        )
    )

    summary = (
        calculate_summary(
            predictions
        )
    )

    league_summaries = (
        calculate_league_summaries(
            predictions
        )
    )

    # --------------------------------------------------------
    # AYARLAR
    # --------------------------------------------------------
    #
    # Burada artık BAREM_MIN / MAX / ADIM yok.
    # --------------------------------------------------------

    output = {

        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "source":
            "basketball.json",

        "settings": {

            "maxHistory":
                MAX_HISTORY,

            "newestWeight":
                NEWEST_WEIGHT,

            "oldestWeight":
                OLDEST_WEIGHT,

            "homeAdvantage":
                HOME_ADVANTAGE,

            "minConfidence":
                MIN_CONFIDENCE,

            "maxConfidence":
                MAX_CONFIDENCE,

            "minSignalDifference":
                MIN_SIGNAL_DIFFERENCE,

            "baremMode":
                "natural_history_average",

            "artificialBarem":
                False,

            "fixedBaremRange":
                False,

            "baremSource":
                "Takimlarin son maclarindaki dogal toplam sayi ortalamasi",
        },

        "summary":
            summary,

        "leagues":
            league_summaries,

        "predictions":
            predictions,
    }

    save_json(
        output
    )

    print_summary(
        predictions
    )

    print(
        f"💾 Kaydedildi: "
        f"{OUTPUT_FILE}"
    )

    print(
        f"🔢 Tahmin sayısı: "
        f"{len(predictions)}"
    )


# ============================================================
# ÇALIŞTIR
# ============================================================

if __name__ == "__main__":
    main()
