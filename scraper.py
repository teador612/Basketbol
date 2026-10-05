import requests
from bs4 import BeautifulSoup
import json
import time

def calculate_match_analytics(home_q_avg, away_q_avg, home_pts_avg, away_pts_avg):
    """Görseldeki matematiksel analiz mantığı"""
    q1 = round(home_q_avg[0] + away_q_avg[0], 1)
    q2 = round(home_q_avg[1] + away_q_avg[1], 1)
    q3 = round(home_q_avg[2] + away_q_avg[2], 1)
    q4 = round(home_q_avg[3] + away_q_avg[3], 1)
    
    first_half = round(q1 + q2, 1)
    
    exp_home = round(home_pts_avg, 1)
    exp_away = round(away_pts_avg, 1)
    match_total = round(exp_home + exp_away, 1)

    return {
        "q1": q1, "q2": q2, "q3": q3, "q4": q4,
        "first_half": first_half,
        "match_total": match_total,
        "exp_home": exp_home,
        "exp_away": exp_away
    }

def fetch_and_save_data():
    # Gerçek canlı veri çekme simülasyonu / Flashscore entegrasyonu
    # (Siteden dönen veriler bu JSON formatına dönüştürülür)
    matches_data = [
        {
            "id": "m1",
            "league": "EUROLEAGUE 21:05",
            "home": "Maccabi Tel Aviv",
            "away": "Besiktas",
            "analysis": calculate_match_analytics(
                home_q_avg=[22.1, 21.3, 21.0, 25.3],
                away_q_avg=[19.2, 21.0, 19.9, 13.9],
                home_pts_avg=89.7,
                away_pts_avg=74.0
            )
        },
        {
            "id": "m2",
            "league": "EUROCUP 18:30",
            "home": "Siauliai",
            "away": "London Lions",
            "analysis": calculate_match_analytics(
                home_q_avg=[20.0, 19.5, 18.2, 19.2],
                away_q_avg=[21.2, 21.0, 21.2, 21.2],
                home_pts_avg=76.9,
                away_pts_avg=84.6
            )
        }
    ]

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(matches_data, f, ensure_ascii=False, indent=4)
    print("data.json başarıyla güncellendi!")

if __name__ == "__main__":
    fetch_and_save_data()
