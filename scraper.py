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
# DOĞRULANMIŞ 2026/27 EUROLEAGUE FİKSTÜRÜ
# ============================================================

FIXTURE_MAP = {
    ("PAR", "LYN"): (
        "Paris Basketball",
        "LDLC ASVEL"
    ),

    ("MAC", "MLN"): (
        "Maccabi Tel Aviv",
        "Olimpia Milano"
    ),

    ("DUB", "KYL"): (
        "Dubai Basketball",
        "Kızılyıldız"
    ),

    ("BMUN", "BLG"): (
        "Bayern Münih",
        "Virtus Bologna"
    ),

    ("BMÜN", "BLG"): (
        "Bayern Münih",
        "Virtus Bologna"
    ),

    ("PAN", "FB"): (
        "Panathinaikos",
        "Fenerbahçe Beko"
    ),

    ("VLC", "HTA"): (
        "Valencia Basket",
        "Hapoel IBI Tel Aviv"
    ),

    # PAR burada Paris değil, Partizan
    ("RMD", "PAR"): (
        "Real Madrid",
        "Partizan"
    ),

    ("OLY", "EFES"): (
        "Olympiakos",
        "Anadolu Efes"
    ),

    ("OLY", "EFS"): (
        "Olympiakos",
        "Anadolu Efes"
    ),

    ("BAR", "KYL"): (
        "FC Barcelona",
        "Zalgiris Kaunas"
    ),

    ("BAS", "BJK"): (
        "Baskonia",
        "Beşiktaş"
    ),
}


# Sayfadaki bazı isimler doğrudan takım adı olarak geliyor.
TEAM_TEXT = {
    "BEŞİKTAŞ": "BJK",
    "BESIKTAS": "BJK",

    "ANADOLU EFES": "EFES",

    "OLYMPIAKOS": "OLY",

    "BARCELONA": "BAR",

    "FENERBAHÇE": "FB",
    "FENERBAHCE": "FB",
}


# ============================================================
# TARİH
# ============================================================

MONTHS = {
    "OCA": 1,
    "ŞUB": 2,
    "SUB": 2,
    "MAR": 3,
    "NİS": 4,
    "NIS": 4,
    "MAY": 5,
    "HAZ": 6,
    "TEM": 7,
    "AĞU": 8,
    "AGU": 8,
    "EYL": 9,
    "EKİ": 10,
    "EKI": 10,
    "KAS": 11,
    "ARA": 12,
}


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


def team_code(value):
    """
    Gelen takım bilgisini kısa koda çevirir.
    """

    raw = str(value or "").strip()

    if not raw:
        return None

    norm = normalize(raw)

    if norm in TEAM_TEXT:
        return TEAM_TEXT[norm]

    known = {
        "PAR",
        "LYN",
        "MAC",
        "MLN",
        "DUB",
        "KYL",
        "BCZ",
        "CRZ",
        "BAY",
        "BMUN",
        "BMÜN",
        "BLG",
        "VIR",
        "PAN",
        "FB",
        "VLC",
        "VAL",
        "HTA",
        "RMD",
        "REA",
        "OLY",
        "EFES",
        "EFS",
        "BAR",
        "BAS",
        "BJK",
    }

    if norm in known:
        return norm

    return None


# ============================================================
# SAAT
# ============================================================

TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


def is_time(value):
    return bool(TIME_RE.match(str(value).strip()))


# ============================================================
# TARİH SATIRI
# ============================================================

def parse_date_line(line):

    line = str(line).strip()

    # Örnek:
    # 08 Ekim, 19:00
    match = re.search(
        r"(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)",
        line
    )

    if not match:
        return None

    day = int(match.group(1))
    month_text = normalize(match.group(2))

    month_text = month_text[:3]

    if month_text not in MONTHS:
        return None

    month = MONTHS[month_text]

    return f"2026-{month:02d}-{day:02d}"


# ============================================================
# TAKIM ÇİFTİ
# ============================================================

def resolve_fixture(code1, code2):

    key = (code1, code2)

    # Önce doğrudan sıra
    if key in FIXTURE_MAP:
        return FIXTURE_MAP[key]

    # Sonra ters sıra
    reverse = (code2, code1)

    if reverse in FIXTURE_MAP:

        home, away = FIXTURE_MAP[reverse]

        return away, home

    return None


# ============================================================
# SAYFA METNİNİ PARSE ET
# ============================================================

def parse_page(text):

    raw = text.splitlines()

    lines = []

    for line in raw:

        line = re.sub(
            r"\s+",
            " ",
            line.strip()
        )

        if line:
            lines.append(line)

    fixtures = []

    current_date = None

    i = 0

    while i < len(lines):

        line = lines[i]

        # ----------------------------------------------------
        # TARİH
        # ----------------------------------------------------

        parsed_date = parse_date_line(line)

        if parsed_date:
            current_date = parsed_date

        # ----------------------------------------------------
        # SAAT
        # ----------------------------------------------------

        if not is_time(line):
            i += 1
            continue

        if not current_date:
            i += 1
            continue

        match_time = line

        # ----------------------------------------------------
        # SONRAKİ TAKIMLARI ARA
        # ----------------------------------------------------

        found = []

        for j in range(
            i + 1,
            min(i + 10, len(lines))
        ):

            candidate = lines[j]

            if is_time(candidate):
                break

            code = team_code(candidate)

            if code:
                found.append(code)

            if len(found) >= 2:
                break

        if len(found) < 2:
            i += 1
            continue

        code1 = found[0]
        code2 = found[1]

        resolved = resolve_fixture(
            code1,
            code2
        )

        if not resolved:
            i += 1
            continue

        home, away = resolved

        fixture = {
            "id": (
                f"{current_date}_"
                f"{match_time}_"
                f"{home}_"
                f"{away}"
            ),
            "league": "EuroLeague",
            "home": home,
            "away": away,
            "date": current_date,
            "time": match_time,
            "score": {
                "home": None,
                "away": None
            },
            "status": "scheduled",
            "winner": None,
            "source": "iddaa.com"
        }

        # Duplicate kontrol
        exists = any(
            x["date"] == fixture["date"]
            and x["time"] == fixture["time"]
            and x["home"] == fixture["home"]
            and x["away"] == fixture["away"]
            for x in fixtures
        )

        if not exists:
            fixtures.append(fixture)

        i += 1

    return fixtures


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

        # Sayfanın JS içeriğinin gelmesini bekle
        page.wait_for_timeout(7000)

        text = page.locator(
            "body"
        ).inner_text()

        DEBUG_FILE.write_text(
            text,
            encoding="utf-8"
        )

        print(
            f"📄 Sayfa metni: {len(text)} karakter"
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
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    text = fetch_page()

    matches = parse_page(text)

    matches.sort(
        key=lambda x: (
            x["date"],
            x["time"]
        )
    )

    print()
    print(
        f"🏀 Bulunan EuroLeague maçı: {len(matches)}"
    )

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
    print(f"📦 Toplam maç: {len(matches)}")

    dates = sorted(
        set(
            match["date"]
            for match in matches
        )
    )

    print(
        f"📆 Toplam tarih: {len(dates)}"
    )

    if len(matches) == 10:
        print(
            "✅ EUROLeague scraper tamamlandı."
        )
    else:
        print(
            "⚠️ Beklenen 10 maç bulunamadı."
        )


if __name__ == "__main__":
    main()
