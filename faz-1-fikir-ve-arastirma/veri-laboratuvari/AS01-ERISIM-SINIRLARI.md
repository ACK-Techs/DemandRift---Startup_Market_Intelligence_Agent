# AS-01 — Kaynak yeteneği, alan örnekleri ve erişim sınırları

**Sürüm 1.0.0** · Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan
**Ölçüm tarihi: 2026-09-24** · Üreten: `as01_kaynak_kontrol.py`

Bu belge Batuhan'ın F01–F10 kategori/sorgu denemelerine başlamadan önce
**hangi kaynaktan ne beklenebileceğini** söyler. İçindeki her sayı bugün
ölçüldü; hiçbiri geçmiş kayıttan kopyalanmadı.

## 0. Önce en önemlisi: eski kayıt bugünkü başarı değil

Laboratuvarın erişim kayıtları 2 ve 18 Eylül'den. Bugün aynı kaynaklar
yeniden yoklandı ve iki sonuç yan yana kondu:

| | Deneme |
|---|---:|
| Bugün de çalışıyor | 11 |
| Kayıtta da bugün de içerik yok | 14 |
| **Kayıt çalışıyor diyor, bugün çalışmıyor** | **2** |
| Kayıt çalışmıyor diyordu, bugün geldi | 1 |

Gerileyen kayıtlar:

| Fikir | Kaynak | Kayıtlı durum | Bugün |
|---|---|---|---|
| F02 | Capterra | gercek-icerik | challenge |
| F09 | Capterra | gercek-icerik | challenge |

**Capterra F02, F09 ve F10'da planlanmış.** Kaydımız `gercek-icerik` diyor,
bugün bot koruması dönüyor. Bu satır tek başına kartın uyarısının gerekçesidir.

## 1. Üç ayrı eksen karıştırılmaz

Kontrol ve kabul rehberi üç farklı şeyi ayırmayı şart koşuyor ve bu tabloda
üçü de ayrı sütunda:

| Eksen | Soru | Değerler |
|---|---|---|
| **Erişim** | Siteye bugün ulaşılabiliyor mu | `ok`, `robots_disallowed`, `challenge`, `rate_limited`, `source_unavailable` |
| **İçerik** | Gelen şey ne | `gercek-icerik`, `api-yaniti`, `js-kabugu`, `aday-kesif`, `arsiv` |
| **Artefakt** | Ham dosya bu depoda var mı | `depoda`, `yalniz-yerelde`, `hicbir-yerde` |

HTTP 200 dönmesi içerik geldiği anlamına gelmez: Google Play bugün **200 OK**
döndü ve gövdesinde **0 karakter** görünür metin vardı.

## 2. Bugün ne çalışıyor

12 deneme içerik verdi. Alanlar gerçekten dolu mu diye her birinden
örnek çekildi; **bulunmayan alan boş bırakıldı, uydurulmadı**:

| Kaynak | Dolu alan | Başlık örneği | Puan | Fiyat | Yazar | Artefakt |
|---|---:|---|---|---|---|---|
| Apple App Store | 10/11 | `‎Sleep Cycle - Tracker & Sounds Ap` | 4.7 | 0 | Sleep Cycle AB | `e390abde1bdd` |
| Google Play Store | 2/11 | `` | — | — | — | `b1da17ff4bd1` |
| GitHub | 5/11 | `Detect breaking OpenAPI contract c` | — | — | — | `73ae278a80f3` |
| Stack Overflow | 6/11 | `Is ServiceLocator an anti-pattern?` | — | — | davidoff | `9197928c0d62` |
| Hacker News | 6/11 | `Swagger::Diff – detect breaking AP` | — | — | ezekg | `5d5e1beb787d` |
| Shopify App Store | 6/11 | `Best Support Apps For 2026 - Shopi` | — | $2.99 | — | `197a32b295b5` |
| Hugging Face | 4/11 | `oguzhankarahan/asr-300m-turkish` | — | — | — | `93f16549d6e1` |
| Steam | 6/11 | `Steam Search` | — | $1.99 | — | `76b9e6c2b3e2` |
| Armut | 7/11 | `Ev Temizliği | Memnuniyet Garantil` | 4.4 | — | Ezgi B. Ş. | `319c22fae587` |

Rehberin istediği 11 alan: `baslik`, `govde`, `kaynak_url`, `alinma_tarihi`, `yayin_tarihi`, `yazar`, `puan`, `puan_olcegi`, `fiyat`, `para_birimi`, `donem`.

**Apple App Store 11 alanın 10'unu veriyor** — F01, F08 ve F10 için en güçlü
kaynak. **Armut** Türkçe yerel hizmet için puan ve gerçek yorumcu adı
döndürüyor. **Stack Overflow ve Hacker News** resmî API'leriyle çalışıyor.

## 3. Politika engeli — kazımayla çözülmez

8 deneme robots.txt tarafından durduruldu:

| Kaynak | Bugünkü robots.txt | Etkilenen fikirler |
|---|---|---|
| **Reddit** | `User-agent: * / Disallow: /` — tam yasak | F01, F02, F04, F06, F07, F08, F09 |
| **Trustpilot** | Tam yasak | F07 |
| **stackoverflow.com** | `Disallow: /` + `Content-signal: search=no, ai-train=no` | F03 |

Reddit **on fikrin yedisinde** planlanmış ve tek satırla kapalı. Ama Reddit'in
kendi robots.txt'i izinli yolu gösteriyor:

```
# See .../Public-Content-Policy for access and use restrictions
# See https://www.reddit.com/r/reddit4researchers/ for ... research and non-commercial use
```

**Bu bir kazıma sorunu değil, izin sorunudur.** Çözümü kod değil, hesap ve
şartname onayı. Karar Çağlar'a ait.

`stackoverflow.com` kapalı ama **`api.stackexchange.com` resmî API'si açık** ve
bugün gerçek sonuç döndürdü. F03 için yol budur.

## 4. Teknik engel — robots izinli, içerik gelmiyor

| Kaynak | Bugün | Ne yapılabilir |
|---|---|---|
| G2 | `challenge` | Arşiv (Common Crawl) — **canlı değil**, `arsiv` olarak işaretlenir |
| Capterra | `challenge` | Aynı; ayrıca kayıtla çelişiyor |
| Capterra Education | `challenge` | Aynı |
| Google Play | 200 OK, 0 karakter | Aynı uygulamalar **Apple App Store**'da alınabiliyor |
| Apple App Store | çalışıyor, `rate_limited` eşiği düşük | İstek aralığı artırılmalı |

Bot koruması **aşılmaz** — tarayıcı taklidi, UA rotasyonu ve CAPTCHA çözme
yoktur. Site bizi bot olarak tanıyıp reddediyorsa bu bir karardır.

## 5. Kendi teslimimizdeki sınır

Depo üç fazlı yapıya taşınırken ham artefaktlar ikiye bölündü. 1249
normalize belgenin ham dosyası nerede:

| | Belge |
|---|---:|
| Bu depoda | **21** |
| Yalnız yerel arşivde (depoda yok) | **1228** |
| Hiçbir yerde | 0 |

Rehber açık: *"kayıp artefakt başarılı sayılmaz"* ve *"indeksteki dosya
gerçekten checkout'ta veya kayıtlı depoda bulunuyor mu?"*

Bugünkü yoklamanın 14 kanıt
artefaktı **bu depoya** yazıldı; Batuhan hash'ten doğrulayabilir. Geçmiş
korpusun tamamı için karar gerekiyor — 1332 dosya yaklaşık 700 MB.

## 6. Bu belge ne söylemez

- **Bir kaynağın bugün engelli olması o pazarda talep olmadığını göstermez.**
  Erişilememe sıfır sonuç değildir.
- Sayılar **erişim ve alan ölçümüdür**, kanıt yeterliliği değil. 3 bağımsız
  örnek / 2 ayrı kaynak eşiği Faz 3'e aittir ve bunun yerine geçmez.
- Fiyat alanları **satıcının ilan ettiği fiyattır**; kullanıcının ödediği
  değildir.
- Bu ölçüm 2026-09-24 tarihlidir. Batuhan denemeye başlarken yeniden koşmalıdır;
  bu belge de bir snapshot'tır.

## 7. Yeniden üretim

```bash
python3 as01_kaynak_kontrol.py --yaz          # ağsız: yalnız kayıtlı durum
python3 as01_kaynak_kontrol.py --yaz --canli  # bugünkü yoklama (28 istek)
python3 -m unittest test_as01_kaynak_kontrol
```
