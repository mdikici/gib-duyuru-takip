import requests
from bs4 import BeautifulSoup
import hashlib
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# ============ İZLENECEK URL'LER ============
URL_LISTESI = [
    {
        "isim": "GİB Duyuru Arşivi (Güncel)",
        "url":  "https://www.gib.gov.tr/duyuru-arsivi/guncel",
        "hash_file": "hash_gib_guncel.txt",
        "notified_file": "notified_gib_guncel.txt",
        "text_file": "text_gib_guncel.txt",
        "api": "https://gib.gov.tr/api/gibportal/duyuru/listPublish",
    },
    {
        "isim": "YN ÖKC Duyuru Arşivi",
        "url":  "https://ynokc.gib.gov.tr/Home/DuyuruArsiv",
        "hash_file": "hash_ynokc.txt",
        "notified_file": "notified_ynokc.txt",
        "text_file": "text_ynokc.txt",
    },
    {
        "isim": "eBelge Duyuruları",
        "url":  "https://ebelge.gib.gov.tr/duyurular.html",
        "hash_file": "hash_ebelge.txt",
        "notified_file": "notified_ebelge.txt",
        "text_file": "text_ebelge.txt",
    },
    {
        "isim": "Onay Alan Firmalar (1003)",
        "url":  "https://ynokc.gib.gov.tr/Home/OnayAlanFirmalar/1003",
        "hash_file": "hash_onay_firmalar.txt",
        "notified_file": "notified_onay_firmalar.txt",
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


def yeni_satirlari_bul(eski_metin, yeni_metin, max_satir=30):
    """Yeni metinde olup eski metinde olmayan satırları döndürür."""
    eski_set = set(s.strip() for s in eski_metin.splitlines() if s.strip())
    yeni_satirlar = [s.strip() for s in yeni_metin.splitlines() if s.strip()]

    yeni_eklenenler = []
    for satir in yeni_satirlar:
        if satir not in eski_set:
            yeni_eklenenler.append(satir)
            if len(yeni_eklenenler) >= max_satir:
                yeni_eklenenler.append("... (daha fazla yeni içerik var)")
                break

    return yeni_eklenenler


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
        return True
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ E-posta hatası: {e}")
        return False


def kontrol_et(site):
    isim = site["isim"]
    hash_file = site["hash_file"]
    notified_file = site["notified_file"]
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
        # İlk kayıtta bildirim yapılmadı, notified dosyasını da yaz
        with open(notified_file, "w", encoding="utf-8") as f:
            f.write(yeni_hash)
        return None

    eski_hash = open(hash_file, encoding="utf-8").read().strip()
    eski_metin = open(text_file, encoding="utf-8").read()

    # Son bildirilen hash'i oku (yoksa eski hash kabul et)
    if os.path.exists(notified_file):
        son_bildirilen_hash = open(notified_file, encoding="utf-8").read().strip()
    else:
        son_bildirilen_hash = ""

    # Hash aynıysa hiçbir şey yapma
    if eski_hash == yeni_hash:
        print(f"[{time.strftime('%H:%M:%S')}] Değişiklik yok: {isim}")
        # Hash dosyasını güncelle (içerik değişmemiş olsa da tutarlılık için)
        with open(hash_file, "w", encoding="utf-8") as f:
            f.write(yeni_hash)
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(yeni_metin)
        return None

    # Hash değişti ama bu değişiklik DAHA ÖNCE bildirilmiş mi?
    if yeni_hash == son_bildirilen_hash:
        print(f"[{time.strftime('%H:%M:%S')}] Değişiklik var ama zaten bildirilmiş: {isim}")
        with open(hash_file, "w", encoding="utf-8") as f:
            f.write(yeni_hash)
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(yeni_metin)
        return None

    # Gerçekten yeni bir değişiklik var → bildir
    print(f"[{time.strftime('%H:%M:%S')}] 🔔 YENİ DEĞİŞİKLİK: {isim}")

    yeni_icerikler = yeni_satirlari_bul(eski_metin, yeni_metin)

    # Güncel hash, metin ve bildirilen hash'i kaydet
    with open(hash_file, "w", encoding="utf-8") as f:
        f.write(yeni_hash)
    with open(text_file, "w", encoding="utf-8") as f:
        f.write(yeni_metin)
    with open(notified_file, "w", encoding="utf-8") as f:
        f.write(yeni_hash)

    return {
        "isim": isim,
        "url": site["url"],
        "yeni_icerikler": yeni_icerikler,
    }


def main():
    degisenler = []

    for site in URL_LISTESI:
        sonuc = kontrol_et(site)
        if sonuc:
            degisenler.append(sonuc)

    if degisenler:
        parcalar = []
        for d in degisenler:
            satirlar = []
            for s in d["yeni_icerikler"]:
                if len(s) > 200:
                    s = s[:200] + "..."
                satirlar.append(f"  • {s}")

            if not satirlar:
                satirlar = ["  (yeni içerik tespit edilemedi)"]

            parcalar.append(
                f"📍 {d['isim']}\n"
                f"🔗 {d['url']}\n\n"
                f"Yeni içerik:\n"
                + "\n".join(satirlar)
                + "\n"
            )

        icerik = (
            f"Aşağıdaki sayfalarda yeni içerik tespit edildi:\n\n"
            + "\n" + ("─" * 40 + "\n").join(parcalar)
            + f"\n⏰ Zaman: {time.strftime('%d.%m.%Y %H:%M:%S')}\n"
        )
        email_gonder("🔔 Sayfa Güncellemesi", icerik)
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Hiçbir sayfada yeni değişiklik yok.")


if __name__ == "__main__":
    main()
