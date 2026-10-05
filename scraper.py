import os
import json
import requests
from datetime import datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo
# =========================================================
# AYARLAR
# =========================================================
TZ = ZoneInfo("Europe/Istanbul")
TODAY = datetime.now(TZ).date()
DATE = TODAY.isoformat()
OUTPUT_FILE = "data.json"
BALLDONTLIE_KEY = os.getenv("BALLDONTLIE_API_KEY")
NBA_URL = "https://api.balldontlie.io/v1/games"
EUROLEAGUE_URL = "https://api-live.euroleague.net"
# 2026-2027 EuroLeague sezonu
EUROLEAGUE_SEASON = "E2026"
TIMEOUT = 20
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
})
# =========================================================
# HTTP
# =========================================================
def get_json(url, params=None, headers=None):
    try:
        r = session.get(
            url,
            params=params,
            headers=headers,
            timeout=TIMEOUT,
        )
        print(
            f"   🌐 HTTP {r.status_code}: "
            f"{r.url[:180]}"
        )
        if r.status_code != 200:
            print(
                f"   ❌ HTTP hatası: {r.status_code}"
            )
            print(r.text[:500])
            return {}
        try:
            return r.json()
        except Exception as e:
            print(
                f"   ❌ JSON okunamadı: {e}"
            )
            print(r.text[:500])
            return {}
    except requests.Timeout:
        print(
            f"   ❌ Zaman aşımı: {url}"
        )
        return {}
    except requests.RequestException as e:
        print(
            f"   ❌ Bağlantı hatası: {e}"
        )
        return {}
    except Exception as e:
        print(
            f"   ❌ Beklenmeyen HTTP hatası: {e}"
        )
        return {}
# =========================================================
# GENEL TARİH PARSE
# =========================================================
def parse_any_date(value):
    """
    API'den gelebilecek çok farklı tarih formatlarını
    Türkiye tarihine çevirir.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TZ).date().isoformat()
    if isinstance(value, dict):
        for key in (
            "datetime",
            "date",
            "start",
            "startDate",
            "gameDate",
            "utcDate",
            "localDate",
            "startTime",
            "scheduled",
            "timestamp",
        ):
            if key in value and value[key] is not None:
                result = parse_any_date(value[key])
                if result:
                    return result
        return None
    value = str(value).strip()
    if not value:
        return None
    # Unix timestamp
    if value.isdigit():
        try:
            number = int(value)
            # milisaniye
            if number > 10_000_000_000:
                number = number / 1000
            dt = datetime.fromtimestamp(
                number,
                tz=timezone.utc,
            )
            return dt.astimezone(TZ).date().isoformat()
        except Exception:
            pass
    # ISO / RFC format
    try:
        v = value
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )
        return dt.astimezone(
            TZ
        ).date().isoformat()
    except Exception:
        pass
    # İlk 10 karakter YYYY-MM-DD
    if len(value) >= 10:
        first10 = value[:10]
        try:
            datetime.strptime(
                first10,
                "%Y-%m-%d",
            )
            return first10
        except Exception:
            pass
    # DD.MM.YYYY
    for fmt in (
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ):
        try:
            dt = datetime.strptime(
                value[:10],
                fmt,
            )
            return dt.date().isoformat()
        except Exception:
            pass
    return None
# =========================================================
# RECURSIVE TARİH ARAMA
# =========================================================
def find_date_recursive(obj, depth=0):
    """
    EuroLeague gibi payloadlarda tarih bazen birkaç
    seviyenin altında olabilir.
    """
    if depth > 5:
        return None
    if isinstance(obj, dict):
        # Öncelikli tarih alanları
        priority_keys = (
            "datetime",
            "date",
            "gameDate",
            "startDate",
            "utcDate",
            "localDate",
            "startTime",
            "scheduled",
            "timestamp",
        )
        for key in priority_keys:
            if key in obj:
                result = parse_any_date(
                    obj[key]
                )
                if result:
                    return result
        # Sonra diğer alanları tara
        for value in obj.values():
            if isinstance(
                value,
                (dict, list)
            ):
                result = find_date_recursive(
                    value,
                    depth + 1,
                )
                if result:
                    return result
    elif isinstance(obj, list):
        for item in obj[:50]:
            result = find_date_recursive(
                item,
                depth + 1,
            )
            if result:
                return result
    return None
# =========================================================
# NBA
# =========================================================
def nba_headers():
    if BALLDONTLIE_KEY:
        return {
            "Authorization":
                BALLDONTLIE_KEY
        }
    return {}
def normalize_nba_game(game):
    home = game.get(
        "home_team",
        {}
    )
    away = game.get(
        "visitor_team",
        {}
    )
    if not home.get("id"):
        return None
    if not away.get("id"):
        return None
    game_date = (
        parse_any_date(
            game.get("datetime")
        )
        or
        parse_any_date(
            game.get("date")
        )
    )
    if game_date != DATE:
        return None
    return {
        "id": game.get("id"),
        "league": "NBA",
        "league_id": "NBA",
        "season": game.get(
            "season"
        ),
        "home": {
            "id": home.get("id"),
            "name": home.get(
                "full_name"
            ),
        },
        "away": {
            "id": away.get("id"),
            "name": away.get(
                "full_name"
            ),
        },
        "raw": game,
    }
def get_nba_today():
    print()
    print(
        "🏀 NBA maçları alınıyor..."
    )
    if not BALLDONTLIE_KEY:
        print(
            "❌ BALLDONTLIE_API_KEY "
            "bulunamadı."
        )
        return []
    result = []
    # -----------------------------------------------------
    # Önce tarih filtresi
    # -----------------------------------------------------
    for season_type in (
        "preseason",
        "regular",
    ):
        data = get_json(
            NBA_URL,
            params={
                "dates[]": DATE,
                "season_type":
                    season_type,
                "per_page": 100,
            },
            headers=nba_headers(),
        )
        games = data.get(
            "data",
            []
        )
        print(
            f"   📦 NBA "
            f"{season_type}: "
            f"{len(games)}"
        )
        for game in games:
            item = normalize_nba_game(
                game
            )
            if item:
                result.append(item)
    # -----------------------------------------------------
    # API tarih filtresi boş dönerse
    # ikinci güvenlik sorgusu
    # -----------------------------------------------------
    if not result:
        print(
            "   🔎 NBA alternatif "
            "tarih sorgusu deneniyor..."
        )
        data = get_json(
            NBA_URL,
            params={
                "start_date": DATE,
                "end_date": DATE,
                "per_page": 100,
            },
            headers=nba_headers(),
        )
        games = data.get(
            "data",
            []
        )
        print(
            f"   📦 NBA alternatif: "
            f"{len(games)}"
        )
        for game in games:
            item = normalize_nba_game(
                game
            )
            if item:
                result.append(item)
    # Duplicate temizle
    unique = {}
    for game in result:
        key = str(
            game.get("id")
        )
        unique[key] = game
    result = list(
        unique.values()
    )
    print(
        f"   ✅ NBA bugün toplam: "
        f"{len(result)} maç"
    )
    # Debug
    for game in result:
        print(
            f"      • "
            f"{game['away']['name']} "
            f"- "
            f"{game['home']['name']}"
        )
    return result
# =========================================================
# NBA GEÇMİŞİ
# =========================================================
def get_nba_history(team_id):
    end_date = TODAY
    start_date = (
        end_date -
        timedelta(days=180)
    )
    result = []
    cursor = None
    # En fazla 5 sayfa
    for _ in range(5):
        params = {
            "team_ids[]":
                team_id,
            "start_date":
                start_date.isoformat(),
            "end_date":
                end_date.isoformat(),
            "per_page": 100,
        }
        if cursor:
            params["cursor"] = cursor
        data = get_json(
            NBA_URL,
            params=params,
            headers=nba_headers(),
        )
        games = data.get(
            "data",
            []
        )
        for game in games:
            home = game.get(
                "home_team",
                {}
            )
            away = game.get(
                "visitor_team",
                {}
            )
            home_score = game.get(
                "home_team_score"
            )
            away_score = game.get(
                "visitor_team_score"
            )
            if (
                home_score is None
                or
                away_score is None
            ):
                continue
            try:
                home_score = float(
                    home_score
                )
                away_score = float(
                    away_score
                )
            except Exception:
                continue
            # Gelecek / oynanmamış
            if (
                home_score == 0
                and
                away_score == 0
            ):
                continue
            game_date = (
                parse_any_date(
                    game.get(
                        "datetime"
                    )
                )
                or
                parse_any_date(
                    game.get(
                        "date"
                    )
                )
            )
            if not game_date:
                continue
            if (
                str(home.get("id"))
                == str(team_id)
            ):
                result.append({
                    "home": True,
                    "for": home_score,
                    "against":
                        away_score,
                    "date":
                        game_date,
                })
            elif (
                str(away.get("id"))
                == str(team_id)
            ):
                result.append({
                    "home": False,
                    "for": away_score,
                    "against":
                        home_score,
                    "date":
                        game_date,
                })
        meta = data.get(
            "meta",
            {}
        )
        cursor = meta.get(
            "next_cursor"
        )
        if not cursor:
            break
    result.sort(
        key=lambda x:
            x["date"],
        reverse=True,
    )
    return result
# =========================================================
# EUROLEAGUE
# =========================================================
def get_euroleague_all():
    print()
    print(
        "🌍 EuroLeague sezon verisi "
        "alınıyor..."
    )
    url = (
        f"{EUROLEAGUE_URL}"
        f"/v2/competitions/E"
        f"/seasons/"
        f"{EUROLEAGUE_SEASON}"
        f"/games"
    )
    data = get_json(url)
    games = data.get(
        "data",
        []
    )
    if not games:
        # Bazı cevaplarda doğrudan liste
        if isinstance(
            data,
            list
        ):
            games = data
    print(
        f"   📦 EuroLeague sezon maçları: "
        f"{len(games)}"
    )
    return games
# =========================================================
# EUROLEAGUE TAKIM
# =========================================================
def euro_home(game):
    for key in (
        "local",
        "home",
        "homeTeam",
        "localTeam",
    ):
        value = game.get(key)
        if isinstance(
            value,
            dict
        ):
            return value
    return {}
def euro_away(game):
    for key in (
        "road",
        "away",
        "awayTeam",
        "roadTeam",
    ):
        value = game.get(key)
        if isinstance(
            value,
            dict
        ):
            return value
    return {}
def euro_team_id(team):
    if not isinstance(
        team,
        dict
    ):
        return None
    for key in (
        "clubCode",
        "code",
        "id",
        "teamCode",
        "teamId",
        "clubId",
    ):
        value = team.get(key)
        if value is not None:
            return value
    return None
def euro_team_name(team):
    if not isinstance(
        team,
        dict
    ):
        return ""
    for key in (
        "name",
        "clubName",
        "nameShort",
        "teamName",
        "shortName",
    ):
        value = team.get(key)
        if value:
            return str(value)
    return ""
# =========================================================
# EUROLEAGUE TARİH
# =========================================================
def euro_date(game):
    if not isinstance(
        game,
        dict
    ):
        return None
    # Öncelikli alanlar
    for key in (
        "datetime",
        "date",
        "gameDate",
        "startDate",
        "utcDate",
        "localDate",
        "startTime",
        "scheduled",
        "timestamp",
    ):
        if key in game:
            parsed = parse_any_date(
                game.get(key)
            )
            if parsed:
                return parsed
    # Recursive fallback
    return find_date_recursive(
        game
    )
# =========================================================
# EUROLEAGUE BUGÜN
# =========================================================
def get_euroleague_today(
    all_games
):
    result = []
    # Debug için tarih dağılımı
    date_counter = {}
    for game in all_games:
        d = euro_date(game)
        if d:
            date_counter[d] = (
                date_counter.get(
                    d,
                    0
                ) + 1
            )
        if d != DATE:
            continue
        home = euro_home(
            game
        )
        away = euro_away(
            game
        )
        home_id = euro_team_id(
            home
        )
        away_id = euro_team_id(
            away
        )
        if home_id is None:
            continue
        if away_id is None:
            continue
        result.append({
            "id":
                game.get(
                    "gameCode"
                )
                or game.get("id"),
            "league":
                "EuroLeague",
            "league_id":
                "E",
            "season":
                EUROLEAGUE_SEASON,
            "home": {
                "id":
                    home_id,
                "name":
                    euro_team_name(
                        home
                    ),
            },
            "away": {
                "id":
                    away_id,
                "name":
                    euro_team_name(
                        away
                    ),
            },
            "raw": game,
        })
    print(
        f"   📦 EuroLeague bugün: "
        f"{len(result)} maç"
    )
    # Eğer 0 ise en yakın tarihleri göster
    if not result and date_counter:
        dates = sorted(
            date_counter.items()
        )
        print(
            "   🔎 API'den gelen "
            "tarih örnekleri:"
        )
        for d, count in dates[:15]:
            print(
                f"      {d}: "
                f"{count} maç"
            )
    for game in result:
        print(
            f"      • "
            f"{game['away']['name']} "
            f"- "
            f"{game['home']['name']}"
        )
    return result
# =========================================================
# EUROLEAGUE SKOR
# =========================================================
def euro_points(obj):
    if not isinstance(
        obj,
        dict
    ):
        return None
    for key in (
        "score",
        "points",
        "total",
        "homeScore",
        "awayScore",
        "localScore",
        "roadScore",
    ):
        value = obj.get(key)
        if value is not None:
            try:
                return float(
                    value
                )
            except Exception:
                pass
    return None
def euro_game_score(
    game,
    team_id
):
    home = euro_home(
        game
    )
    away = euro_away(
        game
    )
    home_id = euro_team_id(
        home
    )
    away_id = euro_team_id(
        away
    )
    home_score = euro_points(
        home
    )
    away_score = euro_points(
        away
    )
    if home_score is None:
        for key in (
            "homeScore",
            "localScore",
        ):
            if game.get(key) is not None:
                try:
                    home_score = float(
                        game.get(key)
                    )
                    break
                except Exception:
                    pass
    if away_score is None:
        for key in (
            "awayScore",
            "roadScore",
        ):
            if game.get(key) is not None:
                try:
                    away_score = float(
                        game.get(key)
                    )
                    break
                except Exception:
                    pass
    if (
        home_score is None
        or
        away_score is None
    ):
        return None
    d = euro_date(
        game
    )
    if not d:
        return None
    if str(home_id) == str(team_id):
        return {
            "home": True,
            "for":
                home_score,
            "against":
                away_score,
            "date": d,
        }
    if str(away_id) == str(team_id):
        return {
            "home": False,
            "for":
                away_score,
            "against":
                home_score,
            "date": d,
        }
    return None
# =========================================================
# EUROLEAGUE TAKIM GEÇMİŞİ
# =========================================================
def get_euro_history(
    team_id,
    all_games
):
    result = []
    for game in all_games:
        item = euro_game_score(
            game,
            team_id
        )
        if not item:
            continue
        # Bugün ve gelecek yok
        if item["date"] >= DATE:
            continue
        if (
            item["for"] == 0
            and
            item["against"] == 0
        ):
            continue
        result.append(
            item
        )
    result.sort(
        key=lambda x:
            x["date"],
        reverse=True,
    )
    return result
# =========================================================
# SON 5
# =========================================================
def last_5_home(history):
    return [
        x
        for x in history
        if x["home"]
    ][:5]
def last_5_away(history):
    return [
        x
        for x in history
        if not x["home"]
    ][:5]
# =========================================================
# ANALİZ
# =========================================================
def analyse(
    game,
    euro_games
):
    league = game[
        "league"
    ]
    home_id = game[
        "home"
    ]["id"]
    away_id = game[
        "away"
    ]["id"]
    print(
        f"\n🔎 "
        f"{game['home']['name']} "
        f"- "
        f"{game['away']['name']}"
    )
    if league == "NBA":
        home_history = (
            get_nba_history(
                home_id
            )
        )
        away_history = (
            get_nba_history(
                away_id
            )
        )
    else:
        home_history = (
            get_euro_history(
                home_id,
                euro_games
            )
        )
        away_history = (
            get_euro_history(
                away_id,
                euro_games
            )
        )
    home_games = last_5_home(
        home_history
    )
    away_games = last_5_away(
        away_history
    )
    print(
        f"   🏠 İç saha geçmişi: "
        f"{len(home_games)}"
    )
    print(
        f"   ✈️ Dış saha geçmişi: "
        f"{len(away_games)}"
    )
    if not home_games:
        print(
            "   ⚠️ Ev sahibi için "
            "yeterli veri yok."
        )
        return None
    if not away_games:
        print(
            "   ⚠️ Deplasman için "
            "yeterli veri yok."
        )
        return None
    home_for = mean(
        x["for"]
        for x in home_games
    )
    home_against = mean(
        x["against"]
        for x in home_games
    )
    away_for = mean(
        x["for"]
        for x in away_games
    )
    away_against = mean(
        x["against"]
        for x in away_games
    )
    expected_home = (
        home_for +
        away_against
    ) / 2
    expected_away = (
        away_for +
        home_against
    ) / 2
    match_total = (
        expected_home +
        expected_away
    )
    quarter_avg = (
        match_total / 4
    )
    first_half = (
        match_total / 2
    )
    sample = min(
        len(home_games),
        len(away_games)
    )
    confidence = {
        5: 85,
        4: 80,
        3: 75,
        2: 65,
        1: 55,
        0: 0,
    }.get(
        sample,
        0
    )
    print(
        f"   📊 Beklenen skor: "
        f"{expected_home:.1f} - "
        f"{expected_away:.1f}"
    )
    print(
        f"   📈 Maç toplamı: "
        f"{match_total:.1f}"
    )
    print(
        f"   🎯 Güven: "
        f"%{confidence}"
    )
    return {
        "id":
            game.get("id"),
        "league":
            league,
        "league_id":
            game.get(
                "league_id"
            ),
        "season":
            game.get(
                "season"
            ),
        "home":
            game["home"]["name"],
        "away":
            game["away"]["name"],
        "home_team_id":
            home_id,
        "away_team_id":
            away_id,
        "games":
            sample,
        "home_for_avg":
            round(
                home_for,
                2
            ),
        "home_against_avg":
            round(
                home_against,
                2
            ),
        "away_for_avg":
            round(
                away_for,
                2
            ),
        "away_against_avg":
            round(
                away_against,
                2
            ),
        "exp_home":
            round(
                expected_home,
                2
            ),
        "exp_away":
            round(
                expected_away,
                2
            ),
        "match_total":
            round(
                match_total,
                2
            ),
        "quarter_avg":
            round(
                quarter_avg,
                2
            ),
        "first_half":
            round(
                first_half,
                2
            ),
        "q1":
            round(
                quarter_avg,
                2
            ),
        "q2":
            round(
                quarter_avg,
                2
            ),
        "q3":
            round(
                quarter_avg,
                2
            ),
        "q4":
            round(
                quarter_avg,
                2
            ),
        "confidence":
            confidence,
        "date":
            DATE,
    }
# =========================================================
# ANA
# =========================================================
def main():
    print("=" * 55)
    print(
        "🏀 NBA + EUROLEAGUE "
        "BASKETBOL ANALİZİ"
    )
    print("=" * 55)
    print(
        f"📅 Türkiye tarihi: {DATE}"
    )
    # -----------------------------------------------------
    # NBA
    # -----------------------------------------------------
    nba_games = (
        get_nba_today()
    )
    # -----------------------------------------------------
    # EURO
    # -----------------------------------------------------
    euro_all = (
        get_euroleague_all()
    )
    euro_today = (
        get_euroleague_today(
            euro_all
        )
    )
    # -----------------------------------------------------
    # BİRLEŞTİR
    # -----------------------------------------------------
    all_games = (
        nba_games +
        euro_today
    )
    print()
    print(
        f"🎯 Toplam maç: "
        f"{len(all_games)}"
    )
    # -----------------------------------------------------
    # 0 MAÇ
    # -----------------------------------------------------
    if not all_games:
        print()
        print(
            "⚠️ Bugün için API'lerden "
            "hiç maç bulunamadı."
        )
        output = {
            DATE: []
        }
        with open(
            OUTPUT_FILE,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump(
                output,
                f,
                ensure_ascii=False,
                indent=2
            )
        print(
            "📁 data.json boş gün olarak "
            "güncellendi."
        )
        return
    # -----------------------------------------------------
    # ANALİZ
    # -----------------------------------------------------
    results = []
    for i, game in enumerate(
        all_games,
        1
    ):
        print(
            f"\n[{i}/{len(all_games)}] "
            f"{game['league']}"
        )
        try:
            result = analyse(
                game,
                euro_all
            )
            if result:
                results.append(
                    result
                )
        except Exception as e:
            print(
                f"❌ Analiz hatası: "
                f"{e}"
            )
    # -----------------------------------------------------
    # JSON
    # -----------------------------------------------------
    output = {
        DATE: results
    }
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )
    print()
    print("=" * 55)
    print(
        f"✅ {len(results)} maç analiz edildi."
    )
    print(
        f"📁 {OUTPUT_FILE}"
    )
    print("=" * 55)
if __name__ == "__main__":
    main()
