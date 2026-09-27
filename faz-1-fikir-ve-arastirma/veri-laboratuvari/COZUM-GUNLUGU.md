# Çözüm Günlüğü ve Kaynak Sağlık Kayıtları — AS-06

**Sürüm 1.0.0** · Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan
Üreten: `cozum_gunlugu.py` · Son ölçüm: 2026-09-24

Bu belge bir **başarı raporu değildir.** Denenip yürümeyen yollar, yanlış
çıkan tahminler ve geri alınan kararlar da burada. Bir yolun *denenmiş ve
çalışmamış* olduğunu bilmek, *hiç denenmemiş* olmasından farklıdır — ikincisi
tekrar denemeye değer, birincisi aynı duvara yeniden çarpmaktır.

## Özet

| Bulgu durumu | Adet |
|---|---:|
| Çözüldü | 13 |
| Kısmen çözüldü | 4 |
| Çözülemedi (sınır kaydı) | 3 |
| **Toplam** | **20** |

Her bulgu bir tarihe, bir script sürümüne ve bir commit'e bağlı; her satırın
altında Batuhan'ın çalıştırabileceği komut var.

## 1. Çözülen bulgular

Bunların hepsinde **öncesi ve sonrası ölçüldü**; iddia değil, ölçüm.

#### CG-01 — robots_state RFC 9309'un altinda kaliyordu

| | |
|---|---|
| **Ne denendi** | api.stackexchange.com/robots.txt — resmi API host'u robots.txt yerine HTTP 400 + JSON hata donduruyor |
| **Tarih** | 2026-09-24 · `bulk_site_access_lab.py` · commit `bc446ef` |
| **Önce** | robots_preflight_blocked — istek hic atilmadi |
| **Sonra** | robots=absent; API calisti, 4980 karakter, 3 gercek sonuc |
| **Kalan sınır** | stackoverflow.com ayri: HTTP 418 ile GECERLI bir 'Disallow: /' donduruyor ve bu yasak korunuyor |
| **FB-ID** | — |

```bash
python3 as01_kaynak_kontrol.py --canli  (F03 satiri)
```

#### CG-02 — iTunes Search API beyan edilen MIME yuzunden reddediliyordu

| | |
|---|---|
| **Ne denendi** | itunes.apple.com/search?term=Booksy&entity=software — gecerli JSON'u text/javascript tipiyle servis ediyor |
| **Tarih** | 2026-09-24 · `bulk_site_access_lab.py` · commit `635ce4b` |
| **Önce** | mime_or_sniff_mismatch — dort terimde de basarisiz |
| **Sonra** | Booksy Biz id=725335996, puan 4.52, 14.888 yorum sayisi alindi |
| **Kalan sınır** | — |
| **FB-ID** | — |

```bash
python3 alternatif_kaynak.py --canli  (F09 App Store satirlari)
```

#### CG-03 — Fiyat deseni para birimi onde gelen bicimi kaciriyordu

| | |
|---|---|
| **Ne denendi** | fresha.com/pricing — fiyatlar 'TRY 240.95 per month' bicimde |
| **Tarih** | 2026-09-24 · `normalize_belgeler.py` · commit `302497e` |
| **Önce** | fiyat alani bos; 55 fiyat isareti olan sayfadan 0 fiyat cikti |
| **Sonra** | TRY 240.95 yakalandi; TL, EUR, GBP onek bicimleri de |
| **Kalan sınır** | — |
| **FB-ID** | — |

```bash
python3 -c "import normalize_belgeler as n; print(n.alan_cikar('urun','TRY 240.95 per month',''))"
```

#### CG-08 — Apple musteri yorumu RSS ucu bos donuyor

| | |
|---|---|
| **Ne denendi** | itunes.apple.com/us/rss/customerreviews/page=1/id=725335996/json — Booksy Biz ve Fresha for business icin denendi |
| **Tarih** | 2026-09-24 · `alternatif_kaynak.py` · commit `635ce4b` |
| **Önce** | belgelenmis uc; yorum METNI icin ilk tercih |
| **Sonra** | gecerli JSON donuyor ama 'entry' dizisi bos — uc fiilen emekli |
| **Kalan sınır** | Calisan yol uygulama SAYFASININ kendisi cikti: apps.apple.com/.../id725335996 icinde gercek yorum metni var. |
| **FB-ID** | — |

```bash
python3 alternatif_kaynak.py --canli  (F09 App Store satiri)
```

#### CG-09 — HTTP 200 + gercek icerik, ilgisiz sonuc

| | |
|---|---|
| **Ne denendi** | sourceforge.net/directory/?q=salon+scheduling+software |
| **Tarih** | 2026-09-24 · `alternatif_kaynak.py` · commit `302497e` |
| **Önce** | aday listesinde 'calisiyor' sayiliyordu |
| **Sonra** | 200 OK, 19 bin karakter; icerik Kubernetes orkestrasyon ve kripto fiyatlama — nisle ilgisi yok |
| **Kalan sınır** | Her adaya ucuncu bir test eklendi: erisim ve icerik yetmiyor, nisin kendi kelimeleri govdede aranmali. Anahtar kelime eslesmesi ilgililik degildir. |
| **FB-ID** | — |

```bash
python3 -m unittest test_alternatif_kaynak.IlgililikTests
```

#### CG-12 — Arşiv kopyalarının kendi tarihi hiçbir tabloda yoktu

| | |
|---|---|
| **Ne denendi** | 104 Common Crawl kopyasının warc_timestamp'i koşu JSON'undan okundu ve dizindeki tarihle karşılaştırıldı |
| **Tarih** | 2026-09-25 · `alternatif_fark.py` · commit `af28f5f` |
| **Önce** | ARTEFAKT-DIZINI.csv hepsine 2026-09-03 (bizim indirme tarihimiz) yazıyordu |
| **Sonra** | 94 kopya 180 günü, 93'ü bir yılı aşıyor; en eskisi 596 gün. Her satır kendi tarihini ve guncel_veri_mi=hayır taşıyor |
| **Kalan sınır** | Arşiv içeriği tazelenemez; yalnız yaşı görünür oldu. |
| **FB-ID** | — |

```bash
python3 alternatif_fark.py --yaz
```

#### CG-13 — Alan çıkarımı sayfaya değil kaynağın ailesine bakıyordu

| | |
|---|---|
| **Ne denendi** | Fiyat yüzeyi olarak çekilmiş 48 sayfada fiyat çıkmıyordu; 25'inin gövdesinde apaçık fiyat vardı (Kagi, Sistrix, Exploding Topics) |
| **Tarih** | 2026-09-25 · `normalize_belgeler.py` · commit `bc7bf2a` |
| **Önce** | alan 212, fiyat 56, fiyat sayfası olup fiyat çıkmayan 48 |
| **Sonra** | alan 273, fiyat 108, fiyat çıkmayan 16 |
| **Kalan sınır** | Kalan 16 sayfada gövdede gerçekten fiyat yok. |
| **FB-ID** | — |

```bash
python3 normalize_belgeler.py --yaz
```

#### CG-15 — Yoklama artefaktları kanıt zincirine hiç girmiyordu

| | |
|---|---|
| **Ne denendi** | AS-01 ve AS-03 scriptleri artefaktı diske yazıyor ama EK-ARTEFAKT-DIZINI.csv'ye satır eklemiyordu |
| **Tarih** | 2026-09-27 · `normalize_belgeler.py` · commit `b24fcbe` |
| **Önce** | Fresha'nın TRY fiyatı, Booksy'nin no-show yorumu, Filestage ve Ziflow raporlarda kanıt diye gösteriliyordu ama veri kümesinde yoktu; AS-04'ün iki karşıt bulgusu sayımda görünmüyordu |
| **Sonra** | 21 artefakt dizine işlendi; belge 1249→1270, alan 273→307, karşıt bulgular sayımda göründü |
| **Kalan sınır** | Scriptler hâlâ dizine kendileri yazmıyor; geri dolduruldu. |
| **FB-ID** | — |

```bash
python3 kanit_sayimi.py --yaz
```

#### CG-16 — Aynı şirketin farklı markaları bağımsız sayılıyordu

| | |
|---|---|
| **Ne denendi** | 3/2 sayımı geçen hücrelerde ortak sahiplik arandı |
| **Tarih** | 2026-09-27 · `source_fit_matrix.py` · commit `3bce1e3` |
| **Önce** | GetApp ve Software Advice (ikisi de Gartner'ın) b2b-web-yazilimi/competitor_discovery'de 2 bağımsız kaynak sayılıyordu |
| **Sonra** | Bilinen sahiplik gruplamaya eklendi; 421→415 grup, geçen hiçbir hücrede aynı sahibin iki markası ayrı değil |
| **Kalan sınır** | Sahiplik listesi BEYAN EDİLMİŞ bilgidir, ölçülmüş değil; Batuhan'ın incelemesine açık. Listede olmayan ortak sahiplikler hâlâ ayrı sayılır. |
| **FB-ID** | — |

```bash
python3 -m unittest test_source_fit_matrix.KopyalarBagimsizSayilmazTests
```

#### CG-17 — Yakalanan sayfalarda üçüncü taraf API anahtarları vardı

| | |
|---|---|
| **Ne denendi** | GitHub push protection iki kez reddetti; tüm sağlayıcı desenleri (Replicate, Stripe, Clerk, JWT...) tarandı |
| **Tarih** | 2026-09-25 · `ic_sayfa_gecisi.py` · commit `952f4b5` |
| **Önce** | push reddi: 'Push cannot contain secrets' — bir Replicate token, iki pk_live, bir JWT |
| **Sonra** | 4 artefakt redakte edildi; orijinaller local-originals/ altına, shared-redactions.json'a 9 kayıt |
| **Kalan sınır** | Anahtarlar sitelerin kendi yayımladığı değerlerdi, bizim değil. Yeni artefakt eklenirken tarama tekrarlanmalı. |
| **FB-ID** | — |

```bash
grep -rE 'r8_[A-Za-z0-9]{35,}|pk_live_' results/raw/
```

#### CG-18 — as01_kaynak_kontrol.py komut satırından çalışmıyordu

| | |
|---|---|
| **Ne denendi** | Batuhan'ın source_plan.py'si bu scripti LAB_SCRIPT olarak çağırıyor; çalıştırılınca NameError veriyordu |
| **Tarih** | 2026-09-27 · `as01_kaynak_kontrol.py` · commit `—` |
| **Önce** | `python3 as01_kaynak_kontrol.py --canli` → NameError: iddialari_dogrula is not defined |
| **Sonra** | if __name__ bloğu dosya sonuna taşındı; script çalışıyor |
| **Kalan sınır** | Modül olarak import edilince sorun yoktu, bu yüzden testler yakalamamıştı. CLI yolu test edilmiyor. |
| **FB-ID** | — |

```bash
python3 as01_kaynak_kontrol.py --yaz
```

#### CG-19 — İçerik-adresli yazıcı redaksiyon sözleşmesiyle çarpışıyor

| | |
|---|---|
| **Ne denendi** | BT-02 sağlık taraması redakte edilmiş bir sayfayı yeniden çekince yazıcı durdu |
| **Tarih** | 2026-09-27 · `saglik_taramasi.py` · commit `—` |
| **Önce** | ValueError: existing_raw_artifact_hash_mismatch — tarama çöktü |
| **Sonra** | Saklama tarama tarafından yönetiliyor; redakte dosyanın üzerine yazılmıyor. 305 kaynak tarandı |
| **Kalan sınır** | İki sözleşme yapısal olarak çelişiyor: dosya adı orijinal hash'i korurken baytlar farklı. Yeni yazan her modül bunu bilmek zorunda. |
| **FB-ID** | — |

```bash
python3 saglik_taramasi.py --canli --sinir 6
```

#### CG-20 — Normalize taşınmadan sonra artefaktların çoğunu bulamıyordu

| | |
|---|---|
| **Ne denendi** | Depo üç fazlı yapıya taşındıktan sonra script ilk kez koşturuldu |
| **Tarih** | 2026-09-25 · `normalize_belgeler.py` · commit `bc7bf2a` |
| **Önce** | 1249 belge 179'a düştü; iyi bir veri kümesi eksik olanla üzerine yazıldı |
| **Sonra** | İki arşiv konumuna da bakıyor; 1249 geri geldi |
| **Kalan sınır** | Artefaktların 1021'i hâlâ yalnız yerel arşivde; depoya yalnız sayı çıkarılanlar alındı. |
| **FB-ID** | — |

```bash
python3 normalize_belgeler.py --yaz
```

## 2. Kısmen çözülenler

Bir tarafı açıldı, bir tarafı açık kaldı. Açık kalan taraf gizlenmiyor.

#### CG-06 — Google Play HTTP 200 donuyor ama govde bos

| | |
|---|---|
| **Ne denendi** | play.google.com/store/apps/details?id=... — robots izinli, istek basarili |
| **Tarih** | 2026-09-24 · `as01_kaynak_kontrol.py` · commit `bc446ef` |
| **Önce** | erisim listesinde 'ok' gorunuyordu |
| **Sonra** | 200 OK, 0 karakter gorunur metin; js-kabugu olarak ayrildi |
| **Kalan sınır** | Sayfa tamamen tarayicida uretiliyor. Ayni uygulamalar Apple App Store'da aliniyor (21-28 bin karakter, puan ve fiyatla); Google Play tarafi acik kaliyor. |
| **FB-ID** | AS01-0097 |

```bash
python3 as01_kaynak_kontrol.py --canli  (F01/F10 Google Play)
```

#### CG-10 — F02 icin kullanici sikayeti kaynagi bulunamadi

| | |
|---|---|
| **Ne denendi** | Filestage/Ziflow (satici sitesi), SourceForge (ilgisiz), GetApp (challenge), Hacker News API (0 sonuc), iTunes Search (mobil uygulama yok) |
| **Tarih** | 2026-09-24 · `alternatif_kaynak.py` · commit `635ce4b` |
| **Önce** | F02'nin uc kaynagi da kapaliydi |
| **Sonra** | fiyat/urun icin Filestage ve Ziflow bulundu; sikayet icin hicbiri |
| **Kalan sınır** | Satici kendi hakkindaki sikayeti yayimlamaz. F02 fiyat ve urun iddiasi icin arastirilabilir, memnuniyetsizlik icin arastirilamaz. Filestage ve Ziflow katalogda YOK — registry karari Batuhan'da. |
| **FB-ID** | AS01-0134, AS01-0135 |

```bash
python3 alternatif_kaynak.py --canli  (F02 satirlari)
```

#### CG-11 — Ham arsiv depo disinda kaldi; iddialar dogrulanamiyordu

| | |
|---|---|
| **Ne denendi** | Uc fazli yapiya tasinma sonrasi artefakt konumu sayildi |
| **Tarih** | 2026-09-24 · `as01_kaynak_kontrol.py` · commit `474a09c` |
| **Önce** | 1249 normalize belgenin 21'inin ham dosyasi depoda (%1.7) |
| **Sonra** | sayi cikarilan 154 dosya depoya alindi; KATEGORI-ALANLARI.csv'deki 164 alanin 164'u dogrulanabilir |
| **Kalan sınır** | SourceFitMatrix ornek kayitlari 101/346'da; tamamlamak ~75 MB daha demek, karar Batuhan'da. Kalan 1070 belge ana sayfa ve sitemap — dogrulanacak iddia tasimiyorlar. |
| **FB-ID** | — |

```bash
python3 -m unittest test_as01_kaynak_kontrol.CikarilanSayininKaynagiDepodaTests
```

#### CG-14 — Filtre gerçek kanıt eliyordu

| | |
|---|---|
| **Ne denendi** | 'Ölçüm kanıtı üretmez' diye elenen 76 belgede fiyat çıktı; bağlamları tek tek okundu |
| **Tarih** | 2026-09-25 · `hata_incelemesi.py` · commit `bc7bf2a` |
| **Önce** | 76 belge elenmişti, hangisinin gerçek olduğu bilinmiyordu |
| **Sonra** | 10'u gerçek kanıt (Airbnb ₺4.733 + 4.78 puan, AppSumo $39 + 3 yorum), 66'sı gürültü ('$2.3 billion in AUM' gibi) |
| **Kalan sınır** | Ayrım kuralı yazıldı ama filtreye henüz uygulanmadı; 10 kanıt hâlâ elenmiş durumda. |
| **FB-ID** | — |

```bash
python3 hata_incelemesi.py --yaz
```

## 3. Çözülemeyenler — sınır kayıtları

Bunlar başarısızlık değil **sınır** kaydıdır. Yol denendi, yürümedi, sebebi
ölçüldü. Aynı yolu tekrar denemek yerine sebebe bakılmalı.

#### CG-04 — Reddit kazimayla alinamiyor

| | |
|---|---|
| **Ne denendi** | reddit.com/robots.txt bugun yeniden cekildi; /r/*/.rss, /r/*/new.json, /dev/api dahil yedi yol robots'a soruldu |
| **Tarih** | 2026-09-24 · `as01_kaynak_kontrol.py` · commit `bc446ef` |
| **Önce** | kayitta 'kismi/dosya-yok'; sebep belirsizdi |
| **Sonra** | sebep kesin: 'User-agent: * / Disallow: /' — yedi yolun yedisi yasak |
| **Kalan sınır** | Politika engeli. Reddit'in kendi robots.txt'i izinli yolu gosteriyor: Public Content Policy ve r/reddit4researchers. Hesap ve sartname onayi gerekir; karar Cağlar'da. 10 fikrin 7'sini etkiliyor. |
| **FB-ID** | AS01-0075 |

```bash
python3 as01_kaynak_kontrol.py --canli  (Reddit satirlari)
```

#### CG-05 — Capterra kayitla celisiyor: kayit calisiyor diyor, bugun kapali

| | |
|---|---|
| **Ne denendi** | capterra.com/proofing-software/ ve /salon-software/ — robots izin veriyor, istek bot korumasina takiliyor |
| **Tarih** | 2026-09-24 · `as01_kaynak_kontrol.py` · commit `bc446ef` |
| **Önce** | 2 Eylul kaydi: erisim=cekildi, icerik=gercek-icerik |
| **Sonra** | bugun challenge; F02, F09 ve F10'u etkiliyor |
| **Kalan sınır** | Bot korumasi asilmiyor. Arsiv (Common Crawl) kopyasi var ama canli degil ve 'arsiv' etiketiyle tasinmali. |
| **FB-ID** | AS01-0135 |

```bash
python3 as01_kaynak_kontrol.py --canli  (F02/F09 Capterra)
```

#### CG-07 — Uygulama magazasi kayit sayfalari bos geliyor

| | |
|---|---|
| **Ne denendi** | galaxystore.samsung.com/detail/... ve apps.microsoft.com/detail/... — sitemap'lerden 14.948 kayit adresi cikarildi, 6 tanesi test edildi |
| **Tarih** | 2026-09-18 · `ic_sayfa_gecisi.py` · commit `298f5c0` |
| **Önce** | 14.948 aday adres; mobil-uygulama kategorisi 1/6 hucrede doluydu |
| **Sonra** | Microsoft bos govde, Samsung 38 karakter; kategori acik kaldi |
| **Kalan sınır** | Istemci tarafinda uretilen magaza sayfalari bu hatla alinamiyor. Adres sayisi coklugu ise yaramiyor. |
| **FB-ID** | — |

```bash
AS01-ALTERNATIF-KAYNAK.csv · kayit sayfasi testi
```

## 4. Kaynak sağlık kayıtları

**Başarılı ve başarısız kaynaklar birlikte tutulur.** Çalışmayanı silmek, bir
sonraki turda aynı siteyi yeniden deneyip aynı duvara çarpmak demektir.

| Sağlık | Kaynak |
|---|---:|
| `saglikli` — içerik geliyor | 269 |
| `bot-korumasi` — site reddediyor | 11 |
| `politika-kapali` — robots yasağı | 14 |
| `icerik-yetersiz` — 200 ama gövde boş | 5 |

| Kaynak | source_id | Sağlık | Sebep | Yeniden denenebilir mi |
|---|---|---|---|---|
| Bing | `source-0004` | politika-kapali | robots.txt 401/403 — tam yasak | hayır — politika |
| DuckDuckGo | `source-0005` | saglikli | içerik geliyor | evet |
| Yahoo Search | `source-0006` | saglikli | içerik geliyor | evet |
| Kagi | `source-0009` | saglikli | içerik geliyor | evet |
| Tavily | `source-0011` | saglikli | içerik geliyor | evet |
| Serper | `source-0013` | saglikli | içerik geliyor | evet |
| Firecrawl | `source-0016` | saglikli | içerik geliyor | evet |
| GitHub | `source-0017` | saglikli | içerik geliyor | evet |
| SourceForge | `source-0020` | saglikli | içerik geliyor | evet |
| Codeberg | `source-0021` | saglikli | içerik geliyor | evet |
| Hacker News | `source-0022` | saglikli | içerik geliyor | evet |
| Stack Overflow | `source-0023` | saglikli | içerik geliyor | evet |
| Dev.to | `source-0029` | saglikli | içerik geliyor | evet |
| Hashnode | `source-0030` | saglikli | içerik geliyor | evet |
| DZone | `source-0033` | saglikli | içerik geliyor | evet |
| InfoQ | `source-0034` | saglikli | içerik geliyor | evet |
| Slashdot | `source-0035` | saglikli | içerik geliyor | evet |
| Docker Hub | `source-0038` | saglikli | içerik geliyor | evet |
| PyPI | `source-0040` | saglikli | içerik geliyor | evet |
| RubyGems | `source-0041` | saglikli | içerik geliyor | evet |
| Maven Central | `source-0043` | saglikli | içerik geliyor | evet |
| Homebrew Formulae | `source-0046` | adres-hatasi | adres yanıt vermiyor ya da sayfa yok | belirsiz |
| Libraries.io | `source-0047` | politika-kapali | robots.txt 401/403 — tam yasak | hayır — politika |
| Open VSX Registry | `source-0048` | saglikli | içerik geliyor | evet |
| Visual Studio Marketplace | `source-0049` | saglikli | içerik geliyor | evet |
| BetaList | `source-0052` | saglikli | içerik geliyor | evet |
| Uneed | `source-0053` | saglikli | içerik geliyor | evet |
| Microlaunch | `source-0054` | saglikli | içerik geliyor | evet |
| Peerlist | `source-0055` | saglikli | içerik geliyor | evet |
| Startup Stash | `source-0057` | saglikli | içerik geliyor | evet |
| SaaSHub | `source-0058` | saglikli | içerik geliyor | evet |
| AlternativeTo | `source-0059` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| Futurepedia | `source-0062` | saglikli | içerik geliyor | evet |
| Toolify | `source-0063` | saglikli | içerik geliyor | evet |
| AppSumo | `source-0065` | saglikli | içerik geliyor | evet |
| PitchWall | `source-0066` | saglikli | içerik geliyor | evet |
| Fazier | `source-0067` | politika-kapali | robots.txt 401/403 — tam yasak | hayır — politika |
| Failory | `source-0071` | saglikli | içerik geliyor | evet |
| Y Combinator Companies | `source-0072` | saglikli | içerik geliyor | evet |
| Wellfound | `source-0073` | saglikli | içerik geliyor | evet |
| Reddit | `source-0075` | politika-kapali | robots.txt yolu yasaklıyor — aşılmaz | hayır — politika |
| Mastodon | `source-0077` | saglikli | içerik geliyor | evet |
| TikTok | `source-0082` | saglikli | içerik geliyor | evet |
| Tumblr | `source-0086` | politika-kapali | robots.txt 401/403 — tam yasak | hayır — politika |
| Substack | `source-0089` | saglikli | içerik geliyor | evet |
| Slack | `source-0091` | saglikli | içerik geliyor | evet |
| Telegram | `source-0092` | saglikli | içerik geliyor | evet |
| Discourse | `source-0093` | saglikli | içerik geliyor | evet |
| Groups.io | `source-0094` | saglikli | içerik geliyor | evet |
| Lemmy | `source-0095` | saglikli | içerik geliyor | evet |
| Apple App Store | `source-0096` | saglikli | içerik geliyor | evet |
| Google Play Store | `source-0097` | icerik-yetersiz | HTTP 200 ama görünür metin yok — sayfa tarayıcıda üretiliyor | hayır — bu yöntemle |
| Huawei AppGallery | `source-0098` | saglikli | içerik geliyor | evet |
| Samsung Galaxy Store | `source-0099` | saglikli | içerik geliyor | evet |
| Aptoide | `source-0105` | saglikli | içerik geliyor | evet |
| F-Droid | `source-0106` | saglikli | içerik geliyor | evet |
| APKMirror | `source-0107` | saglikli | içerik geliyor | evet |
| Uptodown | `source-0108` | saglikli | içerik geliyor | evet |
| Firefox Add-ons | `source-0110` | saglikli | içerik geliyor | evet |
| Safari Extensions | `source-0112` | saglikli | içerik geliyor | evet |
| Opera Add-ons | `source-0113` | saglikli | içerik geliyor | evet |
| Shopify App Store | `source-0114` | saglikli | içerik geliyor | evet |
| WooCommerce Marketplace | `source-0115` | saglikli | içerik geliyor | evet |
| WordPress Plugin Directory | `source-0116` | saglikli | içerik geliyor | evet |
| Wix App Market | `source-0117` | saglikli | içerik geliyor | evet |
| BigCommerce App Marketplace | `source-0119` | saglikli | içerik geliyor | evet |
| Webflow Apps | `source-0120` | saglikli | içerik geliyor | evet |
| Atlassian Marketplace | `source-0121` | saglikli | içerik geliyor | evet |
| Salesforce AppExchange | `source-0122` | saglikli | içerik geliyor | evet |
| Slack Marketplace | `source-0124` | icerik-yetersiz | HTTP 200 ama görünür metin yok — sayfa tarayıcıda üretiliyor | hayır — bu yöntemle |
| Google Workspace Marketplace | `source-0127` | saglikli | içerik geliyor | evet |
| monday.com Apps Marketplace | `source-0128` | saglikli | içerik geliyor | evet |
| Notion Integrations | `source-0129` | saglikli | içerik geliyor | evet |
| Zapier App Directory | `source-0130` | saglikli | içerik geliyor | evet |
| Airtable Marketplace | `source-0132` | icerik-yetersiz | HTTP 200 ama görünür metin yok — sayfa tarayıcıda üretiliyor | hayır — bu yöntemle |
| Canva Apps Marketplace | `source-0133` | saglikli | içerik geliyor | evet |
| G2 | `source-0134` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| Capterra | `source-0135` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| GetApp | `source-0136` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| Software Advice | `source-0137` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| PeerSpot | `source-0140` | saglikli | içerik geliyor | evet |
| SourceForge Reviews | `source-0141` | saglikli | içerik geliyor | evet |
| Serchen | `source-0143` | saglikli | içerik geliyor | evet |
| FinancesOnline | `source-0144` | saglikli | içerik geliyor | evet |
| SoftwareSuggest | `source-0146` | saglikli | içerik geliyor | evet |
| Tekpon | `source-0147` | saglikli | içerik geliyor | evet |
| Trustpilot | `source-0148` | politika-kapali | robots.txt yolu yasaklıyor — aşılmaz | hayır — politika |
| Reviews.io | `source-0152` | saglikli | içerik geliyor | evet |
| Amazon | `source-0159` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| Walmart | `source-0162` | adres-hatasi | adres yanıt vermiyor ya da sayfa yok | belirsiz |
| Alibaba | `source-0164` | saglikli | içerik geliyor | evet |
| Trendyol | `source-0166` | saglikli | içerik geliyor | evet |
| n11 | `source-0168` | politika-kapali | robots.txt 401/403 — tam yasak | hayır — politika |
| Çiçeksepeti | `source-0169` | saglikli | içerik geliyor | evet |
| Pazarama | `source-0170` | saglikli | içerik geliyor | evet |
| Gumroad | `source-0175` | saglikli | içerik geliyor | evet |
| Lemon Squeezy | `source-0176` | saglikli | içerik geliyor | evet |
| Envato Market | `source-0178` | saglikli | içerik geliyor | evet |
| ThemeForest | `source-0179` | saglikli | içerik geliyor | evet |
| CodeCanyon | `source-0180` | saglikli | içerik geliyor | evet |
| Etsy Reviews | `source-0181` | saglikli | içerik geliyor | evet |
| Censys | `source-0193` | saglikli | içerik geliyor | evet |
| WhoisXML API | `source-0199` | saglikli | içerik geliyor | evet |
| DomainTools | `source-0200` | saglikli | içerik geliyor | evet |
| BuiltWith | `source-0201` | saglikli | içerik geliyor | evet |
| Wappalyzer | `source-0202` | saglikli | içerik geliyor | evet |
| urlscan.io | `source-0206` | saglikli | içerik geliyor | evet |
| HTTP Archive | `source-0209` | saglikli | içerik geliyor | evet |
| Cloudflare Radar | `source-0210` | politika-kapali | robots.txt 401/403 — tam yasak | hayır — politika |
| Bing Webmaster Tools | `source-0216` | saglikli | içerik geliyor | evet |
| Ahrefs | `source-0217` | saglikli | içerik geliyor | evet |
| Semrush | `source-0218` | saglikli | içerik geliyor | evet |
| Moz | `source-0219` | saglikli | içerik geliyor | evet |
| Ubersuggest | `source-0220` | saglikli | içerik geliyor | evet |
| Mangools | `source-0221` | saglikli | içerik geliyor | evet |
| SE Ranking | `source-0222` | icerik-yetersiz | HTTP 200 ama görünür metin yok — sayfa tarayıcıda üretiliyor | hayır — bu yöntemle |
| Majestic | `source-0224` | saglikli | içerik geliyor | evet |
| Sistrix | `source-0225` | bicim-uyusmazligi | beyan edilen tip beklenenden farklı | belirsiz |
| Serpstat | `source-0226` | saglikli | içerik geliyor | evet |
| Exploding Topics | `source-0229` | saglikli | içerik geliyor | evet |
| Glimpse | `source-0230` | saglikli | içerik geliyor | evet |
| Trend Hunter | `source-0231` | politika-kapali | robots.txt 401/403 — tam yasak | hayır — politika |
| SparkToro | `source-0233` | saglikli | içerik geliyor | evet |
| BuzzSumo | `source-0234` | saglikli | içerik geliyor | evet |
| Meta Ad Library | `source-0236` | bicim-uyusmazligi | beyan edilen tip beklenenden farklı | belirsiz |
| Pathmatics | `source-0244` | saglikli | içerik geliyor | evet |
| Sensor Tower | `source-0245` | saglikli | içerik geliyor | evet |
| SocialPeta | `source-0248` | saglikli | içerik geliyor | evet |
| BigSpy | `source-0249` | saglikli | içerik geliyor | evet |
| Crunchbase | `source-0252` | saglikli | içerik geliyor | evet |
| PitchBook | `source-0253` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| Dealroom | `source-0255` | saglikli | içerik geliyor | evet |
| CB Insights | `source-0256` | butce | koşu bütçesi bitti; kaynak hakkında bilgi vermez | belirsiz |
| PrivCo | `source-0257` | saglikli | içerik geliyor | evet |
| ZoomInfo | `source-0260` | saglikli | içerik geliyor | evet |
| Apollo | `source-0261` | saglikli | içerik geliyor | evet |
| Clearbit | `source-0262` | saglikli | içerik geliyor | evet |
| OpenCorporates | `source-0264` | saglikli | içerik geliyor | evet |
| SEC EDGAR | `source-0265` | politika-kapali | robots.txt 401/403 — tam yasak | hayır — politika |
| Companies House | `source-0266` | saglikli | içerik geliyor | evet |
| MERSİS | `source-0269` | saglikli | içerik geliyor | evet |
| AngelList | `source-0271` | saglikli | içerik geliyor | evet |
| Techstars Companies | `source-0272` | saglikli | içerik geliyor | evet |
| 500 Global Companies | `source-0273` | saglikli | içerik geliyor | evet |
| Republic | `source-0275` | saglikli | içerik geliyor | evet |
| Seedrs | `source-0276` | saglikli | içerik geliyor | evet |
| Indeed | `source-0279` | saglikli | içerik geliyor | evet |
| Lever Jobs | `source-0286` | saglikli | içerik geliyor | evet |
| Ashby Jobs | `source-0287` | saglikli | içerik geliyor | evet |
| SmartRecruiters | `source-0289` | saglikli | içerik geliyor | evet |
| Remote OK | `source-0290` | saglikli | içerik geliyor | evet |
| We Work Remotely | `source-0291` | saglikli | içerik geliyor | evet |
| Welcome to the Jungle | `source-0294` | saglikli | içerik geliyor | evet |
| Yenibiris | `source-0296` | saglikli | içerik geliyor | evet |
| Secretcv | `source-0297` | saglikli | içerik geliyor | evet |
| Eleman.net | `source-0298` | saglikli | içerik geliyor | evet |
| İşkur | `source-0299` | saglikli | içerik geliyor | evet |
| OpenStreetMap | `source-0303` | saglikli | içerik geliyor | evet |
| Foursquare | `source-0304` | saglikli | içerik geliyor | evet |
| HERE WeGo | `source-0307` | saglikli | içerik geliyor | evet |
| TomTom | `source-0309` | saglikli | içerik geliyor | evet |
| Nextdoor | `source-0312` | saglikli | içerik geliyor | evet |
| Houzz | `source-0315` | saglikli | içerik geliyor | evet |
| Fresha | `source-0317` | saglikli | içerik geliyor | evet |
| Booksy | `source-0318` | saglikli | içerik geliyor | evet |
| Armut | `source-0319` | saglikli | içerik geliyor | evet |
| Google Scholar | `source-0321` | saglikli | içerik geliyor | evet |
| Semantic Scholar | `source-0322` | saglikli | içerik geliyor | evet |
| BASE | `source-0326` | saglikli | içerik geliyor | evet |
| Dimensions | `source-0328` | saglikli | içerik geliyor | evet |
| Web of Science | `source-0330` | saglikli | içerik geliyor | evet |
| PubMed | `source-0331` | saglikli | içerik geliyor | evet |
| DOAJ | `source-0347` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| Zenodo | `source-0348` | saglikli | içerik geliyor | evet |
| Dryad | `source-0351` | saglikli | içerik geliyor | evet |
| Kaggle | `source-0352` | saglikli | içerik geliyor | evet |
| World Bank Open Data | `source-0354` | saglikli | içerik geliyor | evet |
| IMF Data | `source-0356` | saglikli | içerik geliyor | evet |
| United Nations Data | `source-0357` | saglikli | içerik geliyor | evet |
| US Census Bureau | `source-0361` | saglikli | içerik geliyor | evet |
| Federal Reserve Economic Data | `source-0363` | saglikli | içerik geliyor | evet |
| WHO Global Health Observatory | `source-0364` | saglikli | içerik geliyor | evet |
| Our World in Data | `source-0366` | saglikli | içerik geliyor | evet |
| TÜİK | `source-0367` | saglikli | içerik geliyor | evet |
| İstanbul Büyükşehir Belediyesi Açık Veri Portalı | `source-0374` | saglikli | içerik geliyor | evet |
| data.gov.uk | `source-0376` | saglikli | içerik geliyor | evet |
| Destatis | `source-0378` | saglikli | içerik geliyor | evet |
| BTK | `source-0382` | saglikli | içerik geliyor | evet |
| SPK | `source-0384` | saglikli | içerik geliyor | evet |
| TCMB | `source-0385` | saglikli | içerik geliyor | evet |
| European Commission | `source-0391` | saglikli | içerik geliyor | evet |
| European Data Protection Board | `source-0392` | saglikli | içerik geliyor | evet |
| European Medicines Agency | `source-0393` | saglikli | içerik geliyor | evet |
| European Banking Authority | `source-0394` | saglikli | içerik geliyor | evet |
| European Securities and Markets Authority | `source-0395` | saglikli | içerik geliyor | evet |
| Consumer Financial Protection Bureau | `source-0401` | saglikli | içerik geliyor | evet |
| UK Legislation | `source-0402` | saglikli | içerik geliyor | evet |
| UK Financial Conduct Authority | `source-0403` | saglikli | içerik geliyor | evet |
| UK Information Commissioner's Office | `source-0404` | saglikli | içerik geliyor | evet |
| Competition and Markets Authority | `source-0405` | saglikli | içerik geliyor | evet |
| The Trademark Search Company | `source-0418` | bicim-uyusmazligi | beyan edilen tip beklenenden farklı | belirsiz |
| NICE | `source-0422` | saglikli | içerik geliyor | evet |
| CDC | `source-0423` | saglikli | içerik geliyor | evet |
| ECDC | `source-0424` | saglikli | içerik geliyor | evet |
| MedlinePlus | `source-0429` | saglikli | içerik geliyor | evet |
| Global Health Data Exchange | `source-0431` | politika-kapali | robots.txt 401/403 — tam yasak | hayır — politika |
| Federal Reserve | `source-0432` | saglikli | içerik geliyor | evet |
| FRED | `source-0433` | saglikli | içerik geliyor | evet |
| World Bank | `source-0434` | saglikli | içerik geliyor | evet |
| European Central Bank | `source-0436` | saglikli | içerik geliyor | evet |
| Bank for International Settlements | `source-0437` | saglikli | içerik geliyor | evet |
| Financial Conduct Authority | `source-0438` | saglikli | içerik geliyor | evet |
| Open Banking UK | `source-0439` | saglikli | içerik geliyor | evet |
| NYSE | `source-0441` | saglikli | içerik geliyor | evet |
| Borsa İstanbul | `source-0442` | saglikli | içerik geliyor | evet |
| Yahoo Finance | `source-0443` | saglikli | içerik geliyor | evet |
| Investing.com | `source-0445` | politika-kapali | robots.txt 401/403 — tam yasak | hayır — politika |
| DefiLlama | `source-0449` | saglikli | içerik geliyor | evet |
| U.S. Department of Education | `source-0450` | politika-kapali | robots.txt 401/403 — tam yasak | hayır — politika |
| National Center for Education Statistics | `source-0451` | saglikli | içerik geliyor | evet |
| UNESCO Institute for Statistics | `source-0452` | saglikli | içerik geliyor | evet |
| YÖK | `source-0454` | saglikli | içerik geliyor | evet |
| MEB | `source-0456` | saglikli | içerik geliyor | evet |
| Coursera | `source-0458` | saglikli | içerik geliyor | evet |
| edX | `source-0459` | saglikli | içerik geliyor | evet |
| Skillshare | `source-0461` | saglikli | içerik geliyor | evet |
| Class Central | `source-0462` | saglikli | içerik geliyor | evet |
| Capterra Education Software | `source-0466` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| Trulia | `source-0470` | saglikli | içerik geliyor | evet |
| Rightmove | `source-0471` | saglikli | içerik geliyor | evet |
| ImmobilienScout24 | `source-0476` | saglikli | içerik geliyor | evet |
| Emlakjet | `source-0479` | saglikli | içerik geliyor | evet |
| Tapu ve Kadastro Genel Müdürlüğü | `source-0481` | saglikli | içerik geliyor | evet |
| RICS | `source-0483` | saglikli | içerik geliyor | evet |
| U.S. Census Building Permits | `source-0484` | saglikli | içerik geliyor | evet |
| Airbnb | `source-0486` | saglikli | içerik geliyor | evet |
| Hostelworld | `source-0493` | bicim-uyusmazligi | beyan edilen tip beklenenden farklı | belirsiz |
| Rome2Rio | `source-0497` | saglikli | içerik geliyor | evet |
| Lyft | `source-0499` | saglikli | içerik geliyor | evet |
| Bolt | `source-0500` | saglikli | içerik geliyor | evet |
| Moovit | `source-0502` | saglikli | içerik geliyor | evet |
| FlightAware | `source-0503` | saglikli | içerik geliyor | evet |
| Deliveroo | `source-0509` | saglikli | içerik geliyor | evet |
| Just Eat | `source-0510` | saglikli | içerik geliyor | evet |
| Steam | `source-0518` | saglikli | içerik geliyor | evet |
| GOG | `source-0520` | butce | koşu bütçesi bitti; kaynak hakkında bilgi vermez | belirsiz |
| itch.io | `source-0521` | saglikli | içerik geliyor | evet |
| PlayStation Store | `source-0522` | saglikli | içerik geliyor | evet |
| Nintendo eShop | `source-0524` | saglikli | içerik geliyor | evet |
| Game Developer | `source-0530` | saglikli | içerik geliyor | evet |
| Metacritic | `source-0531` | saglikli | içerik geliyor | evet |
| OpenCritic | `source-0532` | saglikli | içerik geliyor | evet |
| Hugging Face | `source-0534` | saglikli | içerik geliyor | evet |
| OpenRouter | `source-0535` | saglikli | içerik geliyor | evet |
| Replicate | `source-0536` | icerik-yetersiz | HTTP 200 ama görünür metin yok — sayfa tarayıcıda üretiliyor | hayır — bu yöntemle |
| Together AI | `source-0537` | saglikli | içerik geliyor | evet |
| Artificial Analysis | `source-0538` | saglikli | içerik geliyor | evet |
| AWS Marketplace | `source-0541` | saglikli | içerik geliyor | evet |
| Smithery | `source-0546` | bicim-uyusmazligi | beyan edilen tip beklenenden farklı | belirsiz |
| Glama | `source-0547` | saglikli | içerik geliyor | evet |
| MCP.so | `source-0548` | saglikli | içerik geliyor | evet |
| Zapier | `source-0551` | saglikli | içerik geliyor | evet |
| Make | `source-0552` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| Bing News | `source-0554` | saglikli | içerik geliyor | evet |
| Financial Times | `source-0558` | bicim-uyusmazligi | beyan edilen tip beklenenden farklı | belirsiz |
| TechCrunch | `source-0561` | saglikli | içerik geliyor | evet |
| The Verge | `source-0562` | saglikli | içerik geliyor | evet |
| Ars Technica | `source-0564` | politika-kapali | robots.txt 401/403 — tam yasak | hayır — politika |
| Fast Company | `source-0568` | saglikli | içerik geliyor | evet |
| Sifted | `source-0571` | saglikli | içerik geliyor | evet |
| EU-Startups | `source-0572` | saglikli | içerik geliyor | evet |
| Crunchbase News | `source-0573` | bicim-uyusmazligi | beyan edilen tip beklenenden farklı | belirsiz |
| Axios | `source-0574` | bot-korumasi | site bizi bot olarak tanıyıp reddediyor — aşılmaz | hayır — bu yöntemle |
| Rest of World | `source-0575` | bicim-uyusmazligi | beyan edilen tip beklenenden farklı | belirsiz |
| Bloomberg HT | `source-0579` | saglikli | içerik geliyor | evet |
| Ekonomim | `source-0580` | saglikli | içerik geliyor | evet |
| Dünya | `source-0581` | saglikli | içerik geliyor | evet |
| Typeform | `source-0583` | saglikli | içerik geliyor | evet |
| SurveyMonkey | `source-0585` | saglikli | içerik geliyor | evet |
| Tally | `source-0586` | saglikli | içerik geliyor | evet |
| Qualtrics | `source-0588` | saglikli | içerik geliyor | evet |
| Respondent | `source-0590` | saglikli | içerik geliyor | evet |
| Prolific | `source-0591` | saglikli | içerik geliyor | evet |
| UserTesting | `source-0592` | saglikli | içerik geliyor | evet |
| Maze | `source-0594` | saglikli | içerik geliyor | evet |
| Lookback | `source-0595` | saglikli | içerik geliyor | evet |
| dscout | `source-0596` | saglikli | içerik geliyor | evet |
| Wynter | `source-0597` | saglikli | içerik geliyor | evet |
| Pollfish | `source-0599` | saglikli | içerik geliyor | evet |
| Great Question | `source-0601` | adres-hatasi | sunucu isteği reddetti | belirsiz |
| Sprig | `source-0602` | saglikli | içerik geliyor | evet |
| Hotjar | `source-0603` | saglikli | içerik geliyor | evet |
| Microsoft Clarity | `source-0604` | saglikli | içerik geliyor | evet |
| UsabilityHub | `source-0605` | saglikli | içerik geliyor | evet |
| Lyssna | `source-0606` | saglikli | içerik geliyor | evet |
| Vendr | `source-0607` | saglikli | içerik geliyor | evet |
| Vertice | `source-0609` | saglikli | içerik geliyor | evet |
| Sastrify | `source-0610` | saglikli | içerik geliyor | evet |
| CloudPrice | `source-0612` | saglikli | içerik geliyor | evet |
| Vantage | `source-0613` | saglikli | içerik geliyor | evet |
| Infracost | `source-0614` | saglikli | içerik geliyor | evet |
| Azure Pricing Calculator | `source-0616` | saglikli | içerik geliyor | evet |
| StartupMarket | `source-0619` | saglikli | içerik geliyor | evet |
| startups.watch | `source-0620` | saglikli | içerik geliyor | evet |
| TÜBİTAK | `source-0622` | saglikli | içerik geliyor | evet |
| KOSGEB | `source-0623` | saglikli | içerik geliyor | evet |
| Bilişim Vadisi | `source-0624` | saglikli | içerik geliyor | evet |
| İTÜ Çekirdek | `source-0626` | saglikli | içerik geliyor | evet |
| Galata Business Angels | `source-0633` | saglikli | içerik geliyor | evet |
| Arya Women Investment Platform | `source-0634` | saglikli | içerik geliyor | evet |
| Founder Institute Türkiye | `source-0635` | saglikli | içerik geliyor | evet |
| Meetup | `source-0636` | saglikli | içerik geliyor | evet |

Sağlık "çalışıyor mu" değil **hangi duvara çarpıyor** sorusunu cevaplar.
`politika-kapali` ve `bot-korumasi` farklı şeylerdir: birincisi sitenin açık
kararı, ikincisi teknik reddi. İkisi de aşılmıyor ama çözümleri farklı —
birincisi izin, ikincisi başka yüzey gerektirir.

## 5. Bu günlük ne söylemez

- Bir kaynağın kapalı olması o pazarda talep olmadığını göstermez.
- `cozulemedi` satırları kapatılmış değildir; koşul değişirse yeniden açılır.
- Ölçümler 2026-09-24 tarihlidir. Kaynak durumu değişir — CG-05 tam olarak
  bunun örneği: üç hafta önce çalışan Capterra bugün kapalı.

## 6. Yeniden üretim

```bash
python3 cozum_gunlugu.py --yaz
python3 -m unittest test_cozum_gunlugu
```
