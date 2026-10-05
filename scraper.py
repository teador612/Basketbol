import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright
URL = "https://www.iddaa.com/euroleague-avrupa-basketbol-ligi"
OUTPUT = Path("data.json")
# EuroLeague takımları
TEAMS = [
    "Anadolu Efes",
    "AS Monaco",
    "Baskonia",
    "Bayern Münih",
    "Dubai Basketball",
    "Olimpia Milano",
    "FC Barcelona",
    "Fenerbahçe Beko",
    "Hapoel IBI Tel Aviv",
    "Kızılyıldız",
    "LDLC ASVEL",
    "Maccabi Rapyd Tel Aviv",
    "Olympiakos",
    "Panathinaikos",
    "Paris Basketball",
    "Partizan",
    "Real Madrid",
    "Valencia Basket",
    "Virtus Bologna",
    "Zalgiris Kaunas",
]
# Sayfada farklı yazılabilen isimler
TEAM_ALIASES = {
    "Anadolu Efes": [
        "Anadolu Efes",
        "A. Efes",
    ],
    "AS Monaco": [
        "AS Monaco",
        "Monaco",
    ],
    "Baskonia": [
        "Baskonia",
        "Kosner Baskonia",
    ],
    "Bayern Münih": [
        "Bayern Münih",
        "Bayern Munich",
        "B. Münih",
    ],
    "Dubai Basketball": [
        "Dubai Basketball",
        "Dubai BC",
        "Dubai Basketball FC",
    ],
    "Olimpia Milano": [
        "Olimpia Milano",
        "EA7 Emporio Armani Milan",
        "EA7 Emporio Armani Milano",
    ],
    "FC Barcelona": [
        "FC Barcelona",
        "Barcelona",
    ],
    "Fenerbahçe Beko": [
        "Fenerbahçe Beko",
        "Fenerbahce",
        "Fenerbahçe",
        "Fenerbahce Tarfin",
    ],
    "Hapoel IBI Tel Aviv": [
        "Hapoel IBI Tel Aviv",
        "Hapoel Tel Aviv",
        "Hap.Tel Aviv",
    ],
    "Kızılyıldız": [
        "Kızılyıldız",
        "Crvena Zvezda",
        "C.Zvezda",
    ],
    "LDLC ASVEL": [
        "LDLC ASVEL",
        "ASVEL",
    ],
    "Maccabi Rapyd Tel Aviv": [
        "Maccabi Rapyd Tel Aviv",
        "Maccabi Tel Aviv",
        "Maccabi",
    ],
    "Olympiakos": [
        "Olympiakos",
        "Olympiacos",
    ],
    "Panathinaikos": [
        "Panathinaikos",
        "Panathinaikos AKTOR",
    ],
    "Paris Basketball": [
        "Paris Basketball",
        "Paris BC",
        "Paris",
    ],
    "Partizan": [
        "Partizan",
    ],
    "Real Madrid": [
        "Real Madrid",
        "R. Madrid",
    ],
    "Valencia Basket": [
        "Valencia Basket",
        "Valencia",
    ],
    "Virtus Bologna": [
        "Virtus Bologna",
        "Virtus Olidata Bologna",
        "V. Bologna",
    ],
    "Zalgiris Kaunas": [
        "Zalgiris Kaunas",
        "Zalgiris",
    ],
}
def normalize(text):
    if not text:
        return ""
    text = text.lower()
    replacements = {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "â": "a",
        "î": "i",
        "û": "u",
    }
    for a, b in replacements.items():
        text = text.replace(a, b)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
def find_team(text):
    n = normalize(text)
    # Önce uzun isimlerden başla
    candidates = []
    for official, aliases in TEAM_ALIASES.items():
        for alias in aliases:
            a = normalize(alias)
            if a and a in n:
                candidates.append((len(a), official))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]
def parse_score(text):
    """
    94 84
    94-84
    94 : 84
    gibi skorları yakalar.
    """
    patterns = [
        r"\b(\d{2,3})\s*[-:]\s*(\d{2,3})\b",
        r"\b(\d{2,3})\s+(\d{2,3})\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            a = int(m.group(1))
            b = int(m.group(2))
            # Saatleri skor zannetme
            if 0 <= a <= 200 and 0 <= b <= 200:
                return a, b
    return None, None
def extract_date(text):
    """
    29 Sep 2026
    30 Sep 2026
    5 Oct 2026
    gibi tarihleri yakalar.
    """
    patterns = [
        r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})\b",
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
    ]
    months = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
        "January": 1,
        "February": 2,
        "March": 3,
        "April": 4,
        "May": 5,
        "June": 6,
        "July": 7,
        "August": 8,
        "September": 9,
        "October": 10,
        "November": 11,
        "December": 12,
    }
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            day = int(m.group(1))
            month = months[m.group(2).title()]
            year = int(m.group(3))
            return f"{year:04d}-{month:02d}-{day:02d}"
    return None
def detect_status(text):
    n = normalize(text)
    if "ft" in n or "finished" in n or "tamamlandi" in n:
        return "finished"
    if (
        "live" in n
        or "canli" in n
        or "1. yarı" in n
        or "2. yarı" in n
        or "quarter" in n
    ):
        return "live"
    return "scheduled"
def build_match(home, away, score_home, score_away, date, raw):
    if score_home is not None and score_away is not None:
        if score_home > score_away:
            winner = "home"
        elif score_away > score_home:
            winner = "away"
        else:
            winner = "draw"
    else:
        winner = None
    return {
        "id": normalize(home) + "__" + normalize(away) + "__" + str(date),
        "league": "EuroLeague",
        "home": home,
        "away": away,
        "date": date,
        "score": {
            "home": score_home,
            "away": score_away,
        },
        "status": detect_status(raw),
        "winner": winner,
        "source": "iddaa.com",
    }
async def get_page_text(page):
    print("🌐 iddaa.com açılıyor...")
    await page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=90000,
    )
    print("✅ Sayfa açıldı")
    # Next.js / Broadage widget'ın yüklenmesi için zaman tanı
    await page.wait_for_timeout(8000)
    # Widget'ın kendisini beklemeyi dene
    selectors = [
        '[id*="DOM_element_id"]',
        '[class*="broadage"]',
        '[class*="Broadage"]',
        'iframe',
    ]
    for selector in selectors:
        try:
            count = await page.locator(selector).count()
            if count:
                print(f"🔎 {selector}: {count} adet")
        except Exception:
            pass
    text = await page.locator("body").inner_text()
    return text
async def main():
    print("=" * 60)
    print("🏀 EUROLEAGUE SCRAPER")
    print("=" * 60)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        page = await browser.new_page(
            viewport={
                "width": 1440,
                "height": 1000,
            },
            locale="tr-TR",
        )
        try:
            text = await get_page_text(page)
            print(f"📄 Sayfa metni: {len(text)} karakter")
            # Debug için
            Path("iddaa-rendered.txt").write_text(
                text,
                encoding="utf-8",
            )
            print("📁 iddaa-rendered.txt oluşturuldu")
            matches = []
            lines = [
                x.strip()
                for x in text.splitlines()
                if x.strip()
            ]
            current_date = None
            for i, line in enumerate(lines):
                possible_date = extract_date(line)
                if possible_date:
                    current_date = possible_date
                # Bu satır veya yakınındaki birkaç satır içinde
                # iki EuroLeague takımı arıyoruz.
                block = " ".join(lines[max(0, i - 2): min(len(lines), i + 6)])
                teams = []
                for official in TEAM_ALIASES:
                    if find_team(block) == official:
                        if official not in teams:
                            teams.append(official)
                # Daha sağlam takım tespiti
                found = []
                for official, aliases in TEAM_ALIASES.items():
                    for alias in aliases:
                        if normalize(alias) in normalize(block):
                            if official not in found:
                                found.append(official)
                if len(found) < 2:
                    continue
                # Aynı takımın iki kez yakalanmasını engelle
                found = list(dict.fromkeys(found))
                if len(found) < 2:
                    continue
                home = found[0]
                away = found[1]
                score_home, score_away = parse_score(block)
                # Aynı maç için tarih yoksa o anki başlığı kullan
                match_date = current_date
                if not match_date:
                    match_date = datetime.now().strftime("%Y-%m-%d")
                raw = block
                match = build_match(
                    home,
                    away,
                    score_home,
                    score_away,
                    match_date,
                    raw,
                )
                if not any(x["id"] == match["id"] for x in matches):
                    matches.append(match)
            # Eğer genel text parser yeterli sonuç vermediyse,
            # DOM elemanlarını ayrıca tarıyoruz.
            if len(matches) < 2:
                print("⚠️ Metin taraması az maç buldu.")
                print("🔎 DOM taraması başlıyor...")
                elements = await page.locator(
                    "div, li, article, section"
                ).all()
                for element in elements:
                    try:
                        txt = (await element.inner_text()).strip()
                    except Exception:
                        continue
                    if not txt or len(txt) > 500:
                        continue
                    found = []
                    for official, aliases in TEAM_ALIASES.items():
                        for alias in aliases:
                            if normalize(alias) in normalize(txt):
                                if official not in found:
                                    found.append(official)
                    if len(found) < 2:
                        continue
                    found = list(dict.fromkeys(found))
                    home = found[0]
                    away = found[1]
                    score_home, score_away = parse_score(txt)
                    date = extract_date(txt)
                    if not date:
                        date = current_date
                    if not date:
                        date = datetime.now().strftime("%Y-%m-%d")
                    match = build_match(
                        home,
                        away,
                        score_home,
                        score_away,
                        date,
                        txt,
                    )
                    if not any(x["id"] == match["id"] for x in matches):
                        matches.append(match)
            # Tarihe göre sırala
            matches.sort(
                key=lambda x: (
                    x.get("date", ""),
                    x.get("home", ""),
                    x.get("away", ""),
                )
            )
            print()
            print(f"🏀 Bulunan EuroLeague maçı: {len(matches)}")
            for match in matches:
                score = match["score"]
                if (
                    score["home"] is not None
                    and score["away"] is not None
                ):
                    result = f'{score["home"]}-{score["away"]}'
                else:
                    result = "-"
                print(
                    f'  {match["date"]} | '
                    f'{match["home"]} - {match["away"]} | '
                    f'{result}'
                )
            if not matches:
                print()
                print("❌ Hiç EuroLeague maçı bulunamadı.")
                print("📁 iddaa-rendered.txt dosyasını kontrol et.")
                await browser.close()
                return
            # Tarihe göre grupla
            output = {}
            for match in matches:
                date = match["date"]
                if date not in output:
                    output[date] = []
                output[date].append(match)
            # Mevcut dosya varsa geçmişi koru
            old = {}
            if OUTPUT.exists():
                try:
                    old = json.loads(
                        OUTPUT.read_text(encoding="utf-8")
                    )
                    if not isinstance(old, dict):
                        old = {}
                except Exception:
                    old = {}
            # Yeni veriler mevcut tarihler için güncellensin,
            # eski tarihler silinmesin.
            for date, new_matches in output.items():
                if date not in old:
                    old[date] = new_matches
                    continue
                old_map = {
                    x.get("id"): x
                    for x in old[date]
                    if isinstance(x, dict)
                }
                for match in new_matches:
                    old_map[match["id"]] = match
                old[date] = list(old_map.values())
            OUTPUT.write_text(
                json.dumps(
                    old,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print()
            print(f"💾 {OUTPUT} yazıldı")
            print(f"📦 Toplam tarih: {len(old)}")
        finally:
            await browser.close()
    print()
    print("✅ EUROLeague scraper tamamlandı.")
if __name__ == "__main__":
    asyncio.run(main())
