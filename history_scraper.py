import json
import re
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
    "Anadolu Efes": "Anadolu Efes",
    "Efes": "Anadolu Efes",

    "Baskonia": "Baskonia",
    "Baskonia Vitoria-Gasteiz": "Baskonia",

    "Bayern Münih": "Bayern Münih",
    "Bayern Munich": "Bayern Münih",

    "Beşiktaş": "Beşiktaş",
    "Besiktas": "Beşiktaş",

    "Dubai Basketball": "Dubai Basketball",
    "Dubai": "Dubai Basketball",

    "FC Barcelona": "FC Barcelona",
    "Barcelona": "FC Barcelona",

    "Fenerbahçe Beko": "Fenerbahçe Beko",
    "Fenerbahce Beko": "Fenerbahçe Beko",
    "Fenerbahçe": "Fenerbahçe Beko",

    "Hapoel IBI Tel Aviv": "Hapoel IBI Tel Aviv",
    "Hapoel Tel Aviv": "Hapoel IBI Tel Aviv",

    "Kızılyıldız": "Kızılyıldız",
    "Crvena Zvezda": "Kızılyıldız",

    "LDLC ASVEL": "LDLC ASVEL",
    "ASVEL": "LDLC ASVEL",

    "Maccabi Tel Aviv": "Maccabi Tel Aviv",
    "Maccabi Rapyd Tel Aviv": "Maccabi Tel Aviv",

    "Olimpia Milano": "Olimpia Milano",
    "EA7 Emporio Armani Milan": "Olimpia Milano",
    "Milan": "Olimpia Milano",

    "Olympiakos": "Olympiakos",
    "Olympiacos": "Olympiakos",

    "Panathinaikos": "Panathinaikos",
    "Panathinaikos Aktor": "Panathinaikos",

    "Paris Basketball": "Paris Basketball",
    "Paris": "Paris Basketball",

    "Partizan": "Partizan",
    "KK Partizan": "Partizan",

    "Real Madrid": "Real Madrid",

    "Valencia Basket": "Valencia Basket",
    "Valencia": "Valencia Basket",

    "Virtus Bologna": "Virtus Bologna",
    "Virtus": "Virtus Bologna",

    "Zalgiris Kaunas": "Zalgiris Kaunas",
    "Zalgiris": "Zalgiris Kaunas",
}


def normalize(text):
    if text is None:
        return ""

    text = str(text)

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

    for a, b in replacements.items():
        text = text.replace(a, b)

    text = re.sub(r"\s+", " ", text)

    return text.strip().lower()


def compact(text):
    return re.sub(
        r"[^a-z0-9]",
        "",
        normalize(text),
    )


def canonical_team(name):
    if not name:
        return None

    n = normalize(name)

    for alias, team in ALIASES.items():
        if normalize(alias) == n:
            return team

    return None


def load_teams():
    if not DATA_FILE.exists():
        raise RuntimeError("data.json bulunamadı")

    with open(
        DATA_FILE,
        "r",
        encoding="utf-8",
    ) as f:
        data = json.load(f)

    teams = set()

    for match in data.get("matches", []):

        home = canonical_team(
            match.get("home")
        )

        away = canonical_team(
            match.get("away")
        )

        if home:
            teams.add(home)

        if away:
            teams.add(away)

    return sorted(teams)


def team_in_text(text, team):
    ntext = compact(text)

    for alias, canonical in ALIASES.items():

        if canonical != team:
            continue

        alias_compact = compact(alias)

        if alias_compact and alias_compact in ntext:
            return True

    return False


def find_teams(text, teams):
    result = []

    for team in teams:

        if team_in_text(text, team):
            result.append(team)

    return result


def parse_date(text):
    if not text:
        return None

    patterns = [
        r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})",
        r"(\d{1,2})[-/.](\d{1,2})[-/.](20\d{2})",
    ]

    for pattern in patterns:

        m = re.search(pattern, text)

        if not m:
            continue

        try:

            if m.group(1).startswith("20"):
                year = int(m.group(1))
                month = int(m.group(2))
                day = int(m.group(3))
            else:
                day = int(m.group(1))
                month = int(m.group(2))
                year = int(m.group(3))

            return (
                f"{year:04d}-"
                f"{month:02d}-"
                f"{day:02d}"
            )

        except Exception:
            pass

    return None


def valid_final_score(home, away):
    """
    Çeyrek skorlarını elemek için sıkı filtre.

    EuroLeague finalinde:
    - iki takım da makul basketbol skoru üretmiş olmalı
    - toplam skor çok düşük olmamalı
    """

    if home is None or away is None:
        return False

    if home < 40 or away < 40:
        return False

    if home > 160 or away > 160:
        return False

    if home + away < 100:
        return False

    return True


def score_candidates(text):
    """
    Metindeki skor adaylarını çıkarır.
    """

    patterns = [
        r"\b(\d{2,3})\s*[-:]\s*(\d{2,3})\b",
        r"\b(\d{2,3})\s+(\d{2,3})\b",
    ]

    results = []

    for pattern in patterns:

        for m in re.finditer(
            pattern,
            text,
        ):

            try:

                home = int(m.group(1))
                away = int(m.group(2))

            except Exception:
                continue

            if valid_final_score(
                home,
                away,
            ):
                results.append(
                    (
                        m.start(),
                        m.end(),
                        home,
                        away,
                    )
                )

    return results


def extract_from_text(
    text,
    teams,
    found,
):
    if not text:
        return

    scores = score_candidates(text)

    for start, end, home_score, away_score in scores:

        window_start = max(
            0,
            start - 600,
        )

        window_end = min(
            len(text),
            end + 600,
        )

        window = text[
            window_start:window_end
        ]

        detected = find_teams(
            window,
            teams,
        )

        if len(detected) != 2:
            continue

        date = parse_date(window)

        if not date:
            date = datetime.utcnow().strftime(
                "%Y-%m-%d"
            )

        home = detected[0]
        away = detected[1]

        if home == away:
            continue

        key = (
            date,
            home,
            away,
        )

        candidate = {
            "date": date,
            "home": home,
            "away": away,
            "homeScore": home_score,
            "awayScore": away_score,
        }

        # Aynı maç için daha yüksek ve makul
        # skor bulunan kaydı tercih et.
        if key not in found:
            found[key] = candidate

        else:

            old = found[key]

            old_total = (
                old["homeScore"]
                + old["awayScore"]
            )

            new_total = (
                home_score
                + away_score
            )

            if new_total > old_total:
                found[key] = candidate


def extract_dom_match_blocks(
    page,
    teams,
    found,
):
    """
    Sayfadaki elementleri tek tek kontrol eder.
    Böylece body text içindeki birbirine karışmış
    çeyrek skorlarını mümkün olduğunca engeller.
    """

    elements = page.locator(
        "body *"
    )

    count = min(
        elements.count(),
        5000,
    )

    for i in range(count):

        try:
            element = elements.nth(i)

            text = element.inner_text(
                timeout=100
            ).strip()

        except Exception:
            continue

        if not text:
            continue

        if len(text) > 500:
            continue

        detected = find_teams(
            text,
            teams,
        )

        if len(detected) != 2:
            continue

        scores = score_candidates(text)

        if len(scores) != 1:
            continue

        _, _, home_score, away_score = scores[0]

        date = parse_date(text)

        if not date:
            date = datetime.utcnow().strftime(
                "%Y-%m-%d"
            )

        home = detected[0]
        away = detected[1]

        if home == away:
            continue

        key = (
            date,
            home,
            away,
        )

        candidate = {
            "date": date,
            "home": home,
            "away": away,
            "homeScore": home_score,
            "awayScore": away_score,
        }

        if key not in found:
            found[key] = candidate


def calculate_stats(
    history,
    teams,
):
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

    print("=" * 60)
    print("🏀 IDDAA.COM EUROLEAGUE GEÇMİŞ VERİ SCRAPER")
    print("=" * 60)

    teams = load_teams()

    print(
        f"\n📦 Takım sayısı: {len(teams)}"
    )

    print("\n📋 Takımlar:")

    for team in teams:
        print(
            f"   • {team}"
        )

    found = {}

    network_responses = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            locale="tr-TR",
            viewport={
                "width": 1440,
                "height": 1200,
            },
        )

        page = context.new_page()

        def on_response(response):

            try:

                content_type = response.headers.get(
                    "content-type",
                    "",
                ).lower()

                resource_type = (
                    response.request.resource_type
                )

                if (
                    "json" in content_type
                    or resource_type in (
                        "xhr",
                        "fetch",
                    )
                ):

                    body = response.text()

                    if body and len(body) > 20:

                        network_responses.append(
                            body
                        )

            except Exception:
                pass

        page.on(
            "response",
            on_response,
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

                for _ in range(10):

                    page.mouse.wheel(
                        0,
                        1800,
                    )

                    page.wait_for_timeout(
                        1000
                    )

                page.wait_for_timeout(
                    5000
                )

                # Önce DOM'dan gerçek maç bloklarını dene
                extract_dom_match_blocks(
                    page,
                    teams,
                    found,
                )

                # Sonra body text
                try:

                    body_text = page.locator(
                        "body"
                    ).inner_text(
                        timeout=15000
                    )

                    extract_from_text(
                        body_text,
                        teams,
                        found,
                    )

                except Exception:
                    pass

            except Exception as e:

                print(
                    f"⚠️ Sayfa hatası: {e}"
                )

        browser.close()

    print(
        f"\n📡 Yakalanan ağ cevabı: "
        f"{len(network_responses)}"
    )

    print(
        "\n🔎 Ağ cevapları taranıyor..."
    )

    for body in network_responses:

        extract_from_text(
            body,
            teams,
            found,
        )

    history = list(found.values())

    # Kesin filtre
    history = [
        m for m in history
        if valid_final_score(
            m["homeScore"],
            m["awayScore"],
        )
    ]

    # Aynı maçı tekrar alma
    unique = {}

    for match in history:

        key = (
            match["date"],
            match["home"],
            match["away"],
        )

        old = unique.get(key)

        if old is None:

            unique[key] = match

        else:

            old_total = (
                old["homeScore"]
                + old["awayScore"]
            )

            new_total = (
                match["homeScore"]
                + match["awayScore"]
            )

            if new_total > old_total:
                unique[key] = match

    history = list(
        unique.values()
    )

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

        print(
            "\n📋 BULUNAN MAÇLAR:"
        )

        for match in history[:30]:

            print(
                f"   {match['date']} | "
                f"{match['home']} "
                f"{match['homeScore']}-"
                f"{match['awayScore']} "
                f"{match['away']}"
            )

    if not history:

        raise RuntimeError(
            "Gerçek final skorlu EuroLeague "
            "geçmiş maçı bulunamadı."
        )

    team_stats = calculate_stats(
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
        "💾 history.json oluşturuldu"
    )

    print("\n📋 SON 5 EV / DEPLASMAN")

    for team in teams:

        s = team_stats[team]

        print(
            f"\n{team}"
        )

        print(
            f"   🏠 Ev: "
            f"{s['home']['games']} maç | "
            f"Attı: {s['home']['scored']} | "
            f"Yedi: {s['home']['conceded']}"
        )

        print(
            f"   ✈️ Dep: "
            f"{s['away']['games']} maç | "
            f"Attı: {s['away']['scored']} | "
            f"Yedi: {s['away']['conceded']}"
        )

    print(
        "\n✅ history.json oluşturuldu."
    )


if __name__ == "__main__":
    main()
