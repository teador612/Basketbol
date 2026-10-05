import requests
import json
import time
from datetime import datetime
from statistics import mean

BASE = "https://www.sofascore.com/api/v1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

REQUEST_TIMEOUT = 10
HISTORY_PAGES = 2
MAX_MATCHES_PER_TEAM = 10


def get_json(url):
    try:
        response = SESSION.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        print(f"API {response.status_code}: {url}")
    except Exception as e:
        print(f"API hatası: {e}")
    return None


def safe_mean(values, fallback=0):
    values = [float(x) for x in values if x is not None]
    if not values:
        return fallback
    return mean(values)


def get_score_value(score, key):
    value = score.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def get_team_score(event, team_id):
    """
    Takımın bu maçta attığı skor ve periyot skorlarını döndürür.
    """
    home_team = event.get("homeTeam", {})
    away_team = event.get("awayTeam", {})

    if home_team.get("id") == team_id:
        score = event.get("homeScore", {})
    elif away_team.get("id") == team_id:
        score = event.get("awayScore", {})
    else:
        return None

    current = (
        get_score_value(score, "current")
        or get_score_value(score, "display")
    )

    q1 = get_score_value(score, "period1")
    q2 = get_score_value(score, "period2")
    q3 = get_score_value(score, "period3")
    q4 = get_score_value(score, "period4")

    if current is None:
        return None

    if None in (q1, q2, q3, q4):
        return None

    return {
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "q4": q4,
        "total": current,
    }


def get_last_matches(team_id):
    """
    Takımın tamamlanmış son maçlarını getirir.
    İlk 10 geçerli maç alınır.
    """
    matches = []

    for page in range(HISTORY_PAGES):
        url = f"{BASE}/team/{team_id}/events/last/{page}"
        data = get_json(url)

        if not data:
            continue

        events = data.get("events", [])

        for event in events:
            status = event.get("status", {})

            # Sadece tamamlanmış maçlar
            if status.get("type") != "finished":
                continue

            score = get_team_score(event, team_id)

            if not score:
                continue

            home = event.get("homeTeam", {})
            away = event.get("awayTeam", {})

            is_home = home.get("id") == team_id

            opponent_score = (
                event.get("awayScore", {})
                if is_home
                else event.get("homeScore", {})
            )

            opponent_total = (
                get_score_value(opponent_score, "current")
                or get_score_value(opponent_score, "display")
            )

            if opponent_total is None:
                continue

            matches.append({
                "home": is_home,
                "team_total": score["total"],
                "opponent_total": opponent_total,
                "q1": score["q1"],
                "q2": score["q2"],
                "q3": score["q3"],
                "q4": score["q4"],
            })

            if len(matches) >= MAX_MATCHES_PER_TEAM:
                return matches

        time.sleep(0.15)

    return matches


def calculate_team_stats(matches):
    """
    Takımın son maçlarından hücum + savunma + periyot
    ortalamalarını hesaplar.
    """
    if not matches:
        return None

    home_matches = [m for m in matches if m["home"]]
    away_matches = [m for m in matches if not m["home"]]

    stats = {
        "games": len(matches),
        "points": safe_mean([m["team_total"] for m in matches], 80),
        "allowed": safe_mean([m["opponent_total"] for m in matches], 80),
        "q1": safe_mean([m["q1"] for m in matches], 20),
        "q2": safe_mean([m["q2"] for m in matches], 20),
        "q3": safe_mean([m["q3"] for m in matches], 20),
        "q4": safe_mean([m["q4"] for m in matches], 20),
    }

    # Ev/deplasman performansı
    stats["home_points"] = safe_mean([m["team_total"] for m in home_matches], stats["points"])
    stats["home_allowed"] = safe_mean([m["opponent_total"] for m in home_matches], stats["allowed"])
    stats["away_points"] = safe_mean([m["team_total"] for m in away_matches], stats["points"])
    stats["away_allowed"] = safe_mean([m["opponent_total"] for m in away_matches], stats["allowed"])

    return stats


def calculate_period_prediction(home_stats, away_stats):
    """
    Hücum + rakip savunması üzerinden periyot tahmini.
    """
    home_attack = home_stats["points"]
    away_attack = away_stats["points"]

    home_defense = home_stats["allowed"]
    away_defense = away_stats["allowed"]

    home_attack_adj = (home_attack * 0.65 + home_stats["home_points"] * 0.35)
    away_attack_adj = (away_attack * 0.65 + away_stats["away_points"] * 0.35)

    home_defense_adj = (home_defense * 0.65 + home_stats["home_allowed"] * 0.35)
    away_defense_adj = (away_defense * 0.65 + away_stats["away_allowed"] * 0.35)

    expected_home = (home_attack_adj * 0.55 + away_defense_adj * 0.45)
    expected_away = (away_attack_adj * 0.55 + home_defense_adj * 0.45)

    home_q = [home_stats["q1"], home_stats["q2"], home_stats["q3"], home_stats["q4"]]
    away_q = [away_stats["q1"], away_stats["q2"], away_stats["q3"], away_stats["q4"]]

    home_q_total = sum(home_q) if sum(home_q) > 0 else 80
    away_q_total = sum(away_q) if sum(away_q) > 0 else 80

    home_ratio = expected_home / home_q_total
    away_ratio = expected_away / away_q_total

    home_periods = [x * home_ratio for x in home_q]
    away_periods = [x * away_ratio for x in away_q]

    q1 = home_periods[0] + away_periods[0]
    q2 = home_periods[1] + away_periods[1]
    q3 = home_periods[2] + away_periods[2]
    q4 = home_periods[3] + away_periods[3]

    first_half = q1 + q2
    match_total = expected_home + expected_away

    return {
        "q1": round(q1, 1),
        "q2": round(q2, 1),
        "q3": round(q3, 1),
        "q4": round(q4, 1),
        "first_half": round(first_half, 1),
        "match_total": round(match_total, 1),
        "exp_home": round(expected_home, 1),
        "exp_away": round(expected_away, 1),
    }


def calculate_confidence(home_stats, away_stats):
    games = min(home_stats["games"], away_stats["games"])
    data_score = min(games / 10, 1) * 60
    quality_score = 40
    return round(min(100, data_score + quality_score), 1)


def run_scraper():
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"{BASE}/sport/basketball/scheduled-events/{today}"

    data = get_json(url)
    if not data:
        print("❌ Günün maçları alınamadı.")
        return

    events = data.get("events", [])
    all_matches = []

    for index, event in enumerate(events):
        home_team = event.get("homeTeam", {})
        away_team = event.get("awayTeam", {})

        home_id = home_team.get("id")
        away_id = away_team.get("id")

        if not home_id or not away_id:
            continue

        home_name = home_team.get("name", "Ev Sahibi")
        away_name = away_team.get("name", "Deplasman")
        league = event.get("tournament", {}).get("name", "BASKETBOL").upper()
        timestamp = event.get("startTimestamp", 0)

        try:
            time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M")
        except Exception:
            time_str = "--:--"

        home_matches = get_last_matches(home_id)
        away_matches = get_last_matches(away_id)

        home_stats = calculate_team_stats(home_matches)
        away_stats = calculate_team_stats(away_matches)

        fallback_stats = {
            "games": 0, "points": 80, "allowed": 80,
            "q1": 20, "q2": 20, "q3": 20, "q4": 20,
            "home_points": 80, "home_allowed": 80,
            "away_points": 80, "away_allowed": 80
        }

        if not home_stats: home_stats = fallback_stats
        if not away_stats: away_stats = fallback_stats

        analysis = calculate_period_prediction(home_stats, away_stats)
        confidence = calculate_confidence(home_stats, away_stats)

        analysis["confidence"] = confidence
        analysis["home_games"] = home_stats["games"]
        analysis["away_games"] = away_stats["games"]

        all_matches.append({
            "id": f"m_{event.get('id', index)}",
            "league": f"{league} {time_str}",
            "home": home_name,
            "away": away_name,
            "homeId": home_id,
            "awayId": away_id,
            "analysis": analysis,
            "stats": {
                "home": {
                    "games": home_stats["games"],
                    "points": round(home_stats["points"], 1),
                    "allowed": round(home_stats["allowed"], 1)
                },
                "away": {
                    "games": away_stats["games"],
                    "points": round(away_stats["points"], 1),
                    "allowed": round(away_stats["allowed"], 1)
                }
            }
        })

    output = {today: all_matches}
    with open("data.json", "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    run_scraper()
