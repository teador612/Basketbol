import json
import math
from pathlib import Path
from datetime import datetime, timezone


# ============================================================
# DOSYALAR
# ============================================================

DATA_FILE = Path("data.json")
HISTORY_FILE = Path("history.json")
PREDICTIONS_FILE = Path("predictions.json")


# ============================================================
# ANA AYARLAR
# ============================================================

LAST_N = 10

# En yeni maça verilen ağırlık.
# 1.00 = en yeni
# 0.55 = en eski
NEWEST_WEIGHT = 1.00
OLDEST_WEIGHT = 0.55

# Ev sahibi avantajı.
HOME_ADVANTAGE = 2.0

# Güven hesabı sınırları.
MIN_CONFIDENCE = 50.0
MAX_CONFIDENCE = 95.0

# Tahmin farkının güven üzerindeki etkisi.
EDGE_CONFIDENCE_FACTOR = 2.8

# Veri miktarının güvene etkisi.
SAMPLE_CONFIDENCE_MAX = 8.0

# İstikrarın güvene etkisi.
STABILITY_CONFIDENCE_MAX = 7.0


# ============================================================
# TAKIM İSİMLERİ
# ============================================================

def normalize(name):

    if not name:
        return ""

    name = str(name).lower().strip()

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

    return replacements.get(
        name,
        name
    )


# ============================================================
# JSON OKUMA
# ============================================================

def load_json(path):

    if not path.exists():
        print(f"❌ {path} bulunamadı.")
        return None

    try:

        with path.open(
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as error:

        print(
            f"❌ {path} okunamadı: {error}"
        )

        return None


# ============================================================
# SAYI
# ============================================================

def safe_float(value):

    try:

        if value is None:
            return None

        number = float(value)

        if not math.isfinite(number):
            return None

        return number

    except (
        TypeError,
        ValueError
    ):

        return None


# ============================================================
# TARİH
# ============================================================

def date_value(value):

    if not value:
        return ""

    return str(value)[:10]


# ============================================================
# SON 10 İÇ SAHA MAÇI
# ============================================================

def get_home_history(
    history,
    team
):

    team_normalized =
        normalize(team)

    matches = []

    for match in history:

        if not isinstance(
            match,
            dict
        ):
            continue

        home =
            normalize(
                match.get("home")
            )

        if home != team_normalized:
            continue

        home_score =
            safe_float(
                match.get("homeScore")
            )

        away_score =
            safe_float(
                match.get("awayScore")
            )

        if (
            home_score is None
            or away_score is None
        ):
            continue

        date =
            date_value(
                match.get("date")
            )

        matches.append(
            {
                "date": date,

                "opponent":
                    match.get(
                        "away"
                    ),

                "scored":
                    home_score,

                "conceded":
                    away_score,

                "total":
                    home_score +
                    away_score
            }
        )

    matches.sort(
        key=lambda x:
            x.get("date", ""),
        reverse=True
    )

    return matches[:LAST_N]


# ============================================================
# SON 10 DEPLASMAN MAÇI
# ============================================================

def get_away_history(
    history,
    team
):

    team_normalized =
        normalize(team)

    matches = []

    for match in history:

        if not isinstance(
            match,
            dict
        ):
            continue

        away =
            normalize(
                match.get("away")
            )

        if away != team_normalized:
            continue

        home_score =
            safe_float(
                match.get("homeScore")
            )

        away_score =
            safe_float(
                match.get("awayScore")
            )

        if (
            home_score is None
            or away_score is None
        ):
            continue

        date =
            date_value(
                match.get("date")
            )

        matches.append(
            {
                "date": date,

                "opponent":
                    match.get(
                        "home"
                    ),

                "scored":
                    away_score,

                "conceded":
                    home_score,

                "total":
                    home_score +
                    away_score
            }
        )

    matches.sort(
        key=lambda x:
            x.get("date", ""),
        reverse=True
    )

    return matches[:LAST_N]


# ============================================================
# AĞIRLIK
#
# Örnek:
#
# En yeni  : 1.00
# ...
# En eski  : 0.55
#
# Son maçlar daha etkili.
# ============================================================

def calculate_weights(count):

    if count <= 0:
        return []

    if count == 1:
        return [1.0]

    weights = []

    for index in range(count):

        position =
            index / (
                count - 1
            )

        weight =
            NEWEST_WEIGHT - (
                position *
                (
                    NEWEST_WEIGHT -
                    OLDEST_WEIGHT
                )
            )

        weights.append(
            weight
        )

    return weights


# ============================================================
# AĞIRLIKLI ORTALAMA
# ============================================================

def weighted_average(
    matches,
    field
):

    if not matches:
        return None

    weights =
        calculate_weights(
            len(matches)
        )

    numerator = 0.0
    denominator = 0.0

    for match, weight in zip(
        matches,
        weights
    ):

        value =
            safe_float(
                match.get(field)
            )

        if value is None:
            continue

        numerator += (
            value *
            weight
        )

        denominator += weight

    if denominator <= 0:
        return None

    return (
        numerator /
        denominator
    )


# ============================================================
# AĞIRLIKLI TOPLAM ORTALAMASI
# ============================================================

def weighted_total_average(
    matches
):

    if not matches:
        return None

    weights =
        calculate_weights(
            len(matches)
        )

    numerator = 0.0
    denominator = 0.0

    for match, weight in zip(
        matches,
        weights
    ):

        scored =
            safe_float(
                match.get("scored")
            )

        conceded =
            safe_float(
                match.get("conceded")
            )

        if (
            scored is None
            or conceded is None
        ):
            continue

        total =
            scored +
            conceded

        numerator += (
            total *
            weight
        )

        denominator += weight

    if denominator <= 0:
        return None

    return (
        numerator /
        denominator
    )


# ============================================================
# AĞIRLIKLI İSTİKRAR
#
# Maç toplamları birbirine yakınsa:
# daha stabil.
#
# Çok dağınıksa:
# daha düşük güven.
# ============================================================

def calculate_stability(
    matches
):

    if len(matches) < 2:
        return 0.50

    weights =
        calculate_weights(
            len(matches)
        )

    values = []

    for match in matches:

        scored =
            safe_float(
                match.get("scored")
            )

        conceded =
            safe_float(
                match.get("conceded")
            )

        if (
            scored is None
            or conceded is None
        ):
            continue

        values.append(
            scored +
            conceded
        )

    if len(values) < 2:
        return 0.50

    total_weight =
        sum(weights[:len(values)])

    if total_weight <= 0:
        return 0.50

    weighted_mean =
        sum(
            value * weight
            for value, weight
            in zip(
                values,
                weights
            )
        ) / total_weight

    variance =
        sum(
            weight *
            (
                value -
                weighted_mean
            ) ** 2

            for value, weight
            in zip(
                values,
                weights
            )
        ) / total_weight

    standard_deviation =
        math.sqrt(
            variance
        )

    # Basketbolda toplam sayı
    # dağılımının makul olduğu
    # seviyede normalize edilir.
    stability =
        1.0 - min(
            standard_deviation / 35.0,
            1.0
        )

    return max(
        0.0,
        min(
            1.0,
            stability
        )
    )


# ============================================================
# TAKIM PROFİLİ
# ============================================================

def team_profile(
    matches
):

    if not matches:

        return {
            "sample": 0,
            "scored": None,
            "conceded": None,
            "total": None,
            "stability": 0.50
        }

    return {

        "sample":
            len(matches),

        "scored":
            weighted_average(
                matches,
                "scored"
            ),

        "conceded":
            weighted_average(
                matches,
                "conceded"
            ),

        "total":
            weighted_total_average(
                matches
            ),

        "stability":
            calculate_stability(
                matches
            )
    }


# ============================================================
# BEKLENEN TAKIM SAYILARI
#
# Ev:
#   ev takımının hücumu
#   +
#   deplasman takımının savunması
#
# Deplasman:
#   deplasman takımının hücumu
#   +
#   ev takımının savunması
#
# Ev avantajı ayrıca eklenir.
# ============================================================

def calculate_expected_score(
    home_profile,
    away_profile
):

    required = [
        home_profile.get("scored"),
        home_profile.get("conceded"),
        away_profile.get("scored"),
        away_profile.get("conceded")
    ]

    if any(
        value is None
        for value in required
    ):
        return None, None

    home_attack =
        home_profile["scored"]

    home_defense =
        home_profile["conceded"]

    away_attack =
        away_profile["scored"]

    away_defense =
        away_profile["conceded"]


    # Ev sahibinin beklenen sayısı.
    base_home =
        (
            home_attack +
            away_defense
        ) / 2.0


    # Deplasmanın beklenen sayısı.
    base_away =
        (
            away_attack +
            home_defense
        ) / 2.0


    # Ev avantajı.
    expected_home =
        base_home +
        HOME_ADVANTAGE


    expected_away =
        base_away


    return (
        round(
            expected_home,
            2
        ),

        round(
            expected_away,
            2
        )
    )


# ============================================================
# BAREM
#
# Artık:
#
#  - sadece toplam ortalamalarının ortalaması değil
#  - hücum + savunma profili
#  - son maç ağırlığı
#
# kullanılıyor.
# ============================================================

def calculate_line(
    home_profile,
    away_profile
):

    home_total =
        home_profile.get(
            "total"
        )

    away_total =
        away_profile.get(
            "total"
        )

    if (
        home_total is None
        or away_total is None
    ):
        return None

    # İki takımın kendi oyun temposunun
    # ağırlıklı birleşimi.
    raw_line =
        (
            home_total *
            0.52
        ) + (
            away_total *
            0.48
        )

    return round(
        raw_line,
        2
    )


# ============================================================
# GÜVEN
#
# Güven sadece farktan oluşmuyor.
#
# 1) Beklenen toplam - barem farkı
# 2) Örneklem büyüklüğü
# 3) Son maçların istikrarı
#
# birlikte kullanılıyor.
# ============================================================

def calculate_confidence(
    expected_total,
    line,
    home_profile,
    away_profile
):

    if (
        expected_total is None
        or line is None
    ):
        return None

    edge =
        abs(
            expected_total -
            line
        )

    # 0 fark = %50 taban.
    edge_score =
        edge *
        EDGE_CONFIDENCE_FACTOR


    # 10 maçın tamamı varsa maksimum
    # veri güveni.
    home_sample =
        home_profile.get(
            "sample",
            0
        )

    away_sample =
        away_profile.get(
            "sample",
            0
        )

    sample_ratio =
        (
            min(
                home_sample,
                LAST_N
            ) +
            min(
                away_sample,
                LAST_N
            )
        ) / (
            LAST_N * 2
        )

    sample_score =
        sample_ratio *
        SAMPLE_CONFIDENCE_MAX


    home_stability =
        home_profile.get(
            "stability",
            0.50
        )

    away_stability =
        away_profile.get(
            "stability",
            0.50
        )

    stability =
        (
            home_stability +
            away_stability
        ) / 2.0

    stability_score =
        stability *
        STABILITY_CONFIDENCE_MAX


    confidence =
        MIN_CONFIDENCE + \
        edge_score + \
        sample_score + \
        stability_score


    confidence =
        max(
            MIN_CONFIDENCE,
            min(
                MAX_CONFIDENCE,
                confidence
            )
        )


    return round(
        confidence,
        1
    )


# ============================================================
# ANA ALT / ÜST TAHMİN
# ============================================================

def calculate_prediction(
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

    # Tam eşitlik çok nadir.
    # Sistem yine tahmin üretir.
    return "Üst"


# ============================================================
# ANA
# ============================================================

def main():

    print("=" * 70)
    print(
        "🏀 BASKETBOL MAÇ TOPLAM ALT / ÜST TAHMİN MOTORU"
    )
    print("=" * 70)

    data =
        load_json(
            DATA_FILE
        )

    history_data =
        load_json(
            HISTORY_FILE
        )


    if not data:
        print(
            "❌ data.json okunamadı."
        )
        return


    if not history_data:
        print(
            "❌ history.json okunamadı."
        )
        return


    fixtures =
        data.get(
            "matches",
            []
        )

    history =
        history_data.get(
            "matches",
            []
        )


    print()
    print(
        f"📅 Gelecek/güncel maç: {len(fixtures)}"
    )

    print(
        f"📚 Geçmiş maç kaydı: {len(history)}"
    )

    print(
        f"📊 Örneklem: Son {LAST_N} maç"
    )

    print(
        "⚖️ Ağırlık: Yeni maçlar daha yüksek"
    )

    print(
        f"🏠 Ev avantajı: +{HOME_ADVANTAGE}"
    )


    predictions = []


    for match in fixtures:

        if not isinstance(
            match,
            dict
        ):
            continue


        home =
            match.get(
                "home"
            )

        away =
            match.get(
                "away"
            )


        if not home or not away:
            continue


        # ----------------------------------------------------
        # SON 10
        # ----------------------------------------------------

        home_history =
            get_home_history(
                history,
                home
            )

        away_history =
            get_away_history(
                history,
                away
            )


        home_profile =
            team_profile(
                home_history
            )

        away_profile =
            team_profile(
                away_history
            )


        # ----------------------------------------------------
        # BEKLENEN SAYILAR
        # ----------------------------------------------------

        expected_home, expected_away =
            calculate_expected_score(
                home_profile,
                away_profile
            )


        if (
            expected_home is not None
            and expected_away is not None
        ):

            expected_total =
                (
                    expected_home +
                    expected_away
                )

            expected_total =
                round(
                    expected_total,
                    2
                )

        else:

            expected_total = None


        # ----------------------------------------------------
        # BAREM
        # ----------------------------------------------------

        line =
            calculate_line(
                home_profile,
                away_profile
            )


        # ----------------------------------------------------
        # ANA TAHMİN
        # ----------------------------------------------------

        prediction =
            calculate_prediction(
                expected_total,
                line
            )


        # ----------------------------------------------------
        # GÜVEN
        # ----------------------------------------------------

        confidence =
            calculate_confidence(
                expected_total,
                line,
                home_profile,
                away_profile
            )


        # ----------------------------------------------------
        # MAÇ SKORU
        # ----------------------------------------------------

        score =
            match.get(
                "score",
                {}
            )

        if not isinstance(
            score,
            dict
        ):
            score = {}


        home_score =
            safe_float(
                score.get(
                    "home"
                )
            )

        away_score =
            safe_float(
                score.get(
                    "away"
                )
            )


        played =
            (
                home_score is not None
                and
                away_score is not None
            )


        actual_total = None

        if played:

            actual_total =
                round(
                    home_score +
                    away_score,
                    2
                )


        # ----------------------------------------------------
        # KAYIT
        # ----------------------------------------------------

        record = {

            "id":
                match.get(
                    "id"
                ),

            "league":
                match.get(
                    "league",
                    data.get(
                        "league"
                    )
                ),

            "season":
                match.get(
                    "season"
                ),

            "date":
                match.get(
                    "date"
                ),

            "time":
                match.get(
                    "time"
                ),

            "utcDate":
                match.get(
                    "utcDate"
                ),

            "home":
                home,

            "away":
                away,


            "homeScore":
                home_score,

            "awayScore":
                away_score,

            "played":
                played,


            # ----------------------------------------------
            # SON 10
            # ----------------------------------------------

            "homeSample":
                home_profile[
                    "sample"
                ],

            "awaySample":
                away_profile[
                    "sample"
                ],


            "homeLast10":
                home_history,

            "awayLast10":
                away_history,


            # Eski UI uyumluluğu.
            "homeLast5":
                home_history[:5],

            "awayLast5":
                away_history[:5],


            # ----------------------------------------------
            # PROFİLLER
            # ----------------------------------------------

            "homeProfile": {
                "sample":
                    home_profile[
                        "sample"
                    ],

                "scored":
                    (
                        round(
                            home_profile[
                                "scored"
                            ],
                            2
                        )
                        if home_profile[
                            "scored"
                        ] is not None
                        else None
                    ),

                "conceded":
                    (
                        round(
                            home_profile[
                                "conceded"
                            ],
                            2
                        )
                        if home_profile[
                            "conceded"
                        ] is not None
                        else None
                    ),

                "total":
                    (
                        round(
                            home_profile[
                                "total"
                            ],
                            2
                        )
                        if home_profile[
                            "total"
                        ] is not None
                        else None
                    ),

                "stability":
                    round(
                        home_profile[
                            "stability"
                        ],
                        3
                    )
            },


            "awayProfile": {
                "sample":
                    away_profile[
                        "sample"
                    ],

                "scored":
                    (
                        round(
                            away_profile[
                                "scored"
                            ],
                            2
                        )
                        if away_profile[
                            "scored"
                        ] is not None
                        else None
                    ),

                "conceded":
                    (
                        round(
                            away_profile[
                                "conceded"
                            ],
                            2
                        )
                        if away_profile[
                            "conceded"
                        ] is not None
                        else None
                    ),

                "total":
                    (
                        round(
                            away_profile[
                                "total"
                            ],
                            2
                        )
                        if away_profile[
                            "total"
                        ] is not None
                        else None
                    ),

                "stability":
                    round(
                        away_profile[
                            "stability"
                        ],
                        3
                    )
            },


            # ----------------------------------------------
            # BEKLENEN
            # ----------------------------------------------

            "expectedHome":
                expected_home,

            "expectedAway":
                expected_away,

            "expectedTotal":
                expected_total,


            "expected_score": {
                "home":
                    expected_home,

                "away":
                    expected_away
            },


            # ----------------------------------------------
            # ANA BAREM
            # ----------------------------------------------

            "line":
                line,

            "barem":
                line,


            # ----------------------------------------------
            # ANA TAHMİN
            # ----------------------------------------------

            "prediction":
                prediction,

            "market":
                "Maç Toplam Alt/Üst",

            "confidence":
                confidence,


            # ----------------------------------------------
            # GERÇEK SONUÇ
            # ----------------------------------------------

            "actualTotal":
                actual_total,

            "result":
                None,

            "correct":
                None
        }


        predictions.append(
            record
        )


        # ====================================================
        # EKRAN
        # ====================================================

        print()
        print("-" * 70)

        print(
            f"🏀 {home} - {away}"
        )

        print(
            f"📅 {match.get('date', '-')}"
        )


        print(
            f"\n🏠 {home} | Son {LAST_N} iç saha"
        )

        print(
            f"   Örneklem: "
            f"{home_profile['sample']}"
        )

        print(
            f"   Attı: "
            f"{home_profile['scored']}"
        )

        print(
            f"   Yedi: "
            f"{home_profile['conceded']}"
        )

        print(
            f"   Toplam: "
            f"{home_profile['total']}"
        )


        print(
            f"\n✈️ {away} | Son {LAST_N} deplasman"
        )

        print(
            f"   Örneklem: "
            f"{away_profile['sample']}"
        )

        print(
            f"   Attı: "
            f"{away_profile['scored']}"
        )

        print(
            f"   Yedi: "
            f"{away_profile['conceded']}"
        )

        print(
            f"   Toplam: "
            f"{away_profile['total']}"
        )


        print(
            "\n📊 Beklenen skor:"
        )

        print(
            f"   {home}: "
            f"{expected_home}"
        )

        print(
            f"   {away}: "
            f"{expected_away}"
        )


        print(
            f"\n📏 BAREM: {line}"
        )

        print(
            f"🎯 ANA TAHMİN: "
            f"{prediction or '-'}"
        )

        print(
            f"📈 GÜVEN: "
            f"%{confidence if confidence is not None else '-'}"
        )


    # ========================================================
    # KAYDET
    # ========================================================

    output = {

        "source":
            "data.json + history.json",

        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "settings": {

            "mainMarket":
                "Maç Toplam Alt/Üst",

            "lastN":
                LAST_N,

            "homeSample":
                f"Son {LAST_N} iç saha",

            "awaySample":
                f"Son {LAST_N} deplasman",

            "weighting":
                "Yeni maçlar daha yüksek ağırlıklı",

            "newestWeight":
                NEWEST_WEIGHT,

            "oldestWeight":
                OLDEST_WEIGHT,

            "homeAdvantage":
                HOME_ADVANTAGE,

            "lineRounding":
                "Yok",

            "confidence":
                "Fark + örneklem + istikrar",

            "successRateOnlyMainPrediction":
                True,

            "excludedFromMainSuccessRate": [
                "1/X/2",
                "İY Alt/Üst",
                "Q1 Alt/Üst",
                "Q2 Alt/Üst",
                "Q3 Alt/Üst",
                "Q4 Alt/Üst"
            ]
        },

        "predictions":
            predictions
    }


    with PREDICTIONS_FILE.open(
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
    # ÖZET
    # ========================================================

    with_history =
        sum(
            1
            for p in predictions
            if (
                p["homeSample"] > 0
                and
                p["awaySample"] > 0
            )
        )

    full_sample =
        sum(
            1
            for p in predictions
            if (
                p["homeSample"] >= LAST_N
                and
                p["awaySample"] >= LAST_N
            )
        )


    print()
    print("=" * 70)
    print(
        "✅ YENİ MAÇ TOPLAM TAHMİNLERİ OLUŞTURULDU"
    )
    print("=" * 70)

    print(
        f"🎯 Toplam tahmin: "
        f"{len(predictions)}"
    )

    print(
        f"📚 Geçmişi bulunan: "
        f"{with_history}"
    )

    print(
        f"🔟 Tam 10+10 örneklem: "
        f"{full_sample}"
    )

    print(
        f"💾 {PREDICTIONS_FILE}"
    )

    print()
    print(
        "⚖️ Eski maçlar daha düşük ağırlıklı."
    )

    print(
        "🏠 Ev avantajı hesaba katıldı."
    )

    print(
        "📈 Güven artık sadece %50 değil."
    )

    print(
        "📏 Barem 5'in katına yuvarlanmıyor."
    )

    print(
        "🎯 Ana market: Maç Toplam Alt/Üst"
    )

    print("=" * 70)


# ============================================================
# ÇALIŞTIR
# ============================================================

if __name__ == "__main__":
    main()
