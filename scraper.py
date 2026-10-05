import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


URL = "https://www.iddaa.com/euroleague-avrupa-basketbol-ligi"
OUTPUT = Path("data.json")
DEBUG_HTML = Path("iddaa-rendered.html")
DEBUG_TEXT = Path("iddaa-rendered.txt")

TODAY = datetime.now(timezone.utc).date().isoformat()


# ============================================================
# EUROLEGUE TAKIMLARI
# ============================================================

TEAMS = {
    "Anadolu Efes": [
        "Anadolu Efes",
        "A. Efes",
        "Efes"
    ],

    "AS Monaco": [
        "AS Monaco",
        "Monaco"
    ],

    "Baskonia": [
        "Baskonia",
        "Cazoo Baskonia",
        "Baskonia Vitoria"
    ],

    "Bayern Münih": [
        "Bayern Münih",
        "Bayern Munich",
        "B. Münih"
    ],

    "Dubai Basketball": [
        "Dubai Basketball",
        "Dubai BC",
        "Dubai"
    ],

    "Olimpia Milano": [
        "Olimpia Milano",
        "EA7 Emporio Armani Milan",
        "Milano",
        "Olimpia"
    ],

    "FC Barcelona": [
        "FC Barcelona",
        "Barcelona"
    ],

    "Fenerbahçe Beko": [
        "Fenerbahçe Beko",
        "Fenerbahce Beko",
        "Fenerbahce Tarfin",
        "Fenerbahçe"
    ],

    "Hapoel IBI Tel Aviv": [
        "Hapoel IBI Tel Aviv",
        "Hapoel Tel Aviv",
        "Hap.Tel Aviv"
    ],

    "Kızılyıldız": [
        "Kızılyıldız",
        "Crvena Zvezda",
        "C.Zvezda"
    ],

    "LDLC ASVEL": [
        "LDLC ASVEL",
        "ASVEL"
    ],

    "Maccabi Rapyd Tel Aviv": [
        "Maccabi Rapyd Tel Aviv",
        "Maccabi Tel Aviv",
        "Maccabi"
    ],

    "Olympiakos": [
        "Olympiakos",
        "Olympiacos"
    ],

    "Panathinaikos": [
        "Panathinaikos",
        "Panathinaikos AKTOR"
    ],

    "Paris Basketball": [
        "Paris Basketball",
        "Paris BC"
    ],

    "Partizan": [
        "Partizan"
    ],

    "Real Madrid": [
        "Real Madrid",
        "R. Madrid"
    ],

    "Valencia Basket": [
        "Valencia Basket",
        "Valencia"
    ],

    "Virtus Bologna": [
        "Virtus Bologna",
        "Virtus Olidata Bologna",
        "V. Bologna"
    ],

    "Zalgiris Kaunas": [
        "Zalgiris Kaunas",
        "Zalgiris"
    ],
}


# ============================================================
# NORMALIZE
# ============================================================

def normalize(text):
    text = str(text or "").strip().lower()

    replacements = {
        "ş": "s",
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ö": "o",
        "ç": "c",
        "é": "e",
        "á": "a",
        "ã": "a",
    }

    for a, b in replacements.items():
        text = text.replace(a, b)

    text = re.sub(r"\s+", " ", text)
    return text.strip()


TEAM_LOOKUP = {}

for canonical, aliases in TEAMS.items():
    for alias in aliases:
        TEAM_LOOKUP[normalize(alias)] = canonical


def find_team(text):
    n = normalize(text)

    if n in TEAM_LOOKUP:
        return TEAM_LOOKUP[n]

    # Daha uzun alias'ları önce dene
    aliases = sorted(
        TEAM_LOOKUP.items(),
        key=lambda x: len(x[0]),
        reverse=True
    )

    for alias, canonical in aliases:
        if len(alias) >= 6 and alias in n:
            return canonical

    return None


# ============================================================
# SKOR
# ============================================================

def parse_score(text):
    """
    Sadece açık skor formatlarını kabul eder.

    Örnek:
        94 84
        94-84
        94 : 84
    """

    if not text:
        return None

    text = str(text).strip()

    # 94 - 84
    m = re.search(r"\b(\d{1,3})\s*[-:]\s*(\d{1,3})\b", text)

    if m:
        return {
            "home": int(m.group(1)),
            "away": int(m.group(2))
        }

    # 94 84
    m = re.search(r"(?<!\d)(\d{2,3})\s+(\d{2,3})(?!\d)", text)

    if m:
        return {
            "home": int(m.group(1)),
            "away": int(m.group(2))
        }

    return None


# ============================================================
# DURUM
# ============================================================

def detect_status(text):
    n = normalize(text)

    if any(x in n for x in [
        "ft",
        "finished",
        "final",
        "bitti"
    ]):
        return "finished"

    if any(x in n for x in [
        "live",
        "canli",
        "1q",
        "2q",
        "3q",
        "4q",
        "ot"
    ]):
        return "live"

    if any(x in n for x in [
        "sch",
        "scheduled",
        "baslamadi"
    ]):
        return "scheduled"

    return "scheduled"


# ============================================================
# TARİH
# ============================================================

MONTHS = {
    "ocak": 1,
    "subat": 2,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayis": 5,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "agustos": 8,
    "ağustos": 8,
    "eylul": 9,
    "eylül": 9,
    "ekim": 10,
    "kasim": 11,
    "kasım": 11,
    "aralik": 12,
    "aralık": 12,
}


def extract_date(text, fallback=TODAY):
    if not text:
        return fallback

    # 05.10.2026
    m = re.search(
        r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b",
        text
    )

    if m:
        d = int(m.group(1))
        mo = int(m.group(2))
        y = int(m.group(3))

        try:
            return f"{y:04d}-{mo:02d}-{d:02d}"
        except Exception:
            pass

    # 5 October 2026
    m = re.search(
        r"\b(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(20\d{2})\b",
        text
    )

    if m:
        d = int(m.group(1))
        month_name = normalize(m.group(2))
        y = int(m.group(3))

        if month_name in MONTHS:
            return f"{y:04d}-{MONTHS[month_name]:02d}-{d:02d}"

    # 05/10
    m = re.search(
        r"\b(\d{1,2})[./-](\d{1,2})\b",
        text
    )

    if m:
        d = int(m.group(1))
        mo = int(m.group(2))

        try:
            return f"{datetime.now().year:04d}-{mo:02d}-{d:02d}"
        except Exception:
            pass

    return fallback


# ============================================================
# MAÇ BLOĞU
# ============================================================

def make_match(home, away, date, score=None, status="scheduled", source="iddaa.com"):
    if home == away:
        return None

    item = {
        "id": f"{date}_{normalize(home)}_{normalize(away)}",
        "league": "EuroLeague",
        "home": home,
        "away": away,
        "date": date,
        "score": {
            "home": None,
            "away": None
        },
        "status": status,
        "winner": None,
        "source": source
    }

    if score:
        item["score"] = score

        if score["home"] > score["away"]:
            item["winner"] = home

        elif score["away"] > score["home"]:
            item["winner"] = away

        else:
            item["winner"] = "draw"

    return item


# ============================================================
# DOM'DAN GERÇEK FIXTURE SATIRLARINI BUL
# ============================================================

def extract_fixture_rows(page):
    """
    Broadage widget genellikle fixture bilgisini kendi DOM'u içinde
    oluşturuyor.

    Burada bütün sayfayı takım takım bölmek yerine:
      - fixture alanlarını
      - Broadage container'larını
      - iframe'ları
      ayrı ayrı tarıyoruz.
    """

    results = []

    selectors = [
        '[id*="DOM_element_id"]',
        '[class*="broadage"]',
        '[class*="fixture"]',
        '[class*="Fixture"]',
        '[class*="match"]',
        '[class*="Match"]',
        '[class*="event"]',
        '[class*="Event"]',
    ]

    seen = set()

    for selector in selectors:
        try:
            elements = page.locator(selector).all()

            for el in elements:
                try:
                    text = el.inner_text(timeout=1000).strip()
                except Exception:
                    continue

                if not text:
                    continue

                if text in seen:
                    continue

                seen.add(text)

                if len(text) > 20000:
                    continue

                results.append(text)

        except Exception:
            continue

    return results


# ============================================================
# METİN BLOĞUNU MAÇA ÇEVİR
# ============================================================

def parse_fixture_text(text):
    matches = []

    lines = [
        x.strip()
        for x in text.splitlines()
        if x.strip()
    ]

    if len(lines) < 2:
        return matches

    current_date = TODAY

    i = 0

    while i < len(lines):

        line = lines[i]

        # Tarih satırı
        possible_date = extract_date(line, None)

        if possible_date:
            current_date = possible_date

        # Aynı satırda iki takım
        found = []

        for line_index in range(
            max(0, i - 2),
            min(len(lines), i + 3)
        ):
            team = find_team(lines[line_index])

            if team and team not in found:
                found.append(team)

        # TAM OLARAK iki farklı takım bulduysak,
        # aradaki küçük bloğu incele.
        if len(found) == 2:

            block_start = max(0, i - 2)
            block_end = min(len(lines), i + 6)

            block = "\n".join(lines[block_start:block_end])

            score = parse_score(block)
            status = detect_status(block)

            home = found[0]
            away = found[1]

            match = make_match(
                home,
                away,
                current_date,
                score,
                status
            )

            if match:
                matches.append(match)

        i += 1

    return matches


# ============================================================
# SADECE GÜVENİLİR MAÇLARI FİLTRELE
# ============================================================

def validate_matches(matches):

    valid = []
    seen = set()

    for m in matches:

        if not m:
            continue

        home = m["home"]
        away = m["away"]

        if home not in TEAMS:
            continue

        if away not in TEAMS:
            continue

        if home == away:
            continue

        key = (
            m["date"],
            home,
            away
        )

        if key in seen:
            continue

        seen.add(key)
        valid.append(m)

    return valid


# ============================================================
# SAYFAYI ÇEK
# ============================================================

def scrape():

    print("=" * 60)
    print("🏀 EUROLEAGUE SCRAPER")
    print("=" * 60)

    print(
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    all_texts = []

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

        # Widget'ın JS ile oluşmasını bekle
        time.sleep(8)

        # Biraz aşağı kaydır.
        # Broadage widget'ları lazy-load olabilir.
        for _ in range(5):
            page.mouse.wheel(0, 1000)
            time.sleep(1)

        page.mouse.wheel(0, -6000)

        time.sleep(3)

        # ----------------------------------------------------
        # ANA SAYFA
        # ----------------------------------------------------

        try:
            body_text = page.locator("body").inner_text(
                timeout=5000
            )
        except Exception:
            body_text = ""

        if body_text:
            all_texts.append(
                ("MAIN_PAGE", body_text)
            )

        # ----------------------------------------------------
        # BROADAGE / FIXTURE DOM
        # ----------------------------------------------------

        fixture_texts = extract_fixture_rows(page)

        print(
            f'🔎 Broadage/fixture DOM bloğu: '
            f'{len(fixture_texts)}'
        )

        for idx, text in enumerate(fixture_texts):
            all_texts.append(
                (f"FIXTURE_{idx}", text)
            )

        # ----------------------------------------------------
        # IFRAMELAR
        # ----------------------------------------------------

        frames = page.frames

        print(
            f"🔎 iframe/frame: {len(frames)}"
        )

        for idx, frame in enumerate(frames):

            if frame == page.main_frame:
                continue

            try:
                frame_url = frame.url

                print(
                    f"   iframe {idx}: {frame_url[:160]}"
                )

                text = frame.locator(
                    "body"
                ).inner_text(
                    timeout=3000
                )

                if text.strip():
                    all_texts.append(
                        (
                            f"IFRAME_{idx}",
                            text
                        )
                    )

            except Exception:
                continue

        # ----------------------------------------------------
        # DEBUG
        # ----------------------------------------------------

        try:
            DEBUG_HTML.write_text(
                page.content(),
                encoding="utf-8"
            )
        except Exception:
            pass

        debug_parts = []

        for name, text in all_texts:
            debug_parts.append(
                f"\n\n================ {name} ================\n"
            )
            debug_parts.append(text)

        DEBUG_TEXT.write_text(
            "\n".join(debug_parts),
            encoding="utf-8"
        )

        print(
            f"📄 Toplanan metin: "
            f"{sum(len(x[1]) for x in all_texts)} karakter"
        )

        browser.close()

    # ========================================================
    # PARSE
    # ========================================================

    raw_matches = []

    for source_name, text in all_texts:

        parsed = parse_fixture_text(text)

        if parsed:
            print(
                f"   ✓ {source_name}: "
                f"{len(parsed)} aday"
            )

        raw_matches.extend(parsed)

    matches = validate_matches(raw_matches)

    # ========================================================
    # TARİHE GÖRE SIRALA
    # ========================================================

    matches.sort(
        key=lambda x: (
            x["date"],
            x["home"],
            x["away"]
        )
    )

    # ========================================================
    # DUPLICATE TEMİZLE
    # ========================================================

    unique = {}

    for match in matches:

        key = (
            match["date"],
            match["home"],
            match["away"]
        )

        unique[key] = match

    matches = list(unique.values())

    print(
        f"🏀 Bulunan gerçek EuroLeague maçı: "
        f"{len(matches)}"
    )

    for match in matches:
        score = match["score"]

        if (
            score["home"] is not None
            and score["away"] is not None
        ):
            score_text = (
                f'{score["home"]}-{score["away"]}'
            )
        else:
            score_text = "-"

        print(
            f'  {match["date"]} | '
            f'{match["home"]} - {match["away"]} | '
            f'{score_text} | '
            f'{match["status"]}'
        )

    return matches


# ============================================================
# ESKİ VERİYİ KORU
# ============================================================

def load_old_data():

    if not OUTPUT.exists():
        return {
            "source": URL,
            "updatedAt": datetime.now(
                timezone.utc
            ).isoformat(),
            "matches": []
        }

    try:
        data = json.loads(
            OUTPUT.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(data, dict):
            raise ValueError()

        return data

    except Exception:
        return {
            "source": URL,
            "updatedAt": datetime.now(
                timezone.utc
            ).isoformat(),
            "matches": []
        }


# ============================================================
# MERGE
# ============================================================

def save_data(new_matches):

    old_data = load_old_data()

    old_matches = old_data.get(
        "matches",
        []
    )

    merged = {}

    # Önce eski veriler
    for match in old_matches:

        if not isinstance(match, dict):
            continue

        key = (
            match.get("date"),
            match.get("home"),
            match.get("away")
        )

        if all(key):
            merged[key] = match

    # Yeni veriler üzerine yaz
    for match in new_matches:

        key = (
            match["date"],
            match["home"],
            match["away"]
        )

        # Eski kaydı koruyarak güncelle
        if key in merged:

            old = merged[key]

            # Yeni skor varsa güncelle
            if (
                match["score"]["home"] is not None
                and match["score"]["away"] is not None
            ):
                old["score"] = match["score"]
                old["winner"] = match["winner"]

            old["status"] = match["status"]
            old["source"] = match["source"]

            merged[key] = old

        else:
            merged[key] = match

    final_matches = list(
        merged.values()
    )

    final_matches.sort(
        key=lambda x: (
            x.get("date", ""),
            x.get("home", ""),
            x.get("away", "")
        )
    )

    result = {
        "source": URL,
        "league": "EuroLeague",
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "matches": final_matches
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"💾 data.json yazıldı"
    )

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

    try:

        matches = scrape()

        if not matches:
            print(
                "⚠️ Gerçek fixture bulunamadı."
            )
            print(
                "📁 iddaa-rendered.html ve "
                "iddaa-rendered.txt oluşturuldu."
            )

            # Eski data.json'ı bozma
            raise SystemExit(0)

        save_data(matches)

        print(
            "✅ EuroLeague scraper tamamlandı."
        )

    except Exception as e:

        print(
            f"❌ SCRAPER HATASI: {e}"
        )

        raise
