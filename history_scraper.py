import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


# ============================================================
# AYARLAR
# ============================================================

DATA_FILE = Path("data.json")
HISTORY_FILE = Path("history.json")

URL = "https://www.iddaa.com/euroleague-avrupa-basketbol-ligi"

LAST_N = 5


# ============================================================
# TAKIM İSİMLERİ
# ============================================================

ALIASES = {
    "Anadolu Efes": "Anadolu Efes",
    "Efes": "Anadolu Efes",

    "Baskonia": "Baskonia",

    "Bayern Münih": "Bayern Münih",
    "B. Münih": "Bayern Münih",
    "Bayern Munich": "Bayern Münih",

    "Beşiktaş": "Beşiktaş",
    "Besiktas": "Beşiktaş",

    "Dubai Basketball": "Dubai Basketball",
    "Dubai BC": "Dubai Basketball",
    "Dubai": "Dubai Basketball",

    "FC Barcelona": "FC Barcelona",
    "Barcelona": "FC Barcelona",

    "Fenerbahçe Beko": "Fenerbahçe Beko",
    "Fenerbahce Beko": "Fenerbahçe Beko",
    "Fenerbahçe": "Fenerbahçe Beko",

    "Hapoel IBI Tel Aviv": "Hapoel IBI Tel Aviv",
    "Hap.Tel Aviv": "Hapoel IBI Tel Aviv",
    "Hapoel Tel Aviv": "Hapoel IBI Tel Aviv",

    "Kızılyıldız": "Kızılyıldız",
    "Kizilyildiz": "Kızılyıldız",

    "LDLC ASVEL": "LDLC ASVEL",
    "ASVEL": "LDLC ASVEL",

    "Maccabi Tel Aviv": "Maccabi Tel Aviv",
    "Maccabi Rapyd Tel Aviv": "Maccabi Tel Aviv",
    "Maccabi": "Maccabi Tel Aviv",

    "Olimpia Milano": "Olimpia Milano",
    "EA7 Emporio Armani Milan": "Olimpia Milano",
    "Milan": "Olimpia Milano",

    "Olympiakos": "Olympiakos",
    "Olympiacos": "Olympiakos",

    "Panathinaikos": "Panathinaikos",

    "Paris Basketball": "Paris Basketball",
    "Paris BC": "Paris Basketball",

    "Partizan": "Partizan",

    "Real Madrid": "Real Madrid",
    "R. Madrid": "Real Madrid",

    "Valencia Basket": "Valencia Basket",
    "Valencia": "Valencia Basket",

    "Virtus Bologna": "Virtus Bologna",
    "V. Bologna": "Virtus Bologna",

    "Zalgiris Kaunas": "Zalgiris Kaunas",
    "Zalgiris": "Zalgiris Kaunas",
}


def normalize_team(name):

    if not name:
        return ""

    name = str(name).strip()

    if name in ALIASES:
        return ALIASES[name]

    # Büyük/küçük harf toleransı
    low = name.lower()

    for key, value in ALIASES.items():

        if key.lower() == low:
            return value

    return name


# ============================================================
# DATA.JSON
# ============================================================

def load_teams():

    if not DATA_FILE.exists():

        raise RuntimeError(
            "data.json bulunamadı"
        )

    with open(
        DATA_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        data = json.load(f)

    teams = set()

    for match in data.get("matches", []):

        home = match.get("home")
        away = match.get("away")

        if home:
            teams.add(
                normalize_team(home)
            )

        if away:
            teams.add(
                normalize_team(away)
            )

    return sorted(teams)


# ============================================================
# JSON İÇİNDE RECURSIVE GEZ
# ============================================================

def walk_json(value):

    if isinstance(value, dict):

        yield value

        for child in value.values():

            yield from walk_json(child)

    elif isinstance(value, list):

        for child in value:

            yield from walk_json(child)


# ============================================================
# SKOR ÇÖZ
# ============================================================

def parse_score(value):

    if value is None:
        return None

    if isinstance(value, dict):

        # Muhtemel alanlar
        home_keys = [
            "homeScore",
            "home_score",
            "homePoints",
            "home_points",
            "scoreHome",
            "home"
        ]

        away_keys = [
            "awayScore",
            "away_score",
            "awayPoints",
            "away_points",
            "scoreAway",
            "away"
        ]

        home = None
        away = None

        for key in home_keys:

            if key in value:

                try:
                    home = int(value[key])
                    break
                except Exception:
                    pass

        for key in away_keys:

            if key in value:

                try:
                    away = int(value[key])
                    break
                except Exception:
                    pass

        if home is not None and away is not None:

            return home, away

        # İç içe score
        for child in value.values():

            result = parse_score(child)

            if result:
                return result

    if isinstance(value, str):

        match = re.search(
            r"\b(\d{2,3})\s*[-:]\s*(\d{2,3})\b",
            value
        )

        if match:

            return (
                int(match.group(1)),
                int(match.group(2))
            )

    return None


# ============================================================
# JSON'DAN MAÇ BUL
# ============================================================

def extract_matches_from_json(
    obj,
    teams
):

    matches = []

    team_set = set(teams)

    for item in walk_json(obj):

        if not isinstance(item, dict):
            continue

        # ----------------------------------------------------
        # Takım isimlerini bul
        # ----------------------------------------------------

        home = None
        away = None

        home_keys = [
            "home",
            "homeTeam",
            "home_team",
            "homeName",
            "homeTeamName"
        ]

        away_keys = [
            "away",
            "awayTeam",
            "away_team",
            "awayName",
            "awayTeamName"
        ]

        for key in home_keys:

            value = item.get(key)

            if isinstance(value, dict):

                value = (
                    value.get("name")
                    or value.get("teamName")
                    or value.get("shortName")
                )

            if value:

                normalized = normalize_team(
                    str(value)
                )

                if normalized in team_set:

                    home = normalized
                    break

        for key in away_keys:

            value = item.get(key)

            if isinstance(value, dict):

                value = (
                    value.get("name")
                    or value.get("teamName")
                    or value.get("shortName")
                )

            if value:

                normalized = normalize_team(
                    str(value)
                )

                if normalized in team_set:

                    away = normalized
                    break

        if not home or not away:
            continue

        # ----------------------------------------------------
        # Skor
        # ----------------------------------------------------

        score = None

        for key in [
            "score",
            "result",
            "finalScore",
            "matchScore"
        ]:

            if key in item:

                score = parse_score(
                    item[key]
                )

                if score:
                    break

        if not score:

            score = parse_score(item)

        if not score:
            continue

        home_score, away_score = score

        # ----------------------------------------------------
        # Tarih
        # ----------------------------------------------------

        date_value = None

        for key in [
            "date",
            "matchDate",
            "startDate",
            "startTime",
            "dateTime"
        ]:

            if key in item:

                date_value = item[key]

                if date_value:
                    break

        if not date_value:
            continue

        date_iso = parse_date(
            date_value
        )

        if not date_iso:
            continue

        matches.append({
            "date": date_iso,
            "home": home,
            "away": away,
            "homeScore": home_score,
            "awayScore": away_score
        })

    return matches


# ============================================================
# TARİH ÇÖZ
# ============================================================

def parse_date(value):

    if value is None:
        return None

    value = str(value).strip()

    # ISO
    try:

        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        return dt.strftime(
            "%Y-%m-%d"
        )

    except Exception:
        pass

    # DD.MM.YYYY
    match = re.search(
        r"(\d{1,2})\.(\d{1,2})\.(\d{4})",
        value
    )

    if match:

        try:

            dt = datetime.strptime(
                match.group(0),
                "%d.%m.%Y"
            )

            return dt.strftime(
                "%Y-%m-%d"
            )

        except Exception:
            pass

    # YYYY-MM-DD
    match = re.search(
        r"(\d{4})-(\d{2})-(\d{2})",
        value
    )

    if match:

        return match.group(0)

    return None


# ============================================================
# TAKIM İSTATİSTİĞİ
# ============================================================

def calculate_stats(
    history,
    team
):

    team = normalize_team(team)

    home_games = [
        m for m in history
        if m["home"] == team
    ]

    away_games = [
        m for m in history
        if m["away"] == team
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

    def average(values):

        if not values:
            return None

        return round(
            sum(values) / len(values),
            2
        )

    return {

        "home": {

            "games": len(home_games),

            "scored": average([
                x["homeScore"]
                for x in home_games
            ]),

            "conceded": average([
                x["awayScore"]
                for x in home_games
            ]),

            "matches": home_games
        },

        "away": {

            "games": len(away_games),

            "scored": average([
                x["awayScore"]
                for x in away_games
            ]),

            "conceded": average([
                x["homeScore"]
                for x in away_games
            ]),

            "matches": away_games
        }
    }


# ============================================================
# ANA
# ============================================================

def main():

    print("=" * 60)
    print("🏀 IDDAA.COM EUROLEAGUE GEÇMİŞ VERİ")
    print("=" * 60)

    teams = load_teams()

    print(
        f"📦 Takım sayısı: {len(teams)}"
    )

    captured_json = []

    captured_text = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context()

        page = context.new_page()

        # ----------------------------------------------------
        # Network JSON yakala
        # ----------------------------------------------------

        def response_handler(response):

            try:

                content_type = (
                    response.headers
                    .get("content-type", "")
                    .lower()
                )

                url = response.url

                if (
                    "json" not in content_type
                    and not url.lower().endswith(".json")
                ):
                    return

                text = response.text()

                if len(text) > 5_000_000:
                    return

                try:

                    obj = json.loads(text)

                    captured_json.append({
                        "url": url,
                        "data": obj
                    })

                except Exception:
                    pass

            except Exception:
                pass

        page.on(
            "response",
            response_handler
        )

        print("\n🌐 iddaa.com açılıyor...")

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        page.wait_for_timeout(
            8000
        )

        print(
            f"📡 Yakalanan JSON cevap: "
            f"{len(captured_json)}"
        )

        # ----------------------------------------------------
        # Body text
        # ----------------------------------------------------

        try:

            body = page.locator(
                "body"
            ).inner_text()

            captured_text.append(body)

        except Exception:
            pass

        # ----------------------------------------------------
        # Biraz daha bekle
        # ----------------------------------------------------

        page.wait_for_timeout(
            5000
        )

        browser.close()

    # ========================================================
    # JSON VERİLERİNDEN MAÇLARI ÇIKAR
    # ========================================================

    all_matches = {}

    print("\n🔎 JSON cevapları taranıyor...")

    for packet in captured_json:

        found = extract_matches_from_json(
            packet["data"],
            teams
        )

        if found:

            print(
                f"   ✅ {len(found)} maç: "
                f"{packet['url']}"
            )

        for match in found:

            key = (
                match["date"],
                match["home"],
                match["away"]
            )

            all_matches[key] = match

    # ========================================================
    # TEXT İÇİN BASİT KONTROL
    # ========================================================

    print(
        f"\n🏀 Toplam bulunan geçmiş maç: "
        f"{len(all_matches)}"
    )

    if not all_matches:

        print("\n❌ İddaa.com'dan geçmiş maç verisi alınamadı.")

        print(
            "❌ Sahte veri oluşturulmadı."
        )

        print(
            "📡 Yakalanan JSON: "
            f"{len(captured_json)}"
        )

        raise RuntimeError(
            "iddaa.com geçmiş maç veri kaynağı bulunamadı"
        )

    # ========================================================
    # GEÇMİŞ
    # ========================================================

    history = list(
        all_matches.values()
    )

    history.sort(
        key=lambda x: x["date"]
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
    # KAYDET
    # ========================================================

    output = {

        "source": URL,

        "league": "EuroLeague",

        "updatedAt": datetime.now(
            timezone.utc
        ).isoformat(),

        "lastN": LAST_N,

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
    # ÖZET
    # ========================================================

    print("\n" + "=" * 60)
    print("📊 SONUÇ")
    print("=" * 60)

    print(
        f"🏀 Geçmiş maç: {len(history)}"
    )

    print(
        f"👥 Takım: {len(team_stats)}"
    )

    print(
        f"💾 {HISTORY_FILE}"
    )

    print("\n📋 SON 5 İSTATİSTİK")

    for team in teams:

        stats = team_stats[team]

        h = stats["home"]
        a = stats["away"]

        print(f"\n🏀 {team}")

        print(
            f"   🏠 İç saha: "
            f"{h['games']} maç | "
            f"Attı: {h['scored']} | "
            f"Yedi: {h['conceded']}"
        )

        print(
            f"   ✈️ Deplasman: "
            f"{a['games']} maç | "
            f"Attı: {a['scored']} | "
            f"Yedi: {a['conceded']}"
        )

    print("\n✅ history.json oluşturuldu.")


if __name__ == "__main__":
    main()
