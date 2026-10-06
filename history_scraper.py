import json
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


DATA_FILE = Path("data.json")
HISTORY_FILE = Path("history.json")

URLS = [
    "https://www.iddaa.com/canli-skor/basketbol",
    "https://www.iddaa.com/euroleague-avrupa-basketbol-ligi",
]

LAST_N = 5


ALIASES = {
    "Paris": "Paris Basketball",
    "Paris Basket": "Paris Basketball",
    "Paris BC": "Paris Basketball",
    "Paris Basketball": "Paris Basketball",

    "ASVEL": "LDLC ASVEL",
    "Asvel": "LDLC ASVEL",
    "LDLC ASVEL": "LDLC ASVEL",

    "BC Dubai": "Dubai Basketball",
    "Dubai": "Dubai Basketball",
    "Dubai BC": "Dubai Basketball",
    "Dubai Basketball": "Dubai Basketball",

    "Kızılyıldız": "Kızılyıldız",
    "Crvena Zvezda": "Kızılyıldız",

    "Maccabi Tel Aviv": "Maccabi Tel Aviv",
    "Maccabi Rapyd Tel Aviv": "Maccabi Tel Aviv",
    "M.Tel Aviv": "Maccabi Tel Aviv",

    "Olimpia Milano": "Olimpia Milano",
    "EA7 Emporio Armani Milan": "Olimpia Milano",
    "Milan": "Olimpia Milano",

    "Bayern Münih": "Bayern Münih",
    "B. Münih": "Bayern Münih",
    "Bayern Munich": "Bayern Münih",

    "Virtus Bologna": "Virtus Bologna",
    "V. Bologna": "Virtus Bologna",
    "Bologna": "Virtus Bologna",

    "Panathinaikos": "Panathinaikos",
    "Panathinaikos Aktor": "Panathinaikos",

    "Fenerbahçe": "Fenerbahçe Beko",
    "Fenerbahçe Beko": "Fenerbahçe Beko",
    "Fenerbahce Beko": "Fenerbahçe Beko",

    "Valencia": "Valencia Basket",
    "Valencia Basket": "Valencia Basket",

    "Hapoel Tel Aviv": "Hapoel IBI Tel Aviv",
    "Hap.Tel Aviv": "Hapoel IBI Tel Aviv",
    "Hapoel IBI Tel Aviv": "Hapoel IBI Tel Aviv",

    "Real Madrid": "Real Madrid",
    "R. Madrid": "Real Madrid",

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
    "Besiktas": "Beşiktaş",
}


def normalize_text(value):
    if value is None:
        return ""

    value = str(value)

    value = value.replace("\u00a0", " ")
    value = value.replace("İ", "I")
    value = value.replace("ı", "i")
    value = value.replace("Ş", "S")
    value = value.replace("ş", "s")
    value = value.replace("Ğ", "G")
    value = value.replace("ğ", "g")
    value = value.replace("Ü", "U")
    value = value.replace("ü", "u")
    value = value.replace("Ö", "O")
    value = value.replace("ö", "o")
    value = value.replace("Ç", "C")
    value = value.replace("ç", "c")

    value = re.sub(r"\s+", " ", value)

    return value.strip().lower()


def normalize_team(name):
    if not name:
        return None

    name = str(name).strip()

    if name in ALIASES:
        return ALIASES[name]

    normalized = normalize_text(name)

    for source, target in ALIASES.items():
        if normalize_text(source) == normalized:
            return target

    return name.strip()


def load_teams():
    if not DATA_FILE.exists():
        raise RuntimeError("data.json bulunamadı")

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    teams = set()

    for match in data.get("matches", []):
        home = normalize_team(match.get("home"))
        away = normalize_team(match.get("away"))

        if home:
            teams.add(home)

        if away:
            teams.add(away)

    return sorted(teams)


def is_known_team(name, teams):
    if not name:
        return False

    normalized = normalize_text(name)

    for team in teams:
        if normalized == normalize_text(team):
            return True

        if normalized_team_match(normalized, normalize_text(team)):
            return True

    return False


def normalized_team_match(a, b):
    a = re.sub(r"[^a-z0-9]+", "", a)
    b = re.sub(r"[^a-z0-9]+", "", b)

    return a == b


def parse_score_value(value):
    if value is None:
        return None

    if isinstance(value, dict):
        pairs = [
            ("home", "away"),
            ("homeScore", "awayScore"),
            ("home_score", "away_score"),
            ("homePoints", "awayPoints"),
            ("home_points", "away_points"),
            ("scoreHome", "scoreAway"),
        ]

        for home_key, away_key in pairs:
            if home_key in value and away_key in value:
                try:
                    h = int(value[home_key])
                    a = int(value[away_key])

                    if 0 <= h <= 300 and 0 <= a <= 300:
                        return h, a
                except Exception:
                    pass

        for key in [
            "score",
            "result",
            "finalScore",
            "final_score",
            "matchScore",
        ]:
            if key in value:
                result = parse_score_value(value[key])

                if result:
                    return result

        return None

    if isinstance(value, (list, tuple)):
        if len(value) >= 2:
            try:
                h = int(value[0])
                a = int(value[1])

                if 0 <= h <= 300 and 0 <= a <= 300:
                    return h, a
            except Exception:
                pass

        return None

    text = str(value)

    patterns = [
        r"(\d{1,3})\s*[-:]\s*(\d{1,3})",
        r"(\d{1,3})\s*–\s*(\d{1,3})",
        r"(\d{1,3})\s+(\d{1,3})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            try:
                h = int(match.group(1))
                a = int(match.group(2))

                if 0 <= h <= 300 and 0 <= a <= 300:
                    return h, a
            except Exception:
                pass

    return None


def parse_date(value):
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    # ISO tarih
    match = re.search(
        r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})",
        text
    )

    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))

            return f"{year:04d}-{month:02d}-{day:02d}"
        except Exception:
            pass

    # Türkçe tarih
    match = re.search(
        r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})",
        text
    )

    if match:
        try:
            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))

            return f"{year:04d}-{month:02d}-{day:02d}"
        except Exception:
            pass

    return None


def get_string(obj, keys):
    if not isinstance(obj, dict):
        return None

    lowered = {
        str(k).lower(): v
        for k, v in obj.items()
    }

    for key in keys:
        if key.lower() in lowered:
            value = lowered[key.lower()]

            if isinstance(value, (str, int, float)):
                return str(value)

    return None


def get_team_from_object(obj, home=True):
    if not isinstance(obj, dict):
        return None

    if home:
        keys = [
            "home",
            "homeTeam",
            "home_team",
            "homeName",
            "homeTeamName",
            "homeParticipant",
            "homeCompetitor",
            "teamHome",
            "localTeam",
            "hostTeam",
        ]
    else:
        keys = [
            "away",
            "awayTeam",
            "away_team",
            "awayName",
            "awayTeamName",
            "awayParticipant",
            "awayCompetitor",
            "teamAway",
            "visitorTeam",
            "guestTeam",
        ]

    value = get_string(obj, keys)

    if value:
        return normalize_team(value)

    return None


def get_date_from_object(obj):
    if not isinstance(obj, dict):
        return None

    keys = [
        "date",
        "matchDate",
        "gameDate",
        "startDate",
        "startTime",
        "dateTime",
        "datetime",
        "eventDate",
        "scheduledAt",
        "playedAt",
    ]

    for key in keys:
        value = get_string(obj, [key])

        if value:
            result = parse_date(value)

            if result:
                return result

    return None


def get_score_from_object(obj):
    if not isinstance(obj, dict):
        return None

    # Önce doğrudan skor alanlarını dene
    for key in [
        "score",
        "result",
        "finalScore",
        "final_score",
        "matchScore",
        "scores",
    ]:
        if key in obj:
            result = parse_score_value(obj[key])

            if result:
                return result

    # Sonra home/away score alanlarını dene
    home_keys = [
        "homeScore",
        "home_score",
        "homePoints",
        "home_points",
        "scoreHome",
        "homeResult",
    ]

    away_keys = [
        "awayScore",
        "away_score",
        "awayPoints",
        "away_points",
        "scoreAway",
        "awayResult",
    ]

    home_value = get_string(obj, home_keys)
    away_value = get_string(obj, away_keys)

    if home_value is not None and away_value is not None:
        try:
            h = int(float(home_value))
            a = int(float(away_value))

            if 0 <= h <= 300 and 0 <= a <= 300:
                return h, a
        except Exception:
            pass

    return None


def extract_from_dict(obj, teams, found):
    if not isinstance(obj, dict):
        return

    home = get_team_from_object(obj, True)
    away = get_team_from_object(obj, False)
    score = get_score_from_object(obj)
    date = get_date_from_object(obj)

    if home and away and score:
        known_home = None
        known_away = None

        for team in teams:
            if normalized_team_match(
                normalize_text(home),
                normalize_text(team)
            ):
                known_home = team

            if normalized_team_match(
                normalize_text(away),
                normalize_text(team)
            ):
                known_away = team

        if known_home and known_away:
            home_score, away_score = score

            if date is None:
                date = datetime.utcnow().strftime("%Y-%m-%d")

            match = {
                "date": date,
                "home": known_home,
                "away": known_away,
                "homeScore": home_score,
                "awayScore": away_score,
            }

            key = (
                match["date"],
                match["home"],
                match["away"],
            )

            found[key] = match

    for value in obj.values():
        walk_json(value, teams, found)


def walk_json(value, teams, found):
    if isinstance(value, dict):
        extract_from_dict(value, teams, found)

    elif isinstance(value, list):
        for item in value:
            walk_json(item, teams, found)


def extract_from_text(text, teams, found):
    if not text:
        return

    # Tarih + takım + skor yakalamaya çalış
    date_pattern = (
        r"(\d{1,2}[./-]\d{1,2}[./-]20\d{2}"
        r"|20\d{2}[./-]\d{1,2}[./-]\d{1,2})"
    )

    score_pattern = r"(\d{1,3})\s*[-:]\s*(\d{1,3})"

    for date_match in re.finditer(date_pattern, text):
        start = max(0, date_match.start() - 500)
        end = min(len(text), date_match.end() + 1000)

        block = text[start:end]

        score_match = re.search(score_pattern, block)

        if not score_match:
            continue

        home_score = int(score_match.group(1))
        away_score = int(score_match.group(2))

        if home_score > 300 or away_score > 300:
            continue

        # Bilinen takımları blok içinde ara
        found_teams = []

        for team in teams:
            if normalize_text(team) in normalize_text(block):
                found_teams.append(team)

        if len(found_teams) < 2:
            continue

        # Aynı blokta iki takım bulunduysa olası eşleşme
        for i in range(len(found_teams)):
            for j in range(i + 1, len(found_teams)):
                home = found_teams[i]
                away = found_teams[j]

                date = parse_date(date_match.group(1))

                if not date:
                    continue

                match = {
                    "date": date,
                    "home": home,
                    "away": away,
                    "homeScore": home_score,
                    "awayScore": away_score,
                }

                key = (
                    date,
                    home,
                    away,
                )

                found[key] = match


def calculate_team_stats(history, teams):
    team_stats = {}

    for team in teams:
        home_games = [
            m for m in history
            if normalize_text(m["home"]) == normalize_text(team)
        ]

        away_games = [
            m for m in history
            if normalize_text(m["away"]) == normalize_text(team)
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

        team_stats[team] = {
            "home": {
                "games": len(home_games),
                "scored": round(
                    sum(home_for) / len(home_for),
                    2
                ) if home_for else 0,
                "conceded": round(
                    sum(home_against) / len(home_against),
                    2
                ) if home_against else 0,
            },
            "away": {
                "games": len(away_games),
                "scored": round(
                    sum(away_for) / len(away_for),
                    2
                ) if away_for else 0,
                "conceded": round(
                    sum(away_against) / len(away_against),
                    2
                ) if away_against else 0,
            },
        }

    return team_stats


def main():
    print("=" * 60)
    print("🏀 IDDAA.COM EUROLEAGUE GEÇMİŞ VERİ SCRAPER")
    print("=" * 60)

    teams = load_teams()

    print(f"\n📦 Takım sayısı: {len(teams)}")

    if len(teams) == 0:
        raise RuntimeError("data.json içinde takım bulunamadı")

    print("\n📋 Takımlar:")

    for team in teams:
        print(f"   • {team}")

    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            locale="tr-TR"
        )

        page = context.new_page()

        def response_handler(response):
            try:
                content_type = (
                    response.headers.get(
                        "content-type",
                        ""
                    ).lower()
                )

                url = response.url.lower()

                if (
                    "json" in content_type
                    or ".json" in url
                    or "/api/" in url
                ):
                    try:
                        body = response.text()

                        if body and len(body) > 20:
                            captured.append({
                                "url": response.url,
                                "body": body,
                            })

                    except Exception:
                        pass

            except Exception:
                pass

        page.on(
            "response",
            response_handler
        )

        for url in URLS:
            print(f"\n🌐 Açılıyor: {url}")

            try:
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                page.wait_for_timeout(8000)

                # Sayfanın yüklediği dinamik içerikleri tetikle
                for _ in range(4):
                    page.mouse.wheel(
                        0,
                        1800
                    )
                    page.wait_for_timeout(1500)

                # Biraz daha bekle
                page.wait_for_timeout(5000)

            except Exception as e:
                print(
                    f"   ⚠️ Sayfa hatası: {e}"
                )

        print(
            f"\n📡 Yakalanan JSON cevap: "
            f"{len(captured)}"
        )

        browser.close()

    found = {}

    print("\n🔎 JSON cevapları taranıyor...")

    for item in captured:
        body = item["body"]

        # JSON olarak parse etmeyi dene
        try:
            parsed = json.loads(body)

            walk_json(
                parsed,
                teams,
                found
            )

        except Exception:
            pass

        # JSON dışında metin içinde de ara
        extract_from_text(
            body,
            teams,
            found
        )

    history = list(found.values())

    # Sadece gerçek skorları bırak
    history = [
        m for m in history
        if isinstance(m["homeScore"], int)
        and isinstance(m["awayScore"], int)
        and 0 <= m["homeScore"] <= 300
        and 0 <= m["awayScore"] <= 300
    ]

    history.sort(
        key=lambda x: (
            x["date"],
            x["home"],
            x["away"],
        ),
        reverse=True
    )

    print(
        f"🏀 Toplam bulunan geçmiş maç: "
        f"{len(history)}"
    )

    if not history:
        print(
            "\n❌ iddaa.com'dan geçmiş "
            "maç verisi bulunamadı."
        )

        print(
            "❌ Sahte veri oluşturulmadı."
        )

        raise RuntimeError(
            "iddaa.com geçmiş maç veri "
            "kaynağı bulunamadı"
        )

    # --------------------------------------------------
    # HISTORY.JSON
    # --------------------------------------------------

    team_stats = calculate_team_stats(
        history,
        teams
    )

    output = {
        "source": "https://www.iddaa.com",
        "league": "EuroLeague",
        "updatedAt": datetime.utcnow().isoformat() + "Z",
        "lastN": LAST_N,
        "matches": history,
        "teamStats": team_stats,
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

    print(
        f"🏀 Geçmiş maç: {len(history)}"
    )

    print(
        f"💾 Dosya: {HISTORY_FILE}"
    )

    print("\n📋 SON 5 EV / DEPLASMAN")

    for team in teams:
        stats = team_stats.get(team, {})

        home = stats.get("home", {})
        away = stats.get("away", {})

        print(f"\n{team}")

        print(
            f"   🏠 Ev: "
            f"{home.get('games', 0)} maç | "
            f"Attı: {home.get('scored', 0)} | "
            f"Yedi: {home.get('conceded', 0)}"
        )

        print(
            f"   ✈️ Dep: "
            f"{away.get('games', 0)} maç | "
            f"Attı: {away.get('scored', 0)} | "
            f"Yedi: {away.get('conceded', 0)}"
        )

    print("\n✅ history.json oluşturuldu.")


if __name__ == "__main__":
    main()
