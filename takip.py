import requests
from bs4 import BeautifulSoup
import hashlib
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
from datetime import datetime, timezone, timedelta

# ============ İZLENECEK URL'LER ============
URL_LISTESI = [
    {
        "isim": "GİB Duyuru Arşivi (Güncel)",
        "url": "https://www.gib.gov.tr/duyuru-arsivi/guncel",
        "hash_file": "hash_gib_guncel.txt",
        "text_file": "text_gib_guncel.txt",
        "notified_file": "notified_gib_guncel.txt",
        # Artık API kullanmıyoruz, doğrudan HTML'den çekeceğiz.
    },
    {
        "isim": "YN ÖKC Duyuru Arşivi",
        "url": "https://ynokc.gib.gov.tr/Home/DuyuruArsiv",
        "hash_file": "hash_ynokc.txt",
        "text_file": "text_ynokc.txt",
        "notified_file": "notified_ynokc.txt",
    },
    {
        "isim": "eBelge Duyuruları",
        "url": "https://ebelge.gib.gov.tr/duyurular.html",
        "hash_file": "hash_ebelge.txt",
        "text_file": "text_ebelge.txt",
        "notified_file": "notified_ebelge.txt",
    },
    {
        "isim": "Onay Alan Firmalar (1003)",
        "url": "https://ynokc.gib.gov.tr/Home/OnayAlanFirmalar/1003",
        "hash_file": "hash_onay_firmalar.txt",
        "text_file": "text_onay_firmalar.txt",
        "notified_file": "notified_onay_firmalar.txt",
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

# Türkiye saat dilimi (UTC+3)
TR_TZ = timezone(timedelta(hours=3))


def tr_zaman(dt_str):
    """ISO formatındaki zamanı Türkiye saatine çevirir."""
    try:
        # Örnek: "2026-10-20T14:15:56.123929"
        dt = datetime.fromisoformat(dt_str)
        # Eğer saat dilimi yoksa UTC olduğunu varsay (API'den gelen 'ts' alanı)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt_tr = dt.astimezone(TR_TZ)
        return dt_tr.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return dt_str[:16].replace("T", " ")


def sayfa_icerik_al(site):
    """Sayfanın (stabil) metnini ve hash'ini döndürür."""
    url = site["url"]

    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # --- GİB Güncel sayfası için özel ayrıştırma ---
    if "duyuru-arsivi/guncel" in url:
        kayitlar = []
        # Sayfadaki duyuru başlıkları genellikle h3 veya h2 içinde yer alır.
        for baslik in soup.find_all(["h2", "h3"]):
            a = baslik.find("a")
            if not a:
                continue
            baslik_metni = a.get_text(strip=True)
            href = a.get("href", "")

            # Sayfadaki tarih bilgisini, başlığın bulunduğu kapsayıcıdan çekmeye çalış
            tarih_metni = ""
            parent = baslik.find_parent(["div", "article"])
            if parent:
                # Tarih genellikle "21.10.2026" formatındadır.
                import re
                m = re.search(r"\d{2}\.\d{2}\.\d{4}", parent.get_text())
                if m:
                    tarih_metni = m.group(0)

            if baslik_metni and href:
                kayitlar.append({
                    "tarih": tarih_metni,
                    "baslik": baslik_metni,
                    "link": href,
                })

        # Sıralamayı sabitle (tarih, sonra başlık)
        kayitlar.sort(key=lambda x: (x["tarih"], x["baslik"]))

        if kayitlar:
            # Her duyuruyu tek satırda sakla
            satirlar = [
                f"{k['tarih']} | {k['baslik']} | {k['link']}"
                for k in kayitlar
            ]
            metin = "\n".join(satirlar)
            print(f"[DEBUG] {site['isim']}: {len(kayitlar)} duyuru (HTML) çekildi")
        else:
            print(f"[DEBUG] {site['isim']}: duyuru bulunamadı, ham metin kullanılıyor")
            metin = soup.get_text(separator="\n", strip=True)
    else:
        # Diğer sayfalar için genel ayrıştırma
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
    text_file = site["text_file"]
    notified_file = site["notified_file"]

    try:
        yeni_hash, yeni_metin = sayfa_icerik_al(site)
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ {isim} alınamadı: {e}")
        return None

    # --- İlk kayıt ---
    if not os.path.exists(hash_file) or not os.path.exists(text_file):
        print(f"[{time.strftime('%H:%M:%S')}] İlk kayıt: {isim}")
        with open(hash_file, "w", encoding="utf-8") as f:
            f.write(yeni_hash)
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(yeni_metin)
        with open(notified_file, "w", encoding="utf-8") as f:
            f.write(yeni_hash)
        return None

    eski_hash = open(hash_file, encoding="utf-8").read().strip()
    eski_metin = open(text_file, encoding="utf-8").read()

    son_bildirilen_hash = ""
    if os.path.exists(notified_file):
        son_bildirilen_hash = open(notified_file, encoding="utf-8").read().strip()

    # --- Hash aynı → değişiklik yok ---
    if eski_hash == yeni_hash:
        print(f"[{time.strftime('%H:%M:%S')}] Değişiklik yok: {isim}")
        with open(hash_file, "w", encoding="utf-8") as f:
            f.write(yeni_hash)
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(yeni_metin)
        return None

    # --- Hash değişti ama zaten bildirilmiş ---
    if yeni_hash == son_bildirilen_hash:
        print(f"[{time.strftime('%H:%M:%S')}] Değişiklik var ama zaten bildirilmiş: {isim}")
        with open(hash_file, "w", encoding="utf-8") as f:
            f.write(yeni_hash)
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(yeni_metin)
        return None

    # --- Gerçekten yeni bir değişiklik ---
    print(f"[{time.strftime('%H:%M:%S')}] 🔔 YENİ DEĞİŞİKLİK: {isim}")

    # DEBUG: ne değişti?
    old_lines = set(eski_metin.splitlines())
    new_lines = set(yeni_metin.splitlines())
    added = new_lines - old_lines
    removed = old_lines - new_lines
    print(f"[DEBUG] {isim}: +{len(added)} satır eklendi, -{len(removed)} satır silindi")
    for line in list(added)[:5]:
        print(f"[DEBUG]   + {line[:150]}")
    for line in list(removed)[:5]:
        print(f"[DEBUG]   - {line[:150]}")

    yeni_icerikler = yeni_satirlari_bul(eski_metin, yeni_metin)

    # Dosyaları güncelle
    with open(hash_file, "w", encoding="utf-8") as f:
        f.write(yeni_hash)
    with open(text_file, "w", encoding="utf-8") as f:
        f.write(yeni_metin)

    return {
        "isim": isim,
        "url": site["url"],
        "yeni_icerikler": yeni_icerikler,
        "notified_file": notified_file,
        "yeni_hash": yeni_hash,
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
                # Çok uzun satırları kısalt
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

        # E-posta zamanını Türkiye saatine çevir
        simdi_tr = datetime.now(TR_TZ).strftime("%d.%m.%Y %H:%M:%S")

        icerik = (
            f"Aşağıdaki sayfalarda yeni içerik tespit edildi:\n\n"
            + "\n" + ("─" * 40 + "\n").join(parcalar)
            + f"\n⏰ Zaman: {simdi_tr}\n"
        )

        basarili = email_gonder("🔔 Sayfa Güncellemesi", icerik)

        if basarili:
            for d in degisenler:
                with open(d["notified_file"], "w", encoding="utf-8") as f:
                    f.write(d["yeni_hash"])
    else:
        print(f"[{time.strftime('%H:%M:%S')}] Hiçbir sayfada yeni değişiklik yok.")


if __name__ == "__main__":
    main()
