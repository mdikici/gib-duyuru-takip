import requests
from bs4 import BeautifulSoup
import hashlib
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# ============ AYARLAR ============
URL = "https://ynokc.gib.gov.tr/Home/DuyuruArsiv"

# Hash dosyası repoda saklanacak
HASH_FILE = "son_hash.txt"

# GitHub Secrets'tan okunacak (aşağıda tanımlayacağız)
GONDEREN_EMAIL = os.environ.get("GONDEREN_EMAIL")
GONDEREN_SIFRE = os.environ.get("GONDEREN_SIFRE")
ALICI_EMAIL = "mrtdkc@gmail.com"
# ==================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36"
}


def sayfa_hash_al():
    r = requests.get(URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    body = soup.find("body")
    metin = body.get_text(separator=" ", strip=True) if body else r.text
    return hashlib.sha256(metin.encode("utf-8")).hexdigest(), metin


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


def kontrol_et():
    try:
        yeni_hash, metin = sayfa_hash_al()
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Sayfa alınamadı: {e}")
        return

    if os.path.exists(HASH_FILE):
        eski_hash = open(HASH_FILE, encoding="utf-8").read().strip()
        if eski_hash != yeni_hash:
            print(f"[{time.strftime('%H:%M:%S')}] 🔔 DEĞİŞİKLİK VAR!")
            email_gonder(
                "🔔 GİB Duyuru Arşivi Değişti!",
                f"İzlenen sayfada değişiklik var.\n\nURL: {URL}\n"
                f"Zaman: {time.strftime('%d.%m.%Y %H:%M:%S')}\n"
            )
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Değişiklik yok.")
    else:
        print(f"[{time.strftime('%H:%M:%S')}] İlk kayıt oluşturuldu.")

    with open(HASH_FILE, "w", encoding="utf-8") as f:
        f.write(yeni_hash)


if __name__ == "__main__":
    kontrol_et()
