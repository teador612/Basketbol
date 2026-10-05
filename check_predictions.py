import json
from pathlib import Path
from datetime import datetime

PREDICTIONS_FILE = Path("predictions.json")
HISTORY_FILE = Path("history.json")
OUTPUT_FILE = Path("predictions.json")


# =========================================================
# DOSYA OKU
# =========================================================

def load_json(path):

    if not path.exists():
        print(f"❌ Dosya bulunamadı: {path}")
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================================================
# TAKIM ADI NORMALİZASYONU
# =========================================================

def normalize(name):

    if not name:
        return ""

    name = name.lower().strip()

    replacements = {
        "fenerbahce": "fenerbahçe beko",
        "fenerbahçe": "fenerbahçe beko",
        "fenerbahçe tarfin": "fenerbahçe beko",

        "barcelona": "fc barcelona",

        "valencia": "valencia basket",

        "asvel": "ldlc asvel",
        "asvel lyon-villeurbanne": "ldlc asvel",

        "bayern munich": "bayern münih",
        "bayern münchen": "bayern münih",

        "besiktas": "beşiktaş",

        "zalgiris": "zalgiris kaunas",

        "olympiacos": "olympiakos",

        "crvena zvezda": "kızılyıldız",

        "dubai": "dubai basketball",

        "hapoel tel aviv": "hapoel ibi tel aviv",
    }

    return replacements.get(name, name)


# =========================================================
# SONUCU HESAPLA
# =========================================================

def get_match_result(match):

    home_score = match.get("homeScore")
    away_score = match.get("awayScore")

    if home_score is None or away_score is None:
        return None

    try:
        home_score = int(home_score)
        away_score = int(away_score)
    except:
        return None

    if home_score > away_score:
        return "1"

    if away_score > home_score:
        return "2"

    # Basketbolda normal maç için beraberlik yok.
    # Uzatma dahil nihai skor kullanılır.
    return None


# =========================================================
# GEÇMİŞTEKİ MAÇI BUL
# =========================================================

def find_result(history, prediction):

    prediction_date = prediction.get("date")
    prediction_home = normalize(
        prediction.get("home")
    )
    prediction_away = normalize(
        prediction.get("away")
    )

    for match in history:

        if match.get("date") != prediction_date:
            continue

        home = normalize(
            match.get("home")
        )

        away = normalize(
            match.get("away")
        )

        if home != prediction_home:
            continue

        if away != prediction_away:
            continue

        result = get_match_result(match)

        if result is None:
            return None, None

        return result, match

    return None, None


# =========================================================
# ANA
# =========================================================

def main():

    print("=" * 70)
    print("🏀 EUROLEAGUE ANA TAHMİN SONUÇ KONTROLÜ")
    print("=" * 70)

    predictions_data = load_json(
        PREDICTIONS_FILE
    )

    history_data = load_json(
        HISTORY_FILE
    )

    if not predictions_data:
        return

    if not history_data:
        return

    predictions = predictions_data.get(
        "predictions",
        []
    )

    history = history_data.get(
        "matches",
        []
    )

    print(
        f"\n🎯 Ana tahmin sayısı: {len(predictions)}"
    )

    completed = 0
    correct = 0
    wrong = 0

    for prediction in predictions:

        predicted = prediction.get(
            "prediction"
        )

        # Tahmin yoksa başarı hesabına girmez
        if predicted not in ("1", "2"):
            prediction["result"] = None
            prediction["correct"] = None
            continue

        result, match = find_result(
            history,
            prediction
        )

        # Maç henüz oynanmadı
        if result is None:

            prediction["result"] = None
            prediction["correct"] = None

            continue

        completed += 1

        prediction["result"] = result

        if predicted == result:

            prediction["correct"] = True

            correct += 1

        else:

            prediction["correct"] = False

            wrong += 1

    # =====================================================
    # SADECE ANA TAHMİNLER
    # =====================================================

    if completed > 0:

        success_rate = round(
            (correct / completed) * 100,
            2
        )

    else:

        success_rate = None

    # =====================================================
    # İSTATİSTİK
    # =====================================================

    statistics = {
        "totalPredictions": len(predictions),

        "completedPredictions": completed,

        "correct": correct,

        "wrong": wrong,

        "successRate": success_rate,

        "calculation": "Sadece ana tahminler (1/2)"
    }

    # =====================================================
    # VERİYİ GÜNCELLE
    # =====================================================

    predictions_data["updatedAt"] = (
        datetime.utcnow().isoformat() + "Z"
    )

    predictions_data["statistics"] = statistics

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            predictions_data,
            f,
            ensure_ascii=False,
            indent=2
        )

    # =====================================================
    # EKRAN
    # =====================================================

    print("\n" + "=" * 70)

    print("📊 ANA TAHMİN İSTATİSTİĞİ")

    print("=" * 70)

    print(
        f"🎯 Toplam tahmin: {len(predictions)}"
    )

    print(
        f"🏁 Oynanan: {completed}"
    )

    print(
        f"✅ Başarılı: {correct}"
    )

    print(
        f"❌ Başarısız: {wrong}"
    )

    if success_rate is not None:

        print(
            f"📈 BAŞARI ORANI: %{success_rate}"
        )

    else:

        print(
            "📈 BAŞARI ORANI: Henüz sonuç yok"
        )

    # =====================================================
    # MAÇLAR
    # =====================================================

    print("\n" + "=" * 70)

    print("📋 MAÇ SONUÇLARI")

    print("=" * 70)

    for prediction in predictions:

        predicted = prediction.get(
            "prediction"
        )

        if predicted not in ("1", "2"):
            continue

        home = prediction.get(
            "home"
        )

        away = prediction.get(
            "away"
        )

        result = prediction.get(
            "result"
        )

        correct_status = prediction.get(
            "correct"
        )

        print(
            f"\n{home} - {away}"
        )

        print(
            f"   🎯 Ana tahmin: {predicted}"
        )

        if result is None:

            print(
                "   ⏳ Maç henüz oynanmadı"
            )

        elif correct_status is True:

            print(
                f"   🏁 Sonuç: {result}"
            )

            print(
                "   ✅ BAŞARILI"
            )

        else:

            print(
                f"   🏁 Sonuç: {result}"
            )

            print(
                "   ❌ BAŞARISIZ"
            )

    print("\n" + "=" * 70)

    print("💾 predictions.json güncellendi")
    print("=" * 70)


if __name__ == "__main__":
    main()
