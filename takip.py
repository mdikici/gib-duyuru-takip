import requests
from bs4 import BeautifulSoup
import hashlib
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# ============ İZLENECEK URL'LER ============
# Buraya istediğin kadar URL ekleyebilirsin.
# Her URL için ayrı bir "isim" ve "hash dosyası" otomatik oluşturulur.
URL_LISTESI = [
    {
        "isim": "GİB ynökc",
        "url":  "https://ynokc.gib.gov.tr/Home/DuyuruArsiv",
        "hash_file": "hash_gib.txt",
    },
    {
        "isim": "GİB duyuru",
        "url":  "https://www.gib.gov.tr/duyuru-arsivi/guncel",
        "hash_file": "hash_sayfa2.txt",
    },
    {
        "isim": "GİB e-belge",
        "url":  "https://ebelge.gib.gov.tr/duyurular.html",
        "hash_file": "hash_sayfa3.txt",
    },
]

# ============ E-POSTA AYARLARI ============
GONDEREN_EMAIL = os.environ.get("GONDEREN_EMAIL")
GONDEREN_SIFRE = os.environ.get("GONDEREN_SIFRE")
ALICI_EMAIL = "mrtdkc@gmail.com"
# ==========================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36"
}


def sayfa_hash_al(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    body = soup.find("body")
    metin = body.get_text(separator=" ", strip=True) if body else r.text
    return hashlib.sha256(metin.encode("utf-8")).hexdigest()


def email_gonder(konu, icerik):
    msg = MIMEMultipart()
    msg["From"] = GONDEREN_EMAIL
    msg["To"] = ALICI_EMAIL
    msg["Subject"] = konu
    msg.attach(MIMEText(icerik, "plain", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GONDEREN_EMAIL, GONDEREN_SIFRE)
            server.send_message(msg)
        print(f"[{time.strftime('%H:%M:%S')}] ✅ E-posta gönderildi.")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ E-posta hatası: {e}")


def kontrol_et(site):
    isim = site["isim"]
    url = site["url"]
    hash_file = site["hash_file"]

    try:
        yeni_hash = sayfa_hash_al(url)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ {isim} alınamadı: {e}")
        return False

    if os.path.exists(hash_file):
        eski_hash = open(hash_file, encoding="utf-8").read().strip()
        if eski_hash != yeni_hash:
            print(f"[{time.strftime('%H:%M:%S')}] 🔔 DEĞİŞİKLİK: {isim}")
            with open(hash_file, "w", encoding="utf-8") as f:
                f.write(yeni_hash)
            return True
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Değişiklik yok: {isim}")
    else:
        print(f"[{time.strftime('%H:%M:%S')}] İlk kayıt: {isim}")

    with open(hash_file, "w", encoding="utf-8") as f:
        f.write(yeni_hash)
    return False


def main():
    degisenler = []

    for site in URL_LISTESI:
        if kontrol_et(site):
            degisenler.append(site)

    if degisenler:
        satirlar = []
        for s in degisenler:
            satirlar.append(f"• {s['isim']}\n  {s['url']}")
        icerik = (
            f"Aşağıdaki sayfalarda değişiklik tespit edildi:\n\n"
            + "\n\n".join(satirlar)
            + f"\n\nZaman: {time.strftime('%d.%m.%Y %H:%M:%S')}\n"
        )
        email_gonder("🔔 Sayfa Değişikliği Tespit Edildi", icerik)
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Hiçbir sayfada değişiklik yok.")


if __name__ == "__main__":
    main()
