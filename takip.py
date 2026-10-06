import requests
from bs4 import BeautifulSoup
import hashlib
import os
import smtplib
import difflib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# ============ İZLENECEK URL'LER ============
URL_LISTESI = [
    {
        "isim": "GİB Duyuru Arşivi (Güncel)",
        "url":  "https://www.gib.gov.tr/duyuru-arsivi/guncel",
        "hash_file": "hash_gib_guncel.txt",
        "text_file": "text_gib_guncel.txt",
        "api": "https://gib.gov.tr/api/gibportal/duyuru/listPublish",
    },
    {
        "isim": "YN ÖKC Duyuru Arşivi",
        "url":  "https://ynokc.gib.gov.tr/Home/DuyuruArsiv",
        "hash_file": "hash_ynokc.txt",
        "text_file": "text_ynokc.txt",
    },
    {
        "isim": "eBelge Duyuruları",
        "url":  "https://ebelge.gib.gov.tr/duyurular.html",
        "hash_file": "hash_ebelge.txt",
        "text_file": "text_ebelge.txt",
    },
    {
        "isim": "Onay Alan Firmalar (1003)",
        "url":  "https://ynokc.gib.gov.tr/Home/OnayAlanFirmalar/1003",
        "hash_file": "hash_onay_firmalar.txt",
        "text_file": "text_onay_firmalar.txt",
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


def sayfa_icerik_al(site):
    """Sayfanın metnini ve hash'ini döndürür."""
    url = site["url"]

    if site.get("api"):
        # API POST metodu istiyor
        payload = {
            "preview": False,
            "page": 0,
            "size": 50,
            "sortFieldName": "startdate",
            "sortType": "DESC"
        }
        r = requests.post(
            site["api"],
            json=payload,
            headers=HEADERS,
            timeout=20
        )
        r.raise_for_status()
        metin = r.text
    else:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        body = soup.find("body")
        metin = body.get_text(separator="\n", strip=True) if body else r.text

    icerik_hash = hashlib.sha256(metin.encode("utf-8")).hexdigest()
    return icerik_hash, metin


def fark_bul(eski_metin, yeni_metin, max_satir=30):
    """İki metin arasındaki farkı okunabilir şekilde döndürür."""
    eski_satirlar = eski_metin.splitlines()
    yeni_satirlar = yeni_metin.splitlines()

    farklar = []
    for satir in difflib.unified_diff(
        eski_satirlar, yeni_satirlar,
        lineterm="", n=1
    ):
        # Sadece eklenen (+) ve silinen (-) satırları al
        if satir.startswith("+") and not satir.startswith("+++"):
            farklar.append(f"➕ {satir[1:].strip()}")
        elif satir.startswith("-") and not satir.startswith("---"):
            farklar.append(f"➖ {satir[1:].strip()}")

        if len(farklar) >= max_satir:
            farklar.append("... (daha fazla fark var)")
            break

    return "\n".join(farklar) if farklar else "(Metin farkı hesaplanamadı)"


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
    hash_file = site["hash_file"]
    text_file = site["text_file"]

    try:
        yeni_hash, yeni_metin = sayfa_icerik_al(site)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ {isim} alınamadı: {e}")
        return None

    # İlk kayıt
    if not os.path.exists(hash_file) or not os.path.exists(text_file):
        print(f"[{time.strftime('%H:%M:%S')}] İlk kayıt: {isim}")
        with open(hash_file, "w", encoding="utf-8") as f:
            f.write(yeni_hash)
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(yeni_metin)
        return None

    eski_hash = open(hash_file, encoding="utf-8").read().strip()
    eski_metin = open(text_file, encoding="utf-8").read()

    if eski_hash != yeni_hash:
        print(f"[{time.strftime('%H:%M:%S')}] 🔔 DEĞİŞİKLİK: {isim}")
        fark = fark_bul(eski_metin, yeni_metin)

        # Güncel hash ve metni kaydet
        with open(hash_file, "w", encoding="utf-8") as f:
            f.write(yeni_hash)
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(yeni_metin)

        return {"isim": isim, "url": site["url"], "fark": fark}
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Değişiklik yok: {isim}")
        return None


def main():
    degisenler = []

    for site in URL_LISTESI:
        sonuc = kontrol_et(site)
        if sonuc:
            degisenler.append(sonuc)

    if degisenler:
        parcalar = []
        for d in degisenler:
            parcalar.append(
                f"═══════════════════════════════════\n"
                f"📍 {d['isim']}\n"
                f"🔗 {d['url']}\n"
                f"───────────────────────────────────\n"
                f"{d['fark']}\n"
            )
        icerik = (
            f"Aşağıdaki sayfalarda değişiklik tespit edildi:\n\n"
            + "\n".join(parcalar)
            + f"\n⏰ Zaman: {time.strftime('%d.%m.%Y %H:%M:%S')}\n"
        )
        email_gonder("🔔 Sayfa Değişikliği Tespit Edildi", icerik)
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Hiçbir sayfada değişiklik yok.")


if __name__ == "__main__":
    main()
