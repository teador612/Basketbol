import requests
import json
import re
import time
from datetime import datetime
from urllib.parse import urljoin

BASE_URL = "https://www.iddaa.com"
EUROLEAGUE_URL = "https://www.iddaa.com/euroleague-avrupa-basketbol-ligi"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.iddaa.com/",
}

TIMEOUT = 20

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def get_page(url):
    print(f"\n🌐 İstek: {url}")

    try:
        response = SESSION.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        print(f"   HTTP: {response.status_code}")
        print(f"   Boyut: {len(response.text)}")

        if response.status_code != 200:
            print("❌ Sayfa alınamadı.")
            return None

        return response.text

    except Exception as e:
        print(f"❌ İstek hatası: {e}")
        return None


def clean_text(value):
    if value is None:
        return ""

    value = str(value)

    value = (
        value.replace("\\u002F", "/")
        .replace("\\/", "/")
        .replace("&nbsp;", " ")
        .replace("&amp;", "&")
    )

    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)

    return value.strip()


def extract_json_scripts(html):
    """
    Sayfadaki JSON benzeri script bloklarını bulur.
    """

    results = []

    patterns = [
        r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
        r'<script[^>]*>(\{.*?\})</script>',
    ]

    for pattern in patterns:
        matches = re.findall(
            pattern,
            html,
            flags=re.DOTALL | re.IGNORECASE
        )

        for item in matches:
            item = item.strip()

            if len(item) < 20:
                continue

            try:
                data = json.loads(item)
                results.append(data)
            except Exception:
                continue

    return results


def find_euroleague_strings(html):
    """
    HTML/JS içinde EuroLeague ile ilişkili takım isimlerini arar.
    """

    teams = [
        "Anadolu Efes",
        "Fenerbahçe Beko",
        "Real Madrid",
        "Barcelona",
        "Panathinaikos",
        "Olympiakos",
        "Partizan",
        "Bayern Münih",
        "Monaco",
        "Baskonia",
        "Valencia",
        "Virtus Bologna",
        "Zalgiris",
        "Kızılyıldız",
        "Maccabi",
        "ASVEL",
        "Paris Basketball",
        "Dubai Basketball",
        "Olimpia Milano",
        "Hapoel",
    ]

    found = []

    lower_html = html.lower()

    for team in teams:
        if team.lower() in lower_html:
            found.append(team)

    return found


def recursive_find_matches(data, found=None):
    """
    JSON içerisinde maç benzeri objeleri recursive olarak arar.
    """

    if found is None:
        found = []

    if isinstance(data, dict):

        keys = {str(k).lower() for k in data.keys()}

        has_home = any(
            x in keys
            for x in [
                "home",
                "hometeam",
                "home_team",
                "homeTeam".lower()
            ]
        )

        has_away = any(
            x in keys
            for x in [
                "away",
                "awayteam",
                "away_team",
                "awayTeam".lower()
            ]
        )

        if has_home and has_away:
            found.append(data)

        for value in data.values():
            recursive_find_matches(value, found)

    elif isinstance(data, list):

        for item in data:
            recursive_find_matches(item, found)

    return found


def get_value(obj, names):
    if not isinstance(obj, dict):
        return None

    lower_map = {
        str(k).lower(): v
        for k, v in obj.items()
    }

    for name in names:
        key = name.lower()

        if key in lower_map:
            return lower_map[key]

    return None


def normalize_team(value):
    if isinstance(value, dict):

        name = get_value(
            value,
            [
                "name",
                "teamName",
                "displayName",
                "shortName"
            ]
        )

        if name:
            return clean_text(name)

    if value:
        return clean_text(value)

    return ""


def normalize_match(match):
    home = get_value(
        match,
        [
            "home",
            "homeTeam",
            "home_team",
            "homeName"
        ]
    )

    away = get_value(
        match,
        [
            "away",
            "awayTeam",
            "away_team",
            "awayName"
        ]
    )

    home = normalize_team(home)
    away = normalize_team(away)

    if not home or not away:
        return None

    return {
        "home": home,
        "away": away,
        "date": get_value(
            match,
            [
                "date",
                "startDate",
                "matchDate",
                "eventDate"
            ]
        ),
        "time": get_value(
            match,
            [
                "time",
                "startTime",
                "matchTime"
            ]
        ),
        "score": get_value(
            match,
            [
                "score",
                "result",
                "homeScore"
            ]
        ),
        "raw": match
    }


def unique_matches(matches):
    result = []
    seen = set()

    for match in matches:

        key = (
            match["home"].lower(),
            match["away"].lower()
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(match)

    return result


def save_data(matches):

    today = datetime.now().strftime("%Y-%m-%d")

    output = {
        today: matches
    }

    with open(
        "data.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            ensure_ascii=False,
            indent=4
        )

    print()
    print("=" * 60)
    print(f"💾 data.json oluşturuldu")
    print(f"📅 Tarih: {today}")
    print(f"🏀 Maç sayısı: {len(matches)}")
    print("=" * 60)


def run():

    print("=" * 60)
    print("🏀 IDDAA.COM EUROLEAGUE SCRAPER")
    print("=" * 60)

    print(
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    html = get_page(EUROLEAGUE_URL)

    if not html:
        print("❌ EuroLeague sayfası alınamadı.")
        return

    print()
    print("🔎 EuroLeague takımları aranıyor...")

    teams = find_euroleague_strings(html)

    print(
        f"   Bulunan takım adı: {len(teams)}"
    )

    for team in teams:
        print(f"   • {team}")

    print()
    print("🔎 JSON verileri aranıyor...")

    json_blocks = extract_json_scripts(html)

    print(
        f"   JSON blokları: {len(json_blocks)}"
    )

    all_matches = []

    for index, data in enumerate(json_blocks):

        matches = recursive_find_matches(data)

        if matches:
            print(
                f"   JSON #{index + 1}: "
                f"{len(matches)} maç benzeri kayıt"
            )

        for raw_match in matches:

            normalized = normalize_match(raw_match)

            if normalized:
                all_matches.append(normalized)

    all_matches = unique_matches(all_matches)

    print()
    print("=" * 60)
    print("📊 SONUÇ")
    print("=" * 60)

    if not all_matches:

        print("⚠️ HTML içerisinde doğrudan maç verisi bulunamadı.")
        print()
        print(
            "Bu durumda iddaa.com maçları JavaScript ile "
            "harici bir veri kaynağından yüklüyor demektir."
        )

        # Debug için sayfanın küçük bir bölümünü kaydet
        with open(
            "iddaa-euroleague-debug.html",
            "w",
            encoding="utf-8"
        ) as file:
            file.write(html)

        print()
        print(
            "📁 iddaa-euroleague-debug.html oluşturuldu."
        )

        return

    for index, match in enumerate(all_matches, 1):

        print(
            f"{index:02d}. "
            f"{match['home']} - {match['away']}"
        )

    save_data(all_matches)


if __name__ == "__main__":
    run()
