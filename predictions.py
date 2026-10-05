import json
from pathlib import Path
from datetime import datetime

DATA_FILE = Path("data.json")
HISTORY_FILE = Path("history.json")
PREDICTIONS_FILE = Path("predictions.json")

LAST_N = 5


# =========================================================
# YARDIMCI
# =========================================================

def normalize(name):
    if not name:
        return ""

    name = name.lower().strip()

    replacements = {
        "fenerbahce": "fenerbahçe",
        "fenerbahçe tarfin": "fenerbahçe beko",
        "fenerbahce tarfin": "fenerbahçe beko",
        "fenerbahçe": "fenerbahçe beko",

        "barcelona": "fc barcelona",

        "valencia": "valencia basket",

        "baskonia vitoria-gasteiz": "baskonia",

        "lyon-villeurbanne": "ldlc asvel",
        "asvel": "ldlc asvel",

        "crvena zvezda": "kızılyıldız",
        "cr. zvezda": "kızılyıldız",

        "bayern munich": "bayern münih",
        "bayern münchen": "bayern münih",

        "besiktas": "beşiktaş",

        "zal": "zalgiris kaunas",
        "zalgiris": "zalgiris kaunas",

        "olympiacos": "olympiakos",

        "real madrid": "real madrid",

        "partizan mozart bet": "partizan",
        "kk partizan": "partizan",

        "dubai": "dubai basketball",

        "maccabi rapyd tel aviv": "maccabi tel aviv",

        "panathinaikos aktor": "panathinaikos",

        "hapoel tel aviv": "hapoel ibi tel aviv",
    }

    return replacements.get(name, name)


# =========================================================
# DOSYALARI OKU
# =========================================================

def load_json(path):
    if not path.exists():
        print(f"❌ {path} bulunamadı")
        return None

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================================================
# TAKIMIN SON 5 İÇ SAHA MAÇI
# =========================================================

def get_home_last5(history, team):

    team = normalize(team)

    matches = []

    for match in history:

        if normalize(match.get("home")) != team:
            continue

        home_score = match.get("homeScore")
        away_score = match.get("awayScore")

        if home_score is None or away_score is None:
            continue

        matches.append({
            "date": match.get("date"),
            "opponent": match.get("away"),
            "scored": home_score,
            "conceded": away_score
        })

    matches.sort(
        key=lambda x: x["date"] or "",
        reverse=True
    )

    return matches[:LAST_N]


# =========================================================
# TAKIMIN SON 5 DEPLASMAN MAÇI
# =========================================================

def get_away_last5(history, team):

    team = normalize(team)

    matches = []

    for match in history:

        if normalize(match.get("away")) != team:
            continue

        home_score = match.get("homeScore")
        away_score = match.get("awayScore")

        if home_score is None or away_score is None:
            continue

        matches.append({
            "date": match.get("date"),
            "opponent": match.get("home"),
            "scored": away_score,
            "conceded": home_score
        })

    matches.sort(
        key=lambda x: x["date"] or "",
        reverse=True
    )

    return matches[:LAST_N]


# =========================================================
# ORTALAMA
# =========================================================

def averages(matches):

    if not matches:
        return {
            "sample": 0,
            "scored": None,
            "conceded": None
        }

    scored = sum(
        x["scored"]
        for x in matches
    )

    conceded = sum(
        x["conceded"]
        for x in matches
    )

    count = len(matches)

    return {
        "sample": count,
        "scored": round(scored / count, 2),
        "conceded": round(conceded / count, 2)
    }


# =========================================================
# BEKLENEN SAYI
# =========================================================

def calculate_expected(home_avg, away_avg):

    if (
        home_avg["scored"] is None
        or home_avg["conceded"] is None
        or away_avg["scored"] is None
        or away_avg["conceded"] is None
    ):
        return None, None

    expected_home = (
        home_avg["scored"]
        +
        away_avg["conceded"]
    ) / 2

    expected_away = (
        away_avg["scored"]
        +
        home_avg["conceded"]
    ) / 2

    return (
        round(expected_home, 2),
        round(expected_away, 2)
    )


# =========================================================
# ANA TAHMİN
# =========================================================

def calculate_prediction(expected_home, expected_away):

    if expected_home is None or expected_away is None:
        return None, None

    difference = abs(
        expected_home - expected_away
    )

    # Kazanan taraf
    if expected_home > expected_away:
        prediction = "1"
    elif expected_away > expected_home:
        prediction = "2"
    else:
        prediction = None

    # Basit güven yüzdesi
    #
    # Fark arttıkça güven artar.
    # 10 sayı veya üzeri fark %90'a yaklaşır.
    #
    confidence = 50 + (difference * 4)

    confidence = min(
        95,
        max(50, confidence)
    )

    confidence = round(
        confidence,
        1
    )

    return prediction, confidence


# =========================================================
# ANA
# =========================================================

def main():

    print("=" * 65)
    print("🏀 EUROLEAGUE TAHMİN MOTORU")
    print("=" * 65)

    data = load_json(DATA_FILE)
    history_data = load_json(HISTORY_FILE)

    if not data or not history_data:
        return

    fixtures = data.get("matches", [])
    history = history_data.get("matches", [])

    print(f"\n📅 Gelecek/güncel maç: {len(fixtures)}")
    print(f"📚 Geçmiş maç: {len(history)}")

    predictions = []

    for match in fixtures:

        home = match.get("home")
        away = match.get("away")

        if not home or not away:
            continue

        home_last5 = get_home_last5(
            history,
            home
        )

        away_last5 = get_away_last5(
            history,
            away
        )

        home_avg = averages(
            home_last5
        )

        away_avg = averages(
            away_last5
        )

        expected_home, expected_away = calculate_expected(
            home_avg,
            away_avg
        )

        prediction, confidence = calculate_prediction(
            expected_home,
            expected_away
        )

        record = {
            "id": match.get("id"),

            "date": match.get("date"),
            "time": match.get("time"),

            "home": home,
            "away": away,

            "home_last5_home": home_last5,
            "away_last5_away": away_last5,

            "home_average": home_avg,
            "away_average": away_avg,

            "expected_score": {
                "home": expected_home,
                "away": expected_away
            },

            "prediction": prediction,
            "confidence": confidence,

            "result": None,
            "correct": None
        }

        predictions.append(record)

        # -------------------------------------------------
        # EKRANA YAZ
        # -------------------------------------------------

        print("\n" + "-" * 65)

        print(
            f"🏀 {home} - {away}"
        )

        print(
            f"\n🏠 {home} SON 5 İÇ SAHA"
        )

        for game in home_last5:
            print(
                f"   {game['date']} | "
                f"{game['scored']}-{game['conceded']} | "
                f"{game['opponent']}"
            )

        print(
            f"   Attı: {home_avg['scored']}"
        )

        print(
            f"   Yedi: {home_avg['conceded']}"
        )

        print(
            f"\n✈️ {away} SON 5 DEPLASMAN"
        )

        for game in away_last5:
            print(
                f"   {game['date']} | "
                f"{game['scored']}-{game['conceded']} | "
                f"{game['opponent']}"
            )

        print(
            f"   Attı: {away_avg['scored']}"
        )

        print(
            f"   Yedi: {away_avg['conceded']}"
        )

        print(
            f"\n📊 Beklenen sayı:"
        )

        print(
            f"   {home}: {expected_home}"
        )

        print(
            f"   {away}: {expected_away}"
        )

        if prediction:

            print(
                f"\n🎯 ANA TAHMİN: {prediction}"
            )

            print(
                f"📈 Güven: %{confidence}"
            )

        else:

            print(
                "\n⚠️ Tahmin üretilemedi"
            )

    # =====================================================
    # KAYDET
    # =====================================================

    output = {
        "source": "history.json",
        "updatedAt": datetime.utcnow().isoformat() + "Z",
        "method": {
            "homeSample": "Son 5 iç saha",
            "awaySample": "Son 5 deplasman",

            "expectedHome":
                "(Ev iç saha attığı + Deplasman deplasman yediği) / 2",

            "expectedAway":
                "(Deplasman deplasman attığı + Ev iç saha yediği) / 2",

            "prediction":
                "Beklenen sayı yüksek olan takım"
        },

        "predictions": predictions
    }

    with open(
        PREDICTIONS_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("\n" + "=" * 65)
    print("✅ TAHMİNLER OLUŞTURULDU")
    print("=" * 65)

    print(
        f"🎯 Toplam tahmin: {len(predictions)}"
    )

    print(
        f"💾 {PREDICTIONS_FILE}"
    )


if __name__ == "__main__":
    main()
