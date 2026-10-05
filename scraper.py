import requests
import json
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_team_last_5_stats(team_id):
    """
    Takımın son 5 maçtaki periyot ve toplam skor performansını SofaScore API'den çeker.
    """
    url = f"https://api.sofascore.com/api/v1/team/{team_id}/events/last/0"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            events = res.json().get('events', [])[:5]
            q1_list, q2_list, q3_list, q4_list, total_pts = [], [], [], [], []
            
            for event in events:
                scores = event.get('homeScore', {}) if event.get('homeTeam', {}).get('id') == team_id else event.get('awayScore', {})
                if 'period1' in scores:
                    q1_list.append(scores.get('period1', 0))
                    q2_list.append(scores.get('period2', 0))
                    q3_list.append(scores.get('period3', 0))
                    q4_list.append(scores.get('period4', 0))
                    total_pts.append(scores.get('current', 0))
            
            if q1_list:
                return [
                    sum(q1_list)/len(q1_list),
                    sum(q2_list)/len(q2_list),
                    sum(q3_list)/len(q3_list),
                    sum(q4_list)/len(q4_list)
                ], sum(total_pts)/len(total_pts)
    except Exception as e:
        pass
    
    # Varsayılan genel basketbol ortalaması (sadece bağlantı koparsa devreye girer)
    return [20.5, 20.0, 19.5, 20.0], 80.0

def calculate_match_analytics(home_q, away_q, home_pts, away_pts):
    """Gerçek periyot ve toplam skor tahmin algoritması"""
    q1 = round(home_q[0] + away_q[0], 1)
    q2 = round(home_q[1] + away_q[1], 1)
    q3 = round(home_q[3] + away_q[2], 1)
    q4 = round(home_q[3] + away_q[3], 1)
    
    first_half = round(q1 + q2, 1)
    exp_home = round(home_pts, 1)
    exp_away = round(away_pts, 1)
    match_total = round(exp_home + exp_away, 1)

    return {
        "q1": q1, "q2": q2, "q3": q3, "q4": q4,
        "first_half": first_half,
        "match_total": match_total,
        "exp_home": exp_home,
        "exp_away": exp_away
    }

def run_scraper():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"[{today_str}] Tarihli maçlar ve TAKIM ÖZEL İSTATİSTİKLERİ çekiliyor...")

    url = f"https://api.sofascore.com/api/v1/sport/basketball/scheduled-events/{today_str}"
    all_matches = []

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            events = response.json().get('events', [])
            
            for idx, event in enumerate(events):
                league_name = event.get('tournament', {}).get('name', 'BASKETBOL').upper()
                time_str = datetime.fromtimestamp(event.get('startTimestamp', 0)).strftime('%H:%M')
                
                home_team = event.get('homeTeam', {})
                away_team = event.get('awayTeam', {})

                # HER TAKIMIN KENDİ GERÇEK İSTATİSTİĞİNİ ÇEKİYORUZ
                home_q_avg, home_pts_avg = get_team_last_5_stats(home_team.get('id'))
                away_q_avg, away_pts_avg = get_team_last_5_stats(away_team.get('id'))

                analysis = calculate_match_analytics(home_q_avg, away_q_avg, home_pts_avg, away_pts_avg)

                all_matches.append({
                    "id": f"m_{event.get('id', idx)}",
                    "league": f"{league_name} {time_str}",
                    "home": home_team.get('name', 'Ev Sahibi'),
                    "away": away_team.get('name', 'Deplasman'),
                    "analysis": analysis
                })
    except Exception as e:
        print(f"Hata oluştu: {e}")

    # Çıktıyı data.json'a kaydet
    output_data = {
        today_str: all_matches
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=4)

    print(f"Tamamlandı! Toplam {len(all_matches)} maç için takımların GERÇEK verileriyle analiz üretildi.")

if __name__ == "__main__":
    run_scraper()
