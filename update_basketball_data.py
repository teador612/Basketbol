import json
import re
from pathlib import Path
from datetime import datetime, timezone

import requests


# ============================================================
# AYARLAR
# ============================================================

BASKETBALL_FILE = Path("basketball.json")
OUTPUT_FILE = Path("odds.json")

BILYONER_URL = (
    "https://www.bilyoner.com/"
    "api/v3/mobile/aggregator/"
    "gamelist/all/v1"
)

TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.bilyoner.com/iddaa/basketbol",
}


# ============================================================
# GENEL
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).strip()
    )


def normalize(value):
    value = clean_text(value).lower()

    replacements = {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
        "é": "e",
        "á": "a",
        "à": "a",
        "ä": "a",
        "-": " ",
        "_": " ",
        ".": " ",
        ",": " ",
        "'": "",
        '"': "",
        "/": " ",
        "\\": " ",
        "(": " ",
        ")": " ",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()


def number(value):
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    try:
        if isinstance(value, str):
            value = value.replace(",", ".")

        return float(value)

    except Exception:
        return None


# ============================================================
# BASKETBALL JSON
# ============================================================

def load_matches():

    if not BASKETBALL_FILE.exists():
        raise RuntimeError(
            f"{BASKETBALL_FILE} bulunamadı."
        )

    with BASKETBALL_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        data = json.load(file)

    matches = data.get(
        "matches",
        []
    )

    if not isinstance(matches, list):
        raise RuntimeError(
            "basketball.json içindeki matches alanı geçersiz."
        )

    return matches


# ============================================================
# BİLYONER
# ============================================================

def fetch_bilyoner():

    print()
    print("=" * 70)
    print("💰 BİLYONER ODDS")
    print("=" * 70)

    params = {
        "tabType": "2",
        "bulletinType": "2",
    }

    try:

        response = requests.get(
            BILYONER_URL,
            params=params,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        print(
            f"✅ HTTP {response.status_code}"
        )

        return data

    except Exception as e:

        print(
            "❌ Bilyoner isteği başarısız:"
        )

        print(e)

        return None


# ============================================================
# JSON RECURSIVE TARAMA
# ============================================================

def walk(value):

    if isinstance(value, dict):

        yield value

        for child in value.values():
            yield from walk(child)

    elif isinstance(value, list):

        for child in value:
            yield from walk(child)


# ============================================================
# ANAHTAR ARAMA
# ============================================================

def find_value(
    obj,
    names,
):

    if not isinstance(
        obj,
        dict
    ):
        return None

    lowered = {
        str(key).lower(): value
        for key, value in obj.items()
    }

    for name in names:

        if name.lower() in lowered:

            value = lowered[
                name.lower()
            ]

            if value is not None:
                return value

    return None


# ============================================================
# TAKIM ADI BUL
# ============================================================

def find_team_name(
    obj,
    home=True,
):

    if not isinstance(
        obj,
        dict
    ):
        return ""

    if home:

        keys = [
            "homeTeam",
            "homeTeamName",
            "home",
            "homeName",
            "homeTeamTitle",
            "homeCompetitor",
            "homeParticipant",
        ]

    else:

        keys = [
            "awayTeam",
            "awayTeamName",
            "away",
            "awayName",
            "awayTeamTitle",
            "awayCompetitor",
            "awayParticipant",
        ]

    value = find_value(
        obj,
        keys
    )

    if isinstance(
        value,
        dict
    ):

        value = (
            value.get("name")
            or
            value.get("displayName")
            or
            value.get("title")
            or
            value.get("shortName")
            or
            value.get("teamName")
            or
            ""
        )

    return clean_text(
        value
    )


# ============================================================
# MARKET METİN
# ============================================================

def object_text(obj):

    try:

        return normalize(
            json.dumps(
                obj,
                ensure_ascii=False
            )
        )

    except Exception:
        return ""


# ============================================================
# BASKETBALL FİLTRESİ
# ============================================================

def is_basketball(obj):

    text = object_text(
        obj
    )

    basketball_words = [
        "basketbol",
        "basketball",
        "nba",
        "euroleague",
        "euro lig",
        "eurocup",
    ]

    return any(
        word in text
        for word in basketball_words
    )


# ============================================================
# MARKET TÜRÜ
# ============================================================

def detect_market_type(obj):

    text = object_text(
        obj
    )

    # --------------------------------------------------------
    # TOPLAM SAYI
    # --------------------------------------------------------

    if (
        "toplam sayi" in text
        or
        "toplam puan" in text
        or
        "total points" in text
        or
        "total score" in text
    ):

        if (
            "ilk yari" in text
            or
            "1. yari" in text
            or
            "first half" in text
        ):
            return "firstHalfTotal"

        if (
            "ceyrek" in text
            or
            "quarter" in text
        ):
            return "quarterTotal"

        return "total"

    # --------------------------------------------------------
    # EV SAHİBİ SAYI
    # --------------------------------------------------------

    if (
        "ev sahibi takim sayi" in text
        or
        "ev sahibi sayi" in text
        or
        "home team total" in text
        or
        "home total" in text
    ):

        return "homeTotal"

    # --------------------------------------------------------
    # DEPLASMAN SAYI
    # --------------------------------------------------------

    if (
        "deplasman takim sayi" in text
        or
        "deplasman sayi" in text
        or
        "away team total" in text
        or
        "away total" in text
    ):

        return "awayTotal"

    return None


# ============================================================
# BAREM BUL
# ============================================================

def find_line(obj):

    keys = [
        "line",
        "lineValue",
        "handicap",
        "handicapValue",
        "threshold",
        "total",
        "value",
        "marketValue",
        "marketLine",
        "point",
        "points",
    ]

    value = find_value(
        obj,
        keys
    )

    result = number(
        value
    )

    if result is not None:

        # Basketbol baremleri genellikle
        # 100+ sayı civarında olur.
        if 20 <= result <= 400:
            return result

    # İç içe obje kontrolü

    for key in (
        "market",
        "selection",
        "outcome",
        "option",
        "details",
    ):

        child = find_value(
            obj,
            [key]
        )

        if isinstance(
            child,
            dict
        ):

            result = find_line(
                child
            )

            if result is not None:
                return result

    return None


# ============================================================
# ORAN BUL
# ============================================================

def find_odd(obj):

    keys = [
        "odd",
        "odds",
        "rate",
        "price",
        "decimalOdd",
        "decimalOdds",
        "value",
        "coefficient",
        "ratio",
    ]

    for key in keys:

        value = find_value(
            obj,
            [key]
        )

        if isinstance(
            value,
            dict
        ):
            continue

        result = number(
            value
        )

        if result is not None:

            if (
                1.01 <= result <= 100
            ):
                return result

    return None


# ============================================================
# ALT / ÜST
# ============================================================

def detect_side(obj):

    text = object_text(
        obj
    )

    # Önce açık anahtarları kontrol et.

    direct = find_value(
        obj,
        [
            "side",
            "selectionName",
            "outcomeName",
            "optionName",
            "name",
            "title",
            "description",
            "label",
        ]
    )

    direct_text = normalize(
        direct
    )

    if (
        direct_text == "alt"
        or
        " under" in f" {direct_text}"
        or
        direct_text.startswith("under ")
        or
        direct_text.endswith(" under")
    ):
        return "under"

    if (
        direct_text == "ust"
        or
        direct_text == "üst"
        or
        " over" in f" {direct_text}"
        or
        direct_text.startswith("over ")
        or
        direct_text.endswith(" over")
    ):
        return "over"

    # Tüm obje metninden kontrol.

    if (
        re.search(
            r"\balt\b",
            text
        )
    ):
        return "under"

    if (
        re.search(
            r"\bust\b",
            text
        )
        or
        re.search(
            r"\büst\b",
            text
        )
    ):
        return "over"

    if re.search(
        r"\bunder\b",
        text
    ):
        return "under"

    if re.search(
        r"\bover\b",
        text
    ):
        return "over"

    return None


# ============================================================
# MAÇ ADI
# ============================================================

def extract_match_name(obj):

    home = find_team_name(
        obj,
        True
    )

    away = find_team_name(
        obj,
        False
    )

    if home and away:

        return (
            clean_text(home),
            clean_text(away)
        )

    # Bazı yapılarda eventName bulunabilir.

    event_name = find_value(
        obj,
        [
            "eventName",
            "matchName",
            "gameName",
            "fixtureName",
            "name",
            "title",
        ]
    )

    if isinstance(
        event_name,
        str
    ):

        separators = [
            " - ",
            " vs ",
            " v ",
            " / ",
            " @ ",
        ]

        for separator in separators:

            if separator in event_name:

                parts = event_name.split(
                    separator,
                    1
                )

                if len(parts) == 2:

                    return (
                        clean_text(parts[0]),
                        clean_text(parts[1])
                    )

    return (
        "",
        ""
    )


# ============================================================
# MATCH EŞLEŞTİRME
# ============================================================

def team_similarity(
    a,
    b
):

    a = normalize(a)
    b = normalize(b)

    if not a or not b:
        return False

    if a == b:
        return True

    if (
        a in b
        or
        b in a
    ):
        return True

    a_words = set(
        a.split()
    )

    b_words = set(
        b.split()
    )

    if not a_words or not b_words:
        return False

    common = (
        a_words & b_words
    )

    return len(common) >= min(
        2,
        len(a_words),
        len(b_words)
    )


def find_basketball_match(
    home,
    away,
    matches
):

    for match in matches:

        mh = match.get(
            "homeTeam",
            ""
        )

        ma = match.get(
            "awayTeam",
            ""
        )

        if (
            team_similarity(
                home,
                mh
            )
            and
            team_similarity(
                away,
                ma
            )
        ):

            return match

    return None


# ============================================================
# MARKET ÇIKAR
# ============================================================

def extract_markets(
    data,
    matches
):

    result = {}

    candidates = 0

    for obj in walk(data):

        if not isinstance(
            obj,
            dict
        ):
            continue

        market_type = detect_market_type(
            obj
        )

        if market_type not in {
            "total",
            "homeTotal",
            "awayTotal",
            "firstHalfTotal",
            "quarterTotal",
        }:
            continue

        if not is_basketball(
            obj
        ):
            continue

        home, away = extract_match_name(
            obj
        )

        if not home or not away:
            continue

        match = find_basketball_match(
            home,
            away,
            matches
        )

        if match is None:
            continue

        line = find_line(
            obj
        )

        if line is None:
            continue

        side = detect_side(
            obj
        )

        odd = find_odd(
            obj
        )

        if side is None or odd is None:
            continue

        candidates += 1

        match_id = str(
            match.get("id")
        )

        if match_id not in result:

            result[match_id] = {
                "matchId": match_id,
                "league": match.get(
                    "league"
                ),
                "date": match.get(
                    "date"
                ),
                "homeTeam": match.get(
                    "homeTeam"
                ),
                "awayTeam": match.get(
                    "awayTeam"
                ),
                "total": [],
                "homeTotal": [],
                "awayTotal": [],
                "firstHalfTotal": [],
                "quarterTotal": [],
            }

        market = result[
            match_id
        ][
            market_type
        ]

        existing = None

        for item in market:

            if (
                item.get("line")
                == line
            ):
                existing = item
                break

        if existing is None:

            existing = {
                "line": line
            }

            market.append(
                existing
            )

        existing[
            side
        ] = odd

    # Sadece iki tarafı da bulunan
    # marketleri bırak.

    for match_id in result:

        item = result[
            match_id
        ]

        for market_name in (
            "total",
            "homeTotal",
            "awayTotal",
            "firstHalfTotal",
            "quarterTotal",
        ):

            clean_market = []

            for market in item[
                market_name
            ]:

                if (
                    market.get("under")
                    is None
                    and
                    market.get("over")
                    is None
                ):
                    continue

                clean_market.append(
                    market
                )

            clean_market.sort(
                key=lambda x: x.get(
                    "line",
                    0
                )
            )

            item[
                market_name
            ] = clean_market

    print()
    print(
        f"🎯 Yakalanan market seçimi: "
        f"{candidates}"
    )

    return result


# ============================================================
# KAYDET
# ============================================================

def save_odds(
    markets
):

    output = {
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "source": (
            "Bilyoner "
            "gamelist/all/v1"
        ),

        "totalMatches": len(
            markets
        ),

        "matches": list(
            markets.values()
        ),
    }

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    print()
    print("=" * 70)
    print("💾 ODDS.JSON")
    print("=" * 70)

    print(
        f"🏀 Eşleşen maç: "
        f"{len(markets)}"
    )

    total_lines = 0

    for item in markets.values():

        total_lines += len(
            item["total"]
        )

        total_lines += len(
            item["homeTotal"]
        )

        total_lines += len(
            item["awayTotal"]
        )

    print(
        f"📊 Toplam barem: "
        f"{total_lines}"
    )

    print(
        f"📁 Dosya: "
        f"{OUTPUT_FILE}"
    )


# ============================================================
# ÖZET
# ============================================================

def print_summary(
    markets
):

    print()
    print("=" * 70)
    print("📊 BAREM ÖZETİ")
    print("=" * 70)

    for item in markets.values():

        print()
        print(
            f"🏀 {item['homeTeam']} - "
            f"{item['awayTeam']}"
        )

        print(
            f"   Toplam: "
            f"{len(item['total'])}"
        )

        print(
            f"   Ev sahibi: "
            f"{len(item['homeTotal'])}"
        )

        print(
            f"   Deplasman: "
            f"{len(item['awayTotal'])}"
        )

        print(
            f"   İlk yarı: "
            f"{len(item['firstHalfTotal'])}"
        )

        print(
            f"   Çeyrek: "
            f"{len(item['quarterTotal'])}"
        )

        if item["total"]:

            print(
                "   Toplam baremler:"
            )

            for market in item["total"]:

                print(
                    f"      {market.get('line')} "
                    f"Alt={market.get('under')} "
                    f"Üst={market.get('over')}"
                )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("🏀 BİLYONER GERÇEK BASKETBOL BAREMLERİ")
    print("=" * 70)

    matches = load_matches()

    print(
        f"📦 basketball.json maçları: "
        f"{len(matches)}"
    )

    data = fetch_bilyoner()

    if not data:

        raise RuntimeError(
            "Bilyoner verisi alınamadı."
        )

    markets = extract_markets(
        data,
        matches
    )

    save_odds(
        markets
    )

    print_summary(
        markets
    )

    print()
    print(
        "✅ Odds güncellemesi tamamlandı."
    )


if __name__ == "__main__":
    main()
