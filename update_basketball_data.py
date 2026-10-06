import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests


# ============================================================
# AYARLAR
# ============================================================

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT = DATA_DIR / "basketball.json"

EUROLEAGUE_SEASON = "E2026"

EUROLEAGUE_URL = (
    "https://api-live.euroleague.net"
    f"/v2/competitions/E/seasons/{EUROLEAGUE_SEASON}/games"
)

ESPN_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/basketball/nba/scoreboard"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Son 5 maç için geçmişte yeterli veri bırakıyoruz.
HISTORY_DAYS = 120

# Gelecekteki maçları da JSON'a koy.
FUTURE_DAYS = 30


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def safe_int(value):
    try:
        if value is None:
            return None

        text = str(value).strip()

        if text == "":
            return None

        return int(float(text))

    except (TypeError, ValueError):
        return None


def parse_date(value):
    """
    Bütün tarihleri timezone-aware UTC datetime'a çevirir.

    Böylece:
    naive datetime
    aware datetime

    karşılaştırma hatası oluşmaz.
    """

    if not value:
        return None

    try:
        text = str(value).strip()

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        dt = datetime.fromisoformat(text)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        return dt

    except Exception:
        pass

    try:
        dt = datetime.strptime(
            str(value)[:10],
            "%Y-%m-%d"
        )

        return dt.replace(tzinfo=timezone.utc)

    except Exception:
        return None


def safe_date_key(value):
    dt = parse_date(value)

    if dt is None:
        return datetime.max.replace(tzinfo=timezone.utc)

    return dt


def safe_reverse_date_key(value):
    dt = parse_date(value)

    if dt is None:
        return datetime.min.replace(tzinfo=timezone.utc)

    return dt


# ============================================================
# EUROLEAGUE
# ============================================================

def get_euroleague_games():
    print()
    print("========================================")
    print("🌍 EUROLEAGUE")
    print("========================================")

    try:
        response = requests.get(
            EUROLEAGUE_URL,
            headers=HEADERS,
            timeout=30
        )

        print("HTTP:", response.status_code)

        response.raise_for_status()

        data = response.json()

    except Exception as e:
        print("❌ EuroLeague hatası:", e)
        return []

    if isinstance(data, list):
        raw_games = data

    elif isinstance(data, dict):
        raw_games = (
            data.get("data")
            or data.get("games")
            or []
        )

    else:
        raw_games = []

    print("📦 EuroLeague ham maç:", len(raw_games))

    matches = []

    for game in raw_games:

        if not isinstance(game, dict):
            continue

        local = game.get("local") or {}
        road = game.get("road") or {}

        home_club = local.get("club") or {}
        away_club = road.get("club") or {}

        home_team = (
            home_club.get("name")
            or home_club.get("abbreviatedName")
        )

        away_team = (
            away_club.get("name")
            or away_club.get("abbreviatedName")
        )

        if not home_team or not away_team:
            continue

        played = bool(game.get("played"))

        home_score = safe_int(local.get("score"))
        away_score = safe_int(road.get("score"))

        # Oynanmış görünse bile skor yoksa oynanmış kabul etmiyoruz.
        if not played:
            home_score = None
            away_score = None

        if played and (
            home_score is None
            or away_score is None
        ):
            played = False
            home_score = None
            away_score = None

        matches.append({
            "id": game.get("id"),
            "league": "EuroLeague",
            "season": EUROLEAGUE_SEASON,
            "date": game.get("date"),
            "utcDate": game.get("utcDate"),
            "round": game.get("round"),
            "homeTeam": home_team,
            "awayTeam": away_team,
            "homeScore": home_score,
            "awayScore": away_score,
            "played": played,
            "status": (
                "finished"
                if played
                else "scheduled"
            ),
        })

    print("✅ EuroLeague işlenen:", len(matches))

    return matches


# ============================================================
# NBA - ESPN TEK GÜN
# ============================================================

def get_nba_day(date_value):
    date_text = date_value.strftime("%Y%m%d")

    try:
        response = requests.get(
            ESPN_URL,
            params={
                "dates": date_text,
                "limit": 100,
            },
            headers=HEADERS,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

    except Exception as e:
        print(
            f"   ❌ {date_text} NBA hatası: {e}"
        )
        return []

    events = data.get("events") or []

    matches = []

    for event in events:

        if not isinstance(event, dict):
            continue

        competitions = event.get("competitions") or []

        if not competitions:
            continue

        competition = competitions[0]

        competitors = (
            competition.get("competitors")
            or []
        )

        home = None
        away = None

        for competitor in competitors:

            if not isinstance(competitor, dict):
                continue

            team = competitor.get("team") or {}

            item = {
                "id": team.get("id"),
                "name": (
                    team.get("displayName")
                    or team.get("shortDisplayName")
                    or team.get("name")
                ),
                "abbreviation": team.get(
                    "abbreviation"
                ),
                "score": safe_int(
                    competitor.get("score")
                ),
            }

            home_away = competitor.get(
                "homeAway"
            )

            if home_away == "home":
                home = item

            elif home_away == "away":
                away = item

        if not home or not away:
            continue

        if not home.get("name") or not away.get("name"):
            continue

        status_data = (
            event.get("status")
            or {}
        )

        status_type = (
            status_data.get("type")
            or {}
        )

        state = (
            status_type.get("state")
            or ""
        ).lower()

        completed = bool(
            status_type.get("completed")
        )

        played = (
            completed
            or state == "post"
        )

        home_score = (
            home.get("score")
            if played
            else None
        )

        away_score = (
            away.get("score")
            if played
            else None
        )

        # Skor yoksa oynanmış kabul etme.
        if played and (
            home_score is None
            or away_score is None
        ):
            played = False
            home_score = None
            away_score = None

        matches.append({
            "id": event.get("id"),
            "league": "NBA",
            "season": "2026-27",
            "date": event.get("date"),
            "utcDate": event.get("date"),
            "round": None,
            "homeTeam": home["name"],
            "awayTeam": away["name"],
            "homeScore": home_score,
            "awayScore": away_score,
            "played": played,
            "status": (
                "finished"
                if played
                else "scheduled"
            ),
        })

    return matches


# ============================================================
# NBA - TARİH ARALIĞI
# ============================================================

def get_nba_games():
    print()
    print("========================================")
    print("🏀 NBA")
    print("========================================")

    today = datetime.now(
        timezone.utc
    ).date()

    start = today - timedelta(
        days=HISTORY_DAYS
    )

    end = today + timedelta(
        days=FUTURE_DAYS
    )

    print(
        f"📅 NBA tarih aralığı: "
        f"{start} → {end}"
    )

    all_matches = []

    current = start

    total_days = (
        end - start
    ).days + 1

    day_number = 0

    while current <= end:

        day_number += 1

        print(
            f"   NBA gün "
            f"{day_number}/{total_days}: "
            f"{current}"
        )

        games = get_nba_day(
            datetime.combine(
                current,
                datetime.min.time(),
                tzinfo=timezone.utc,
            )
        )

        all_matches.extend(games)

        current += timedelta(days=1)

    # ID ile tekrarları temizle.
    unique = {}

    for match in all_matches:

        game_id = match.get("id")

        if game_id:
            unique[str(game_id)] = match

    matches = list(
        unique.values()
    )

    # Burada sadece UTC-aware tarih kullanılıyor.
    matches.sort(
        key=lambda x: safe_date_key(
            x.get("date")
        )
    )

    print(
        "🏀 NBA toplam maç:",
        len(matches)
    )

    return matches


# ============================================================
# SON 5 EV MAÇI
# ============================================================

def last_five_home(
    matches,
    team,
    before_date
):
    if not team:
        return []

    target = parse_date(
        before_date
    )

    if target is None:
        return []

    previous = []

    for match in matches:

        if match.get("homeTeam") != team:
            continue

        if not match.get("played"):
            continue

        home_score = match.get(
            "homeScore"
        )

        away_score = match.get(
            "awayScore"
        )

        if home_score is None:
            continue

        if away_score is None:
            continue

        match_date = parse_date(
            match.get("date")
        )

        if match_date is None:
            continue

        # Sadece mevcut maçtan önceki maçlar.
        if match_date >= target:
            continue

        previous.append(match)

    previous.sort(
        key=lambda x: safe_reverse_date_key(
            x.get("date")
        ),
        reverse=True,
    )

    result = []

    for match in previous[:5]:

        result.append({
            "date": match.get("date"),
            "opponent": match.get(
                "awayTeam"
            ),
            "scored": match.get(
                "homeScore"
            ),
            "conceded": match.get(
                "awayScore"
            ),
        })

    return result


# ============================================================
# SON 5 DEPLASMAN MAÇI
# ============================================================

def last_five_away(
    matches,
    team,
    before_date
):
    if not team:
        return []

    target = parse_date(
        before_date
    )

    if target is None:
        return []

    previous = []

    for match in matches:

        if match.get("awayTeam") != team:
            continue

        if not match.get("played"):
            continue

        home_score = match.get(
            "homeScore"
        )

        away_score = match.get(
            "awayScore"
        )

        if home_score is None:
            continue

        if away_score is None:
            continue

        match_date = parse_date(
            match.get("date")
        )

        if match_date is None:
            continue

        # Sadece mevcut maçtan önceki maçlar.
        if match_date >= target:
            continue

        previous.append(match)

    previous.sort(
        key=lambda x: safe_reverse_date_key(
            x.get("date")
        ),
        reverse=True,
    )

    result = []

    for match in previous[:5]:

        result.append({
            "date": match.get("date"),
            "opponent": match.get(
                "homeTeam"
            ),
            "scored": match.get(
                "awayScore"
            ),
            "conceded": match.get(
                "homeScore"
            ),
        })

    return result


# ============================================================
# HER MAÇA SON 5 VERİLERİNİ EKLE
# ============================================================

def add_last_five(matches):

    print()
    print("========================================")
    print("📊 SON 5 VERİLER HESAPLANIYOR")
    print("========================================")

    finished = []

    for match in matches:

        if not match.get("played"):
            continue

        if match.get("homeScore") is None:
            continue

        if match.get("awayScore") is None:
            continue

        finished.append(match)

    print(
        "Geçmişte kullanılabilir maç:",
        len(finished)
    )

    for match in matches:

        match["homeLast5"] = last_five_home(
            finished,
            match.get("homeTeam"),
            match.get("date"),
        )

        match["awayLast5"] = last_five_away(
            finished,
            match.get("awayTeam"),
            match.get("date"),
        )

    return matches


# ============================================================
# KONTROL
# ============================================================

def print_samples(matches):

    print()
    print("========================================")
    print("🔎 SON 5 KONTROL")
    print("========================================")

    shown = 0

    for match in matches:

        home_last5 = (
            match.get("homeLast5")
            or []
        )

        away_last5 = (
            match.get("awayLast5")
            or []
        )

        if not home_last5 and not away_last5:
            continue

        print()
        print(
            f"{match.get('league')} | "
            f"{match.get('homeTeam')} - "
            f"{match.get('awayTeam')}"
        )

        print(
            "Maç tarihi:",
            match.get("date")
        )

        print("EV SON 5:")

        if home_last5:

            for item in home_last5:

                print(
                    f"  {item.get('date')} | "
                    f"{item.get('scored')}-"
                    f"{item.get('conceded')} | "
                    f"{item.get('opponent')}"
                )

        else:
            print("  Veri yok")

        print("DEP SON 5:")

        if away_last5:

            for item in away_last5:

                print(
                    f"  {item.get('date')} | "
                    f"{item.get('scored')}-"
                    f"{item.get('conceded')} | "
                    f"{item.get('opponent')}"
                )

        else:
            print("  Veri yok")

        shown += 1

        if shown >= 5:
            break

    print()
    print(
        "Kontrol edilen maç:",
        shown
    )


# ============================================================
# ANA
# ============================================================

def main():

    print("🏀 BASKETBOL VERİ GÜNCELLEYİCİ")

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    euroleague = (
        get_euroleague_games()
    )

    nba = get_nba_games()

    # Birleştir.
    matches = (
        nba
        + euroleague
    )

    # ID tekrarlarını temizle.
    unique = {}

    for match in matches:

        game_id = match.get("id")

        if game_id:
            key = (
                f"{match.get('league')}:"
                f"{game_id}"
            )
        else:
            key = (
                f"{match.get('league')}:"
                f"{match.get('date')}:"
                f"{match.get('homeTeam')}:"
                f"{match.get('awayTeam')}"
            )

        unique[key] = match

    matches = list(
        unique.values()
    )

    # Tekrar tarih sıralaması.
    matches.sort(
        key=lambda x: safe_date_key(
            x.get("date")
        )
    )

    # Son 5 verilerini ekle.
    matches = add_last_five(
        matches
    )

    # Kontrol çıktısı.
    print_samples(
        matches
    )

    # İstatistikler.
    nba_finished = sum(
        1
        for m in nba
        if (
            m.get("played")
            and m.get("homeScore") is not None
            and m.get("awayScore") is not None
        )
    )

    euro_finished = sum(
        1
        for m in euroleague
        if (
            m.get("played")
            and m.get("homeScore") is not None
            and m.get("awayScore") is not None
        )
    )

    # JSON.
    output = {
        "updatedAt": now_iso(),
        "total": len(matches),

        "nba": len(nba),
        "nbaFinished": nba_finished,

        "euroleague": len(euroleague),
        "euroleagueFinished": euro_finished,

        "matches": matches,
    }

    with OUTPUT.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print("========================================")
    print("✅ TAMAMLANDI")
    print("========================================")

    print(
        "📁 Dosya:",
        OUTPUT
    )

    print(
        "🏀 Toplam maç:",
        len(matches)
    )

    print(
        "NBA:",
        len(nba),
        "| Oynanan:",
        nba_finished
    )

    print(
        "EuroLeague:",
        len(euroleague),
        "| Oynanan:",
        euro_finished
    )

    print(
        "🕒 Güncelleme:",
        output["updatedAt"]
    )


if __name__ == "__main__":
    main()
