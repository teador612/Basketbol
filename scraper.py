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
# IDDAA TAKIM KODLARI
# ============================================================

TEAM_CODES = {
    "EFES": "Anadolu Efes",
    "MON": "AS Monaco",

    "BAS": "Baskonia",
    "BMÜN": "Bayern Münih",
    "BMUN": "Bayern Münih",

    "DUB": "Dubai Basketball",
    "MLN": "Olimpia Milano",

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

    "BJK": "Beşiktaş",
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
    normalize(code): team
    for code, team in TEAM_CODES.items()
}


# ============================================================
# AYLAR
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


FULL_MONTHS = {
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


# ============================================================
# TARİH
# ============================================================

def make_date(day, month):
    year = datetime.now().year
    return f"{year:04d}-{month:02d}-{int(day):02d}"


# ============================================================
# TAKIM BUL
# ============================================================

def team_from_code(value):
    return NORMALIZED_CODES.get(
        normalize(value)
    )


# ============================================================
# GERÇEK SKOR
# ============================================================

def parse_real_score(lines):
    """
    SADECE açıkça skor formatında olan değerleri kabul eder.

    Kabul:
        94-84
        101 - 97

    Kabul etmez:
        19:00
        21:15
        21:30
    """

    for line in lines:

        # Saat kesinlikle skor değildir.
        if re.fullmatch(
            r"\d{1,2}:\d{2}",
            line.strip()
        ):
            continue

        m = re.fullmatch(
            r"(\d{2,3})\s*-\s*(\d{2,3})",
            line.strip()
        )

        if not m:
            continue

        home = int(m.group(1))
        away = int(m.group(2))

        # Basketbol için makul sınır
        if home > 200 or away > 200:
            continue

        return {
            "home": home,
            "away": away
        }

    return {
        "home": None,
        "away": None
    }


# ============================================================
# FIXTURE PARSER
# ============================================================

def parse_fixture_lines(text):

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    matches = []

    current_date = None

    i = 0

    while i < len(lines):

        line = lines[i]

        # ----------------------------------------------------
        # GÜN BAŞLIĞI
        #
        # ÇAR
        # 07
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

            month = MONTHS[
                normalize(lines[i + 2])
            ]

            current_date = make_date(
                day,
                month
            )

            i += 3
            continue

        # ----------------------------------------------------
        # TAM TARİH + SAAT
        #
        # 08 Ekim, 19:00
        # ----------------------------------------------------

        date_time_match = re.search(
            r"(\d{1,2})\s+"
            r"([A-Za-zÇĞİÖŞÜçğıöşü]+)"
            r"[,\s]+"
            r"(\d{1,2}:\d{2})",
            line
        )

        if date_time_match:

            day = int(
                date_time_match.group(1)
            )

            month_name = normalize(
                date_time_match.group(2)
            )

            if month_name in FULL_MONTHS:

                current_date = make_date(
                    day,
                    FULL_MONTHS[month_name]
                )

        # ----------------------------------------------------
        # SAAT BUL
        # ----------------------------------------------------

        time_match = re.search(
            r"\b(\d{1,2}:\d{2})\b",
            line
        )

        if not time_match:
            i += 1
            continue

        match_time = time_match.group(1)

        # ----------------------------------------------------
        # SAATİN ALTINDAKİ TAKIMLARI ARA
        # ----------------------------------------------------

        block = lines[
            i + 1:
            min(i + 10, len(lines))
        ]

        found_teams = []

        for item in block:

            team = team_from_code(item)

            if team and team not in found_teams:
                found_teams.append(team)

            if len(found_teams) == 2:
                break

        # İki takım yoksa geç
        if len(found_teams) != 2:
            i += 1
            continue

        home = found_teams[0]
        away = found_teams[1]

        if home == away:
            i += 1
            continue

        # ----------------------------------------------------
        # SKOR
        # ----------------------------------------------------

        score = parse_real_score(block)

        has_score = (
            score["home"] is not None
            and score["away"] is not None
        )

        if has_score:

            status = "finished"

            if score["home"] > score["away"]:
                winner = home

            elif score["away"] > score["home"]:
                winner = away

            else:
                winner = "draw"

        else:

            status = "scheduled"
            winner = None

        # ----------------------------------------------------
        # MAÇ
        # ----------------------------------------------------

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
            "time": match_time,
            "score": score,
            "status": status,
            "winner": winner,
            "source": "iddaa.com",
        }

        matches.append(match)

        # Aynı fixture'ın tekrar okunmasını engelle
        i += 4

    # ========================================================
    # DUPLICATE
    # ========================================================

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
# IDDAA SAYFASI
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

        # Broadage fixture yüklenmesini bekle
        time.sleep(8)

        # Sayfanın aşağısındaki fixture alanlarını tetikle
        page.evaluate(
            """
            window.scrollTo(
                0,
                document.body.scrollHeight
            );
            """
        )

        time.sleep(3)

        page.evaluate(
            """
            window.scrollTo(0, 0);
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
# DATA.JSON
# ============================================================

def save(matches):

    # Eski data.json'daki hatalı maçları
    # artık KESİNLİKLE taşımıyoruz.

    data = {
        "source": URL,
        "league": "EuroLeague",
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "matches": sorted(
            matches,
            key=lambda x: (
                x.get("date", ""),
                x.get("time", ""),
                x.get("home", "")
            )
        )
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
        f"{len(matches)}"
    )

    print(
        f"📆 Toplam tarih: "
        f"{len(set(
            x.get('date')
            for x in matches
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
            "⚠️ Hiçbir EuroLeague maçı bulunamadı."
        )

        print(
            "❗ data.json değiştirilmedi."
        )

        raise SystemExit(0)

    save(matches)

    print(
        "✅ EUROLeague scraper tamamlandı."
    )
