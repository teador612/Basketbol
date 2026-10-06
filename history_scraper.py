import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


# ============================================================
# AYARLAR
# ============================================================

DATA_FILE = Path("data.json")
HISTORY_FILE = Path("history.json")

MACKOLIK_BASE = "https://arsiv.mackolik.com"

SEASON = "2026/2027"

LAST_N = 5


# ============================================================
# TAKIMLAR
# Mackolik takım ID'leri
# ============================================================

TEAM_IDS = {
    "Anadolu Efes": 44,
}


# ============================================================
# TAKIM İSİMLERİ
# ============================================================

ALIASES = {
    "Paris": "Paris Basketball",
    "Paris Basket": "Paris Basketball",
    "Paris Basketball": "Paris Basketball",

    "ASVEL": "LDLC ASVEL",
    "Asvel": "LDLC ASVEL",
    "Asvel Lyon-Villeurbanne": "LDLC ASVEL",
    "LDLC ASVEL": "LDLC ASVEL",

    "BC Dubai": "Dubai Basketball",
    "Dubai": "Dubai Basketball",
    "Dubai Basketball": "Dubai Basketball",

    "Kızılyıldız": "Kızılyıldız",
    "Crvena Zvezda": "Kızılyıldız",

    "Maccabi Tel Aviv": "Maccabi Tel Aviv",
    "M.Tel Aviv": "Maccabi Tel Aviv",

    "Olimpia Milano": "Olimpia Milano",

    "Bayern Münih": "Bayern Münih",
    "B.Münih": "Bayern Münih",
    "Bayern Munich": "Bayern Münih",

    "Virtus Bologna": "Virtus Bologna",
    "Bologna": "Virtus Bologna",

    "Panathinaikos": "Panathinaikos",
    "Panathinaikos Aktor": "Panathinaikos",

    "Fenerbahçe": "Fenerbahçe Beko",
    "Fenerbahçe Tarfin": "Fenerbahçe Beko",
    "Fenerbahçe Beko": "Fenerbahçe Beko",

    "Valencia": "Valencia Basket",
    "Valencia Basket": "Valencia Basket",

    "Hapoel Tel Aviv": "Hapoel IBI Tel Aviv",
    "H.Tel Aviv": "Hapoel IBI Tel Aviv",
    "Hapoel IBI Tel Aviv": "Hapoel IBI Tel Aviv",

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
    if not name:
        return ""

    name = name.strip()

    return ALIASES.get(name, name)


# ============================================================
# DATA.JSON'DAN TAKIMLARI AL
# ============================================================

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


# ============================================================
# TAKIM SAYFASI
# ============================================================

def team_url(team):

    team_id = TEAM_IDS.get(team)

    if not team_id:
        return None

    return (
        f"{MACKOLIK_BASE}"
        f"/Basketbol-Takim/{team_id}"
    )


# ============================================================
# TAKIM MAÇLARINI AL
# ============================================================

def parse_team_matches(page, team, url):

    print(f"\n🏀 {team}")

    print(f"   🌐 {url}")

    try:

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(2500)

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

    in_euroleague = False

    for i, line in enumerate(lines):

        low = line.lower()

        # ----------------------------------------------------
        # EuroLeague başlangıcı
        # ----------------------------------------------------

        if "euroleague" in low:

            in_euroleague = True

            continue

        if not in_euroleague:
            continue

        # ----------------------------------------------------
        # Başka lig bölümü
        # ----------------------------------------------------

        if (
            "türkiye sigorta" in low
            or "bsl" in low
            or "basketbol süper ligi" in low
            or "acb ligi" in low
        ):
            continue

        # ----------------------------------------------------
        # Tarih satırı
        # ----------------------------------------------------

        date_match = re.match(
            r"^(\d{1,2}\.\d{1,2}\.\d{4})",
            line
        )

        if not date_match:
            continue

        date_raw = date_match.group(1)

        # ----------------------------------------------------
        # Skor ara
        #
        # Örnek:
        #
        # 24.09.2026 | Image | MS | Barcelona | 89-82 |
        # Image | Anadolu Efes | IY 45-44
        # ----------------------------------------------------

        score_match = re.search(
            r"\b(\d{1,3})-(\d{1,3})\b",
            line
        )

        if not score_match:
            continue

        home_score = int(score_match.group(1))
        away_score = int(score_match.group(2))

        before_score = line[:score_match.start()]
        after_score = line[score_match.end():]

        # ----------------------------------------------------
        # | parçalarına ayır
        # ----------------------------------------------------

        before_parts = [
            x.strip()
            for x in before_score.split("|")
            if x.strip()
        ]

        after_parts = [
            x.strip()
            for x in after_score.split("|")
            if x.strip()
        ]

        # ----------------------------------------------------
        # Takım isimlerini bul
        # ----------------------------------------------------

        home = None
        away = None

        # Skordan önceki son anlamlı takım
        for part in reversed(before_parts):

            clean = part.strip()

            if (
                clean
                and clean.lower() not in {
                    "image",
                    "ms",
                    "v"
                }
                and not re.match(
                    r"^\d+$",
                    clean
                )
            ):

                home = normalize_team(clean)

                break

        # Skordan sonraki ilk anlamlı takım
        for part in after_parts:

            clean = part.strip()

            if (
                clean
                and clean.lower() not in {
                    "image",
                    "iy",
                    "ms"
                }
                and not clean.startswith("IY")
            ):

                away = normalize_team(clean)

                break

        if not home or not away:
            continue

        # ----------------------------------------------------
        # Tarih
        # ----------------------------------------------------

        try:

            date_obj = datetime.strptime(
                date_raw,
                "%d.%m.%Y"
            )

            date_iso = date_obj.strftime(
                "%Y-%m-%d"
            )

        except Exception:
            continue

        current = normalize_team(team)

        if (
            current != home
            and current != away
        ):
            continue

        matches.append({
            "date": date_iso,
            "home": home,
            "away": away,
            "homeScore": home_score,
            "awayScore": away_score
        })

    # ========================================================
    # TEKRARLARI TEMİZLE
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

    matches.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    print(
        f"   ✅ Bulunan tamamlanmış maç: {len(matches)}"
    )

    # Son maçları göster
    for match in matches[:5]:

        print(
            f"      {match['date']} | "
            f"{match['home']} "
            f"{match['homeScore']}-"
            f"{match['awayScore']} "
            f"{match['away']}"
        )

    return matches


# ============================================================
# SON 5 İÇ SAHA / DEPLASMAN
# ============================================================

def calculate_stats(history, team):

    team = normalize_team(team)

    home_games = [
        m for m in history
        if normalize_team(m["home"]) == team
    ]

    away_games = [
        m for m in history
        if normalize_team(m["away"]) == team
    ]

    home_games.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    away_games.sort(
        key=lambda x: x["date"],
        reverse=True
    )

    home_games = home_games[:LAST_N]
    away_games = away_games[:LAST_N]

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

    def avg(values):

        if not values:
            return None

        return round(
            sum(values) / len(values),
            2
        )

    return {
        "home": {
            "games": len(home_games),
            "scored": avg(home_for),
            "conceded": avg(home_against),
            "matches": home_games
        },

        "away": {
            "games": len(away_games),
            "scored": avg(away_for),
            "conceded": avg(away_against),
            "matches": away_games
        }
    }


# ============================================================
# ANA
# ============================================================

def main():

    print("=" * 60)
    print("🏀 EUROLEAGUE GEÇMİŞ VERİ SCRAPER")
    print("=" * 60)

    teams = load_fixture_teams()

    if not teams:

        print("❌ data.json içinde takım bulunamadı")

        return

    print(
        f"📦 Fikstürde bulunan takım: {len(teams)}"
    )

    all_matches = {}

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        for team in teams:

            url = team_url(team)

            if not url:

                print(
                    f"\n⚠️ {team} için "
                    f"Mackolik ID tanımlı değil"
                )

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

    # ========================================================
    # GEÇMİŞ
    # ========================================================

    history = list(
        all_matches.values()
    )

    history.sort(
        key=lambda x: (
            x["date"],
            x["home"],
            x["away"]
        )
    )

    # ========================================================
    # TAKIM İSTATİSTİKLERİ
    # ========================================================

    team_stats = {}

    for team in teams:

        team_stats[team] = calculate_stats(
            history,
            team
        )

    # ========================================================
    # HISTORY.JSON
    # ========================================================

    output = {
        "source": MACKOLIK_BASE,
        "season": SEASON,
        "lastN": LAST_N,
        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "matches": history,
        "teamStats": team_stats
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

    # ========================================================
    # SONUÇ
    # ========================================================

    print("\n" + "=" * 60)
    print("📊 SONUÇ")
    print("=" * 60)

    print(
        f"🏀 Toplam geçmiş maç: {len(history)}"
    )

    print(
        f"👥 Takım sayısı: {len(team_stats)}"
    )

    print(
        f"💾 Dosya: {HISTORY_FILE}"
    )

    print("\n📋 SON 5 İÇ SAHA / DEPLASMAN")

    for team in teams:

        stats = team_stats[team]

        home = stats["home"]
        away = stats["away"]

        print(f"\n🏀 {team}")

        print(
            f"   🏠 İç saha: "
            f"{home['games']} maç"
        )

        if home["games"]:

            print(
                f"      Attı: "
                f"{home['scored']}"
            )

            print(
                f"      Yedi: "
                f"{home['conceded']}"
            )

        else:

            print("      Veri yok")

        print(
            f"   ✈️ Deplasman: "
            f"{away['games']} maç"
        )

        if away["games"]:

            print(
                f"      Attı: "
                f"{away['scored']}"
            )

            print(
                f"      Yedi: "
                f"{away['conceded']}"
            )

        else:

            print("      Veri yok")

    print("\n✅ Geçmiş veri oluşturuldu.")


if __name__ == "__main__":
    main()
