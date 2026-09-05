"""Cekirdek terimi hedef pazarin diline cevirir; ceviremediginde bunu soyler.

Turkiye pazari icin bu modul hic calismaz: fikir Turkce, sorgu Turkce. Yalniz
Ingilizce pazar icin sorgu uretilirken devreye girer.

Ceviri iki yapiyla yapilir ve ikisi de gereklidir:

* **Wiktionary** bir sozluktur; kelimenin olabilecek karsiliklarini verir.
  ``randevu`` icin ``date``, ``rendezvous``, ``appointment`` doner -- ucu de
  dogru ceviri, ama hangisini kastettigimizi sozluk bilemez.
* **Kategori dili** bizim kendi tablomuzdur; belirsizligi cozer. Yerel hizmet
  arastirmasinda ``appointment`` gecerlidir, ``date`` degil.

Tek kelimede takilan cok kelimeli terimler icin ucuncu bir yol var:
**Wikipedia dil baglantilari**. ``kan sekeri`` Wiktionary'de yok ama Turkce
Wikipedia'daki "Kan sekeri seviyesi" makalesinin Ingilizce karsiligi "Blood
sugar level"dir. Wikipedia aramasi bazen alakasiz makaleye duser (``randevu
sistemi`` -> "Saglik.NET"), bu yuzden bulunan basligin aranan kelimeleri
icermesi sarti aranir; icermiyorsa sonuc reddedilir.

Hicbir katman cozemezse **ceviri yapilmaz**: orijinal terim gider ve satirda
uyari kalir. Yanlis ceviri yapmak, cevirmemekten kotudur -- ``randevu`` yerine
``dating`` aramak butun sonucu bozar.

Butun sonuclar ``TERIM-ONBELLEGI.json`` dosyasinda saklanir ve dosya repoya
islenir. Boylece calistirma deterministik kalir (gorev 5'in sarti) ve ayni
terim icin iki kez aga cikilmaz.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ONBELLEK = HERE / "TERIM-ONBELLEGI.json"
UA = "DemandRift-research/1.0 (academic source study; contact via repository)"
BEKLEME = 3.0
GERI_CEKILME = 20.0
ZAMAN_ASIMI = 25.0

# Wikipedia basligi, aranan ifadenin kelimelerinin TAMAMINI icermelidir.
# Kismi ortusme kabul edilirse ifadenin bir parcasi sessizce kaybolur:
# "diyabet takip" -> "Diyabet" -> "diabetes" olur ve takip dusr. Bu yuzden
# esik tam kapsamadir; kismi eslesmeler alt ifade denemesine birakilir.
ASGARI_ORTUSMe = 0.999


def sadelestir(metin: str) -> str:
    metin = metin.replace("ı", "i").replace("I", "i").replace("İ", "i")
    ayrik = unicodedata.normalize("NFKD", metin.casefold())
    return "".join(k for k in ayrik if not unicodedata.combining(k))


def onbellek_yukle(yol: Path = ONBELLEK) -> dict[str, Any]:
    if yol.exists():
        return json.loads(yol.read_text(encoding="utf-8"))
    return {}


def onbellek_yaz(veri: dict[str, Any], yol: Path = ONBELLEK) -> None:
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2, sort_keys=True),
                   encoding="utf-8")


def _istek(adres: str, deneme: int = 2) -> dict[str, Any]:
    """429 (hiz siniri) alinirsa bekleyip bir kez daha dener.

    Hiz siniri sessizce yutulursa 'karsilik yok' sonucu uretilir ve
    onbellege yanlis bir bosluk yazilir; bu, sonraki calistirmalarda da
    tekrarlanir. O yuzden 429 ayirt edilip beklenmeli.
    """
    r = urllib.request.Request(
        adres, headers={"User-Agent": UA, "Accept": "application/json"})
    for kalan in range(deneme, 0, -1):
        try:
            with urllib.request.urlopen(r, timeout=ZAMAN_ASIMI) as h:
                return json.loads(h.read().decode("utf-8"))
        except urllib.error.HTTPError as hata:
            if hata.code == 429 and kalan > 1:
                time.sleep(GERI_CEKILME)
                continue
            raise
    raise urllib.error.URLError("deneme_hakki_bitti")


def adaylari_ayikla(wikitext: str) -> list[str]:
    """Wiktionary kaynak metninden Turkce bolumun karsiliklarini ayiklar.

    Ag erisiminden ayri tutulur ki bicimlendirme kurallari testlenebilsin.
    """
    bolum = re.search(r"==\s*Turkish\s*==(.*?)(?=\n==[^=]|\Z)", wikitext, re.S)
    if not bolum:
        return []
    adaylar: list[str] = []
    for satir in bolum.group(1).splitlines():
        if not satir.startswith("# ") or len(satir) < 4:
            continue
        # Wiki sablonlari once cozulur: {{l|en|date}} -> date, {{gloss|x}} -> x.
        # Duz karakter temizligi bunu yapmaz, 'l|en|date' diye bir aday birakir.
        temiz = re.sub(r"\{\{[^}]*\|([^}|]+)\}\}", r"\1", satir[2:])
        temiz = re.sub(r"[\[\]{}'|]", "", temiz)
        # Once parantezli aciklamalar atilir, sonra hem virgul hem noktali
        # virgulden bolunur: "date (pre-arranged meeting), rendezvous; tryst"
        # uc ayri adaydir. Parantez temizligi bolmeden once yapilmali, yoksa
        # "pursuit of (an end" gibi yarim parcalar aday sanilir.
        temiz = re.sub(r"\([^)]*\)?", "", temiz)
        for parca in re.split(r"[;,]", temiz):
            parca = parca.strip(" .")
            if parca and parca.isascii() and 1 < len(parca) < 40:
                adaylar.append(parca)
    return list(dict.fromkeys(adaylar))


def wiktionary_adaylari(kelime: str) -> list[str]:
    """Ingilizce Wiktionary'den kelimenin Turkce bolumunu ceker ve ayiklar."""
    adres = "https://en.wiktionary.org/w/api.php?" + urllib.parse.urlencode({
        "action": "parse", "page": kelime, "prop": "wikitext",
        "format": "json", "formatversion": "2"})
    try:
        veri = _istek(adres)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
        return []
    return adaylari_ayikla(veri.get("parse", {}).get("wikitext", ""))


def ortusme_orani(ifade: str, baslik: str) -> float:
    """Bulunan basligin, aranan ifadenin kelimelerini kapsama orani."""
    aranan = {sadelestir(k) for k in re.findall(r"\w+", ifade) if len(k) > 2}
    bulunan = {sadelestir(k) for k in re.findall(r"\w+", baslik)}
    return len(aranan & bulunan) / len(aranan) if aranan else 0.0


def wikipedia_karsiligi(ifade: str) -> tuple[str, str, float]:
    """(tr_baslik, en_baslik, ortusme_orani) doner.

    Ortusme, bulunan basligin aranan ifadenin kelimelerini ne kadar
    icerdigidir. Wikipedia aramasi alakasiz makaleye dusebildigi icin
    bu oran bir korumadir.
    """
    ara = "https://tr.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": ifade,
        "srlimit": 1, "format": "json", "formatversion": "2"})
    try:
        sonuc = _istek(ara)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
        return "", "", 0.0
    hits = sonuc.get("query", {}).get("search", [])
    if not hits:
        return "", "", 0.0
    baslik = hits[0]["title"]

    ortusme = ortusme_orani(ifade, baslik)
    if ortusme < ASGARI_ORTUSMe:
        return baslik, "", ortusme

    bag = "https://tr.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "titles": baslik, "prop": "langlinks",
        "lllang": "en", "format": "json", "formatversion": "2"})
    try:
        veri = _istek(bag)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
        return baslik, "", ortusme
    sayfa = (veri.get("query", {}).get("pages") or [{}])[0]
    ll = sayfa.get("langlinks") or []
    return baslik, (ll[0]["title"] if ll else ""), ortusme


def terim_cevir(terim: str, kategori: str, kategori_dili: set[str],
                onbellek: dict[str, Any], cevrimdisi: bool = False,
                ) -> dict[str, Any]:
    """Katmanlari sirayla dener; her durumda gerekceli bir kayit doner."""
    anahtar = f"{sadelestir(terim)}|{kategori}"
    if anahtar in onbellek:
        return dict(onbellek[anahtar], onbellekten=True)

    kayit: dict[str, Any] = {
        "orijinal": terim, "kategori": kategori, "kullanilan": terim,
        "guven": "yok", "cozen_katman": "cozulemedi", "adaylar": [],
        "iz": "", "uyari": "", "onbellekten": False,
    }
    if cevrimdisi:
        kayit["uyari"] = "önbellekte yok ve çevrimdışı çalışıldı"
        kayit["iz"] = "aga cikilmadi"
        return kayit

    izler: list[str] = []

    # Katman 1 -- ifadenin tamami Wikipedia'da (cok kelimeli alan terimleri).
    # Yalniz TAM kapsayan eslesme kabul edilir; yarim eslesme ifadenin bir
    # parcasini sessizce dusrurur.
    kelimeler = terim.split()
    cozulen_araligi: tuple[int, int] | None = None
    wiki_karsiligi = ""
    if len(kelimeler) > 1:
        tr_baslik, en_baslik, ortusme = wikipedia_karsiligi(terim)
        time.sleep(BEKLEME)
        if en_baslik:
            kayit.update({
                "kullanilan": en_baslik.casefold(), "guven": "yuksek",
                "cozen_katman": "wikipedia",
                "iz": f"wikipedia tr:'{tr_baslik}' -> en:'{en_baslik}' "
                      f"(tam kapsama)",
            })
            return kayit
        izler.append(f"wikipedia(tam ifade):'{tr_baslik or 'sonuc yok'}' "
                     f"reddedildi (ortusme {ortusme:.2f})")

    # Katman 2 -- bitisik ikili gruplar. 'kan sekeri takip' ifadesinde
    # 'kan sekeri' Wikipedia'da tam karsiligi olan bir terimdir; 'takip'
    # ayrica cevrilir. Boylece parca kaybolmadan cok kelimeli terim cozulur.
    if len(kelimeler) > 2:
        for i in range(len(kelimeler) - 1):
            ikili = " ".join(kelimeler[i:i + 2])
            tr_baslik, en_baslik, ortusme = wikipedia_karsiligi(ikili)
            time.sleep(BEKLEME)
            if en_baslik:
                cozulen_araligi = (i, i + 2)
                wiki_karsiligi = en_baslik.casefold()
                izler.append(f"wikipedia(ikili '{ikili}') -> '{en_baslik}'")
                break
            izler.append(f"wikipedia(ikili '{ikili}') reddedildi "
                         f"(ortusme {ortusme:.2f})")

    # Katman 2 -- kelime kelime Wiktionary, kategori dili secer
    cevrilen: list[str] = []
    kelime_adaylari: list[str] = []
    coz_sayisi = 0
    atlanacak = set(range(*cozulen_araligi)) if cozulen_araligi else set()
    for sira, kelime in enumerate(kelimeler):
        if sira in atlanacak:
            if sira == min(atlanacak):
                cevrilen.append(wiki_karsiligi)
                coz_sayisi += 1
            continue
        adaylar = wiktionary_adaylari(kelime)
        time.sleep(BEKLEME)
        kelime_adaylari.extend(adaylar)
        if not adaylar:
            cevrilen.append(kelime)
            izler.append(f"wiktionary:{kelime}=karsilik-yok")
            continue
        # Kategori dili ile eslestirme once birebir, sonra govde uzerinden
        # denenir: aday 'tracking' ile kategori kelimesi 'tracker' ayni isi
        # anlatir ama birebir tutmaz.
        eslesen = [a for a in adaylar if sadelestir(a) in kategori_dili]
        if not eslesen:
            eslesen = [a for a in adaylar
                       if any(sadelestir(a)[:5] == k[:5] and len(k) > 4
                              for k in kategori_dili)]
        if eslesen:
            cevrilen.append(eslesen[0])
            coz_sayisi += 1
            izler.append(f"wiktionary:{kelime}={len(adaylar)} aday, "
                         f"kategori dili '{eslesen[0]}' sectti")
        elif len(adaylar) == 1:
            cevrilen.append(adaylar[0])
            coz_sayisi += 1
            izler.append(f"wiktionary:{kelime}=tek aday '{adaylar[0]}'")
        else:
            # Kategori dili karar veremedi. Wikipedia'ya ayni kelime sorulur;
            # donen Ingilizce baslik Wiktionary adaylarindan biriyse iki
            # bagimsiz kaynak ayni seyi soyluyor demektir ve secim guvenlidir.
            # Ortusmuyorsa secim yapilmaz: yanlis ceviri, cevirmemekten kotu.
            _tr, en_baslik, _o = wikipedia_karsiligi(kelime)
            time.sleep(BEKLEME)
            hakem = [a for a in adaylar
                     if sadelestir(a) == sadelestir(en_baslik)]
            if hakem:
                cevrilen.append(hakem[0])
                coz_sayisi += 1
                izler.append(f"wiktionary:{kelime}={len(adaylar)} aday, "
                             f"wikipedia '{en_baslik}' ile ortusen secildi")
            else:
                cevrilen.append(kelime)
                izler.append(f"wiktionary:{kelime}={len(adaylar)} aday, "
                             f"kategori dili secemedi, wikipedia "
                             f"'{en_baslik or 'karsilik yok'}' ortusmedi")

    kayit["adaylar"] = list(dict.fromkeys(kelime_adaylari))
    kayit["iz"] = " | ".join(izler)
    kelime_sayisi = len(kelimeler) - (len(atlanacak) - 1 if atlanacak else 0)
    if coz_sayisi == kelime_sayisi:
        kayit.update({"kullanilan": " ".join(cevrilen), "guven": "yuksek",
                      "cozen_katman": "wikipedia+wiktionary" if atlanacak
                                      else "wiktionary+kategori"})
    elif coz_sayisi:
        kayit.update({"kullanilan": " ".join(cevrilen), "guven": "orta",
                      "cozen_katman": "wiktionary+kategori (kismi)",
                      "uyari": f"{kelime_sayisi - coz_sayisi} kelime çevrilemedi"})
    else:
        kayit["uyari"] = "karşılık seçilemedi; --terim ile verilebilir"
    return kayit


def kategori_dili(kategori_kaynak: list[dict[str, str]], kategori: str,
                  grup_dili: dict[str, tuple[str, ...]]) -> set[str]:
    """Kategorinin kaynak gruplarindan gelen kelimeler.

    Belirsizligi bu kume cozer: yerel hizmet arastirmasinda 'appointment'
    bulunur, 'date' bulunmaz.
    """
    gruplar = {g.strip() for r in kategori_kaynak if r["hedef"] == kategori
               for g in r["kaynak_grubu"].split(" | ")}
    kelimeler: set[str] = set()
    for g in gruplar:
        for kelime in grup_dili.get(g, ()):
            if kelime:
                kelimeler.add(sadelestir(kelime))
    return kelimeler
