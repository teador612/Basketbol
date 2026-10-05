import json
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

STANDING_URL = "https://arsiv.mackolik.com/Basketball/Standing/Default.aspx?id=1644"

DATA_FILE = Path("data.json")
HISTORY_FILE = Path("history.json")

SEASON = "2026/2027"

# ---------------------------------------------------------
# TAKIM İSİMLERİ
# ---------------------------------------------------------

ALIASES = {
    "Paris": "Paris Basketball",
    "Paris Basket": "Paris Basketball",

    "ASVEL": "LDLC ASVEL",
    "Asvel": "LDLC ASVEL",
    "Asvel Lyon-Villeurbanne": "LDLC ASVEL",

    "BC Dubai": "Dubai Basketball",
    "Dubai": "Dubai Basketball",

    "Kızılyıldız": "Kızılyıldız",
    "Crvena Zvezda": "Kızılyıldız",

    "Maccabi Tel Aviv": "Maccabi Tel Aviv",
    "M.Tel Aviv": "Maccabi Tel Aviv",

    "Olimpia Milano": "Olimpia Milano",

    "Bayern Münih": "Bayern Münih",
    "B.Münih": "Bayern Münih",

    "Virtus Bologna": "Virtus Bologna",
    "Bologna": "Virtus Bologna",

    "Panathinaikos": "Panathinaikos",
    "Panathinaikos Aktor": "Panathinaikos",

    "Fenerbahçe": "Fenerbahçe Beko",
    "Fenerbahçe Tarfin": "Fenerbahçe Beko",

    "Valencia": "Valencia Basket",
    "Valencia Basket": "Valencia Basket",

    "Hapoel Tel Aviv": "Hapoel IBI Tel Aviv",
    "H.Tel Aviv": "Hapoel IBI Tel Aviv",

    "Real Madrid": "Real Madrid",

    "Partizan": "Partizan",
    "KK Partizan": "Partizan",

    "Olympiakos": "Olympiakos",

    "Anadolu Efes": "Anadolu Efes",

    "Barcelona": "FC Barcelona",
    "FC Barcelona": "FC Barcelona",

    "Zalgiris": "Zalgiris Kaunas",
    "Zalgiris Kaunas": "Zalgiris Kaunas",

    "Baskonia": "Baskonia",
    "Baskonia Vitoria-Gasteiz": "Baskonia",

    "Beşiktaş": "Beşiktaş",
}


def normalize_team(name):
    name = name.strip()

    if name in ALIASES:
        return ALIASES[name]

    return name


# ---------------------------------------------------------
# DATA.JSON'DAN TAKIMLARI AL
# ---------------------------------------------------------

def load_fixture_teams():
    if not DATA_FILE.exists():
        print("❌ data.json bulunamadı")
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    teams = set()

    for match in data.get("matches", []):
        home = match.get("home")
        away = match.get("away")

        if home:
            teams.add(normalize_team(home))

        if away:
            teams.add(normalize_team(away))

    return sorted(teams)


# ---------------------------------------------------------
# MACKOLIK TAKIM LİNKLERİNİ BUL
# ---------------------------------------------------------

def get_team_urls(page):
    print("\n🔎 Mackolik EuroLeague takım sayfaları aranıyor...")

    page.goto(STANDING_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    links = page.locator("a")

    result = {}

    for i in range(links.count()):
        try:
            a = links.nth(i)

            text = a.inner_text().strip()
            href = a.get_attribute("href")

            if not text or not href:
                continue

            if "/Basketbol-Takim/" not in href:
                continue

            team = normalize_team(text)

            if team not in result:
                if href.startswith("/"):
                    href = "https://arsiv.mackolik.com" + href

                result[team] = href

        except Exception:
            continue

    print(f"✅ Bulunan takım sayfası: {len(result)}")

    return result


# ---------------------------------------------------------
# TAKIM MAÇLARINI PARSE ET
# ---------------------------------------------------------

def parse_team_matches(page, team, url):
    print(f"\n🏀 {team}")

    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(1500)

        text = page.locator("body").inner_text()

    except Exception as e:
        print(f"   ❌ Sayfa alınamadı: {e}")
        return []

    lines = [
        x.strip()
        for x in text.splitlines()
        if x.strip()
    ]

    matches = []

    # EuroLeague bölümünü bul
    start = None

    for i, line in enumerate(lines):
        if "EuroLeague" in line and "Normal Sezon" in line:
            start = i
            break

    if start is None:
        print("   ⚠️ EuroLeague bölümü bulunamadı")
        return []

    # Bir sonraki lig başladığında dur
    end = len(lines)

    for i in range(start + 1, len(lines)):
        line = lines[i]

        if (
            "ACB Ligi" in line
            or "İspanya" in line
            or "Türkiye" in line
            or "Fransa" in line
            or "Almanya" in line
            or "İtalya" in line
        ):
            end = i
            break

    euro_lines = lines[start:end]

    # Örnek:
    #
    # 24.09.2026 | MS | BC Dubai | 78-77 | Real Madrid | IY 38-44
    #
    # veya:
    #
    # 27.09.2026 | MS | Real Madrid | 89-87 | Unicaja
    #

    date_re = re.compile(r"^\d{2}\.\d{2}\.\d{4}")

    score_re = re.compile(r"^\d{1,3}-\d{1,3}$")

    for line in euro_lines:

        if not date_re.match(line):
            continue

        # İçindeki parçaları temizle
        parts = [
            p.strip()
            for p in re.split(r"\s*\|\s*", line)
            if p.strip()
        ]

        if len(parts) < 4:
            continue

        date_raw = parts[0]

        # Skoru bul
        score_index = None

        for i, part in enumerate(parts):
            if score_re.match(part):
                score_index = i
                break

        if score_index is None:
            continue

        if score_index < 2:
            continue

        if score_index + 1 >= len(parts):
            continue

        try:
            home = normalize_team(parts[score_index - 1])
            score = parts[score_index]
            away = normalize_team(parts[score_index + 1])

            # Bazı sayfalarda MS ayrı bir parça olabilir.
            # Ev/deplasman takımını doğrudan skorun iki yanından alıyoruz.

            home_score, away_score = map(
                int,
                score.split("-")
            )

            date_obj = datetime.strptime(
                date_raw,
                "%d.%m.%Y"
            )

            date_iso = date_obj.strftime("%Y-%m-%d")

        except Exception:
            continue

        # Takım gerçekten maçın içinde mi?
        current = normalize_team(team)

        if current != home and current != away:
            continue

        matches.append({
            "date": date_iso,
            "home": home,
            "away": away,
            "homeScore": home_score,
            "awayScore": away_score
        })

    # Aynı maçı tekrar alma
    unique = {}

    for m in matches:
        key = (
            m["date"],
            m["home"],
            m["away"]
        )

        unique[key] = m

    matches = list(unique.values())

    matches.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    print(f"   ✅ Tamamlanan EuroLeague maçı: {len(matches)}")

    return matches


# ---------------------------------------------------------
# ANA
# ---------------------------------------------------------

def main():

    print("=" * 60)
    print("🏀 EUROLEAGUE GEÇMİŞ VERİ SCRAPER")
    print("=" * 60)

    teams = load_fixture_teams()

    if not teams:
        print("❌ data.json içinde takım bulunamadı")
        return

    print(f"\n📦 Fikstürde bulunan takım: {len(teams)}")

    all_matches = {}

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        team_urls = get_team_urls(page)

        for team in teams:

            url = team_urls.get(team)

            # Alias eşleşmesi için tekrar dene
            if not url:
                for source_name, source_url in team_urls.items():

                    if normalize_team(source_name) == normalize_team(team):
                        url = source_url
                        break

            if not url:
                print(f"\n⚠️ {team} için Mackolik sayfası bulunamadı")
                continue

            matches = parse_team_matches(
                page,
                team,
                url
            )

            for match in matches:

                key = (
                    match["date"],
                    match["home"],
                    match["away"]
                )

                all_matches[key] = match

            time.sleep(0.3)

        browser.close()

    history = list(all_matches.values())

    history.sort(
        key=lambda x: (
            x["date"],
            x["home"],
            x["away"]
        )
    )

    output = {
        "source": STANDING_URL,
        "season": SEASON,
        "updatedAt": datetime.utcnow().isoformat() + "Z",
        "matches": history
    }

    with open(
        HISTORY_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("\n" + "=" * 60)
    print("📊 SONUÇ")
    print("=" * 60)

    print(f"🏀 Toplam geçmiş maç: {len(history)}")
    print(f"💾 Dosya: {HISTORY_FILE}")

    # -----------------------------------------------------
    # SON 5 İÇ SAHA / DEPLASMAN KONTROLÜ
    # -----------------------------------------------------

    print("\n📋 TAKIM BAZLI SON 5")

    for team in teams:

        home_games = [
            m for m in history
            if normalize_team(m["home"]) == normalize_team(team)
        ]

        away_games = [
            m for m in history
            if normalize_team(m["away"]) == normalize_team(team)
        ]

        home_games.sort(
            key=lambda x: x["date"],
            reverse=True
        )

        away_games.sort(
            key=lambda x: x["date"],
            reverse=True
        )

        home_games = home_games[:5]
        away_games = away_games[:5]

        home_for = [
            m["homeScore"]
            for m in home_games
        ]

        home_against = [
            m["awayScore"]
            for m in home_games
        ]

        away_for = [
            m["awayScore"]
            for m in away_games
        ]

        away_against = [
            m["homeScore"]
            for m in away_games
        ]

        print(f"\n{team}")

        print(
            f"   🏠 İç saha: {len(home_games)} maç"
        )

        if home_games:
            print(
                f"      Attı: {sum(home_for) / len(home_for):.1f}"
            )
            print(
                f"      Yedi: {sum(home_against) / len(home_against):.1f}"
            )

        print(
            f"   ✈️ Deplasman: {len(away_games)} maç"
        )

        if away_games:
            print(
                f"      Attı: {sum(away_for) / len(away_for):.1f}"
            )
            print(
                f"      Yedi: {sum(away_against) / len(away_against):.1f}"
            )

    print("\n✅ Geçmiş veri oluşturuldu.")


if __name__ == "__main__":
    main()
