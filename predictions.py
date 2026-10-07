# ============================================================
# BASKETBOL TAHMİN SİSTEMİ
# NBA + EUROLEAGUE
#
# basketball.json değişmez.
# played alanına güvenilmez.
# Gelecek maçlar tarih/saat üzerinden belirlenir.
#
# ANA TAHMİN:
# Kullanıcının belirlediği baremler üzerinden
# ÜST / ALT yüzdesi hesaplanır.
# ============================================================

import json
import os
from datetime import datetime, timezone


INPUT_FILE = "basketball.json"
OUTPUT_FILE = "predictions.json"


# ============================================================
# BAREM ARALIKLARI
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


MAX_HISTORY = 10
MIN_SAMPLE = 5
MIN_CONFIDENCE = 70

NEWEST_WEIGHT = 1.00
OLDEST_WEIGHT = 0.55

HOME_ADVANTAGE = 2.0


# ============================================================
# JSON
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

def safe_int(value):

    try:

        if value is None:
            return None

        return int(float(value))

    except Exception:

        return None


def safe_float(value):

    try:

        if value is None:
            return None

        return float(
            str(value).replace(",", ".")
        )

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
        text = text.replace(old, new)

    return " ".join(
        text.split()
    )


# ============================================================
# TARİH PARSE
# ============================================================

def parse_datetime(value):

    if not value:
        return None

    text = str(value).strip()

    try:

        if text.endswith("Z"):
            text = (
                text[:-1]
                + "+00:00"
            )

        dt = datetime.fromisoformat(
            text
        )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt

    except Exception:
        pass

    # Sadece YYYY-MM-DD varsa
    try:

        dt = datetime.strptime(
            text[:10],
            "%Y-%m-%d"
        )

        return dt.replace(
            tzinfo=timezone.utc
        )

    except Exception:

        return None


# ============================================================
# MAÇ TARİHİ
# ============================================================

def match_datetime(match):

    value = (
        match.get("utcDate")
        or
        match.get("date")
    )

    return parse_datetime(
        value
    )


# ============================================================
# GELECEK MAÇ KONTROLÜ
# ============================================================
#
# ARTIK played alanına güvenmiyoruz.
#
# Maç zamanı gelecekteyse:
#     oynanmamış
#
# Maç zamanı geçmişteyse:
#     geçmiş
#
# Ancak maç skoru varsa ve maç gerçekten
# tamamlanmışsa geçmiş kabul edilir.
# ============================================================

def is_future_match(match):

    dt = match_datetime(
        match
    )

    if dt is None:
        return False

    now = datetime.now(
        timezone.utc
    )

    return dt > now


# ============================================================
# SKOR VAR MI?
# ============================================================

def has_score(match):

    home = safe_int(
        match.get("homeScore")
    )

    away = safe_int(
        match.get("awayScore")
    )

    return (
        home is not None
        and
        away is not None
    )


# ============================================================
# GEÇMİŞ MAÇ
# ============================================================

def is_historical_match(match):

    dt = match_datetime(
        match
    )

    if dt is None:
        return False

    now = datetime.now(
        timezone.utc
    )

    if dt < now:

        return has_score(
            match
        )

    return False


# ============================================================
# TOPLAM SKOR
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
        or
        away is None
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
        or
        away is None
    ):
        return None

    if home > away:
        return "1"

    if home < away:
        return "2"

    return "X"


# ============================================================
# BAREMLER
# ============================================================

def generate_barems():

    values = []

    for start, end in BAREM_ARALIKLARI:

        start = safe_float(start)
        end = safe_float(end)

        if (
            start is None
            or
            end is None
        ):
            continue

        current = start

        while current <= end + 0.001:

            value = round(
                current,
                1
            )

            if value not in values:
                values.append(value)

            current += 1.0

    return sorted(values)


BAREMS = generate_barems()


# ============================================================
# GEÇMİŞ VERİ
# ============================================================

def prepare_history(matches):

    history = []

    for match in matches:

        if not is_historical_match(
            match
        ):
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

        if not home or not away:
            continue

        dt = match_datetime(
            match
        )

        timestamp = (
            dt.timestamp()
            if dt
            else 0
        )

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

            "timestamp":
                timestamp,

        })

    history.sort(
        key=lambda x:
            x["timestamp"]
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

        if match[
            "homeTeam"
        ] == team:

            result.append({

                **match,

                "teamScore":
                    match[
                        "homeScore"
                    ],

                "opponentScore":
                    match[
                        "awayScore"
                    ],

            })

        elif match[
            "awayTeam"
        ] == team:

            result.append({

                **match,

                "teamScore":
                    match[
                        "awayScore"
                    ],

                "opponentScore":
                    match[
                        "homeScore"
                    ],

            })

    result.sort(
        key=lambda x:
            x["timestamp"],
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
            "weightedPointsFor": None,
            "weightedPointsAgainst": None,
            "weightedTotal": None,
        }

    total_weight = 0

    pf_total = 0
    pa_total = 0

    weighted_pf = 0
    weighted_pa = 0
    weighted_total = 0

    valid = 0

    for index, game in enumerate(
        games
    ):

        pf = game["teamScore"]
        pa = game["opponentScore"]

        if (
            pf is None
            or
            pa is None
        ):
            continue

        weight = calculate_weight(
            index,
            len(games)
        )

        total_weight += weight

        pf_total += pf
        pa_total += pa

        weighted_pf += (
            pf * weight
        )

        weighted_pa += (
            pa * weight
        )

        weighted_total += (
            (pf + pa)
            *
            weight
        )

        valid += 1

    if (
        valid == 0
        or
        total_weight == 0
    ):

        return {
            "sample": 0,
            "pointsFor": None,
            "pointsAgainst": None,
            "weightedPointsFor": None,
            "weightedPointsAgainst": None,
            "weightedTotal": None,
        }

    return {

        "sample":
            valid,

        "pointsFor":
            pf_total / valid,

        "pointsAgainst":
            pa_total / valid,

        "weightedPointsFor":
            weighted_pf
            /
            total_weight,

        "weightedPointsAgainst":
            weighted_pa
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

    home = team_statistics(
        home_team,
        history
    )

    away = team_statistics(
        away_team,
        history
    )

    # İki takım da bilinmiyorsa
    # beklenen skor üretmiyoruz.
    if (
        home["sample"] == 0
        and
        away["sample"] == 0
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

    if (
        home["sample"] > 0
        and
        away["sample"] > 0
    ):

        expected_home = (

            (
                home[
                    "weightedPointsFor"
                ]
                +
                away[
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
                away[
                    "weightedPointsFor"
                ]
                +
                home[
                    "weightedPointsAgainst"
                ]
            )
            /
            2

        )

    elif home["sample"] > 0:

        expected_home = (
            home[
                "weightedPointsFor"
            ]
            +
            HOME_ADVANTAGE
        )

        expected_away = (
            home[
                "weightedPointsAgainst"
            ]
        )

    else:

        expected_home = (
            away[
                "weightedPointsAgainst"
            ]
            +
            HOME_ADVANTAGE
        )

        expected_away = (
            away[
                "weightedPointsFor"
            ]
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
            home["sample"],

        "awaySample":
            away["sample"],

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

    games = []

    games.extend(
        home_history
    )

    games.extend(
        away_history
    )

    # Aynı maçın iki kez sayılmasını önle.
    seen = set()

    unique = []

    for game in games:

        key = game.get(
            "id"
        )

        if key is None:

            key = (
                game["timestamp"],
                game["homeTeam"],
                game["awayTeam"]
            )

        if key in seen:
            continue

        seen.add(key)

        unique.append(
            game
        )

    unique.sort(
        key=lambda x:
            x["timestamp"],
        reverse=True
    )

    unique = unique[:20]

    if not unique:

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

    push_count = 0

    for index, game in enumerate(
        unique
    ):

        total = game["total"]

        weight = calculate_weight(
            index,
            len(unique)
        )

        total_weight += weight

        if total > barem:

            ust_weight += weight
            ust_count += 1

        elif total < barem:

            alt_weight += weight
            alt_count += 1

        else:

            push_count += 1

    if total_weight <= 0:

        return {

            "barem":
                barem,

            "sample":
                len(unique),

            "ust":
                None,

            "alt":
                None,

            "prediction":
                None,

            "confidence":
                None,

        }

    ust = (
        ust_weight
        /
        total_weight
        *
        100
    )

    alt = (
        alt_weight
        /
        total_weight
        *
        100
    )

    counted = (
        ust
        +
        alt
    )

    if counted > 0:

        ust = (
            ust
            /
            counted
            *
            100
        )

        alt = (
            alt
            /
            counted
            *
            100
        )

    if ust >= alt:

        prediction = "ÜST"
        confidence = ust

    else:

        prediction = "ALT"
        confidence = alt

    return {

        "barem":
            barem,

        "sample":
            len(unique),

        "ust":
            round(
                ust,
                2
            ),

        "alt":
            round(
                alt,
                2
            ),

        "ustCount":
            ust_count,

        "altCount":
            alt_count,

        "pushCount":
            push_count,

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

    return [

        analyze_barem(

            barem,

            home_team,

            away_team,

            history

        )

        for barem in BAREMS

    ]


# ============================================================
# ANA BAREM
# ============================================================

def select_main_prediction(
    barems,
    expected_total
):

    valid = [

        x

        for x in barems

        if (
            x["prediction"]
            is not None
            and
            x["confidence"]
            is not None
        )

    ]

    if not valid:
        return None

    strong = [

        x

        for x in valid

        if x["confidence"]
        >= MIN_CONFIDENCE

    ]

    candidates = (
        strong
        if strong
        else valid
    )

    candidates.sort(

        key=lambda x: (

            -x["confidence"],

            (
                abs(
                    x["barem"]
                    -
                    expected_total
                )
                if expected_total
                is not None
                else 999999
            )

        )

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

    one = 0
    draw = 0
    two = 0

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

            one += weight

        elif (
            game["teamScore"]
            ==
            game["opponentScore"]
        ):

            draw += weight

        else:

            two += weight

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

            two += weight

        elif (
            game["teamScore"]
            ==
            game["opponentScore"]
        ):

            draw += weight

        else:

            one += weight

    total = (
        one
        +
        draw
        +
        two
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
        one
        /
        total
        *
        100
    )

    draw_percent = (
        draw
        /
        total
        *
        100
    )

    away_percent = (
        two
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
# MAÇ TAHMİNİ
# ============================================================

def predict_match(
    match,
    history
):

    home_team = (
        match.get("homeTeam")
        or "-"
    )

    away_team = (
        match.get("awayTeam")
        or "-"
    )

    home_normalized = normalize_team(
        home_team
    )

    away_normalized = normalize_team(
        away_team
    )

    expected = calculate_expected_scores(

        home_normalized,

        away_normalized,

        history

    )

    barems = analyze_all_barems(

        home_normalized,

        away_normalized,

        history

    )

    main = select_main_prediction(

        barems,

        expected[
            "expectedTotal"
        ]

    )

    x2 = calculate_1x2(

        home_normalized,

        away_normalized,

        history

    )

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

        "barems":
            barems,

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

        "homeSample":
            expected[
                "homeSample"
            ],

        "awaySample":
            expected[
                "awaySample"
            ],

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

        "played":
            False,

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

    data = load_json(
        INPUT_FILE
    )

    matches = data.get(
        "matches",
        []
    )

    print(
        "🏀 Toplam maç:",
        len(matches)
    )

    # --------------------------------------------------------
    # GERÇEK GEÇMİŞ
    # --------------------------------------------------------

    history = prepare_history(
        matches
    )

    print(
        "📚 Geçmiş maç:",
        len(history)
    )

    # --------------------------------------------------------
    # GELECEK MAÇLAR
    #
    # played alanına BAKMIYORUZ.
    # --------------------------------------------------------

    upcoming = [

        match

        for match in matches

        if is_future_match(match)

    ]

    print(
        "🔮 Gelecek maç:",
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

            predictions.append(
                prediction
            )

        except Exception as error:

            print(
                "⚠️ Hata:",
                match.get(
                    "homeTeam"
                ),
                "-",
                match.get(
                    "awayTeam"
                ),
                error
            )

    # ========================================================
    # TARİHE GÖRE
    # ========================================================

    predictions.sort(

        key=lambda x:
            str(
                x.get(
                    "utcDate"
                )
                or
                x.get(
                    "date"
                )
                or ""
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
        ) is not None

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
        "✅ Ana tahmin bulunan:",
        with_prediction
    )

    print(
        "⚠️ Ana tahmin bulunmayan:",
        len(predictions)
        -
        with_prediction
    )

    print(
        "📁 Dosya:",
        OUTPUT_FILE
    )

    print()

    # ========================================================
    # ÖRNEK
    # ========================================================

    for item in predictions[:5]:

        print(
            f"🏀 {item['homeTeam']} "
            f"- "
            f"{item['awayTeam']}"
        )

        print(
            "   🎯 ANA:",
            item["prediction"],
            item["line"],
            f"%{item['confidence']}"
            if item["confidence"]
            is not None
            else "-"
        )

        print(
            "   📊 Baremler:",
            len(
                item["barems"]
            )
        )

        print()


if __name__ == "__main__":
    main()
