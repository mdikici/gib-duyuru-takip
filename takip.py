import requests
from bs4 import BeautifulSoup
import hashlib
import os
import json
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
        "text_file": "text_gib_guncel.txt",
        "notified_file": "notified_gib_guncel.txt",
        "api": "https://gib.gov.tr/api/gibportal/duyuru/listPublish",
    },
    {
        "isim": "YN ÖKC Duyuru Arşivi",
        "url":  "https://ynokc.gib.gov.tr/Home/DuyuruArsiv",
        "hash_file": "hash_ynokc.txt",
        "text_file": "text_ynokc.txt",
        "notified_file": "notified_ynokc.txt",
    },
    {
        "isim": "eBelge Duyuruları",
        "url":  "https://ebelge.gib.gov.tr/duyurular.html",
        "hash_file": "hash_ebelge.txt",
        "text_file": "text_ebelge.txt",
        "notified_file": "notified_ebelge.txt",
    },
    {
        "isim": "Onay Alan Firmalar (1003)",
        "url":  "https://ynokc.gib.gov.tr/Home/OnayAlanFirmalar/1003",
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


def sayfa_icerik_al(site):
    """Sayfanın (stabil) metnini ve hash'ini döndürür."""
    url = site["url"]

    if site.get("api"):
        payload = {
            "preview": False,
            "page": 0,
            "size": 50,
            "sortFieldName": "startdate",
            "sortType": "DESC",
        }
        r = requests.post(
            site["api"],
            json=payload,
            headers=HEADERS,
            timeout=20,
        )
        r.raise_for_status()

        try:
            data = r.json()
            # GİB API yanıtı: resultContainer.content
            items = (
                data.get("resultContainer", {}).get("content", [])
                if isinstance(data, dict)
                else []
            )

            kayitlar = []
            for item in items:
                if isinstance(item, dict):
                    kayitlar.append({
                        "id": item.get("id", ""),
                        "title": item.get("title", ""),
                        "ts": item.get("ts", item.get("startdate", "")),
                    })

            # Sıralamayı sabitle (timestamp, sonra id)
            kayitlar.sort(
                key=lambda x: (str(x.get("ts", "")), str(x.get("id", "")))
            )

            if kayitlar:
                metin = json.dumps(
                    kayitlar, sort_keys=True, ensure_ascii=False, indent=2
                )
                print(f"[DEBUG] {site['isim']}: {len(kayitlar)} duyuru çekildi")
            else:
                print(
                    f"[DEBUG] {site['isim']}: duyuru çıkarılamadı "
                    f"(items={len(items)}), ham metin kullanılıyor"
                )
                metin = r.text
        except Exception as e:
            print(f"[DEBUG] {site['isim']}: JSON parse hatası: {e}")
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
        # İlk kayıtta bildirim yapılmadı, notified = mevcut hash
        with open(notified_file, "w", encoding="utf-8") as f:
            f.write(yeni_hash)
        return None

    eski_hash = open(hash_file, encoding="utf-8").read().strip()
    eski_metin = open(text_file, encoding="utf-8").read()

    son_bildirilen_hash = ""
    if os.path.exists(notified_file):
        son_bildirilen_hash = open(notified_file, encoding="utf-8").read().strip()

    # --- Hash aynı → hiçbir şey yapma ---
    if eski_hash == yeni_hash:
        print(f"[{time.strftime('%H:%M:%S')}] Değişiklik yok: {isim}")
        with open(hash_file, "w", encoding="utf-8") as f:
            f.write(yeni_hash)
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(yeni_metin)
        return None

    # --- Hash değişti ama bu değişiklik zaten bildirilmiş ---
    if yeni_hash == son_bildirilen_hash:
        print(
            f"[{time.strftime('%H:%M:%S')}] "
            f"Değişiklik var ama zaten bildirilmiş: {isim}"
        )
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

    # Değişen satırları bul
    yeni_icerikler = yeni_satirlari_bul(eski_metin, yeni_metin)

    # Dosyaları güncelle
    with open(hash_file, "w", encoding="utf-8") as f:
        f.write(yeni_hash)
    with open(text_file, "w", encoding="utf-8") as f:
        f.write(yeni_metin)
    # notified sadece e-posta başarılıysa güncellenecek (aşağıda)

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

        basarili = email_gonder("🔔 Sayfa Güncellemesi", icerik)

        # E-posta başarılıysa notified dosyalarını güncelle
        if basarili:
            for d in degisenler:
                with open(d["notified_file"], "w", encoding="utf-8") as f:
                    f.write(d["yeni_hash"])
    else:
        print(
            f"[{time.strftime('%H:%M:%S')}] "
            f"Hiçbir sayfada yeni değişiklik yok."
        )


if __name__ == "__main__":
    main()
