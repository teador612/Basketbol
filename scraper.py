import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


URL = "https://www.iddaa.com/euroleague-avrupa-basketbol-ligi"
OUTPUT = Path("data.json")
DEBUG_TEXT = Path("iddaa-rendered.txt")


# ============================================================
# IDDAA KISA KOD -> TAKIM
# ============================================================

TEAM_CODES = {
    "EFES": "Anadolu Efes",
    "MON": "AS Monaco",
    "BAS": "Baskonia",
    "BMÜN": "Bayern Münih",
    "BMUN": "Bayern Münih",
    "DUB": "Dubai Basketball",
    "MLN": "Olimpia Milano",
    "MAC": "Maccabi Rapyd Tel Aviv",
    "BAR": "FC Barcelona",
    "FB": "Fenerbahçe Beko",
    "HTA": "Hapoel IBI Tel Aviv",
    "OLY": "Olympiakos",
    "PANA": "Panathinaikos",
    "PAR": "Paris Basketball",
    "PART": "Partizan",
    "RMD": "Real Madrid",
    "VLC": "Valencia Basket",
    "BLG": "Virtus Bologna",
    "ZAL": "Zalgiris Kaunas",
    "KYL": "Zalgiris Kaunas",
    "KIZ": "Kızılyıldız",
    "KZR": "Kızılyıldız",
    "ASV": "LDLC ASVEL",
    "LYN": "LDLC ASVEL",
    "BES": "Beşiktaş",
}


# Bazı kodlar iddaa sayfasında farklılaşabilir.
# İsim üzerinden de eşleştirme yapıyoruz.
TEAM_NAMES = {
    "Anadolu Efes": [
        "Anadolu Efes",
        "Efes",
    ],
    "AS Monaco": [
        "Monaco",
        "AS Monaco",
    ],
    "Baskonia": [
        "Baskonia",
    ],
    "Bayern Münih": [
        "B. Münih",
        "Bayern Münih",
        "Bayern Munich",
    ],
    "Dubai Basketball": [
        "Dubai BC",
        "Dubai Basketball",
    ],
    "Olimpia Milano": [
        "Olimpia Milano",
        "Milano",
    ],
    "FC Barcelona": [
        "Barcelona",
        "FC Barcelona",
    ],
    "Fenerbahçe Beko": [
        "Fenerbahçe Beko",
        "Fenerbahce Beko",
    ],
    "Hapoel IBI Tel Aviv": [
        "Hap.Tel Aviv",
        "Hapoel IBI Tel Aviv",
    ],
    "Kızılyıldız": [
        "Kızılyıldız",
        "Crvena Zvezda",
    ],
    "LDLC ASVEL": [
        "ASVEL",
        "LDLC ASVEL",
    ],
    "Maccabi Rapyd Tel Aviv": [
        "Maccabi",
        "Maccabi Rapyd Tel Aviv",
    ],
    "Olympiakos": [
        "Olympiakos",
        "Olympiacos",
    ],
    "Panathinaikos": [
        "Panathinaikos",
    ],
    "Paris Basketball": [
        "Paris BC",
        "Paris Basketball",
    ],
    "Partizan": [
        "Partizan",
    ],
    "Real Madrid": [
        "R. Madrid",
        "Real Madrid",
    ],
    "Valencia Basket": [
        "Valencia",
        "Valencia Basket",
    ],
    "Virtus Bologna": [
        "V. Bologna",
        "Virtus Bologna",
    ],
    "Zalgiris Kaunas": [
        "Zalgiris",
        "Zalgiris Kaunas",
    ],
}


# ============================================================
# NORMALIZE
# ============================================================

def normalize(value):
    value = str(value or "").strip().upper()

    replacements = {
        "Ş": "S",
        "İ": "I",
        "Ğ": "G",
        "Ü": "U",
        "Ö": "O",
        "Ç": "C",
    }

    for a, b in replacements.items():
        value = value.replace(a, b)

    return re.sub(r"\s+", " ", value).strip()


NORMALIZED_CODES = {
    normalize(k): v
    for k, v in TEAM_CODES.items()
}


# ============================================================
# TARİH
# ============================================================

MONTHS = {
    "OCA": 1,
    "SUB": 2,
    "ŞUB": 2,
    "MAR": 3,
    "NIS": 4,
    "NİS": 4,
    "MAY": 5,
    "HAZ": 6,
    "TEM": 7,
    "AGU": 8,
    "AĞU": 8,
    "EYL": 9,
    "EKI": 10,
    "EKİ": 10,
    "KAS": 11,
    "ARA": 12,
}


def make_date(day, month):
    year = datetime.now().year

    try:
        return f"{year:04d}-{month:02d}-{int(day):02d}"
    except Exception:
        return None


# ============================================================
# SKOR
# ============================================================

def parse_score(value):
    if not value:
        return None

    m = re.search(
        r"(?<!\d)(\d{1,3})\s*[-:]\s*(\d{1,3})(?!\d)",
        value
    )

    if not m:
        return None

    return {
        "home": int(m.group(1)),
        "away": int(m.group(2)),
    }


# ============================================================
# TEAM CODE
# ============================================================

def team_from_code(value):

    key = normalize(value)

    return NORMALIZED_CODES.get(key)


# ============================================================
# FIXTURE PARSER
# ============================================================

def parse_fixture_lines(text):

    lines = [
        x.strip()
        for x in text.splitlines()
        if x.strip()
    ]

    matches = []

    current_date = None

    i = 0

    while i < len(lines):

        line = lines[i]

        # ----------------------------------------------------
        # TARİH BAŞLANGICI
        #
        # Örnek:
        #
        # ÇAR
        # 07
        # EKI
        #
        # PER
        # 08
        # EKI
        # ----------------------------------------------------

        if (
            i + 2 < len(lines)
            and re.fullmatch(
                r"(PZT|SAL|ÇAR|PER|CUM|CMT|PAZ)",
                lines[i],
                re.IGNORECASE
            )
            and re.fullmatch(
                r"\d{1,2}",
                lines[i + 1]
            )
            and normalize(lines[i + 2]) in MONTHS
        ):

            day = int(lines[i + 1])
            month = MONTHS[normalize(lines[i + 2])]

            current_date = make_date(
                day,
                month
            )

            i += 3
            continue

        # ----------------------------------------------------
        # "08 Ekim, 19:00"
        # ----------------------------------------------------

        m = re.search(
            r"(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)[,\s]+(\d{1,2}:\d{2})",
            line
        )

        if m:

            day = int(m.group(1))
            month_name = normalize(m.group(2))

            month_map = {
                "OCAK": 1,
                "SUBAT": 2,
                "ŞUBAT": 2,
                "MART": 3,
                "NISAN": 4,
                "NİSAN": 4,
                "MAYIS": 5,
                "HAZIRAN": 6,
                "HAZİRAN": 6,
                "TEMMUZ": 7,
                "AGUSTOS": 8,
                "AĞUSTOS": 8,
                "EYLUL": 9,
                "EYLÜL": 9,
                "EKIM": 10,
                "EKİM": 10,
                "KASIM": 11,
                "ARALIK": 12,
            }

            if month_name in month_map:
                current_date = make_date(
                    day,
                    month_map[month_name]
                )

        # ----------------------------------------------------
        # MAÇ SAATİ
        #
        # "Yarın, 21:45"
        # "08 Ekim, 19:00"
        #
        # Bunun hemen altında:
        #
        # PAR
        # -
        # LYN
        # -
        # ----------------------------------------------------

        if re.search(
            r"\b\d{1,2}:\d{2}\b",
            line
        ):

            # Sonraki 8 satır içinde iki takım kodu ara.
            block = lines[
                i + 1:min(
                    i + 9,
                    len(lines)
                )
            ]

            found = []

            for item in block:

                team = team_from_code(item)

                if team and team not in found:
                    found.append(team)

            if len(found) >= 2:

                home = found[0]
                away = found[1]

                # Skor aynı blokta varsa al.
                block_text = "\n".join(block)

                score = parse_score(
                    block_text
                )

                status = (
                    "finished"
                    if score
                    else "scheduled"
                )

                winner = None

                if score:

                    if score["home"] > score["away"]:
                        winner = home

                    elif score["away"] > score["home"]:
                        winner = away

                    else:
                        winner = "draw"

                match = {
                    "id": (
                        f"{current_date}_"
                        f"{normalize(home)}_"
                        f"{normalize(away)}"
                    ),
                    "league": "EuroLeague",
                    "home": home,
                    "away": away,
                    "date": current_date,
                    "time": re.search(
                        r"\b\d{1,2}:\d{2}\b",
                        line
                    ).group(0),
                    "score": score or {
                        "home": None,
                        "away": None
                    },
                    "status": status,
                    "winner": winner,
                    "source": "iddaa.com",
                }

                matches.append(match)

                # Bu maç bloğunu tekrar okumamak için
                i += 4
                continue

        i += 1

    # --------------------------------------------------------
    # DUPLICATE
    # --------------------------------------------------------

    unique = {}

    for match in matches:

        key = (
            match["date"],
            match["home"],
            match["away"]
        )

        unique[key] = match

    return list(unique.values())


# ============================================================
# SAYFAYI AL
# ============================================================

def scrape():

    print("=" * 60)
    print("🏀 EUROLEAGUE SCRAPER")
    print("=" * 60)

    print(
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1200
            },
            locale="tr-TR",
            timezone_id="Europe/Istanbul"
        )

        print("🌐 iddaa.com açılıyor...")

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        print("✅ Sayfa açıldı")

        # Broadage fixture widget'ın render olması
        time.sleep(8)

        # Fikstür aşağıda olabilir
        page.evaluate(
            """
            window.scrollTo(
                0,
                document.body.scrollHeight
            )
            """
        )

        time.sleep(3)

        page.evaluate(
            """
            window.scrollTo(0, 0)
            """
        )

        time.sleep(2)

        text = page.locator(
            "body"
        ).inner_text(
            timeout=10000
        )

        DEBUG_TEXT.write_text(
            text,
            encoding="utf-8"
        )

        print(
            f"📄 Sayfa metni: "
            f"{len(text)} karakter"
        )

        browser.close()

    matches = parse_fixture_lines(text)

    # ========================================================
    # SONUÇ
    # ========================================================

    print(
        f"🏀 Bulunan EuroLeague maçı: "
        f"{len(matches)}"
    )

    for match in matches:

        score = match["score"]

        if (
            score["home"] is not None
            and score["away"] is not None
        ):
            score_text = (
                f'{score["home"]}-'
                f'{score["away"]}'
            )
        else:
            score_text = "-"

        print(
            f'  {match["date"]} | '
            f'{match["time"]} | '
            f'{match["home"]} - '
            f'{match["away"]} | '
            f'{score_text}'
        )

    return matches


# ============================================================
# ESKİ DATA
# ============================================================

def load_old():

    if not OUTPUT.exists():
        return []

    try:

        data = json.loads(
            OUTPUT.read_text(
                encoding="utf-8"
            )
        )

        return data.get(
            "matches",
            []
        )

    except Exception:
        return []


# ============================================================
# DATA KAYDET
# ============================================================

def save(matches):

    old_matches = load_old()

    merged = {}

    # Eski kayıtlar
    for match in old_matches:

        key = (
            match.get("date"),
            match.get("home"),
            match.get("away")
        )

        if all(key):
            merged[key] = match

    # Yeni kayıtlar
    for match in matches:

        key = (
            match["date"],
            match["home"],
            match["away"]
        )

        merged[key] = match

    final_matches = list(
        merged.values()
    )

    final_matches.sort(
        key=lambda x: (
            x.get("date", ""),
            x.get("time", ""),
            x.get("home", "")
        )
    )

    data = {
        "source": URL,
        "league": "EuroLeague",
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "matches": final_matches
    }

    OUTPUT.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("💾 data.json yazıldı")

    print(
        f"📦 Toplam maç: "
        f"{len(final_matches)}"
    )

    print(
        f"📆 Toplam tarih: "
        f"{len(set(
            x.get('date')
            for x in final_matches
            if x.get('date')
        ))}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    matches = scrape()

    if not matches:

        print(
            "⚠️ Hiçbir gerçek fixture bulunamadı."
        )

        print(
            "❗ data.json değiştirilmedi."
        )

        raise SystemExit(0)

    save(matches)

    print(
        "✅ EUROLeague scraper tamamlandı."
    )
