# ============================================================
# BASKETBOL TAHMİN SİSTEMİ
# NBA + EUROLEAGUE
#
# VERİ KAYNAĞI:
# basketball.json
#
# ÖZELLİKLER:
# - Veri çekme sistemine dokunmaz.
# - Sadece basketball.json okur.
# - Kullanıcının belirlediği baremleri analiz eder.
# - Her barem için ÜST / ALT yüzdesi üretir.
# - En güçlü baremi ana tahmin yapar.
# - Geçmiş verisi az olan maçları silmez.
# - Tahmin üretilemeyen maçlarda yine kayıt oluşturur.
# - MS handikap YOK.
# ============================================================

import json
import os
from datetime import datetime, timezone


INPUT_FILE = "basketball.json"
OUTPUT_FILE = "predictions.json"


# ============================================================
# BAREM AYARLARI
# ============================================================
#
# BURAYI SEN DEĞİŞTİREBİLİRSİN.
#
# Örnek:
#
# 210.5 - 219.5
# 220.5 - 229.5
#
# Sistem otomatik olarak:
#
# 210.5
# 211.5
# 212.5
# ...
# 219.5
#
# şeklinde baremleri oluşturur.
#
# ============================================================

BAREM_ARALIKLARI = [
    (180.5, 189.5),
    (190.5, 199.5),
    (200.5, 209.5),
    (210.5, 219.5),
    (220.5, 229.5),
    (230.5, 239.5),
    (240.5, 249.5),
]


# Bir barem için minimum geçmiş maç.
#
# Bu sayıdan az maç varsa barem yine gösterilir.
# Ancak güven seviyesi düşük kabul edilir.
MIN_SAMPLE = 5


# Ana tahmin için tercih edilen minimum güven.
MIN_CONFIDENCE = 70


# Takım başına kullanılacak son maç sayısı.
MAX_HISTORY = 10


# Yeni maçların ağırlığı.
NEWEST_WEIGHT = 1.00

# Eski maçların ağırlığı.
OLDEST_WEIGHT = 0.55


# Ev sahibi avantajı.
HOME_ADVANTAGE = 2.0


# ============================================================
# JSON OKU
# ============================================================

def load_json(path):

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} bulunamadı."
        )

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


# ============================================================
# SAYI
# ============================================================

def safe_float(value):

    try:

        if value is None:
            return None

        if isinstance(value, str):
            value = value.replace(",", ".").strip()

        return float(value)

    except Exception:

        return None


def safe_int(value):

    try:

        if value is None:
            return None

        return int(float(value))

    except Exception:

        return None


# ============================================================
# TAKIM NORMALİZASYONU
# ============================================================

def normalize_team(name):

    if not name:
        return ""

    text = str(name).lower().strip()

    replacements = {
        "ı": "i",
        "ş": "s",
        "ğ": "g",
        "ü": "u",
        "ö": "o",
        "ç": "c",
    }

    for old, new in replacements.items():

        text = text.replace(
            old,
            new
        )

    return " ".join(
        text.split()
    )


# ============================================================
# TARİH
# ============================================================

def date_value(match):

    value = (
        match.get("utcDate")
        or match.get("date")
        or ""
    )

    if not value:
        return 0

    try:

        text = str(value)

        if text.endswith("Z"):
            text = (
                text[:-1]
                + "+00:00"
            )

        return datetime.fromisoformat(
            text
        ).timestamp()

    except Exception:

        return 0


# ============================================================
# OYNANMIŞ MI?
# ============================================================

def is_played(match):

    if match.get("played") is True:
        return True

    home = safe_int(
        match.get("homeScore")
    )

    away = safe_int(
        match.get("awayScore")
    )

    return (
        home is not None
        and away is not None
    )


# ============================================================
# TOPLAM SAYI
# ============================================================

def total_score(match):

    home = safe_int(
        match.get("homeScore")
    )

    away = safe_int(
        match.get("awayScore")
    )

    if (
        home is None
        or away is None
    ):
        return None

    return home + away


# ============================================================
# 1X2
# ============================================================

def result_1x2(match):

    home = safe_int(
        match.get("homeScore")
    )

    away = safe_int(
        match.get("awayScore")
    )

    if (
        home is None
        or away is None
    ):
        return None

    if home > away:
        return "1"

    if home < away:
        return "2"

    return "X"


# ============================================================
# BAREMLERİ OLUŞTUR
# ============================================================

def generate_barems():

    barems = []

    for start, end in BAREM_ARALIKLARI:

        start = safe_float(start)
        end = safe_float(end)

        if (
            start is None
            or end is None
        ):
            continue

        if end < start:

            start, end = (
                end,
                start
            )

        current = start

        while current <= end + 0.001:

            value = round(
                current,
                1
            )

            if value not in barems:

                barems.append(
                    value
                )

            current += 1.0

    return sorted(
        barems
    )


BAREMS = generate_barems()


# ============================================================
# GEÇMİŞİ HAZIRLA
# ============================================================

def prepare_history(matches):

    history = []

    for match in matches:

        if not is_played(match):
            continue

        total = total_score(
            match
        )

        if total is None:
            continue

        home = normalize_team(
            match.get(
                "homeTeam"
            )
        )

        away = normalize_team(
            match.get(
                "awayTeam"
            )
        )

        if (
            not home
            or not away
        ):
            continue

        history.append({

            "id":
                match.get("id"),

            "homeTeam":
                home,

            "awayTeam":
                away,

            "homeScore":
                safe_int(
                    match.get(
                        "homeScore"
                    )
                ),

            "awayScore":
                safe_int(
                    match.get(
                        "awayScore"
                    )
                ),

            "total":
                total,

            "result":
                result_1x2(
                    match
                ),

            "date":
                date_value(
                    match
                ),

        })

    history.sort(
        key=lambda x: x["date"]
    )

    return history


# ============================================================
# TAKIM GEÇMİŞİ
# ============================================================

def get_team_history(
    team,
    history
):

    team = normalize_team(
        team
    )

    result = []

    for match in history:

        if match["homeTeam"] == team:

            result.append({

                **match,

                "teamHome":
                    True,

                "teamScore":
                    match["homeScore"],

                "opponentScore":
                    match["awayScore"],

            })

        elif match["awayTeam"] == team:

            result.append({

                **match,

                "teamHome":
                    False,

                "teamScore":
                    match["awayScore"],

                "opponentScore":
                    match["homeScore"],

            })

    result.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    return result[
        :MAX_HISTORY
    ]


# ============================================================
# AĞIRLIK
# ============================================================

def calculate_weight(
    index,
    total
):

    if total <= 1:
        return NEWEST_WEIGHT

    ratio = (
        index
        /
        (total - 1)
    )

    return (
        NEWEST_WEIGHT
        -
        (
            NEWEST_WEIGHT
            -
            OLDEST_WEIGHT
        )
        *
        ratio
    )


# ============================================================
# TAKIM İSTATİSTİKLERİ
# ============================================================

def team_statistics(
    team,
    history
):

    games = get_team_history(
        team,
        history
    )

    if not games:

        return {
            "sample": 0,
            "pointsFor": None,
            "pointsAgainst": None,
            "totalAverage": None,
            "weightedPointsFor": None,
            "weightedPointsAgainst": None,
            "weightedTotal": None,
        }

    total_weight = 0

    points_for = 0
    points_against = 0
    totals = 0

    weighted_points_for = 0
    weighted_points_against = 0
    weighted_total = 0

    valid_games = 0

    for index, game in enumerate(games):

        pf = game["teamScore"]
        pa = game["opponentScore"]

        if (
            pf is None
            or pa is None
        ):
            continue

        weight = calculate_weight(
            index,
            len(games)
        )

        game_total = (
            pf + pa
        )

        points_for += pf
        points_against += pa
        totals += game_total

        weighted_points_for += (
            pf * weight
        )

        weighted_points_against += (
            pa * weight
        )

        weighted_total += (
            game_total * weight
        )

        total_weight += weight

        valid_games += 1

    if (
        valid_games == 0
        or total_weight <= 0
    ):

        return {
            "sample": 0,
            "pointsFor": None,
            "pointsAgainst": None,
            "totalAverage": None,
            "weightedPointsFor": None,
            "weightedPointsAgainst": None,
            "weightedTotal": None,
        }

    return {

        "sample":
            valid_games,

        "pointsFor":
            points_for
            /
            valid_games,

        "pointsAgainst":
            points_against
            /
            valid_games,

        "totalAverage":
            totals
            /
            valid_games,

        "weightedPointsFor":
            weighted_points_for
            /
            total_weight,

        "weightedPointsAgainst":
            weighted_points_against
            /
            total_weight,

        "weightedTotal":
            weighted_total
            /
            total_weight,

    }


# ============================================================
# BEKLENEN SKOR
# ============================================================

def calculate_expected_scores(
    home_team,
    away_team,
    history
):

    home_stats = team_statistics(
        home_team,
        history
    )

    away_stats = team_statistics(
        away_team,
        history
    )

    home_sample = (
        home_stats["sample"]
    )

    away_sample = (
        away_stats["sample"]
    )

    # İki takımın da geçmişi yoksa
    # yine tahmin oluşturacağız.
    #
    # Ancak beklenen skor olmayacak.

    if (
        home_sample == 0
        and away_sample == 0
    ):

        return {

            "expectedHome":
                None,

            "expectedAway":
                None,

            "expectedTotal":
                None,

            "homeSample":
                0,

            "awaySample":
                0,

        }

    # Sadece ev takımında veri varsa
    if (
        home_sample > 0
        and away_sample == 0
    ):

        expected_home = (
            home_stats[
                "weightedPointsFor"
            ]
            +
            HOME_ADVANTAGE
        )

        expected_away = (
            home_stats[
                "weightedPointsAgainst"
            ]
        )

    # Sadece deplasmanda veri varsa
    elif (
        home_sample == 0
        and away_sample > 0
    ):

        expected_home = (
            away_stats[
                "weightedPointsAgainst"
            ]
            +
            HOME_ADVANTAGE
        )

        expected_away = (
            away_stats[
                "weightedPointsFor"
            ]
        )

    # İkisinde de veri varsa
    else:

        expected_home = (
            (
                home_stats[
                    "weightedPointsFor"
                ]
                +
                away_stats[
                    "weightedPointsAgainst"
                ]
            )
            /
            2
            +
            HOME_ADVANTAGE
        )

        expected_away = (
            (
                away_stats[
                    "weightedPointsFor"
                ]
                +
                home_stats[
                    "weightedPointsAgainst"
                ]
            )
            /
            2
        )

    expected_total = (
        expected_home
        +
        expected_away
    )

    return {

        "expectedHome":
            round(
                expected_home,
                2
            ),

        "expectedAway":
            round(
                expected_away,
                2
            ),

        "expectedTotal":
            round(
                expected_total,
                2
            ),

        "homeSample":
            home_sample,

        "awaySample":
            away_sample,

    }


# ============================================================
# BAREM ANALİZİ
# ============================================================

def analyze_barem(
    barem,
    home_team,
    away_team,
    history
):

    home_history = get_team_history(
        home_team,
        history
    )

    away_history = get_team_history(
        away_team,
        history
    )

    combined = []

    combined.extend(
        home_history
    )

    combined.extend(
        away_history
    )

    # Aynı maçı iki kere sayma.
    seen = set()

    relevant = []

    for game in combined:

        key = (
            game.get("id")
            or (
                game["date"],
                game["homeTeam"],
                game["awayTeam"]
            )
        )

        if key in seen:
            continue

        seen.add(key)

        if game["total"] is not None:

            relevant.append(
                game
            )

    relevant.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    # İki takımın toplam son 20 maçı.
    relevant = relevant[:20]

    sample = len(
        relevant
    )

    # Hiç geçmiş veri yoksa bile
    # baremi JSON'a koyuyoruz.
    if sample == 0:

        return {

            "barem":
                barem,

            "sample":
                0,

            "ust":
                None,

            "alt":
                None,

            "prediction":
                None,

            "confidence":
                None,

        }

    ust_weight = 0
    alt_weight = 0

    total_weight = 0

    ust_count = 0
    alt_count = 0

    for index, game in enumerate(
        relevant
    ):

        game_total = game["total"]

        weight = calculate_weight(
            index,
            len(relevant)
        )

        total_weight += weight

        if game_total > barem:

            ust_weight += weight

            ust_count += 1

        elif game_total < barem:

            alt_weight += weight

            alt_count += 1

        # Eşitlik push kabul edilir.
        # Üst veya Alt'a eklenmez.

    if total_weight <= 0:

        return {

            "barem":
                barem,

            "sample":
                sample,

            "ust":
                None,

            "alt":
                None,

            "prediction":
                None,

            "confidence":
                None,

        }

    ust_percent = (
        ust_weight
        /
        total_weight
        *
        100
    )

    alt_percent = (
        alt_weight
        /
        total_weight
        *
        100
    )

    # Eşit barem sonuçlarını hesaptan
    # çıkardığımız için yüzdelerin toplamı
    # 100 olmak zorunda değil.
    #
    # Daha anlaşılır olması için kalan
    # yüzdeleri yeniden normalize ediyoruz.

    combined_percent = (
        ust_percent
        +
        alt_percent
    )

    if combined_percent > 0:

        ust_percent = (
            ust_percent
            /
            combined_percent
            *
            100
        )

        alt_percent = (
            alt_percent
            /
            combined_percent
            *
            100
        )

    if ust_percent >= alt_percent:

        prediction = "ÜST"

        confidence = ust_percent

    else:

        prediction = "ALT"

        confidence = alt_percent

    return {

        "barem":
            barem,

        "sample":
            sample,

        "ust":
            round(
                ust_percent,
                2
            ),

        "alt":
            round(
                alt_percent,
                2
            ),

        "ustCount":
            ust_count,

        "altCount":
            alt_count,

        "prediction":
            prediction,

        "confidence":
            round(
                confidence,
                2
            ),

    }


# ============================================================
# TÜM BAREMLER
# ============================================================

def analyze_all_barems(
    home_team,
    away_team,
    history
):

    results = []

    for barem in BAREMS:

        result = analyze_barem(

            barem,

            home_team,

            away_team,

            history

        )

        results.append(
            result
        )

    return results


# ============================================================
# ANA TAHMİN SEÇİMİ
# ============================================================

def select_main_prediction(
    barem_results,
    expected_total=None
):

    valid = [

        item

        for item in barem_results

        if (
            item["prediction"]
            is not None
            and
            item["confidence"]
            is not None
        )

    ]

    if not valid:

        return None

    # Önce minimum güveni geçenler.
    strong = [

        item

        for item in valid

        if item["confidence"]
        >= MIN_CONFIDENCE

    ]

    candidates = (
        strong
        if strong
        else valid
    )

    # Beklenen toplam varsa
    # bareme yakınlığı ikinci kriter.
    if expected_total is not None:

        candidates.sort(

            key=lambda x: (

                -x["confidence"],

                abs(
                    x["barem"]
                    -
                    expected_total
                )

            )

        )

    else:

        candidates.sort(

            key=lambda x:
                -x["confidence"]

        )

    selected = candidates[0]

    return {

        "barem":
            selected["barem"],

        "prediction":
            selected["prediction"],

        "confidence":
            selected["confidence"],

        "ust":
            selected["ust"],

        "alt":
            selected["alt"],

        "sample":
            selected["sample"],

    }


# ============================================================
# 1X2
# ============================================================

def calculate_1x2(
    home_team,
    away_team,
    history
):

    home_games = get_team_history(
        home_team,
        history
    )

    away_games = get_team_history(
        away_team,
        history
    )

    home_weight = 0
    draw_weight = 0
    away_weight = 0

    # Ev takımının geçmişi
    for index, game in enumerate(
        home_games
    ):

        weight = calculate_weight(
            index,
            len(home_games)
        )

        if (
            game["teamScore"]
            >
            game["opponentScore"]
        ):

            home_weight += weight

        elif (
            game["teamScore"]
            ==
            game["opponentScore"]
        ):

            draw_weight += weight

        else:

            away_weight += weight

    # Deplasman takımının geçmişi
    for index, game in enumerate(
        away_games
    ):

        weight = calculate_weight(
            index,
            len(away_games)
        )

        if (
            game["teamScore"]
            >
            game["opponentScore"]
        ):

            away_weight += weight

        elif (
            game["teamScore"]
            ==
            game["opponentScore"]
        ):

            draw_weight += weight

        else:

            home_weight += weight

    total = (
        home_weight
        +
        draw_weight
        +
        away_weight
    )

    if total <= 0:

        return {

            "prediction":
                None,

            "confidence":
                None,

            "home":
                None,

            "draw":
                None,

            "away":
                None,

        }

    home_percent = (
        home_weight
        /
        total
        *
        100
    )

    draw_percent = (
        draw_weight
        /
        total
        *
        100
    )

    away_percent = (
        away_weight
        /
        total
        *
        100
    )

    values = {

        "1":
            home_percent,

        "X":
            draw_percent,

        "2":
            away_percent,

    }

    prediction = max(
        values,
        key=values.get
    )

    return {

        "prediction":
            prediction,

        "confidence":
            round(
                values[prediction],
                2
            ),

        "home":
            round(
                home_percent,
                2
            ),

        "draw":
            round(
                draw_percent,
                2
            ),

        "away":
            round(
                away_percent,
                2
            ),

    }


# ============================================================
# TEK MAÇ TAHMİNİ
# ============================================================

def predict_match(
    match,
    history
):

    home_team = match.get(
        "homeTeam"
    )

    away_team = match.get(
        "awayTeam"
    )

    if not home_team:
        home_team = "-"

    if not away_team:
        away_team = "-"

    normalized_home = normalize_team(
        home_team
    )

    normalized_away = normalize_team(
        away_team
    )

    expected = calculate_expected_scores(

        normalized_home,

        normalized_away,

        history

    )

    barem_results = analyze_all_barems(

        normalized_home,

        normalized_away,

        history

    )

    main = select_main_prediction(

        barem_results,

        expected[
            "expectedTotal"
        ]

    )

    x2 = calculate_1x2(

        normalized_home,

        normalized_away,

        history

    )

    # ========================================================
    # ÖNEMLİ:
    #
    # Artık main None olsa bile maçı silmiyoruz.
    # Böylece "Veri bulunamadı" problemi yaşanmaz.
    # ========================================================

    if main is None:

        main = {

            "barem":
                None,

            "prediction":
                None,

            "confidence":
                None,

            "ust":
                None,

            "alt":
                None,

            "sample":
                0,

        }

    return {

        "id":
            match.get("id"),

        "league":
            match.get("league"),

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

        # ====================================================
        # ANA TAHMİN
        # ====================================================

        "prediction":
            main["prediction"],

        "line":
            main["barem"],

        "barem":
            main["barem"],

        "confidence":
            main["confidence"],

        "ustPercent":
            main["ust"],

        "altPercent":
            main["alt"],

        # ====================================================
        # BÜTÜN BAREMLER
        # ====================================================

        "barems":
            barem_results,

        # ====================================================
        # MODEL BEKLENTİSİ
        # ====================================================

        "expectedHome":
            expected[
                "expectedHome"
            ],

        "expectedAway":
            expected[
                "expectedAway"
            ],

        "expectedTotal":
            expected[
                "expectedTotal"
            ],

        # ====================================================
        # ÖRNEKLEM
        # ====================================================

        "homeSample":
            expected[
                "homeSample"
            ],

        "awaySample":
            expected[
                "awaySample"
            ],

        # ====================================================
        # 1X2
        # ====================================================

        "prediction1X2":
            x2["prediction"],

        "confidence1X2":
            x2["confidence"],

        "homeWinProbability":
            x2["home"],

        "drawProbability":
            x2["draw"],

        "awayWinProbability":
            x2["away"],

        # ====================================================
        # MAÇ SONUCU
        # ====================================================

        "played":
            is_played(match),

        "homeScore":
            safe_int(
                match.get(
                    "homeScore"
                )
            ),

        "awayScore":
            safe_int(
                match.get(
                    "awayScore"
                )
            ),

    }


# ============================================================
# ANA
# ============================================================

def main():

    print()
    print("=" * 70)
    print("🏀 NBA + EUROLEAGUE BASKETBOL TAHMİN")
    print("=" * 70)

    print()

    print(
        "📁 Veri:",
        INPUT_FILE
    )

    print(
        "🎯 Barem sayısı:",
        len(BAREMS)
    )

    print(
        "📊 Baremler:",
        ", ".join(
            str(x)
            for x in BAREMS
        )
    )

    print(
        "📈 Minimum güven:",
        f"%{MIN_CONFIDENCE}"
    )

    print(
        "📚 Minimum örnek:",
        MIN_SAMPLE
    )

    print()

    data = load_json(
        INPUT_FILE
    )

    matches = data.get(
        "matches",
        []
    )

    if not isinstance(
        matches,
        list
    ):

        raise RuntimeError(
            "basketball.json içindeki matches bulunamadı."
        )

    print(
        "🏀 Toplam maç:",
        len(matches)
    )

    history = prepare_history(
        matches
    )

    print(
        "📚 Geçmiş maç:",
        len(history)
    )

    # ========================================================
    # SADECE OYNANMAMIŞ MAÇLAR
    # ========================================================

    upcoming = [

        match

        for match in matches

        if not is_played(match)

    ]

    print(
        "🔮 Oynanmamış maç:",
        len(upcoming)
    )

    print()

    predictions = []

    for match in upcoming:

        try:

            prediction = predict_match(

                match,

                history

            )

            # Hiçbir maçı tahmin yok
            # diye silmiyoruz.

            predictions.append(
                prediction
            )

        except Exception as error:

            print(
                "⚠️ Maç analiz hatası:",
                match.get(
                    "homeTeam"
                ),
                "-",
                match.get(
                    "awayTeam"
                ),
                error
            )

            # Hata olsa bile temel kayıt
            # oluştur.

            predictions.append({

                "id":
                    match.get(
                        "id"
                    ),

                "league":
                    match.get(
                        "league"
                    ),

                "season":
                    match.get(
                        "season"
                    ),

                "date":
                    match.get(
                        "date"
                    ),

                "utcDate":
                    match.get(
                        "utcDate"
                    ),

                "homeTeam":
                    match.get(
                        "homeTeam"
                    ),

                "awayTeam":
                    match.get(
                        "awayTeam"
                    ),

                "prediction":
                    None,

                "line":
                    None,

                "barem":
                    None,

                "confidence":
                    None,

                "ustPercent":
                    None,

                "altPercent":
                    None,

                "barems":
                    [],

                "expectedHome":
                    None,

                "expectedAway":
                    None,

                "expectedTotal":
                    None,

                "homeSample":
                    0,

                "awaySample":
                    0,

                "prediction1X2":
                    None,

                "confidence1X2":
                    None,

                "homeWinProbability":
                    None,

                "drawProbability":
                    None,

                "awayWinProbability":
                    None,

                "played":
                    False,

                "homeScore":
                    None,

                "awayScore":
                    None,

            })

    # ========================================================
    # TARİH SIRASI
    # ========================================================

    predictions.sort(

        key=lambda x: (

            str(
                x.get("date")
                or ""
            ),

            str(
                x.get("homeTeam")
                or ""
            )

        )

    )

    # ========================================================
    # ÇIKTI
    # ========================================================

    output = {

        "updatedAt":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "source":
            INPUT_FILE,

        "baremAraliklari":
            BAREM_ARALIKLARI,

        "baremler":
            BAREMS,

        "minConfidence":
            MIN_CONFIDENCE,

        "minSample":
            MIN_SAMPLE,

        "totalMatches":
            len(predictions),

        "predictions":
            predictions,

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

            separators=(
                ",",
                ":"
            )

        )

    # ========================================================
    # ÖZET
    # ========================================================

    with_prediction = sum(

        1

        for x in predictions

        if x.get(
            "prediction"
        )

    )

    without_prediction = (
        len(predictions)
        -
        with_prediction
    )

    print()
    print("=" * 70)
    print("✅ TAHMİN DOSYASI OLUŞTURULDU")
    print("=" * 70)

    print(
        "🎯 Toplam maç:",
        len(predictions)
    )

    print(
        "✅ Tahmin bulunan:",
        with_prediction
    )

    print(
        "⚠️ Tahmin bulunmayan:",
        without_prediction
    )

    print(
        "📁 Dosya:",
        OUTPUT_FILE
    )

    print()

    # ========================================================
    # İLK 10 MAÇI GÖSTER
    # ========================================================

    for item in predictions[:10]:

        print(
            f"🏀 {item['homeTeam']} "
            f"- "
            f"{item['awayTeam']}"
        )

        if item["prediction"]:

            print(
                f"   🎯 ANA: "
                f"{item['barem']} "
                f"{item['prediction']} "
                f"%{item['confidence']}"
            )

        else:

            print(
                "   🎯 ANA: "
                "Tahmin için yeterli veri yok"
            )

        if item["barems"]:

            print(
                "   📊 BAREMLER:"
            )

            for barem in item[
                "barems"
            ]:

                if (
                    barem["ust"]
                    is None
                ):

                    continue

                print(

                    f"      "
                    f"{barem['barem']}: "
                    f"ÜST %{barem['ust']} "
                    f"/ "
                    f"ALT %{barem['alt']}"

                )

        print()


if __name__ == "__main__":

    main()
