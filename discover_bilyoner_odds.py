import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


OUTPUT_FILE = Path("bilyoner_network.json")

BILYONER_URL = "https://www.bilyoner.com/iddaa/basketbol"

TIMEOUT = 60_000


def clean(value):
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value).strip()
    )


def looks_like_odds_response(data):
    """
    Gelen JSON'un bahis/oran verisi olma ihtimalini kontrol eder.
    Burada endpoint'i önceden bilmek yerine içeriği arıyoruz.
    """

    if not isinstance(data, (dict, list)):
        return False

    text = json.dumps(
        data,
        ensure_ascii=False
    ).lower()

    keywords = [
        "odds",
        "odd",
        "market",
        "markets",
        "outcome",
        "outcomes",
        "selection",
        "selections",
        "bettype",
        "bettypeid",
        "event",
        "eventid",
        "line",
        "handicap",
        "total",
        "over",
        "under",
        "alt",
        "üst",
        "ust",
    ]

    score = 0

    for keyword in keywords:
        if keyword in text:
            score += 1

    return score >= 3


def looks_like_json_response(response):
    content_type = clean(
        response.headers.get(
            "content-type"
        )
    ).lower()

    url = response.url.lower()

    if "application/json" in content_type:
        return True

    if url.endswith(".json"):
        return True

    if "/api/" in url:
        return True

    if "graphql" in url:
        return True

    if "ajax" in url:
        return True

    return False


def main():

    print("=" * 70)
    print("🔎 BİLYONER BASKETBOL ODDS API KEŞFİ")
    print("=" * 70)

    captured = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            viewport={
                "width": 1440,
                "height": 1000,
            },
            locale="tr-TR",
        )

        page = context.new_page()

        def handle_response(response):

            try:

                if not looks_like_json_response(
                    response
                ):
                    return

                url = response.url

                print()
                print("📡 JSON:")
                print(url)

                try:
                    data = response.json()
                except Exception:
                    return

                if not looks_like_odds_response(
                    data
                ):
                    return

                print(
                    "🎯 ODDS/BET MARKET ADAYI BULUNDU"
                )

                captured.append({
                    "url": url,
                    "method": response.request.method,
                    "status": response.status,
                    "contentType": response.headers.get(
                        "content-type",
                        ""
                    ),
                    "data": data,
                })

            except Exception as e:

                print(
                    f"⚠️ Response okunamadı: {e}"
                )

        page.on(
            "response",
            handle_response
        )

        print()
        print(
            "🌐 Bilyoner basketbol sayfası açılıyor..."
        )

        try:

            page.goto(
                BILYONER_URL,
                wait_until="domcontentloaded",
                timeout=TIMEOUT,
            )

        except Exception as e:

            print(
                f"⚠️ Sayfa açılış uyarısı: {e}"
            )

        print()
        print(
            "⏳ Sayfa verileri bekleniyor..."
        )

        time.sleep(10)

        # ====================================================
        # SAYFAYI AŞAĞI KAYDIR
        # ====================================================

        print(
            "📜 Sayfa aşağı kaydırılıyor..."
        )

        for _ in range(8):

            try:

                page.mouse.wheel(
                    0,
                    1200
                )

            except Exception:
                pass

            time.sleep(1)

        # ====================================================
        # BİRAZ DAHA BEKLE
        # ====================================================

        print(
            "⏳ Ek market istekleri bekleniyor..."
        )

        time.sleep(10)

        # ====================================================
        # SAYFA METNİ
        # ====================================================

        try:

            body_text = page.locator(
                "body"
            ).inner_text()

            print()
            print("=" * 70)
            print("📄 SAYFA KONTROLÜ")
            print("=" * 70)

            keywords = [
                "Toplam Sayı",
                "Toplam Puan",
                "Alt",
                "Üst",
                "Ev Sahibi",
                "Deplasman",
                "İlk Yarı",
                "Çeyrek",
            ]

            for keyword in keywords:

                if keyword.lower() in body_text.lower():

                    print(
                        f"✅ {keyword}"
                    )

                else:

                    print(
                        f"❌ {keyword}"
                    )

        except Exception as e:

            print(
                f"⚠️ Sayfa metni okunamadı: {e}"
            )

        browser.close()

    # ========================================================
    # SONUÇLARI KAYDET
    # ========================================================

    print()
    print("=" * 70)
    print("💾 SONUÇ")
    print("=" * 70)

    if not captured:

        print(
            "❌ Odds JSON endpointi yakalanamadı."
        )

        print()
        print(
            "Bilyoner sayfası büyük ihtimalle "
            "market verisini farklı bir istemci mekanizmasıyla yüklüyor."
        )

        # Boş debug dosyası yine oluşturulsun.

        OUTPUT_FILE.write_text(
            json.dumps(
                {
                    "captured": [],
                    "message": (
                        "Odds endpoint bulunamadı."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return

    # Aynı URL'leri tekilleştir.

    unique = {}

    for item in captured:

        url = item["url"]

        if url not in unique:
            unique[url] = item

    result = {
        "capturedAt": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ",
            time.gmtime()
        ),
        "count": len(unique),
        "responses": list(
            unique.values()
        ),
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"✅ {len(unique)} farklı odds endpoint adayı kaydedildi."
    )

    for url in unique:

        print()
        print(
            "🎯",
            url
        )

    print()
    print(
        f"📁 {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
