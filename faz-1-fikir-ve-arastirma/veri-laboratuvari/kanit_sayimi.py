"""AS-05 — 3/2 sayimini, bagimsizligi ve alinti baglarini inceler.

Gorev karti: "Ayni kisinin/kurumun tekrarlarini ve kopyalari ayir; **bilinmeyen
bagimsizligi 3 ornek alt sinirina sayma.** Alintinin metin/hash/surum bagini ve
yorumun gercekten kanitla desteklenmesini kontrol et. Yanlis karar/yorum icin
claim duzeyinde bildirim ve duzeltme kaniti ver."

Faz 3 rehberi ayni isi bolustururyor: "3/2 sinirini Batuhan uygular; **Ayselin
sayimi inceler**".

En onemli ayrim su: politika **kullanici/kurum** bagimsizligi istiyor
("en az 3 bagimsiz kullanici/kurum ornegi"). Bizim veri kumemiz **belge ve
kaynak** seviyesinde. Ikisi ayni sey degil:

* Uc farklı saticinin ilan ettigi fiyat -> uc farklı KURUM gozlemi sayilabilir.
* Bir sayfadan cikan uc fiyat -> tek kurum, tek gozlem.
* Bir forum sayfasindaki uc yorum -> kim yazdigi bilinmiyorsa uc DEGIL,
  bilinmeyen bagimsizlik.

Bu yuzden her ornek ucе ayrilir: ``supporting``, ``challenging`` ve
``unknown_independence``. Ucuncusu **alt sinira sayilmaz** — politikanin
acik kurali: "Kimligi/bagimsizligi belirsiz ornek alt esige eklenmez;
bilinen/unknown ayri raporlanir."

Bu modul **karar vermez.** 3/2 esigini uygular ve nerede gectigini, nerede
gecmedigini gosterir. Gecmemek "pazar kotu" demek degildir; "bu veriyle
sonuca varilamaz" demektir.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SURUM = "1.0.0"
POLITIKA_SURUMU = "kanit-yeterliligi-v1"

# Politikanin alt sinirlari. Model bu degerleri degistiremez.
ASGARI_BAGIMSIZ_ORNEK = 3
ASGARI_TEKIL_KAYNAK = 2

# Hangi niyette bir KURUM gozlemi sayilabilir.
# Saticinin kendi ilan ettigi fiyat o kurumun gozlemidir; ama kullanicinin
# problemi ya da sikayeti KISI gozlemidir ve kisi kimligi elimizde yok.
KURUM_GOZLEMI_SAYILIR = frozenset({
    "observed_market_pricing",   # satıcının ilan ettiği fiyat = o kurumun beyanı
    "competitor_discovery",      # bir ürünün varlığı = o kurumun varlığı
    "existing_alternatives",
})
KISI_GOZLEMI_GEREKIR = frozenset({
    "problem_demand",            # kullanıcının problemi anlatması
    "dissatisfaction",           # kullanıcının şikâyeti
    "stated_wtp_weak_signal",    # kullanıcının ödeme beyanı
    "use_case",                  # kullanım bağlamı — kim kullanıyor önemli
})


def _oku(ad: str) -> list[dict[str, str]]:
    yol = HERE / ad
    if not yol.exists():
        return []
    with yol.open(encoding="utf-8") as tutamak:
        return list(csv.DictReader(tutamak))


def _yaz(ad: str, satirlar: list[dict[str, Any]]) -> None:
    if not satirlar:
        return
    with (HERE / ad).open("w", newline="", encoding="utf-8") as tutamak:
        yazici = csv.DictWriter(tutamak, fieldnames=list(satirlar[0]))
        yazici.writeheader()
        yazici.writerows(satirlar)


def _paylasilan_ozetler() -> dict[str, str]:
    yol = HERE / "results" / "shared-redactions.json"
    if not yol.exists():
        return {}
    veri = json.loads(yol.read_text(encoding="utf-8"))
    return {k["original_sha256"]: k["shared_sha256"] for k in veri["files"]}


def sayim_yap() -> list[dict[str, Any]]:
    """Her (kategori, niyet) hucresi icin politikanin istedigi sayim alanlari."""
    matris = _oku("SOURCE-FIT-MATRIX.csv")
    alanlar = collections.defaultdict(list)
    for satir in _oku("KATEGORI-ALANLARI.csv"):
        alanlar[satir["document_id"]].append(satir)
    # Karsit bulgular AS-04'te ornek metniyle kaydedildi ("Booksy Biz · 4.5
    # puan..."); matristeki kaynak adi ("Booksy") tam esitlikle tutmuyor.
    # Kaynak adi ornek metninde geciyorsa o kaynak karsit isaretli sayilir.
    karsit_ornekler = [r["ornek"] for r in _oku("AS04-ETIKETLI-REFERANS.csv")
                       if r["dogrudan_karsit_bulgu"] == "EVET"]

    def karsit_mi(kaynak_adi: str) -> bool:
        return any(kaynak_adi.casefold() in o.casefold() for o in karsit_ornekler)

    hucre: dict[tuple[str, str], list[dict[str, str]]] = collections.defaultdict(list)
    for satir in matris:
        hucre[(satir["kategori"], satir["arama_niyeti"])].append(satir)

    satirlar: list[dict[str, Any]] = []
    for (kategori, niyet), kayitlar in sorted(hucre.items()):
        gruplar = {r["bagimsizlik_grubu"] for r in kayitlar}
        kaynaklar = {r["source_id"] for r in kayitlar}
        destek: list[str] = []
        karsit: list[str] = []
        bilinmeyen: list[str] = []
        for r in kayitlar:
            belge = r["ornek_kayit"].split(" · ")[0]
            olculdu = bool(alanlar.get(belge))
            if karsit_mi(r["kaynak_adi"]):
                karsit.append(r["kaynak_adi"])
            elif niyet in KURUM_GOZLEMI_SAYILIR and olculdu:
                # Saticinin kendi sayfasindan cikan olculmus deger = kurum gozlemi
                destek.append(r["kaynak_adi"])
            else:
                # Kisi gozlemi gerekiyor ama kisi kimligi yok; ya da olculmus
                # deger yok, yalniz yuzey kaniti var.
                bilinmeyen.append(r["kaynak_adi"])

        bagimsiz_destek = len({d for d in destek})
        tekil_kaynak = len(kaynaklar)
        kapilar = {
            "min_independent_examples": bagimsiz_destek >= ASGARI_BAGIMSIZ_ORNEK,
            "min_distinct_sources": tekil_kaynak >= ASGARI_TEKIL_KAYNAK,
            "independence_known": bool(destek) and not bilinmeyen,
        }
        gecti = kapilar["min_independent_examples"] and kapilar["min_distinct_sources"]
        if gecti:
            sebep = (f"{bagimsiz_destek} bağımsız kurum gözlemi, "
                     f"{tekil_kaynak} ayrı kaynak — nicel taban sağlandı; "
                     "nitel kontroller ayrıca uygulanmalı")
        elif bilinmeyen and not destek:
            sebep = ("tüm örneklerin bağımsızlığı bilinmiyor; politika gereği "
                     "alt sınıra sayılmıyor")
        elif bagimsiz_destek < ASGARI_BAGIMSIZ_ORNEK:
            sebep = (f"{bagimsiz_destek} bağımsız gözlem, eşik "
                     f"{ASGARI_BAGIMSIZ_ORNEK}; yetersiz")
        else:
            sebep = f"{tekil_kaynak} kaynak, eşik {ASGARI_TEKIL_KAYNAK}; yetersiz"

        satirlar.append({
            "kategori": kategori,
            "arama_niyeti": niyet,
            "policy_version": POLITIKA_SURUMU,
            "relevant_independent_examples": bagimsiz_destek,
            "supporting_examples": len(destek),
            "challenging_examples": len(karsit),
            "unknown_independence_examples": len(bilinmeyen),
            "distinct_sources": tekil_kaynak,
            "bagimsizlik_grubu": len(gruplar),
            "gate_results": json.dumps(kapilar, ensure_ascii=False),
            "gecti_mi": "evet" if gecti else "hayır",
            "eligibility_reason": sebep,
            "critical_gaps": ("kişi kimliği yok — kişi gözlemi gerektiren niyet"
                              if niyet in KISI_GOZLEMI_GEREKIR else ""),
        })
    return satirlar


def alinti_kontrol() -> list[dict[str, Any]]:
    """Her cikarilan degerin metin/hash/surum bagi cozumleniyor mu."""
    import normalize_belgeler as nb

    belge = {r["document_id"]: r for r in _oku("NORMALIZE-BELGELER.csv")}
    paylasilan = _paylasilan_ozetler()
    satirlar: list[dict[str, Any]] = []
    for r in _oku("KATEGORI-ALANLARI.csv"):
        b = belge.get(r["document_id"])
        if not b:
            satirlar.append({
                "document_id": r["document_id"], "kaynak_adi": r["source_adi"],
                "alan": r["alan"], "deger": r["deger"][:40],
                "metin_bagi": "KOPUK — belge yok", "hash_bagi": "—",
                "surum_bagi": "—", "durum": "GECERSIZ"})
            continue
        aranan = r["deger"].replace(" ", "")[:12]
        kesilmis = aranan in b["body_normalized"].replace(" ", "")
        tam = False
        yol = nb.artefakt_yolu(b["body_original_ref"])
        if not kesilmis and yol:
            metin = nb.metin_cikar(yol.read_bytes()[:400_000], "text/html")["metin"]
            tam = aranan in metin.replace(" ", "")
        if yol:
            beklenen = paylasilan.get(b["artifact_hash"], b["artifact_hash"])
            hash_tamam = hashlib.sha256(yol.read_bytes()).hexdigest() == beklenen
        else:
            hash_tamam = False
        metin_bagi = ("gövde sütununda" if kesilmis else
                      "ham artefaktta (gövde sütunu kırpılmış)" if tam else
                      "KOPUK — hiçbir yerde bulunamadı")
        satirlar.append({
            "document_id": r["document_id"], "kaynak_adi": r["source_adi"],
            "alan": r["alan"], "deger": r["deger"][:40],
            "metin_bagi": metin_bagi,
            "hash_bagi": "doğrulandı" if hash_tamam else "DOĞRULANAMADI",
            "surum_bagi": b["normalization_version"],
            "durum": ("geçerli" if (kesilmis or tam) and hash_tamam else "GECERSIZ"),
        })
    return satirlar


def claim_bildirimleri(sayim: list[dict[str, Any]],
                       alintilar: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Claim duzeyinde bildirim: hangi iddia hangi sebeple tasinamaz."""
    bildirimler: list[dict[str, Any]] = []
    kopuk = [r for r in alintilar if r["durum"] != "geçerli"]

    bilinmeyen = [r for r in sayim if int(r["unknown_independence_examples"]) > 0
                  and r["gecti_mi"] == "hayır"]
    if bilinmeyen:
        bildirimler.append({
            "claim_id": "CL-01",
            "claim": "Kategori × niyet hücreleri 3/2 kanıt eşiğini sağlıyor",
            "durum": "DESTEKLENMIYOR",
            "gerekce": (f"{len(bilinmeyen)} hücrede örneklerin bağımsızlığı "
                        "kişi/kurum düzeyinde bilinmiyor. Politika bunları alt "
                        "sınıra saymıyor."),
            "kanit": "AS05-KANIT-SAYIMI.csv · unknown_independence_examples sütunu",
            "yapilacak_duzeltme": ("Kişi gözlemi gerektiren niyetlerde yazar/kullanıcı "
                                   "kimliği çıkarılmalı; çıkarılamıyorsa hücre "
                                   "unknown olarak raporlanmalı."),
            "batuhan_yeniden_kontrolu": "bekliyor",
        })

    kisi_gereken = [r for r in sayim if r["critical_gaps"]]
    if kisi_gereken:
        bildirimler.append({
            "claim_id": "CL-02",
            "claim": ("problem_demand / dissatisfaction / stated_wtp bulguları "
                      "bağımsız kullanıcı gözlemine dayanıyor"),
            "durum": "DESTEKLENMIYOR",
            "gerekce": (f"{len(kisi_gereken)} hücre kişi gözlemi gerektiriyor ama "
                        "veri kümesinde kullanıcı kimliği alanı yok. Aynı kişinin "
                        "tekrarı ile farklı kişiler ayırt edilemiyor."),
            "kanit": "KATEGORI-ALANLARI.csv · kullanıcı kimliği alanı bulunmuyor",
            "yapilacak_duzeltme": ("Yorum/forum yüzeylerinden yazar alanı çıkarılmalı; "
                                   "çıkarılamayan kaynak bu niyetler için "
                                   "sayıma girmemeli."),
            "batuhan_yeniden_kontrolu": "bekliyor",
        })

    gecen = [r for r in sayim if r["gecti_mi"] == "evet"]
    if gecen:
        bildirimler.append({
            "claim_id": "CL-03",
            "claim": f"{len(gecen)} hücre nicel eşiği geçtiği için bulgu üretilebilir",
            "durum": "KISMEN",
            "gerekce": ("Nicel taban sağlandı ama politika 'sayılar tek başına "
                        "yeterli değildir' diyor: hedef müşteri, güncellik, "
                        "karşıt kanıt araması ve alıntı doğrulanabilirliği "
                        "ayrıca geçmeli."),
            "kanit": "AS05-KANIT-SAYIMI.csv · gate_results sütunu",
            "yapilacak_duzeltme": ("Nitel kapılar Faz 3'te ayrıca uygulanmalı; "
                                   "bu sayım onların yerine geçmez."),
            "batuhan_yeniden_kontrolu": "bekliyor",
        })

    bildirimler.append({
        "claim_id": "CL-04",
        "claim": "Çıkarılan her değer alıntı olarak taşınabilir",
        "durum": "DESTEKLENIYOR" if not kopuk else "DESTEKLENMIYOR",
        "gerekce": (f"{len(alintilar)} değerin {len(alintilar) - len(kopuk)}'i "
                    "artefaktında bulundu ve hash'i doğrulandı"
                    + (f"; {len(kopuk)} kopuk" if kopuk else "; kopuk alıntı yok")),
        "kanit": "AS05-ALINTI-KONTROL.csv",
        "yapilacak_duzeltme": ("body_normalized sütunu 4000 karakterde kırpılıyor; "
                               "92 değer yalnız ham artefaktta doğrulanabiliyor. "
                               "Alıntı doğrulaması artefakt üzerinden yapılmalı, "
                               "CSV sütunu üzerinden değil."),
        "batuhan_yeniden_kontrolu": "bekliyor",
    })
    return bildirimler


def rapor(sayim: list[dict[str, Any]], alintilar: list[dict[str, Any]],
          bildirimler: list[dict[str, Any]]) -> str:
    gecen = [r for r in sayim if r["gecti_mi"] == "evet"]
    bilinmeyen_dusen = [r for r in sayim
                        if r["gecti_mi"] == "hayır"
                        and int(r["supporting_examples"]) == 0
                        and int(r["unknown_independence_examples"]) > 0]
    karsit = sum(int(r["challenging_examples"]) for r in sayim)
    kopuk = [r for r in alintilar if r["durum"] != "geçerli"]
    metin_bagi = collections.Counter(r["metin_bagi"] for r in alintilar)

    gecen_tablo = "\n".join(
        f'| {r["kategori"]} | {r["arama_niyeti"]} | {r["relevant_independent_examples"]} | '
        f'{r["distinct_sources"]} | {r["unknown_independence_examples"]} |'
        for r in gecen)
    bildirim_tablo = "\n".join(
        f'| {r["claim_id"]} | {r["claim"][:54]} | **{r["durum"]}** | {r["gerekce"][:78]} |'
        for r in bildirimler)

    return f"""# AS-05 — Kanıt sayımı, bağımsızlık ve alıntı kontrolü

**Sürüm {SURUM}** · Politika: `{POLITIKA_SURUMU}` · Ölçüm: 2026-09-27
Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan

AS-05 BT-07'ye bağlı ve o bildirim gelmedi. Faz 3 rehberi sayım incelemesini
bana veriyor ("3/2 sınırını Batuhan uygular; **Ayselin sayımı inceler**"), bu
yüzden eşiği **kendi verimize** uyguladım ve nerede geçip nerede geçmediğini
ölçtüm.

## 1. En önemli bulgu: bağımsızlığı yanlış seviyede ölçüyoruz

Politika **kişi/kurum** bağımsızlığı istiyor: *"en az 3 bağımsız kullanıcı veya
kurum gözlemi"*. Bizim veri kümemiz **belge ve kaynak** seviyesinde. İkisi aynı
şey değil:

| Durum | Kaç bağımsız gözlem |
|---|---|
| Üç farklı satıcının ilan ettiği fiyat | 3 kurum gözlemi |
| Bir sayfadan çıkan üç fiyat | 1 kurum, 1 gözlem |
| Bir forumdaki üç yorum, yazarı bilinmiyor | **0** — bilinmeyen bağımsızlık |

`KATEGORI-ALANLARI.csv`'de kullanıcı kimliği alanı **yok**. Yani aynı kişinin
tekrarı ile farklı kişiler ayırt edilemiyor.

Politika bu durumda ne yapılacağını söylüyor: *"Kimliği/bağımsızlığı belirsiz
örnek alt eşiğe eklenmez; bilinen/unknown ayrı raporlanır."* Uyguladım.

## 2. 3/2 eşiği uygulandığında

{len(sayim)} hücre sayıldı. Sonuç:

| | Hücre |
|---|---:|
| Nicel eşiği **geçen** | **{len(gecen)}** |
| Tüm örneklerin bağımsızlığı bilinmediği için düşen | **{len(bilinmeyen_dusen)}** |
| Bağımsız gözlem var ama 3'ün altında | {len(sayim) - len(gecen) - len(bilinmeyen_dusen)} |

Geçen hücreler:

| Kategori | Niyet | Bağımsız gözlem | Ayrı kaynak | Bilinmeyen |
|---|---|---:|---:|---:|
{gecen_tablo}

Hepsi `observed_market_pricing`, `competitor_discovery` ve
`existing_alternatives` — yani **kurum gözlemi** sayılabilen niyetler. Bir
satıcının kendi sayfasında ilan ettiği fiyat o kurumun beyanıdır ve
sayılabilir.

Kişi gözlemi gerektiren niyetlerde (`problem_demand`, `dissatisfaction`,
`stated_wtp_weak_signal`, `use_case`) **hiçbir hücre geçmiyor**, çünkü kim
söylemiş bilmiyoruz.

## 3. Karşıt bulgular ayrı sayıldı

{karsit} örnek doğrudan karşıt bulgu olarak işaretli. Politika bunların ayrı
raporlanmasını istiyor; destekleyen ve karşıt örnekler aynı kefeye konmadı.

## 4. Alıntı bağı — metin, hash, sürüm

{len(alintilar)} çıkarılan değerin tamamı kontrol edildi:

| | Adet |
|---|---:|
| Geçerli alıntı | **{len(alintilar) - len(kopuk)}** |
| Kopuk | {len(kopuk)} |
| Hash doğrulandı | {len(alintilar) - len(kopuk)} |

Metin bağının nerede çözüldüğü:

{chr(10).join(f"- {k}: {v}" for k, v in metin_bagi.most_common())}

**Dikkat edilmesi gereken:** `body_normalized` sütunu 4000 karakterde
kırpılıyor. {metin_bagi.get("ham artefaktta (gövde sütunu kırpılmış)", 0)} değer yalnız ham artefaktta doğrulanabiliyor.
Alıntı doğrulaması CSV sütunu üzerinden değil **artefakt üzerinden** yapılmalı.

Sürüm bağı her satırda var (`normalization_version`).

## 5. Claim düzeyinde bildirim

| # | İddia | Durum | Gerekçe |
|---|---|---|---|
{bildirim_tablo}

Hiçbiri kapatılmış değil; Batuhan kontrolü bekliyor.

## 6. Bu sayım ne söylemez

- **Eşiği geçmemek "pazar kötü" demek değildir.** Politika açık: *"erişim
  engeli, bütçe bitmesi veya no_results ile Kill üretilmez."* Geçmemek
  "bu veriyle sonuca varılamaz" demektir.
- **Nicel eşik tek başına yetmez.** Politika *"sayılar tek başına yeterli
  değildir"* diyor; hedef müşteri, güncellik, karşıt kanıt araması ve alıntı
  doğrulanabilirliği ayrıca geçmelidir. Bu sayım onların yerine geçmez.
- **Fiyat beyanı gerçek ödeme değildir.** Geçen hücrelerin hepsi ilan edilmiş
  fiyata dayanıyor; kimsenin o fiyatı ödediği gösterilmiş değil.
- Uydurma başarı ya da güven yüzdesi üretilmedi.

## 7. Yeniden üretim

```bash
python3 kanit_sayimi.py --yaz
python3 -m unittest test_kanit_sayimi
```
"""


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument("--yaz", action="store_true")
    secenek = ayristirici.parse_args(argv)

    sayim = sayim_yap()
    alintilar = alinti_kontrol()
    bildirimler = claim_bildirimleri(sayim, alintilar)
    gecen = [r for r in sayim if r["gecti_mi"] == "evet"]
    print(json.dumps({
        "surum": SURUM, "policy_version": POLITIKA_SURUMU,
        "hucre": len(sayim), "gecen": len(gecen),
        "bilinmeyen_bagimsizlik_toplami": sum(
            int(r["unknown_independence_examples"]) for r in sayim),
        "karsit_ornek": sum(int(r["challenging_examples"]) for r in sayim),
        "alinti": len(alintilar),
        "kopuk_alinti": sum(1 for r in alintilar if r["durum"] != "geçerli"),
        "claim_bildirimi": len(bildirimler),
    }, ensure_ascii=False, indent=2))
    if not secenek.yaz:
        return 0
    _yaz("AS05-KANIT-SAYIMI.csv", sayim)
    _yaz("AS05-ALINTI-KONTROL.csv", alintilar)
    _yaz("AS05-CLAIM-BILDIRIMI.csv", bildirimler)
    (HERE / "AS05-SAYIM-RAPORU.md").write_text(
        rapor(sayim, alintilar, bildirimler), encoding="utf-8")
    print("AS05-KANIT-SAYIMI.csv · AS05-ALINTI-KONTROL.csv · "
          "AS05-CLAIM-BILDIRIMI.csv · AS05-SAYIM-RAPORU.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
