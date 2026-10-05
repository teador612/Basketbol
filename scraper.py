import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


URL = "https://www.iddaa.com/euroleague-avrupa-basketbol-ligi"

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data.json"
DEBUG_FILE = BASE_DIR / "iddaa-rendered.txt"


# ============================================================
# TAKIM İSİMLERİ
# ============================================================

TEAM_NAMES = {
    "EFES": "Anadolu Efes",
    "EFS": "Anadolu Efes",

    "MAC": "Maccabi Tel Aviv",
    "MLN": "Olimpia Milano",
    "MIL": "Olimpia Milano",

    "DUB": "Dubai Basketball",
    "KYL": "Zalgiris Kaunas",
    "BCZ": "Zalgiris Kaunas",

    "CRZ": "Kızılyıldız",
    "KIZ": "Kızılyıldız",

    "BAY": "Bayern Münih",
    "BMUN": "Bayern Münih",
    "BMÜN": "Bayern Münih",
    "BMÜN": "Bayern Münih",

    "VIR": "Virtus Bologna",
    "BLG": "Virtus Bologna",

    "PAN": "Panathinaikos",
    "PANA": "Panathinaikos",

    "FB": "Fenerbahçe Beko",

    "VAL": "Valencia Basket",
    "VLC": "Valencia Basket",

    "HTA": "Hapoel IBI Tel Aviv",

    "REA": "Real Madrid",
    "RMD": "Real Madrid",

    "OLY": "Olympiakos",

    "BAS": "Baskonia",

    "BAR": "FC Barcelona",

    "ASV": "LDLC ASVEL",
    "LYN": "LDLC ASVEL",

    "BJK": "Beşiktaş",

    "PAR": "Paris Basketball",
    "PART": "Partizan",

    "MON": "AS Monaco",
}


# ============================================================
# IDDAA SAYFASINDAKİ AMBIGUOUS EŞLEŞMELER
#
# PAR tek başına güvenilir değil:
#
# PAR - LYN  = Paris Basketball - LDLC ASVEL
# RMD - PAR  = Real Madrid - Partizan
#
# Aynı şekilde sayfadaki bazı kodlar farklı kaynaklarda
# farklı kısa isimlerle gösterilebiliyor.
# ============================================================

PAIR_MAP = {
    frozenset(["PAR", "LYN"]): (
        "Paris Basketball",
        "LDLC ASVEL"
    ),

    frozenset(["PAR", "RMD"]): (
        "Real Madrid",
        "Partizan"
    ),

    frozenset(["MAC", "MLN"]): (
        "Maccabi Tel Aviv",
        "Olimpia Milano"
    ),

    frozenset(["DUB", "KYL"]): (
        "Dubai Basketball",
        "Kızılyıldız"
    ),

    frozenset(["BAY", "VIR"]): (
        "Bayern Münih",
        "Virtus Bologna"
    ),

    frozenset(["BMÜN", "VIR"]): (
        "Bayern Münih",
        "Virtus Bologna"
    ),

    frozenset(["PAN", "FB"]): (
        "Panathinaikos",
        "Fenerbahçe Beko"
    ),

    frozenset(["VAL", "HTA"]): (
        "Valencia Basket",
        "Hapoel IBI Tel Aviv"
    ),

    frozenset(["OLY", "EFES"]): (
        "Olympiakos",
        "Anadolu Efes"
    ),

    frozenset(["OLY", "EFS"]): (
        "Olympiakos",
        "Anadolu Efes"
    ),

    frozenset(["BAS", "BJK"]): (
        "Baskonia",
        "Beşiktaş"
    ),

    frozenset(["BAR", "KYL"]): (
        "FC Barcelona",
        "Zalgiris Kaunas"
    ),
}


# ============================================================
# NORMALİZASYON
# ============================================================

def normalize(text):
    text = str(text or "").strip().upper()

    replacements = {
        "İ": "I",
        "İ": "I",
        "Ş": "S",
        "Ğ": "G",
        "Ü": "U",
        "Ö": "O",
        "Ç": "C",
    }

    for a, b in replacements.items():
        text = text.replace(a, b)

    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        c for c in text
        if not unicodedata.combining(c)
    )

    return text


def clean_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


# ============================================================
# TARİH
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


def parse_header_date(lines, index):
    """
    Örnek:

    ÇAR
    07
    EKI

    veya

    08 Ekim, 19:00
    """

    # Önce klasik başlık formatı
    if index + 2 < len(lines):

        day = lines[index + 1]
        month = normalize(lines[index + 2])[:3]

        if day.isdigit() and month in MONTHS:
            return f"2026-{MONTHS[month]:02d}-{int(day):02d}"

    # "08 Ekim, 19:00" gibi satırlar
    line = clean_text(lines[index])

    m = re.search(
        r"(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)",
        line
    )

    if m:
        day = int(m.group(1))
        month = normalize(m.group(2))[:3]

        if month in MONTHS:
            return f"2026-{MONTHS[month]:02d}-{day:02d}"

    return None


# ============================================================
# SAAT
# ============================================================

TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


def is_time(value):
    return bool(TIME_RE.match(clean_text(value)))


# ============================================================
# TAKIM TOKENI
# ============================================================

KNOWN_CODES = set()

for key in TEAM_NAMES:
    KNOWN_CODES.add(normalize(key))


def token_to_code(token):
    """
    Metindeki kısa kodu tanır.
    """

    raw = clean_text(token)
    norm = normalize(raw)

    if norm in KNOWN_CODES:
        return raw.upper()

    # Literal takım isimleri
    literal = {
        "BESIKTAS": "BJK",
        "BEŞİKTAŞ": "BJK",
        "FENERBAHCE": "FB",
        "FENERBAHCE BEKO": "FB",
        "FENERBAHCE TARFIN": "FB",
        "ANADOLU EFES": "EFES",
        "OLYMPIAKOS": "OLY",
        "BARCELONA": "BAR",
    }

    if norm in literal:
        return literal[norm]

    return None


# ============================================================
# TAKIM ÇİFTİNİ ÇÖZ
# ============================================================

def resolve_pair(token1, token2):
    code1 = token_to_code(token1)
    code2 = token_to_code(token2)

    if not code1 or not code2:
        return None

    pair_key = frozenset([code1, code2])

    # Önce özel eşleşme
    if pair_key in PAIR_MAP:

        home_code = code1
        away_code = code2

        home_name, away_name = PAIR_MAP[pair_key]

        # PAIR_MAP sırası sayfadaki gerçek maç sırasıdır.
        # Token sırasından bağımsız olarak doğru yönü buluyoruz.

        special_pairs = {
            frozenset(["PAR", "LYN"]): ("PAR", "LYN"),
            frozenset(["PAR", "RMD"]): ("RMD", "PAR"),
            frozenset(["MAC", "MLN"]): ("MAC", "MLN"),
            frozenset(["DUB", "KYL"]): ("DUB", "KYL"),
            frozenset(["BAY", "VIR"]): ("BAY", "VIR"),
            frozenset(["BMÜN", "VIR"]): ("BMÜN", "VIR"),
            frozenset(["PAN", "FB"]): ("PAN", "FB"),
            frozenset(["VAL", "HTA"]): ("VAL", "HTA"),
            frozenset(["OLY", "EFES"]): ("OLY", "EFES"),
            frozenset(["OLY", "EFS"]): ("OLY", "EFS"),
            frozenset(["BAS", "BJK"]): ("BAS", "BJK"),
            frozenset(["BAR", "KYL"]): ("BAR", "KYL"),
        }

        ordered = special_pairs.get(pair_key)

        if ordered:
            h, a = ordered

            hname = TEAM_NAMES.get(h, home_name)
            aname = TEAM_NAMES.get(a, away_name)

            return hname, aname

        return home_name, away_name

    # Özel eşleşme yoksa normal sözlük
    return (
        TEAM_NAMES.get(code1),
        TEAM_NAMES.get(code2)
    )


# ============================================================
# TARİH / SAAT / TAKIMLARI AYRIŞTIR
# ============================================================

def parse_fixtures(text):
    raw_lines = text.splitlines()

    lines = []

    for line in raw_lines:
        line = clean_text(line)

        if line:
            lines.append(line)

    fixtures = []

    current_date = None

    i = 0

    while i < len(lines):

        line = lines[i]

        # ----------------------------------------------------
        # TARİH BAŞLIĞI
        # ----------------------------------------------------

        date_match = parse_header_date(lines, i)

        if date_match:
            current_date = date_match

        # ----------------------------------------------------
        # SAAT
        # ----------------------------------------------------

        if not is_time(line):
            i += 1
            continue

        if not current_date:
            i += 1
            continue

        time_value = line

        # ----------------------------------------------------
        # SAATTEN SONRAKİ SATIRLARDA TAKIMLARI BUL
        # ----------------------------------------------------

        candidates = []

        for j in range(i + 1, min(i + 12, len(lines))):

            candidate = lines[j]

            # Yeni tarih / yeni saat başladıysa dur
            if is_time(candidate):
                break

            if candidate in [
                "ÇAR",
                "PER",
                "CUM",
                "CMT",
                "PAZ",
                "PZT",
                "SALI",
            ]:
                break

            code = token_to_code(candidate)

            if code:
                candidates.append((candidate, code))

            # Literal takım adı
            norm = normalize(candidate)

            literal_names = {
                "BESIKTAS",
                "ANADOLU EFES",
                "OLYMPIAKOS",
                "BARCELONA",
            }

            if norm in literal_names:
                candidates.append((candidate, token_to_code(candidate)))

            if len(candidates) >= 2:
                break

        if len(candidates) < 2:
            i += 1
            continue

        token1, code1 = candidates[0]
        token2, code2 = candidates[1]

        resolved = resolve_pair(token1, token2)

        if not resolved:
            i += 1
            continue

        home, away = resolved

        # ----------------------------------------------------
        # AYNI MAÇI TEKRAR EKLEME
        # ----------------------------------------------------

        duplicate = any(
            x["date"] == current_date
            and x["time"] == time_value
            and x["home"] == home
            and x["away"] == away
            for x in fixtures
        )

        if not duplicate:

            fixtures.append({
                "id": f"{current_date}_{time_value}_{normalize(home)}_{normalize(away)}",
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
            })

        i += 1

    return fixtures


# ============================================================
# PLAYWRIGHT
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

        # JS içeriklerinin yüklenmesini bekle
        page.wait_for_timeout(7000)

        text = page.locator("body").inner_text()

        # Debug
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

def save_data(fixtures):

    data = {
        "source": URL,
        "league": "EuroLeague",
        "updatedAt": datetime.now().astimezone().isoformat(),
        "matches": fixtures
    }

    DATA_FILE.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    return data


# ============================================================
# ANA
# ============================================================

def main():

    print("=" * 60)
    print("🏀 EUROLEAGUE SCRAPER")
    print("=" * 60)

    print(
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    text = fetch_page()

    fixtures = parse_fixtures(text)

    # Tarih + saat sıralaması
    fixtures.sort(
        key=lambda x: (
            x["date"],
            x["time"]
        )
    )

    print()
    print(
        f"🏀 Bulunan EuroLeague maçı: {len(fixtures)}"
    )

    for match in fixtures:

        print(
            f"  {match['date']} | "
            f"{match['time']} | "
            f"{match['home']} - "
            f"{match['away']} | -"
        )

    save_data(fixtures)

    print()
    print("💾 data.json yazıldı")
    print(f"📦 Toplam maç: {len(fixtures)}")

    dates = sorted(
        set(x["date"] for x in fixtures)
    )

    print(f"📆 Toplam tarih: {len(dates)}")

    if len(fixtures) == 10:
        print("✅ EUROLeague scraper tamamlandı.")
    else:
        print(
            f"⚠️ Uyarı: Beklenen 10 maç yerine "
            f"{len(fixtures)} maç bulundu."
        )


if __name__ == "__main__":
    main()
