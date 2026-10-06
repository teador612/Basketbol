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
    "Crvena zvezda": "Kızılyıldız",

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

    replacements = {
        "İ": "I",
        "ı": "i",
        "Ş": "S",
        "ş": "s",
        "Ğ": "G",
        "ğ": "g",
        "Ü": "U",
        "ü": "u",
        "Ö": "O",
        "ö": "o",
        "Ç": "C",
        "ç": "c",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value)

    return value.strip().lower()


def compact(value):
    return re.sub(
        r"[^a-z0-9]+",
        "",
        normalize_text(value)
    )


def normalize_team(name):
    if not name:
        return None

    name = str(name).strip()

    if name in ALIASES:
        return ALIASES[name]

    n = normalize_text(name)

    for source, target in ALIASES.items():
        if normalize_text(source) == n:
            return target

    return name


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


def team_aliases_for(team):
    result = [team]

    for source, target in ALIASES.items():
        if target == team:
            result.append(source)

    return list(dict.fromkeys(result))


def find_known_teams(text, teams):
    normalized = normalize_text(text)
    compact_text = compact(text)

    found = []

    for team in teams:
        matched = False

        for alias in team_aliases_for(team):
            if normalize_text(alias) in normalized:
                matched = True
                break

            alias_compact = compact(alias)

            if alias_compact and alias_compact in compact_text:
                matched = True
                break

        if matched and team not in found:
            found.append(team)

    return found


def parse_score_text(text):
    if not text:
        return None

    patterns = [
        r"\b(\d{1,3})\s*[-:]\s*(\d{1,3})\b",
        r"\b(\d{1,3})\s+[–-]\s+(\d{1,3})\b",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, str(text)):
            h = int(match.group(1))
            a = int(match.group(2))

            if 0 <= h <= 300 and 0 <= a <= 300:
                return h, a

    return None


def parse_date(value):
    if value is None:
        return None

    text = str(value)

    patterns = [
        r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})",
        r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if not match:
            continue

        try:
            if pattern.startswith("(20"):
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
            else:
                day = int(match.group(1))
                month = int(match.group(2))
                year = int(match.group(3))

            return f"{year:04d}-{month:02d}-{day:02d}"

        except Exception:
            pass

    return None


def find_date_near(text):
    if not text:
        return None

    match = re.search(
        r"(20\d{2}[-/]\d{1,2}[-/]\d{1,2}"
        r"|\d{1,2}[./-]\d{1,2}[./-]20\d{2})",
        text
    )

    if match:
        return parse_date(match.group(1))

    return None


def get_value(obj, keys):
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
                return value

    return None


def find_score_in_object(obj):
    if not isinstance(obj, dict):
        return None

    direct_pairs = [
        ("homeScore", "awayScore"),
        ("home_score", "away_score"),
        ("homePoints", "awayPoints"),
        ("home_points", "away_points"),
        ("scoreHome", "scoreAway"),
        ("homeResult", "awayResult"),
        ("homePoints", "awayPoints"),
    ]

    lowered = {
        str(k).lower(): v
        for k, v in obj.items()
    }

    for hk, ak in direct_pairs:
        hv = lowered.get(hk.lower())
        av = lowered.get(ak.lower())

        if hv is None or av is None:
            continue

        try:
            h = int(float(hv))
            a = int(float(av))

            if 0 <= h <= 300 and 0 <= a <= 300:
                return h, a
        except Exception:
            pass

    score_keys = [
        "score",
        "scores",
        "result",
        "finalscore",
        "final_score",
        "matchscore",
        "match_score",
        "resultscore",
    ]

    for key in score_keys:
        if key in lowered:
            value = lowered[key]

            if isinstance(value, dict):
                result = find_score_in_object(value)

                if result:
                    return result

            result = parse_score_text(value)

            if result:
                return result

    return None


def find_team_value(obj, home=True):
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
            "homeParticipantName",
            "homeCompetitorName",
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
            "awayParticipantName",
            "awayCompetitorName",
        ]

    value = get_value(obj, keys)

    if value is None:
        return None

    if isinstance(value, dict):
        for key in [
            "name",
            "teamName",
            "displayName",
            "shortName",
            "title",
        ]:
            nested = get_value(value, [key])

            if nested:
                return normalize_team(nested)

    return normalize_team(value)


def find_date_in_object(obj):
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
        "timestamp",
    ]

    for key in keys:
        value = get_value(obj, [key])

        if value:
            result = parse_date(value)

            if result:
                return result

    return None


def save_match(found, date, home, away, score):
    if not home or not away or not score:
        return

    if home == away:
        return

    if home not in CURRENT_TEAMS:
        return

    if away not in CURRENT_TEAMS:
        return

    home_score, away_score = score

    if not (0 <= home_score <= 300):
        return

    if not (0 <= away_score <= 300):
        return

    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    key = (
        date,
        home,
        away,
        home_score,
        away_score,
    )

    found[key] = {
        "date": date,
        "home": home,
        "away": away,
        "homeScore": home_score,
        "awayScore": away_score,
    }


def recursive_scan(value, teams, found, inherited_date=None):
    if isinstance(value, dict):

        current_date = (
            find_date_in_object(value)
            or inherited_date
        )

        home = find_team_value(value, True)
        away = find_team_value(value, False)

        score = find_score_in_object(value)

        if home and away and score:
            save_match(
                found,
                current_date,
                home,
                away,
                score,
            )

        # Bazı API'lerde home/away isimleri farklı
        # alanlarda tutuluyor. Bu durumda bütün string
        # değerlerinden takım eşleştirmeyi dene.
        strings = []

        for key, item in value.items():

            if isinstance(item, str):
                strings.append(item)

            elif isinstance(item, (int, float)):
                continue

        if not (home and away):
            joined = " ".join(strings)

            detected = find_known_teams(
                joined,
                teams,
            )

            if len(detected) >= 2:

                possible_score = score

                if possible_score is None:
                    possible_score = parse_score_text(
                        joined
                    )

                if possible_score:
                    save_match(
                        found,
                        current_date,
                        detected[0],
                        detected[1],
                        possible_score,
                    )

        for child in value.values():
            recursive_scan(
                child,
                teams,
                found,
                current_date,
            )

    elif isinstance(value, list):

        for item in value:
            recursive_scan(
                item,
                teams,
                found,
                inherited_date,
            )


def scan_text(text, teams, found):
    if not text:
        return

    lines = [
        x.strip()
        for x in text.splitlines()
        if x.strip()
    ]

    # Önce satır bazlı arama
    for index, line in enumerate(lines):

        score = parse_score_text(line)

        if not score:
            continue

        start = max(0, index - 6)
        end = min(
            len(lines),
            index + 7,
        )

        block = " ".join(
            lines[start:end]
        )

        detected = find_known_teams(
            block,
            teams,
        )

        if len(detected) < 2:
            continue

        date = find_date_near(block)

        save_match(
            found,
            date,
            detected[0],
            detected[1],
            score,
        )

    # JSON/string bütünlüğü bozulmuşsa geniş pencere
    # ile tekrar tara
    for match in re.finditer(
        r"(\d{1,3})\s*[-:]\s*(\d{1,3})",
        text,
    ):

        home_score = int(match.group(1))
        away_score = int(match.group(2))

        if home_score > 300 or away_score > 300:
            continue

        start = max(
            0,
            match.start() - 1000,
        )

        end = min(
            len(text),
            match.end() + 1000,
        )

        block = text[start:end]

        detected = find_known_teams(
            block,
            teams,
        )

        if len(detected) < 2:
            continue

        date = find_date_near(block)

        save_match(
            found,
            date,
            detected[0],
            detected[1],
            (
                home_score,
                away_score,
            ),
        )


def calculate_team_stats(history, teams):

    stats = {}

    for team in teams:

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
            reverse=True,
        )

        away_games.sort(
            key=lambda x: x["date"],
            reverse=True,
        )

        home_games = home_games[:LAST_N]
        away_games = away_games[:LAST_N]

        home_scored = [
            m["homeScore"]
            for m in home_games
        ]

        home_conceded = [
            m["awayScore"]
            for m in home_games
        ]

        away_scored = [
            m["awayScore"]
            for m in away_games
        ]

        away_conceded = [
            m["homeScore"]
            for m in away_games
        ]

        stats[team] = {
            "home": {
                "games": len(home_games),
                "scored": round(
                    sum(home_scored)
                    / len(home_scored),
                    2,
                ) if home_scored else 0,
                "conceded": round(
                    sum(home_conceded)
                    / len(home_conceded),
                    2,
                ) if home_conceded else 0,
            },

            "away": {
                "games": len(away_games),
                "scored": round(
                    sum(away_scored)
                    / len(away_scored),
                    2,
                ) if away_scored else 0,
                "conceded": round(
                    sum(away_conceded)
                    / len(away_conceded),
                    2,
                ) if away_conceded else 0,
            },
        }

    return stats


def main():

    global CURRENT_TEAMS

    print("=" * 60)
    print("🏀 IDDAA.COM EUROLEAGUE GEÇMİŞ VERİ SCRAPER")
    print("=" * 60)

    teams = load_teams()

    CURRENT_TEAMS = set(teams)

    print(
        f"\n📦 Takım sayısı: {len(teams)}"
    )

    print("\n📋 Takımlar:")

    for team in teams:
        print(f"   • {team}")

    captured = []
    visible_texts = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
        )

        context = browser.new_context(
            locale="tr-TR",
            viewport={
                "width": 1440,
                "height": 1000,
            },
        )

        page = context.new_page()

        def response_handler(response):

            try:

                content_type = response.headers.get(
                    "content-type",
                    "",
                ).lower()

                url = response.url

                # JSON + API + XHR/fetch cevaplarını al
                resource_type = response.request.resource_type

                if (
                    "json" in content_type
                    or "/api/" in url.lower()
                    or resource_type in (
                        "xhr",
                        "fetch",
                    )
                ):

                    try:

                        body = response.text()

                        if body and len(body) > 10:

                            captured.append({
                                "url": url,
                                "body": body,
                            })

                    except Exception:
                        pass

            except Exception:
                pass

        page.on(
            "response",
            response_handler,
        )

        for url in URLS:

            print(
                f"\n🌐 Açılıyor: {url}"
            )

            try:

                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )

                page.wait_for_timeout(
                    10000
                )

                # Sayfanın dinamik içeriklerini tetikle
                for _ in range(8):

                    page.mouse.wheel(
                        0,
                        1800,
                    )

                    page.wait_for_timeout(
                        1200
                    )

                page.wait_for_timeout(
                    5000
                )

                try:

                    text = page.locator(
                        "body"
                    ).inner_text(
                        timeout=15000
                    )

                    if text:
                        visible_texts.append(text)

                        print(
                            f"📄 Görünen metin: "
                            f"{len(text)} karakter"
                        )

                except Exception as e:

                    print(
                        f"⚠️ Metin alınamadı: {e}"
                    )

            except Exception as e:

                print(
                    f"⚠️ Sayfa hatası: {e}"
                )

        browser.close()

    print(
        f"\n📡 Yakalanan ağ cevabı: "
        f"{len(captured)}"
    )

    found = {}

    print(
        "\n🔎 JSON ve ağ cevapları taranıyor..."
    )

    for item in captured:

        body = item["body"]

        try:

            parsed = json.loads(body)

            recursive_scan(
                parsed,
                teams,
                found,
            )

        except Exception:
            pass

        scan_text(
            body,
            teams,
            found,
        )

    print(
        "\n🔎 Sayfa üzerinde görünen metinler "
        "taranıyor..."
    )

    for text in visible_texts:

        scan_text(
            text,
            teams,
            found,
        )

    history = list(found.values())

    history = [
        m for m in history
        if isinstance(
            m["homeScore"],
            int,
        )
        and isinstance(
            m["awayScore"],
            int,
        )
        and 0 <= m["homeScore"] <= 300
        and 0 <= m["awayScore"] <= 300
    ]

    history.sort(
        key=lambda x: (
            x["date"],
            x["home"],
            x["away"],
        ),
        reverse=True,
    )

    print(
        f"\n🏀 Toplam bulunan geçmiş maç: "
        f"{len(history)}"
    )

    if history:

        print("\n📋 BULUNAN MAÇLARDAN ÖRNEK:")

        for match in history[:20]:

            print(
                f"   {match['date']} | "
                f"{match['home']} "
                f"{match['homeScore']}-"
                f"{match['awayScore']} "
                f"{match['away']}"
            )

    if not history:

        print(
            "\n❌ Maç bulunamadı."
        )

        print(
            "❌ Sahte veri oluşturulmadı."
        )

        # Ağ cevaplarının yapısını teşhis etmek için
        # sadece kısa bilgi yazdır.
        print(
            "\n🔍 İlk ağ cevapları:"
        )

        for item in captured[:10]:

            print(
                "\nURL:",
                item["url"],
            )

            preview = re.sub(
                r"\s+",
                " ",
                item["body"],
            )

            print(
                preview[:500]
            )

        raise RuntimeError(
            "iddaa.com geçmiş maç verisi "
            "parse edilemedi"
        )

    team_stats = calculate_team_stats(
        history,
        teams,
    )

    output = {
        "source": "https://www.iddaa.com",
        "league": "EuroLeague",
        "updatedAt": (
            datetime.utcnow()
            .isoformat()
            + "Z"
        ),
        "lastN": LAST_N,
        "matches": history,
        "teamStats": team_stats,
    }

    with open(
        HISTORY_FILE,
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2,
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

        stats = team_stats.get(
            team,
            {},
        )

        home = stats.get(
            "home",
            {},
        )

        away = stats.get(
            "away",
            {},
        )

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

    print(
        "\n✅ history.json oluşturuldu."
    )


if __name__ == "__main__":
    CURRENT_TEAMS = set()
    main()
