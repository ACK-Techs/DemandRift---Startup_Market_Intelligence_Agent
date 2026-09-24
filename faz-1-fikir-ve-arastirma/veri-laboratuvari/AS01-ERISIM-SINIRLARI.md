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
| Armut | 8/11 | `Ev Temizliği | Memnuniyet Garantil` | 4.4 | 2.000 TL | Ezgi B. Ş. | `319c22fae587` |

Rehberin istediği 11 alan: `baslik`, `govde`, `kaynak_url`, `alinma_tarihi`, `yayin_tarihi`, `yazar`, `puan`, `puan_olcegi`, `fiyat`, `para_birimi`, `donem`.

**Apple App Store 11 alanın 10'unu veriyor** — F01, F08 ve F10 için en güçlü
kaynak. **Armut** Türkçe yerel hizmet için puan ve gerçek yorumcu adı
döndürüyor. **Stack Overflow ve Hacker News** resmî API'leriyle çalışıyor.

## 2b. Arşiv, snippet ve gerçek içerik aynı şey değildir

Görev kartı bu üçünün ayrılmasını istiyor. Tanımlar ve bugünkü karşılıkları:

| Tür | Ne demek | Kanıt değeri | Bugün hangi kaynak |
|---|---|---|---|
| **Gerçek içerik** | Sayfanın kendi gövdesi, canlı çekildi | Alıntılanabilir | Apple App Store, Shopify, Steam, Armut |
| **API yanıtı** | Kaynağın resmî ucundan yapılandırılmış veri | Alıntılanabilir | GitHub, Stack Overflow, Hacker News, Hugging Face |
| **Arşiv** | Common Crawl kopyası; **canlı değil**, çekildiği tarihe ait | Sınırlı — `arsiv` işaretlenir, tarihi ayrı yazılır | G2 (yalnız arşivde var) |
| **Snippet / aday keşif** | Sitemap girdisi, arama sonucu satırı, meta açıklama | **Kanıt değildir** — yalnız "şu adres var" der | Hugging Face ve Capterra Education kayıtlarındaki `aday-kesif` |
| **JS kabuğu** | HTTP 200 döndü, gövdede görünür metin yok | Kanıt değildir | Google Play |
| **İndekste var, dosya yok** | Dizin dosyayı gösteriyor, checkout'ta bulunmuyor | Kanıt değildir | Bölüm 5 |

İkisi sık karıştırılır ve karıştırılmamalı:

- **Sitemap bir snippet bile değildir.** İçinde adres listesi vardır, içerik
  yoktur. Bir kaynağın sitemap'inin inmiş olması o kaynaktan veri alındığını
  göstermez.
- **Arşiv kopyası canlı veri değildir.** G2 için elimizde yalnız Common Crawl
  kopyası var; bugün canlı erişim bot korumasına takılıyor. Arşivden gelen
  bulgu kullanılacaksa `arsiv` etiketi ve çekilme tarihi birlikte taşınmalıdır.

## 2c. Laboratuvarın mevcut alan iddiaları ne kadar doğru

`KAYNAK-ALAN.csv` (Görev 4) bu 14 kaynak için 100 alan iddiası taşıyor ve
büyük kısmı `beyan` durumundaydı: iddia var, doğrulama yok. Bugünkü yanıtlar
o iddiaların üzerinde sınandı.

| Sonuç | Alan |
|---|---:|
| **Bugünkü yanıtta bulundu** | **33** |
| Bu yüzeyde bulunamadı | 29 |
| Kaynak içerik vermediği için sınanamadı | 38 |

| Kaynak | Doğrulanan / iddia |
|---|---:|
| Stack Overflow | 6/7 |
| Apple App Store | 6/9 |
| GitHub | 5/6 |
| Hacker News | 5/7 |
| Armut | 4/6 |
| Hugging Face | 3/6 |
| Steam | 3/6 |
| Shopify App Store | 1/6 |
| G2 | 0/9 |
| Capterra | 0/9 |
| Capterra Education Software | 0/4 |
| Google Play Store | 0/9 |
| Reddit | 0/9 |
| Trustpilot | 0/7 |

**"Bulunamadı" alanın yok olduğu anlamına gelmez.** Kaynak başına tek örnek
yüzey yoklandı; alan başka bir uçta bulunabilir. Ayrıntı:
[`AS01-IDDIA-DOGRULAMA.csv`](AS01-IDDIA-DOGRULAMA.csv) — her satır hangi
artefaktta arandığını yazar.

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
| Bu depoda | **179** |
| Yalnız yerel arşivde (depoda yok) | **1070** |
| Hiçbir yerde | 0 |

Rehber açık: *"kayıp artefakt başarılı sayılmaz"* ve *"indeksteki dosya
gerçekten checkout'ta veya kayıtlı depoda bulunuyor mu?"*

Bugünkü yoklamanın 14 kanıt
artefaktı **bu depoya** yazıldı; Batuhan hash'ten doğrulayabilir.

Geçmiş korpus için seçici bir paylaşım yapıldı: **sayı çıkardığımız her
belgenin** ham dosyası depoya alındı (154 dosya, 49 MB). Böylece
`KATEGORI-ALANLARI.csv`'deki her fiyat, puan ve sayının kaynağı açılabiliyor.

| Ne doğrulanabilir | Oran |
|---|---|
| Çıkarılan alanlar (fiyat, puan, yorum sayısı…) | **%100 (164/164)** |
| Bugünkü AS-01 yoklamaları | **%100** |
| SourceFitMatrix örnek kayıtları | %29 (101/346) |

Kalan 1070 belge çoğunlukla ana sayfa ve sitemap; onlardan sayı çıkarılmadı,
yani doğrulanacak bir iddia taşımıyorlar. SourceFitMatrix'in örnek kayıtlarını
da tamamlamak ~75 MB daha eklemek demek — karar Batuhan'ın.

## 5b. Kapalı kaynaklar için aranan alternatifler

F02 ve F09'un hiçbir kaynağı bugün içerik vermiyordu, bu yüzden o iki fikre
izinli alternatif arandı. Ayrıntı ve kanıt:
[`AS01-ALTERNATIF-RAPOR.md`](AS01-ALTERNATIF-RAPOR.md).

| Fikir | İhtiyaç | Bulunan kaynak | Durum |
|---|---|---|---|
| **F09** | Fiyat | Fresha (`source-0317`) — TRY 240.95/ay | Katalogda, hazır |
| **F09** | Kullanıcı şikâyeti | Apple App Store — Booksy Biz (`source-0096`) | Katalogda, hazır |
| **F02** | Fiyat, ürün, iş akışı | Filestage, Ziflow | **Katalogda yok** — registry kararı Batuhan'da |
| **F02** | Kullanıcı şikâyeti | — | **Açık kaldı** |

Bir ayrım önemli: bulunan kaynakların çoğu **satıcının kendi sitesi**. Satıcı
kendi hakkındaki şikâyeti yayımlamaz; "alternatifler" sayfası pazarlamadır.
Kanıt politikası da aynı yere varıyor — *"aynı kurumun pazarlama kopyaları bir
köken"*. Bu yüzden satıcı sayfaları G2/Capterra/Reddit'in yerini **tutmaz**:
fiyat verirler, şikâyet vermezler.

F09'un şikâyet boşluğunu kapatan tek yol üçüncü taraf çıktı: Booksy'nin
işletme uygulamasının App Store sayfasında gerçek kullanıcı yorumu var ve
biri doğrudan F09'un konusu — *"charged for a no show I didn't know I had"*.

**F02 için böyle bir yol bulunamadı.** Filestage ve Ziflow'un mobil uygulaması
yok, Hacker News nişe sonuç vermiyor, inceleme platformları bot korumalı.
Batuhan F02'yi fiyat ve ürün iddiası için araştırabilir, memnuniyetsizlik için
araştıramaz.

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
