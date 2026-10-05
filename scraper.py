import json
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


URL = "https://www.iddaa.com/euroleague-avrupa-basketbol-ligi"

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data.json"
DEBUG_FILE = BASE_DIR / "iddaa-rendered.txt"


# ============================================================
# IDDAA TAKIM KODLARI
# ============================================================

TEAM_CODES = {
    "PAR": "Paris Basketball",
    "LYN": "LDLC ASVEL",

    "DUB": "Dubai Basketball",
    "KYL": "Kızılyıldız",

    "MAC": "Maccabi Tel Aviv",
    "MLN": "Olimpia Milano",

    "BMÜN": "Bayern Münih",
    "BMUN": "Bayern Münih",

    "BLG": "Virtus Bologna",

    "PANA": "Panathinaikos",

    "FB": "Fenerbahçe Beko",

    "VLC": "Valencia Basket",

    "HTA": "Hapoel IBI Tel Aviv",

    "RMD": "Real Madrid",

    "OLY": "Olympiakos",

    "EFES": "Anadolu Efes",

    "BAR": "FC Barcelona",

    "ZAL": "Zalgiris Kaunas",

    "BAS": "Baskonia",

    "BJK": "Beşiktaş",
}


# ============================================================
# IDDAA'NIN AMBIGUOUS KODLARI
# ============================================================
#
# PAR iki farklı takım için kullanılıyor:
#
# PAR - LYN = Paris Basketball - LDLC ASVEL
# RMD - PAR = Real Madrid - Partizan
#
# Bu nedenle PAR tek başına Partizan/Paris olarak çözülmez.
# Maçın diğer takımına göre çözülür.
# ============================================================

def resolve_teams(code1, code2):

    pair = (code1, code2)

    if pair == ("PAR", "LYN"):
        return "Paris Basketball", "LDLC ASVEL"

    if pair == ("RMD", "PAR"):
        return "Real Madrid", "Partizan"

    if pair == ("DUB", "KYL"):
        return "Dubai Basketball", "Kızılyıldız"

    if pair == ("MAC", "MLN"):
        return "Maccabi Tel Aviv", "Olimpia Milano"

    if pair == ("BMÜN", "BLG"):
        return "Bayern Münih", "Virtus Bologna"

    if pair == ("BMUN", "BLG"):
        return "Bayern Münih", "Virtus Bologna"

    if pair == ("PANA", "FB"):
        return "Panathinaikos", "Fenerbahçe Beko"

    if pair == ("VLC", "HTA"):
        return "Valencia Basket", "Hapoel IBI Tel Aviv"

    if pair == ("OLY", "EFES"):
        return "Olympiakos", "Anadolu Efes"

    if pair == ("BAR", "ZAL"):
        return "FC Barcelona", "Zalgiris Kaunas"

    if pair == ("BAS", "BJK"):
        return "Baskonia", "Beşiktaş"

    return None


# ============================================================
# NORMALİZASYON
# ============================================================

def normalize(value):

    value = str(value or "").strip().upper()

    replacements = {
        "İ": "I",
        "Ş": "S",
        "Ğ": "G",
        "Ü": "U",
        "Ö": "O",
        "Ç": "C",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return value


# ============================================================
# TARİH BAŞLIĞI
# ============================================================

MONTHS = {
    "OCA": 1,
    "SUB": 2,
    "MAR": 3,
    "NIS": 4,
    "MAY": 5,
    "HAZ": 6,
    "TEM": 7,
    "AGU": 8,
    "EYL": 9,
    "EKI": 10,
    "KAS": 11,
    "ARA": 12,
}


def parse_day(value):

    value = str(value).strip()

    if value.isdigit():
        day = int(value)

        if 1 <= day <= 31:
            return day

    return None


def parse_month(value):

    value = normalize(value)

    value = value[:3]

    return MONTHS.get(value)


# ============================================================
# SAAT
# ============================================================

TIME_PATTERN = re.compile(r"^\d{1,2}:\d{2}$")


def is_time(value):

    return bool(
        TIME_PATTERN.match(
            str(value).strip()
        )
    )


def extract_time(value):

    value = str(value).strip()

    # "Yarın, 21:45"
    match = re.search(
        r"(\d{1,2}):(\d{2})",
        value
    )

    if not match:
        return None

    return (
        f"{int(match.group(1)):02d}:"
        f"{match.group(2)}"
    )


# ============================================================
# TAKIM KODU
# ============================================================

def get_team_code(value):

    raw = str(value).strip()

    # Doğrudan kod
    if raw in TEAM_CODES:
        return raw

    normalized = normalize(raw)

    # Beşiktaş doğrudan isim geliyor
    if normalized == "BESIKTAS":
        return "BJK"

    # Güvenlik
    for code in TEAM_CODES:

        if normalize(code) == normalized:
            return code

    return None


# ============================================================
# FİKSTÜR PARSER
# ============================================================

def parse_fixtures(text):

    # Boş satırları kaldır
    lines = []

    for line in text.splitlines():

        line = line.strip()

        if line:
            lines.append(line)

    matches = []

    current_date = None

    i = 0

    while i < len(lines):

        line = lines[i]

        # ====================================================
        # TARİH BAŞLIĞI
        # ====================================================

        #
        # ÇAR
        # 07
        # EKI
        #

        if (
            i + 2 < len(lines)
            and lines[i] in {
                "ÇAR",
                "PER",
                "CUM",
                "PAZ",
                "PZT",
                "SAL",
                "SALI",
                "CMT",
            }
        ):

            day = parse_day(
                lines[i + 1]
            )

            month = parse_month(
                lines[i + 2]
            )

            if day and month:

                current_date = (
                    f"2026-{month:02d}-{day:02d}"
                )

                i += 3
                continue

        # ====================================================
        # SAAT
        # ====================================================

        time_value = extract_time(line)

        if not time_value:

            i += 1
            continue

        if not current_date:

            i += 1
            continue

        # ====================================================
        # SAATTEN SONRA TAKIMLARI AL
        # ====================================================

        team_codes = []

        j = i + 1

        while (
            j < len(lines)
            and j < i + 8
        ):

            candidate = lines[j]

            # Yeni gün başladıysa takım aramayı bırak
            if candidate in {
                "ÇAR",
                "PER",
                "CUM",
                "PAZ",
                "PZT",
                "SAL",
                "SALI",
                "CMT",
            }:
                break

            code = get_team_code(candidate)

            if code:
                team_codes.append(code)

            # İlk iki takımı bulduk
            if len(team_codes) == 2:
                break

            j += 1

        # ====================================================
        # İKİ TAKIM YOKSA GEÇ
        # ====================================================

        if len(team_codes) != 2:

            i += 1
            continue

        code1 = team_codes[0]
        code2 = team_codes[1]

        # ====================================================
        # MAÇI ÇÖZ
        # ====================================================

        resolved = resolve_teams(
            code1,
            code2
        )

        if resolved is None:

            print(
                f"⚠️ Tanınmayan eşleşme: "
                f"{code1} - {code2}"
            )

            i += 1
            continue

        home, away = resolved

        # ====================================================
        # MAÇ
        # ====================================================

        match = {
            "id": (
                f"{current_date}_"
                f"{time_value}_"
                f"{normalize(home)}_"
                f"{normalize(away)}"
            ),
            "league": "EuroLeague",
            "home": home,
            "away": away,
            "date": current_date,
            "time": time_value,
            "score": {
                "home": None,
                "away": None
            },
            "status": "scheduled",
            "winner": None,
            "source": "iddaa.com"
        }

        # Duplicate
        duplicate = False

        for old in matches:

            if (
                old["date"] == match["date"]
                and old["time"] == match["time"]
                and old["home"] == match["home"]
                and old["away"] == match["away"]
            ):

                duplicate = True
                break

        if not duplicate:

            matches.append(match)

        i += 1

    return matches


# ============================================================
# IDDAA SAYFASINI AL
# ============================================================

def fetch_page():

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 2000
            },
            locale="tr-TR"
        )

        print("🌐 iddaa.com açılıyor...")

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        print("✅ Sayfa açıldı")

        page.wait_for_timeout(7000)

        text = page.locator(
            "body"
        ).inner_text()

        DEBUG_FILE.write_text(
            text,
            encoding="utf-8"
        )

        print(
            f"📄 Sayfa metni: "
            f"{len(text)} karakter"
        )

        browser.close()

        return text


# ============================================================
# DATA.JSON
# ============================================================

def save_data(matches):

    data = {
        "source": URL,
        "league": "EuroLeague",
        "updatedAt": datetime.now().astimezone().isoformat(),
        "matches": matches
    }

    DATA_FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("🏀 EUROLEAGUE SCRAPER")
    print("=" * 60)

    print(
        f"📅 "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    text = fetch_page()

    matches = parse_fixtures(text)

    matches.sort(
        key=lambda x: (
            x["date"],
            x["time"]
        )
    )

    print()

    print(
        f"🏀 Bulunan EuroLeague maçı: "
        f"{len(matches)}"
    )

    print()

    for match in matches:

        print(
            f"  {match['date']} | "
            f"{match['time']} | "
            f"{match['home']} - "
            f"{match['away']} | -"
        )

    save_data(matches)

    print()

    print("💾 data.json yazıldı")

    print(
        f"📦 Toplam maç: "
        f"{len(matches)}"
    )

    dates = sorted(
        set(
            match["date"]
            for match in matches
        )
    )

    print(
        f"📆 Toplam tarih: "
        f"{len(dates)}"
    )

    if len(matches) == 10:

        print(
            "✅ EUROLeague scraper tamamlandı."
        )

    else:

        print(
            "⚠️ Beklenen 10 maç yerine "
            f"{len(matches)} maç bulundu."
        )


if __name__ == "__main__":
    main()
