import json
import math
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "basketball.json"
OUTPUT_FILE = BASE_DIR / "predictions.json"

MAX_HISTORY = 10

# ------------------------------------------------------------
# AYARLAR
# ------------------------------------------------------------

# En yeni maça daha fazla ağırlık
NEWEST_WEIGHT = 1.00
OLDEST_WEIGHT = 0.55

# Ev sahibi avantajı
HOME_ADVANTAGE = 2.0

# Tahmin güvenini hesaplamak için
MIN_CONFIDENCE = 50
MAX_CONFIDENCE = 95


# ------------------------------------------------------------
# GENEL YARDIMCILAR
# ------------------------------------------------------------

def safe_float(value):
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def normalize_name(value):
    if value is None:
        return ""

    if isinstance(value, dict):
        value = (
            value.get("name")
            or value.get("displayName")
            or value.get("shortName")
            or value.get("team")
            or ""
        )

    return str(value).strip().lower()


def parse_datetime(value):
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt
    except Exception:
        return None


def get_match_datetime(match):
    return (
        parse_datetime(match.get("utcDate"))
        or parse_datetime(match.get("date"))
        or parse_datetime(match.get("datetime"))
        or parse_datetime(match.get("startTime"))
    )


def get_team_name(match, side):
    if side == "home":
        value = (
            match.get("homeTeam")
            or match.get("home")
            or match.get("home_team")
        )
    else:
        value = (
            match.get("awayTeam")
            or match.get("away")
            or match.get("away_team")
        )

    return normalize_name(value)


def get_score(match, side):
    if side == "home":
        keys = [
            "homeScore",
            "home_score",
        ]
    else:
        keys = [
            "awayScore",
            "away_score",
        ]

    for key in keys:
        value = safe_float(match.get(key))
        if value is not None:
            return value

    score = match.get("score")

    if isinstance(score, dict):
        if side == "home":
            value = (
                score.get("home")
                or score.get("homeScore")
                or score.get("home_score")
            )
        else:
            value = (
                score.get("away")
                or score.get("awayScore")
                or score.get("away_score")
            )

        value = safe_float(value)

        if value is not None:
            return value

    return None


def is_played(match):
    played = match.get("played")

    if played is True:
        return True

    home = get_score(match, "home")
    away = get_score(match, "away")

    if home is None or away is None:
        return False

    status = str(match.get("status") or "").lower()

    final_words = [
        "final",
        "finished",
        "complete",
        "completed",
        "closed",
        "post",
        "ended",
    ]

    if any(word in status for word in final_words):
        return True

    # basketball.json üreticisinde played yoksa,
    # iki skorun bulunmasını tamamlanmış kabul ediyoruz.
    if "status" not in match and "played" not in match:
        return True

    return bool(played)


def get_league(match):
    value = (
        match.get("league")
        or match.get("leagueName")
        or match.get("competition")
        or ""
    )

    if isinstance(value, dict):
        value = (
            value.get("name")
            or value.get("displayName")
            or value.get("slug")
            or ""
        )

    return str(value).strip()


def same_league(a, b):
    return normalize_name(get_league(a)) == normalize_name(get_league(b))


# ------------------------------------------------------------
# TARİH KARŞILAŞTIRMA
# ------------------------------------------------------------

def match_is_before(history_match, target_match):
    history_date = get_match_datetime(history_match)
    target_date = get_match_datetime(target_match)

    if history_date is None or target_date is None:
        return True

    return history_date < target_date


# ------------------------------------------------------------
# GEÇMİŞ MAÇ OLUŞTURMA
# ------------------------------------------------------------

def make_history_record(match, team_name):
    home_name = get_team_name(match, "home")
    away_name = get_team_name(match, "away")

    home_score = get_score(match, "home")
    away_score = get_score(match, "away")

    if home_score is None or away_score is None:
        return None

    if normalize_name(team_name) == home_name:
        scored = home_score
        conceded = away_score
        opponent = away_name
        is_home = True
    elif normalize_name(team_name) == away_name:
        scored = away_score
        conceded = home_score
        opponent = home_name
        is_home = False
    else:
        return None

    return {
        "date": match.get("date"),
        "utcDate": match.get("utcDate"),
        "opponent": opponent,
        "scored": scored,
        "conceded": conceded,
        "isHome": is_home,
        "matchId": match.get("id"),
        "league": get_league(match),
        "season": match.get("season"),
        "periods": match.get("periods") or {},
        "hasPeriodData": bool(match.get("hasPeriodData")),
    }


# ------------------------------------------------------------
# TARİH SIRASINA GÖRE SON 10
# ------------------------------------------------------------

def sort_newest_first(history):
    def key(item):
        dt = parse_datetime(item.get("utcDate")) or parse_datetime(item.get("date"))

        if dt is None:
            return datetime.min.replace(tzinfo=timezone.utc)

        return dt

    return sorted(history, key=key, reverse=True)


def get_last_10(history):
    return sort_newest_first(history)[:MAX_HISTORY]


# ------------------------------------------------------------
# AĞIRLIK
# ------------------------------------------------------------

def get_weight(index, sample_size):
    if sample_size <= 1:
        return NEWEST_WEIGHT

    ratio = index / (sample_size - 1)

    return NEWEST_WEIGHT - (
        (NEWEST_WEIGHT - OLDEST_WEIGHT) * ratio
    )


# ------------------------------------------------------------
# TAKIM İSTATİSTİĞİ
# ------------------------------------------------------------

def calculate_team_stats(history):
    if not history:
        return None

    history = get_last_10(history)

    weighted_scored = 0.0
    weighted_conceded = 0.0
    weighted_total = 0.0
    weight_sum = 0.0

    weighted_home_scored = 0.0
    weighted_home_conceded = 0.0
    home_weight_sum = 0.0

    weighted_away_scored = 0.0
    weighted_away_conceded = 0.0
    away_weight_sum = 0.0

    for index, game in enumerate(history):
        scored = safe_float(game.get("scored"))
        conceded = safe_float(game.get("conceded"))

        if scored is None or conceded is None:
            continue

        weight = get_weight(index, len(history))

        total = scored + conceded

        weighted_scored += scored * weight
        weighted_conceded += conceded * weight
        weighted_total += total * weight
        weight_sum += weight

        if game.get("isHome"):
            weighted_home_scored += scored * weight
            weighted_home_conceded += conceded * weight
            home_weight_sum += weight
        else:
            weighted_away_scored += scored * weight
            weighted_away_conceded += conceded * weight
            away_weight_sum += weight

    if weight_sum <= 0:
        return None

    avg_scored = weighted_scored / weight_sum
    avg_conceded = weighted_conceded / weight_sum
    avg_total = weighted_total / weight_sum

    avg_home_scored = (
        weighted_home_scored / home_weight_sum
        if home_weight_sum > 0
        else avg_scored
    )

    avg_home_conceded = (
        weighted_home_conceded / home_weight_sum
        if home_weight_sum > 0
        else avg_conceded
    )

    avg_away_scored = (
        weighted_away_scored / away_weight_sum
        if away_weight_sum > 0
        else avg_scored
    )

    avg_away_conceded = (
        weighted_away_conceded / away_weight_sum
        if away_weight_sum > 0
        else avg_conceded
    )

    return {
        "sample": len(history),
        "scored": avg_scored,
        "conceded": avg_conceded,
        "total": avg_total,
        "homeScored": avg_home_scored,
        "homeConceded": avg_home_conceded,
        "awayScored": avg_away_scored,
        "awayConceded": avg_away_conceded,
    }


# ------------------------------------------------------------
# MAÇ İÇİN GEÇMİŞ BUL
# ------------------------------------------------------------

def find_team_history(all_matches, team_name, target_match):
    team_name = normalize_name(team_name)

    if not team_name:
        return []

    history = []

    for match in all_matches:

        if match is target_match:
            continue

        if not is_played(match):
            continue

        # Çok önemli:
        # Geçmiş sadece aynı ligden alınır.
        if not same_league(match, target_match):
            continue

        if not match_is_before(match, target_match):
            continue

        home = get_team_name(match, "home")
        away = get_team_name(match, "away")

        if team_name != home and team_name != away:
            continue

        record = make_history_record(match, team_name)

        if record is not None:
            history.append(record)

    return get_last_10(history)


# ------------------------------------------------------------
# BEKLENEN SKOR
# ------------------------------------------------------------

def calculate_expected_score(home_stats, away_stats):

    if home_stats is None and away_stats is None:
        return None, None

    if home_stats is None:
        expected_home = away_stats["awayScored"]
        expected_away = away_stats["awayConceded"]

    elif away_stats is None:
        expected_home = home_stats["homeScored"]
        expected_away = home_stats["homeConceded"]

    else:

        # Ev sahibinin hücum gücü
        home_attack = home_stats["homeScored"]

        # Deplasman takımının savunmada verdiği sayı
        away_defense = away_stats["awayConceded"]

        # Deplasmanın hücum gücü
        away_attack = away_stats["awayScored"]

        # Ev sahibinin savunmada verdiği sayı
        home_defense = home_stats["homeConceded"]

        expected_home = (
            (home_attack + away_defense) / 2
        ) + HOME_ADVANTAGE / 2

        expected_away = (
            (away_attack + home_defense) / 2
        ) - HOME_ADVANTAGE / 2

    expected_home = max(0, expected_home)
    expected_away = max(0, expected_away)

    return expected_home, expected_away


# ------------------------------------------------------------
# BAREM
# ------------------------------------------------------------

def calculate_line(home_stats, away_stats, expected_home, expected_away):

    if expected_home is None or expected_away is None:
        return None

    expected_total = expected_home + expected_away

    historical_totals = []

    if home_stats:
        historical_totals.append(home_stats["total"])

    if away_stats:
        historical_totals.append(away_stats["total"])

    if historical_totals:
        history_average = sum(historical_totals) / len(historical_totals)

        # Beklenen skor ile geçmiş ortalamayı dengeliyoruz.
        line = (
            expected_total * 0.65
            + history_average * 0.35
        )
    else:
        line = expected_total

    return round(line, 2)


# ------------------------------------------------------------
# 1X2
# ------------------------------------------------------------

def calculate_1x2(expected_home, expected_away):

    if expected_home is None or expected_away is None:
        return None

    difference = expected_home - expected_away
    distance = abs(difference)

    # Beraberlik ihtimali
    draw_probability = 30 - distance * 2.5
    draw_probability = max(
        10,
        min(30, draw_probability)
    )

    remaining = 100 - draw_probability

    home_share = 1 / (
        1 + math.exp(-difference / 3.5)
    )

    home_probability = remaining * home_share
    away_probability = remaining - home_probability

    probabilities = {
        "1": round(home_probability, 2),
        "X": round(draw_probability, 2),
        "2": round(away_probability, 2),
    }

    prediction = max(
        probabilities,
        key=probabilities.get
    )

    confidence = probabilities[prediction]

    return {
        "prediction": prediction,
        "confidence": round(confidence, 2),
        "homeWinProbability": probabilities["1"],
        "drawProbability": probabilities["X"],
        "awayWinProbability": probabilities["2"],
    }


# ------------------------------------------------------------
# ALT / ÜST
# ------------------------------------------------------------

def calculate_over_under(expected_total, line):

    if expected_total is None or line is None:
        return None, None

    difference = expected_total - line
    edge = abs(difference)

    if difference > 0:
        prediction = "Üst"
    else:
        prediction = "Alt"

    # Kenar büyüdükçe güven artar.
    confidence = 50 + min(25, edge * 3.0)

    return prediction, round(
        max(MIN_CONFIDENCE, min(MAX_CONFIDENCE, confidence)),
        2
    )


# ------------------------------------------------------------
# GERÇEK SONUÇ
# ------------------------------------------------------------

def calculate_actual(match):

    if not is_played(match):
        return None

    home = get_score(match, "home")
    away = get_score(match, "away")

    if home is None or away is None:
        return None

    return {
        "homeScore": home,
        "awayScore": away,
        "total": home + away,
        "result1X2": (
            "1"
            if home > away
            else "2"
            if away > home
            else "X"
        ),
    }


# ------------------------------------------------------------
# TAHMİN SONUCU
# ------------------------------------------------------------

def evaluate_main_prediction(prediction, line, actual_total):

    if prediction not in ("Alt", "Üst"):
        return None

    if line is None or actual_total is None:
        return None

    if actual_total == line:
        return "push"

    actual = "Üst" if actual_total > line else "Alt"

    return "success" if actual == prediction else "failed"


# ------------------------------------------------------------
# TÜM TAHMİNLER
# ------------------------------------------------------------

def build_predictions(data):

    matches = data.get("matches", [])

    if not isinstance(matches, list):
        matches = []

    predictions = []

    # Sadece gerçek maçları sıraya koy.
    matches_sorted = sorted(
        matches,
        key=lambda m: (
            get_match_datetime(m)
            or datetime.min.replace(tzinfo=timezone.utc)
        )
    )

    print()
    print("=" * 60)
    print("🎯 BASKETBOL TAHMİNLERİ")
    print("=" * 60)

    league_counter = {}

    for match in matches_sorted:

        home_team = get_team_name(match, "home")
        away_team = get_team_name(match, "away")

        if not home_team or not away_team:
            continue

        league = get_league(match)

        # ----------------------------------------------------
        # GEÇMİŞ
        # ----------------------------------------------------

        home_history = find_team_history(
            matches_sorted,
            home_team,
            match
        )

        away_history = find_team_history(
            matches_sorted,
            away_team,
            match
        )

        home_history = get_last_10(home_history)
        away_history = get_last_10(away_history)

        home_stats = calculate_team_stats(home_history)
        away_stats = calculate_team_stats(away_history)

        expected_home, expected_away = calculate_expected_score(
            home_stats,
            away_stats
        )

        expected_total = None

        if expected_home is not None and expected_away is not None:
            expected_total = expected_home + expected_away

        line = calculate_line(
            home_stats,
            away_stats,
            expected_home,
            expected_away
        )

        prediction, confidence = calculate_over_under(
            expected_total,
            line
        )

        result_1x2 = calculate_1x2(
            expected_home,
            expected_away
        )

        actual = calculate_actual(match)

        result = None
        success = None

        actual_result_1x2 = None
        success_1x2 = None

        if actual is not None:

            result = evaluate_main_prediction(
                prediction,
                line,
                actual["total"]
            )

            if result == "success":
                success = True
            elif result == "failed":
                success = False
            else:
                success = None

            actual_result_1x2 = actual["result1X2"]

            if result_1x2 is not None:
                success_1x2 = (
                    result_1x2["prediction"]
                    == actual_result_1x2
                )

        item = {
            "id": match.get("id"),

            "league": league,
            "season": match.get("season"),

            "date": match.get("date"),
            "utcDate": match.get("utcDate"),

            "homeTeam": (
                match.get("homeTeam")
                or match.get("home")
            ),

            "awayTeam": (
                match.get("awayTeam")
                or match.get("away")
            ),

            "homeScore": get_score(match, "home"),
            "awayScore": get_score(match, "away"),

            "played": is_played(match),

            # Ana tahmin
            "prediction": prediction,
            "line": line,
            "barem": line,

            "confidence": confidence,

            # Beklenen skor
            "expectedHome": (
                round(expected_home, 2)
                if expected_home is not None
                else None
            ),

            "expectedAway": (
                round(expected_away, 2)
                if expected_away is not None
                else None
            ),

            "expectedTotal": (
                round(expected_total, 2)
                if expected_total is not None
                else None
            ),

            # 1X2
            "prediction1X2": (
                result_1x2["prediction"]
                if result_1x2
                else None
            ),

            "confidence1X2": (
                result_1x2["confidence"]
                if result_1x2
                else None
            ),

            "homeWinProbability": (
                result_1x2["homeWinProbability"]
                if result_1x2
                else None
            ),

            "drawProbability": (
                result_1x2["drawProbability"]
                if result_1x2
                else None
            ),

            "awayWinProbability": (
                result_1x2["awayWinProbability"]
                if result_1x2
                else None
            ),

            # Sonuçlar
            "actualTotal": (
                actual["total"]
                if actual
                else None
            ),

            "actualResult1X2": actual_result_1x2,

            "result1X2": (
                actual_result_1x2
                if actual
                else None
            ),

            "success1X2": success_1x2,

            "result": result,
            "success": success,

            # Örneklem
            "homeSample": (
                len(home_history)
            ),

            "awaySample": (
                len(away_history)
            ),
        }

        predictions.append(item)

        league_counter[league] = (
            league_counter.get(league, 0) + 1
        )

    return predictions, league_counter


# ------------------------------------------------------------
# ÖZET
# ------------------------------------------------------------

def calculate_summary(predictions):

    main_success = 0
    main_failed = 0
    main_push = 0

    main_unplayed = 0

    x2_success = 0
    x2_failed = 0

    for item in predictions:

        result = item.get("result")

        if result == "success":
            main_success += 1

        elif result == "failed":
            main_failed += 1

        elif result == "push":
            main_push += 1

        else:
            main_unplayed += 1

        x2 = item.get("success1X2")

        if x2 is True:
            x2_success += 1

        elif x2 is False:
            x2_failed += 1

    decided_main = main_success + main_failed

    main_rate = (
        main_success / decided_main * 100
        if decided_main > 0
        else 0
    )

    decided_x2 = x2_success + x2_failed

    x2_rate = (
        x2_success / decided_x2 * 100
        if decided_x2 > 0
        else 0
    )

    return {
        "mainMarket": "Maç Toplam Alt/Üst",

        "totalPredictions": len(predictions),

        "completedPredictions": decided_main,

        "success": main_success,

        "failed": main_failed,

        "push": main_push,

        "unplayed": main_unplayed,

        "successRate": round(main_rate, 2),

        "1X2": {
            "completed": decided_x2,
            "success": x2_success,
            "failed": x2_failed,
            "successRate": round(x2_rate, 2),
        },

        "note": (
            "Ana başarı oranı yalnızca Maç Toplam Alt/Üst "
            "tahminlerini içerir. 1/X/2 başarı oranı ayrı hesaplanır."
        ),
    }


# ------------------------------------------------------------
# ANA
# ------------------------------------------------------------

def main():

    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"basketball.json bulunamadı: {INPUT_FILE}"
        )

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)

    print(
        f"📂 Veri: {INPUT_FILE}"
    )

    predictions, league_counter = build_predictions(data)

    summary = calculate_summary(predictions)

    output = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),

        "settings": {
            "maxHistory": MAX_HISTORY,
            "newestWeight": NEWEST_WEIGHT,
            "oldestWeight": OLDEST_WEIGHT,
            "homeAdvantage": HOME_ADVANTAGE,
            "mainMarket": "Maç Toplam Alt/Üst",
            "secondaryMarket": "1/X/2",
        },

        "summary": summary,

        "leagues": league_counter,

        "predictions": predictions,
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
            indent=2
        )

    print()
    print("=" * 60)
    print("📊 TAHMİN ÖZETİ")
    print("=" * 60)

    print(
        f"🎯 Toplam tahmin: "
        f"{summary['totalPredictions']}"
    )

    print(
        f"🏁 Tamamlanan ana tahmin: "
        f"{summary['completedPredictions']}"
    )

    print(
        f"✅ Başarılı: "
        f"{summary['success']}"
    )

    print(
        f"❌ Başarısız: "
        f"{summary['failed']}"
    )

    print(
        f"🟡 Push: "
        f"{summary['push']}"
    )

    print(
        f"⏳ Oynanmamış: "
        f"{summary['unplayed']}"
    )

    print(
        f"📈 Ana başarı oranı: "
        f"%{summary['successRate']}"
    )

    print()
    print("1/X/2:")
    print(
        f"   Tamamlanan: "
        f"{summary['1X2']['completed']}"
    )
    print(
        f"   Başarılı: "
        f"{summary['1X2']['success']}"
    )
    print(
        f"   Başarısız: "
        f"{summary['1X2']['failed']}"
    )
    print(
        f"   Başarı oranı: "
        f"%{summary['1X2']['successRate']}"
    )

    print()
    print("🏆 LİGLER")

    for league, count in sorted(
        league_counter.items()
    ):
        print(
            f"   • {league}: {count} tahmin"
        )

    print()
    print(
        f"💾 Kaydedildi: {OUTPUT_FILE}"
    )

    # --------------------------------------------------------
    # ÖRNEKLEM KONTROLÜ
    # --------------------------------------------------------

    sample_counts = {}

    for item in predictions:

        key = (
            item.get("league"),
            item.get("homeSample"),
            item.get("awaySample"),
        )

        sample_counts[key] = (
            sample_counts.get(key, 0) + 1
        )

    print()
    print("📚 ÖRNEKLEM KONTROLÜ")

    # En çok tekrar eden birkaç örneklem
    top_samples = sorted(
        sample_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]

    for (
        (league, home_sample, away_sample),
        count
    ) in top_samples:

        print(
            f"   {league}: "
            f"{home_sample}/{away_sample} "
            f"→ {count} maç"
        )

    print()
    print("=" * 60)
    print("✅ TAHMİNLER TAMAMLANDI")
    print("=" * 60)


if __name__ == "__main__":
    main()
