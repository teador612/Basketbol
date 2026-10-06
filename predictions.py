import json
from pathlib import Path
from datetime import datetime, timezone


# =========================================================
# DOSYALAR
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

DATA_FILE = BASE_DIR / "data" / "basketball.json"
PREDICTIONS_FILE = BASE_DIR / "predictions.json"

LAST_N = 5


# =========================================================
# JSON OKU
# =========================================================

def load_json(path):

    if not path.exists():
        print(f"❌ Dosya bulunamadı: {path}")
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print(f"❌ JSON okunamadı: {path}")
        print(e)
        return None


# =========================================================
# SON 5 VERİSİNİ AL
# =========================================================

def get_last5(match, key):

    games = match.get(key) or []

    valid = []

    for game in games:

        scored = game.get("scored")
        conceded = game.get("conceded")

        if scored is None or conceded is None:
            continue

        try:
            scored = float(scored)
            conceded = float(conceded)
        except (TypeError, ValueError):
            continue

        valid.append({
            "date": game.get("date"),
            "opponent": game.get("opponent"),
            "scored": scored,
            "conceded": conceded
        })

    valid.sort(
        key=lambda x: x.get("date") or "",
        reverse=True
    )

    return valid[:LAST_N]


# =========================================================
# ORTALAMA
# =========================================================

def averages(games):

    if not games:
        return {
            "sample": 0,
            "scored": None,
            "conceded": None
        }

    scored = sum(
        game["scored"]
        for game in games
    )

    conceded = sum(
        game["conceded"]
        for game in games
    )

    count = len(games)

    return {
        "sample": count,
        "scored": round(scored / count, 2),
        "conceded": round(conceded / count, 2)
    }


# =========================================================
# BEKLENEN SAYI
# =========================================================

def calculate_expected(home_avg, away_avg):

    if home_avg["sample"] == 0:
        return None, None

    if away_avg["sample"] == 0:
        return None, None

    if home_avg["scored"] is None:
        return None, None

    if home_avg["conceded"] is None:
        return None, None

    if away_avg["scored"] is None:
        return None, None

    if away_avg["conceded"] is None:
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

def calculate_prediction(
    expected_home,
    expected_away
):

    if expected_home is None:
        return None, None

    if expected_away is None:
        return None, None

    difference = abs(
        expected_home - expected_away
    )

    if expected_home > expected_away:
        prediction = "1"

    elif expected_away > expected_home:
        prediction = "2"

    else:
        prediction = None

    if prediction is None:
        return None, 50.0

    # Fark arttıkça güven artar.
    confidence = 50 + (
        difference * 4
    )

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
# MAÇ TARİHİ
# =========================================================

def parse_date(value):

    if not value:
        return None

    try:

        text = str(value).strip()

        if text.endswith("Z"):
            text = (
                text[:-1]
                + "+00:00"
            )

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )
        else:
            dt = dt.astimezone(
                timezone.utc
            )

        return dt

    except Exception:
        return None


# =========================================================
# GELECEK MAÇ FİLTRESİ
# =========================================================

def is_upcoming(match):

    if match.get("played"):
        return False

    match_date = parse_date(
        match.get("date")
    )

    if match_date is None:
        return True

    return match_date >= datetime.now(
        timezone.utc
    )


# =========================================================
# ANA
# =========================================================

def main():

    print("=" * 70)
    print("🏀 NBA + EUROLEAGUE TAHMİN MOTORU")
    print("=" * 70)

    data = load_json(
        DATA_FILE
    )

    if not data:
        return

    matches = data.get(
        "matches",
        []
    )

    print()
    print(
        f"📦 Toplam veri: {len(matches)}"
    )

    # -----------------------------------------------------
    # SADECE OYNANMAMIŞ MAÇLAR
    # -----------------------------------------------------

    fixtures = [
        match
        for match in matches
        if is_upcoming(match)
    ]

    fixtures.sort(
        key=lambda match:
        parse_date(
            match.get("date")
        ) or datetime.max.replace(
            tzinfo=timezone.utc
        )
    )

    print(
        f"📅 Güncel/gelecek maç: "
        f"{len(fixtures)}"
    )

    predictions = []

    # =====================================================
    # MAÇLAR
    # =====================================================

    for match in fixtures:

        home = match.get(
            "homeTeam"
        )

        away = match.get(
            "awayTeam"
        )

        if not home or not away:
            continue

        # -------------------------------------------------
        # SON 5
        # -------------------------------------------------

        home_last5 = get_last5(
            match,
            "homeLast5"
        )

        away_last5 = get_last5(
            match,
            "awayLast5"
        )

        # -------------------------------------------------
        # ORTALAMA
        # -------------------------------------------------

        home_avg = averages(
            home_last5
        )

        away_avg = averages(
            away_last5
        )

        # -------------------------------------------------
        # BEKLENEN SKOR
        # -------------------------------------------------

        expected_home, expected_away = (
            calculate_expected(
                home_avg,
                away_avg
            )
        )

        # -------------------------------------------------
        # TAHMİN
        # -------------------------------------------------

        prediction, confidence = (
            calculate_prediction(
                expected_home,
                expected_away
            )
        )

        # -------------------------------------------------
        # KAYIT
        # -------------------------------------------------

        record = {

            "id": match.get("id"),

            "league": match.get(
                "league"
            ),

            "date": match.get(
                "date"
            ),

            "home": home,

            "away": away,

            "homeLast5": home_last5,

            "awayLast5": away_last5,

            "homeAverage": home_avg,

            "awayAverage": away_avg,

            "expectedScore": {
                "home": expected_home,
                "away": expected_away
            },

            "prediction": prediction,

            "confidence": confidence,

            "result": None,

            "correct": None
        }

        predictions.append(
            record
        )

        # =================================================
        # EKRAN
        # =================================================

        print()
        print("-" * 70)

        print(
            f"🏀 {home} - {away}"
        )

        print(
            f"📅 {match.get('date')}"
        )

        print()
        print(
            f"🏠 {home} SON 5 İÇ SAHA "
            f"({home_avg['sample']}/5)"
        )

        for game in home_last5:

            print(
                f"   {game.get('date')} | "
                f"{game.get('scored')}-"
                f"{game.get('conceded')} | "
                f"{game.get('opponent')}"
            )

        print(
            f"   Attı : {home_avg['scored']}"
        )

        print(
            f"   Yedi : {home_avg['conceded']}"
        )

        print()

        print(
            f"✈️ {away} SON 5 DEPLASMAN "
            f"({away_avg['sample']}/5)"
        )

        for game in away_last5:

            print(
                f"   {game.get('date')} | "
                f"{game.get('scored')}-"
                f"{game.get('conceded')} | "
                f"{game.get('opponent')}"
            )

        print(
            f"   Attı : {away_avg['scored']}"
        )

        print(
            f"   Yedi : {away_avg['conceded']}"
        )

        print()

        print("📊 BEKLENEN SAYI")

        print(
            f"   {home}: "
            f"{expected_home}"
        )

        print(
            f"   {away}: "
            f"{expected_away}"
        )

        if prediction:

            print()

            print(
                f"🎯 ANA TAHMİN: "
                f"{prediction}"
            )

            print(
                f"📈 GÜVEN: "
                f"%{confidence}"
            )

        else:

            print()
            print(
                "⚠️ Tahmin üretilemedi"
            )

    # =====================================================
    # JSON
    # =====================================================

    output = {

        "source":
            "data/basketball.json",

        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "method": {

            "homeSample":
                "basketball.json homeLast5",

            "awaySample":
                "basketball.json awayLast5",

            "expectedHome":
                "(Ev iç saha attığı + "
                "Deplasman deplasman yediği) / 2",

            "expectedAway":
                "(Deplasman deplasman attığı + "
                "Ev iç saha yediği) / 2",

            "prediction":
                "Beklenen sayı yüksek olan takım",

            "confidence":
                "50 + fark x 4, maksimum %95"
        },

        "total":
            len(predictions),

        "predictions":
            predictions
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

    # =====================================================
    # SONUÇ
    # =====================================================

    print()
    print("=" * 70)
    print("✅ TAHMİNLER OLUŞTURULDU")
    print("=" * 70)

    print(
        f"🎯 Toplam tahmin: "
        f"{len(predictions)}"
    )

    print(
        f"💾 Dosya: "
        f"{PREDICTIONS_FILE}"
    )


if __name__ == "__main__":
    main()
