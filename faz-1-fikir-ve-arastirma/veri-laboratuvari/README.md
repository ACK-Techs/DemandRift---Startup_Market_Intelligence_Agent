# Kaynak Erişim Laboratuvarı

> **Yeni konum — 22 Eylül 2026:** Bu laboratuvar, çekilmiş içerikler ve mevcut testlerle birlikte Faz 1 altında korunur. Faz 1 kaynak/veri hazırlığını yapar; Faz 2 çalışma anında aynı scriptleri kullanır. Aşağıdaki sayılar geçmiş erişim kayıtlarıdır, yeni canlı test sonucu değildir.
>
> Kökten çalışma: `cd faz-1-fikir-ve-arastirma/veri-laboratuvari`. Mevcut `test_*.py` dosyaları scriptlerle birlikte burada kalır. Yeni fikir test senaryoları [fazın tests dizinindedir](../tests/README.md). Eski raporlar [trash/eski-raporlar](../../trash/eski-raporlar/) altında; gerçek koşu/ham içerik `results/` altında korunur.


DemandRift'in araştırma motoru 636 web kaynağından veri toplamayı planlıyor. Bu
klasör üç soruyu cevaplıyor: **hangi kaynaklar tamamlandı**, **eksik olanların
verisi nasıl çekildi**, ve **bir anahtar kelime bu kaynaklara nasıl sorulur**.

Bütün sayılar artefaktlardan üretilir, elle sayım yoktur. `çekildi` etiketi,
en az bir içerik yüzeyinin başarıyla alındığını gösteren bir **erişim
snapshot**'ıdır; tek başına araştırma sorusuna uygun, güncel veya alıntılanabilir
karar kanıtı anlamına gelmez.

<!-- HARITA:BASLANGIC -->
## Hangi dosya hangi görev

Klasörde 126 dosya var ve GitHub bunları alfabetik sıralıyor.
Aşağıdaki tablo her dosyanın hangi görevin parçası olduğunu söyler.

**Kural:** `test_X.py` dosyası `X.py`'yi korur, ayrı satırı yoktur.

### Ortak — önce bunlar

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`KILAVUZ.md`](KILAVUZ.md) | belge | **Başlangıç noktası.** On dört görevin tamamını sırayla anlatır |
| [`README.md`](README.md) | belge | Bu dosya — klasörün haritası |
| [`dosya_haritasi.py`](dosya_haritasi.py) | kod | README'deki bu haritayı üretir |
| [`.gitignore`](.gitignore) | girdi | İndirilen 721 MB ham artefaktı depo dışında tutar |
| [`source_manifest.json`](source_manifest.json) | girdi | 636 kaynağın kanonik kimlik ve adres listesi |

### Erişim laboratuvarı — 636 kaynağa erişim denemesi ve defteri

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`KAYNAK-DEFTERI.md`](KAYNAK-DEFTERI.md) | belge | Defterin okunabilir özeti |
| [`ARAMA-YUZEYLERI.csv`](ARAMA-YUZEYLERI.csv) | çıktı | Her kaynağın izinli arama yüzeyleri |
| [`ARTEFAKT-DIZINI.csv`](ARTEFAKT-DIZINI.csv) | çıktı | Hangi kaynak hangi dosyaya karşılık geliyor — izlenebilirliğin temeli |
| [`KAYNAK-DEFTERI.csv`](KAYNAK-DEFTERI.csv) | çıktı | 636 kaynağın erişim defteri (çekildi / kısmi / erişim yok) |
| [`OPENSEARCH-SABLONLARI.csv`](OPENSEARCH-SABLONLARI.csv) | çıktı | Sitelerin kendi ilan ettiği arama şablonları |
| [`adaptive_domain_pass.py`](adaptive_domain_pass.py) | kod | Alan adı çözümleme geçişi |
| [`build_artifact_index.py`](build_artifact_index.py) | kod | Artefakt dizinini üretir |
| [`build_coverage_ledger.py`](build_coverage_ledger.py) | kod | Erişim defterini üretir |
| [`build_search_surfaces.py`](build_search_surfaces.py) | kod | Arama yüzeylerini üretir |
| [`bulk_site_access_lab.py`](bulk_site_access_lab.py) | kod | Toplu erişim denemesi |
| [`common_crawl_pass.py`](common_crawl_pass.py) | kod | Common Crawl arşiv geçişi |
| [`export_by_source.py`](export_by_source.py) | kod | Kaynak bazında dışa aktarım |
| [`fetch_opensearch_templates.py`](fetch_opensearch_templates.py) | kod | OpenSearch şablonlarını toplar |
| [`keyword_search_pass.py`](keyword_search_pass.py) | kod | Anahtar kelime arama geçişi |
| [`merge_resolved_domains.py`](merge_resolved_domains.py) | kod | Çözülen adresleri deftere işler |
| [`probe_hackernews_access.py`](probe_hackernews_access.py) | kod | Hacker News özel erişim yolu |
| [`probe_site_access.py`](probe_site_access.py) | kod | Tek kaynak erişim yoklaması |
| [`resolve_missing_domains.py`](resolve_missing_domains.py) | kod | Bulunamayan adresleri çözer |
| [`secondary_index_pass.py`](secondary_index_pass.py) | kod | İkincil dizin geçişi |
| [`summarize_site_access.py`](summarize_site_access.py) | kod | Erişim sonuçlarını özetler |
| [`survey_common_crawl.py`](survey_common_crawl.py) | kod | Arşivde ne var diye tarar |
| [`SITE-LISTESI.md`](SITE-LISTESI.md) | girdi | Başlangıç site listesi — her şeyin kaynağı |
| [`manifest-arsiv-retry-kalan.json`](manifest-arsiv-retry-kalan.json) | girdi | Yeniden denemeden sonra kalanlar |
| [`manifest-arsiv-retry.json`](manifest-arsiv-retry.json) | girdi | Arşivden yeniden denenecek kaynaklar |

### Görev 1 — Ürün kategorilerini belirlemek

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`URUN-KATEGORILERI.md`](URUN-KATEGORILERI.md) | belge | Kategorilerin neden böyle ayrıldığı |
| [`KATEGORI-KAYNAK.csv`](KATEGORI-KAYNAK.csv) | çıktı | 658 satır: hangi kategori hangi kaynak ailesine bağlı |
| [`URUN-KATEGORILERI.csv`](URUN-KATEGORILERI.csv) | çıktı | 15 ürün kategorisi ve katmanlanma kuralları |
| [`build_product_categories.py`](build_product_categories.py) | kod | İki CSV'yi envanterden üretir |

### Görev 2 — Soruları ve kanıtlarını tanımlamak

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`KATEGORI-SORU.csv`](KATEGORI-SORU.csv) | çıktı | 198 satır: her kategori için araştırma sorusu ve gereken kanıt |
| [`build_category_questions.py`](build_category_questions.py) | kod | Soru–kanıt eşlemesini üretir |

### Görev 3 — Defteri aday kataloğa dönüştürmek

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`ADAY-KATALOG.csv`](ADAY-KATALOG.csv) | çıktı | 636 kaynağın aday kataloğu — erişim defterinden türer |
| [`build_candidate_catalog.py`](build_candidate_catalog.py) | kod | Defteri kataloğa çevirir |

### Görev 4 — Hangi alan, hangi izinli yol

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`KAYNAK-ALAN.csv`](KAYNAK-ALAN.csv) | çıktı | 3218 satır: hangi kaynaktan hangi alan, hangi izinli yolla alınır |
| [`build_source_fields.py`](build_source_fields.py) | kod | Alan–izin matrisini üretir |

### Görev 5 — Fikirden kaynak paketine

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`SECIM-ORNEKLERI.csv`](SECIM-ORNEKLERI.csv) | çıktı | 73 satır: örnek ürün fikirlerinden seçilen kaynak paketleri |
| [`select_sources.py`](select_sources.py) | kod | Fikirden kaynak paketi seçer (deterministik) |
| [`terim_sozlugu.py`](terim_sozlugu.py) | kod | Türkçe terimleri hedef pazarın diline çevirir |
| [`TERIM-ONBELLEGI.json`](TERIM-ONBELLEGI.json) | girdi | Çeviri önbelleği — depoya işlenir, aynı sonuç tekrarlanır |

### Görev 6 — Sorguları derlenebilir şablonlara çevirmek

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`DERLENMIS-SORGULAR-US.csv`](DERLENMIS-SORGULAR-US.csv) | çıktı | Aynı tasarımın US pazarı karşılığı |
| [`DERLENMIS-SORGULAR.csv`](DERLENMIS-SORGULAR.csv) | çıktı | 73 derlenmiş sorgu (TR pazarı) |
| [`compile_queries.py`](compile_queries.py) | kod | Şablonları çalıştırılabilir sorgulara derler |
| [`query_templates.py`](query_templates.py) | kod | Sorgu şablonlarının tanımı |

### Görev 7 — Aynı tasarımı iki bütçe seviyesinde

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`BUTCE-KARSILASTIRMA.csv`](BUTCE-KARSILASTIRMA.csv) | çıktı | Ücretsiz ve premium profillerin farkı — 6 satır |
| [`butce_profilleri.py`](butce_profilleri.py) | kod | İki bütçe profilini tanımlar ve karşılaştırır |

### Görev 8 — Tasarımı kontrollü bir deneyle sınamak

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`DENEY-KAYNAK.csv`](DENEY-KAYNAK.csv) | çıktı | Deneyde seçilen 64 kaynak |
| [`DENEY-VERI.csv`](DENEY-VERI.csv) | çıktı | Deneyde gerçekten çekilen 14 veri satırı |
| [`deney.py`](deney.py) | kod | Ön kayıtlı ölçütlerle kontrollü deney |

### Görev 9 — Kategori sözlüğü (veri çalışması Gün 2)

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`INCELEME-GUNLUGU.md`](INCELEME-GUNLUGU.md) | belge | Hangi dosya açıldı, ne görüldü |
| [`KATEGORI-SOZLUGU.md`](KATEGORI-SOZLUGU.md) | belge | Dört eksenli kategori sözlüğü — etiketlerin tanımı |
| [`PILOT-EKSIKLER.csv`](PILOT-EKSIKLER.csv) | çıktı | Sözlüğün karar veremediği 3 kayıt |
| [`PILOT-KAYITLAR.csv`](PILOT-KAYITLAR.csv) | çıktı | 97 açılmış artefaktın etiketleri |
| [`kategori_sozlugu.py`](kategori_sozlugu.py) | kod | Sözlüğü ve pilot çıktıları üretir |

### Görev 10 — Veri envanteri (veri çalışması Gün 1)

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`GUN2-ORNEKLEM-PLANI.md`](GUN2-ORNEKLEM-PLANI.md) | belge | Gün 2'de ne açılacak, ne neden açılmayacak |
| [`KAPSAMA-RAPORU.md`](KAPSAMA-RAPORU.md) | belge | Erişim × içerik çapraz tablosu |
| [`ENVANTER-ISLENEMEYEN.csv`](ENVANTER-ISLENEMEYEN.csv) | çıktı | 754 işlenemeyen artefakt kaydı ve sebebi |
| [`VERI-ENVANTERI.csv`](VERI-ENVANTERI.csv) | çıktı | 636 kaynak: erişim durumu **ve** içerik durumu ayrı sütunlarda |
| [`veri_envanteri.py`](veri_envanteri.py) | kod | Envanteri ve raporları üretir |

### Görev 11 — Normalize veri kümesi (veri çalışması Gün 3)

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`DONUSUM-KURALLARI.md`](DONUSUM-KURALLARI.md) | belge | Dönüşümün on adımı, ölçülmüş sayılarıyla |
| [`VERI-SOZLUGU.md`](VERI-SOZLUGU.md) | belge | Her sütunun anlamı + bu verinin **cevaplayamadığı** sorular |
| [`BELGE-ILISKILERI.csv`](BELGE-ILISKILERI.csv) | çıktı | 98 tekrar ilişkisi — tekrarlar silinmez, ilişkilendirilir |
| [`ISLENEMEYEN-BELGELER.csv`](ISLENEMEYEN-BELGELER.csv) | çıktı | 754 işlenemeyen kayıt ve sebebi |
| [`KATEGORI-ALANLARI.csv`](KATEGORI-ALANLARI.csv) | çıktı | 139 çıkarılan alan; `olcum` / `etiket` ayrımıyla |
| [`NORMALIZE-BELGELER.csv`](NORMALIZE-BELGELER.csv) | çıktı | 591 belge — teknik normalizasyon (Faz 4 şeması) |
| [`SINIFLANDIRMA.csv`](SINIFLANDIRMA.csv) | çıktı | 591 satır — yorumlayıcı sınıflandırma, teknikten **ayrı** tutulur |
| [`normalize_belgeler.py`](normalize_belgeler.py) | kod | Ham artefaktları normalize veri kümesine çevirir |

### Görev 12 — İç sayfa toplama

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`EK-ARTEFAKT-DIZINI.csv`](EK-ARTEFAKT-DIZINI.csv) | çıktı | İç sayfa geçişinin artefakt dizini; ana dizin ayrı bir scriptin çıktısı olduğu için genişletilmez |
| [`IC-SAYFA-ADAYLARI.csv`](IC-SAYFA-ADAYLARI.csv) | çıktı | Kaynak × niyet bazında aday iç sayfa sayıları |
| [`IC-SAYFA-HEDEFLERI.csv`](IC-SAYFA-HEDEFLERI.csv) | çıktı | Çekim için seçilen hedefler (ağsız koşunun çıktısı) |
| [`IC-SAYFA-SONUCLARI.csv`](IC-SAYFA-SONUCLARI.csv) | çıktı | Pilot koşunun sonuçları |
| [`ic_sayfa_gecisi.py`](ic_sayfa_gecisi.py) | kod | Sitemap ve ana sayfa bağlantılarından iç sayfa çeker; her aday bir arama niyetine bağlanır |

### Görev 13 — SourceFitMatrix v1

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`SOURCEFIT-SEMA.md`](SOURCEFIT-SEMA.md) | belge | **Alan sözleşmesi.** Matrisin her sütununun anlamı, yedi niyet ve üç sayım kuralı |
| [`KATEGORI-YETERLILIK.csv`](KATEGORI-YETERLILIK.csv) | çıktı | 112 hücrenin yeterlilik durumu ve boş olanların **sebep kodu** |
| [`PAKET-ONERILERI.csv`](PAKET-ONERILERI.csv) | çıktı | Kategori başına Standard/Deep aday paketi ve gerekçesi |
| [`SOURCE-FIT-MATRIX.csv`](SOURCE-FIT-MATRIX.csv) | çıktı | Kategori × niyet × kaynak eşleşmeleri; her satır açılmış bir belgeye dayanır |
| [`source_fit_matrix.py`](source_fit_matrix.py) | kod | Matrisi, yeterlilik tablosunu, paketleri ve şemayı üretir |

### Görev 14 — Denetim ve sürümlü teslim paketi (veri çalışması Gün 5)

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`DEVIR-NOTU.md`](DEVIR-NOTU.md) | belge | **Devir notu.** Paket içeriği, bağlantı anahtarları, neye güvenilmemeli |
| [`KALITE-RAPORU.md`](KALITE-RAPORU.md) | belge | Denetim sonucu, kategori metrikleri, geçersiz proxy çıkarımları, kalan iş |
| [`DENETIM-BULGULARI.csv`](DENETIM-BULGULARI.csv) | çıktı | Açık bulgular: yanlış etiket, eksik provenance, konu dışı, mükerrer |
| [`DENETIM-ORNEKLERI.csv`](DENETIM-ORNEKLERI.csv) | çıktı | Her kategoriden incelenen örnek kayıtlar (deterministik seçim) |
| [`KALAN-IS.csv`](KALAN-IS.csv) | çıktı | Önceliklendirilmiş kalan iş; çözülebilir ve çözülemez ayrı işaretli |
| [`KALITE-METRIKLERI.csv`](KALITE-METRIKLERI.csv) | çıktı | Kategori bazında kaynak/kayıt, alan doluluğu, tekrar oranı, işlenemeyen |
| [`VERI-PAKETI-ORNEKLERI.csv`](VERI-PAKETI-ORNEKLERI.csv) | çıktı | Hangi ürün tipi hangi soruyu hangi gerçek kayıtla cevaplıyor |
| [`denetim.py`](denetim.py) | kod | Sözlük, veri seti ve eşleme tablosunu birlikte denetler; raporları üretir |

### AS-01 — Batuhan'ın F01–F10 denemeleri için kaynak yeteneği ve erişim sınırları

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`AS01-ALTERNATIF-RAPOR.md`](AS01-ALTERNATIF-RAPOR.md) | belge | Kapalı kaynaklara izinli alternatif; F02 ve F09 için bulunanlar |
| [`AS01-ERISIM-SINIRLARI.md`](AS01-ERISIM-SINIRLARI.md) | belge | **Batuhan için.** Bugün ölçülmüş erişim/içerik/artefakt durumu ve alan örnekleri |
| [`AS01-ALAN-ORNEKLERI.csv`](AS01-ALAN-ORNEKLERI.csv) | çıktı | Her çalışan kaynaktan gerçek alan örneği; bulunmayan alan boş |
| [`AS01-ALTERNATIF-KAYNAK.csv`](AS01-ALTERNATIF-KAYNAK.csv) | çıktı | Denenen adaylar: erişim, içerik ve **ilgililik** ayrı sınanır |
| [`AS01-GERI-BILDIRIM.csv`](AS01-GERI-BILDIRIM.csv) | çıktı | İçerik vermeyen kaynaklar için açık geri bildirim kayıtları |
| [`AS01-IDDIA-DOGRULAMA.csv`](AS01-IDDIA-DOGRULAMA.csv) | çıktı | KAYNAK-ALAN.csv'nin 100 alan iddiasının bugünkü yanıtla sınanması |
| [`AS01-KAYNAK-KONTROL.csv`](AS01-KAYNAK-KONTROL.csv) | çıktı | F01–F10 × kaynak: kayıtlı durum ve bugünkü yoklama yan yana |
| [`alternatif_kaynak.py`](alternatif_kaynak.py) | kod | Alternatif arar; HTTP 200'ü ilgili içerik saymaz |
| [`as01_kaynak_kontrol.py`](as01_kaynak_kontrol.py) | kod | Kaynakları bugün yeniden yoklar, kanıt artefaktını depoya yazar |

### AS-06 — Çözüm günlüğü ve kaynak sağlık kayıtları

| Dosya | Rol | Ne olduğu |
|---|---|---|
| [`COZUM-GUNLUGU.md`](COZUM-GUNLUGU.md) | belge | **Başarı raporu değildir.** Denenen yollar, öncesi/sonrası ve çözülemeyen sınırlar |
| [`COZUM-GUNLUGU.csv`](COZUM-GUNLUGU.csv) | çıktı | 11 bulgu: ne denendi, tarih, script, önce/sonra, sınır, FB-ID, komut |
| [`KAYNAK-SAGLIK.csv`](KAYNAK-SAGLIK.csv) | çıktı | 19 kaynağın sağlığı; çalışan ve çalışmayan **birlikte** tutulur |
| [`cozum_gunlugu.py`](cozum_gunlugu.py) | kod | Günlüğü tutar, sağlık kayıtlarını ölçer |

<details>
<summary><b>Alfabetik dizin</b> — GitHub'ın gösterdiği sırayla, dosyadan göreve</summary>

| Dosya | Görev | Ne olduğu |
|---|---|---|
| [`.gitignore`](.gitignore) | Ortak | İndirilen 721 MB ham artefaktı depo dışında tutar |
| [`ADAY-KATALOG.csv`](ADAY-KATALOG.csv) | Görev 3 | 636 kaynağın aday kataloğu — erişim defterinden türer |
| [`ARAMA-YUZEYLERI.csv`](ARAMA-YUZEYLERI.csv) | Erişim laboratuvarı | Her kaynağın izinli arama yüzeyleri |
| [`ARTEFAKT-DIZINI.csv`](ARTEFAKT-DIZINI.csv) | Erişim laboratuvarı | Hangi kaynak hangi dosyaya karşılık geliyor — izlenebilirliğin temeli |
| [`AS01-ALAN-ORNEKLERI.csv`](AS01-ALAN-ORNEKLERI.csv) | AS-01 | Her çalışan kaynaktan gerçek alan örneği; bulunmayan alan boş |
| [`AS01-ALTERNATIF-KAYNAK.csv`](AS01-ALTERNATIF-KAYNAK.csv) | AS-01 | Denenen adaylar: erişim, içerik ve **ilgililik** ayrı sınanır |
| [`AS01-ALTERNATIF-RAPOR.md`](AS01-ALTERNATIF-RAPOR.md) | AS-01 | Kapalı kaynaklara izinli alternatif; F02 ve F09 için bulunanlar |
| [`AS01-ERISIM-SINIRLARI.md`](AS01-ERISIM-SINIRLARI.md) | AS-01 | **Batuhan için.** Bugün ölçülmüş erişim/içerik/artefakt durumu ve alan örnekleri |
| [`AS01-GERI-BILDIRIM.csv`](AS01-GERI-BILDIRIM.csv) | AS-01 | İçerik vermeyen kaynaklar için açık geri bildirim kayıtları |
| [`AS01-IDDIA-DOGRULAMA.csv`](AS01-IDDIA-DOGRULAMA.csv) | AS-01 | KAYNAK-ALAN.csv'nin 100 alan iddiasının bugünkü yanıtla sınanması |
| [`AS01-KAYNAK-KONTROL.csv`](AS01-KAYNAK-KONTROL.csv) | AS-01 | F01–F10 × kaynak: kayıtlı durum ve bugünkü yoklama yan yana |
| [`BELGE-ILISKILERI.csv`](BELGE-ILISKILERI.csv) | Görev 11 | 98 tekrar ilişkisi — tekrarlar silinmez, ilişkilendirilir |
| [`BUTCE-KARSILASTIRMA.csv`](BUTCE-KARSILASTIRMA.csv) | Görev 7 | Ücretsiz ve premium profillerin farkı — 6 satır |
| [`COZUM-GUNLUGU.csv`](COZUM-GUNLUGU.csv) | AS-06 | 11 bulgu: ne denendi, tarih, script, önce/sonra, sınır, FB-ID, komut |
| [`COZUM-GUNLUGU.md`](COZUM-GUNLUGU.md) | AS-06 | **Başarı raporu değildir.** Denenen yollar, öncesi/sonrası ve çözülemeyen sınırlar |
| [`DENETIM-BULGULARI.csv`](DENETIM-BULGULARI.csv) | Görev 14 | Açık bulgular: yanlış etiket, eksik provenance, konu dışı, mükerrer |
| [`DENETIM-ORNEKLERI.csv`](DENETIM-ORNEKLERI.csv) | Görev 14 | Her kategoriden incelenen örnek kayıtlar (deterministik seçim) |
| [`DENEY-KAYNAK.csv`](DENEY-KAYNAK.csv) | Görev 8 | Deneyde seçilen 64 kaynak |
| [`DENEY-VERI.csv`](DENEY-VERI.csv) | Görev 8 | Deneyde gerçekten çekilen 14 veri satırı |
| [`DERLENMIS-SORGULAR-US.csv`](DERLENMIS-SORGULAR-US.csv) | Görev 6 | Aynı tasarımın US pazarı karşılığı |
| [`DERLENMIS-SORGULAR.csv`](DERLENMIS-SORGULAR.csv) | Görev 6 | 73 derlenmiş sorgu (TR pazarı) |
| [`DEVIR-NOTU.md`](DEVIR-NOTU.md) | Görev 14 | **Devir notu.** Paket içeriği, bağlantı anahtarları, neye güvenilmemeli |
| [`DONUSUM-KURALLARI.md`](DONUSUM-KURALLARI.md) | Görev 11 | Dönüşümün on adımı, ölçülmüş sayılarıyla |
| [`EK-ARTEFAKT-DIZINI.csv`](EK-ARTEFAKT-DIZINI.csv) | Görev 12 | İç sayfa geçişinin artefakt dizini; ana dizin ayrı bir scriptin çıktısı olduğu için genişletilmez |
| [`ENVANTER-ISLENEMEYEN.csv`](ENVANTER-ISLENEMEYEN.csv) | Görev 10 | 754 işlenemeyen artefakt kaydı ve sebebi |
| [`GUN2-ORNEKLEM-PLANI.md`](GUN2-ORNEKLEM-PLANI.md) | Görev 10 | Gün 2'de ne açılacak, ne neden açılmayacak |
| [`IC-SAYFA-ADAYLARI.csv`](IC-SAYFA-ADAYLARI.csv) | Görev 12 | Kaynak × niyet bazında aday iç sayfa sayıları |
| [`IC-SAYFA-HEDEFLERI.csv`](IC-SAYFA-HEDEFLERI.csv) | Görev 12 | Çekim için seçilen hedefler (ağsız koşunun çıktısı) |
| [`IC-SAYFA-SONUCLARI.csv`](IC-SAYFA-SONUCLARI.csv) | Görev 12 | Pilot koşunun sonuçları |
| [`INCELEME-GUNLUGU.md`](INCELEME-GUNLUGU.md) | Görev 9 | Hangi dosya açıldı, ne görüldü |
| [`ISLENEMEYEN-BELGELER.csv`](ISLENEMEYEN-BELGELER.csv) | Görev 11 | 754 işlenemeyen kayıt ve sebebi |
| [`KALAN-IS.csv`](KALAN-IS.csv) | Görev 14 | Önceliklendirilmiş kalan iş; çözülebilir ve çözülemez ayrı işaretli |
| [`KALITE-METRIKLERI.csv`](KALITE-METRIKLERI.csv) | Görev 14 | Kategori bazında kaynak/kayıt, alan doluluğu, tekrar oranı, işlenemeyen |
| [`KALITE-RAPORU.md`](KALITE-RAPORU.md) | Görev 14 | Denetim sonucu, kategori metrikleri, geçersiz proxy çıkarımları, kalan iş |
| [`KAPSAMA-RAPORU.md`](KAPSAMA-RAPORU.md) | Görev 10 | Erişim × içerik çapraz tablosu |
| [`KATEGORI-ALANLARI.csv`](KATEGORI-ALANLARI.csv) | Görev 11 | 139 çıkarılan alan; `olcum` / `etiket` ayrımıyla |
| [`KATEGORI-KAYNAK.csv`](KATEGORI-KAYNAK.csv) | Görev 1 | 658 satır: hangi kategori hangi kaynak ailesine bağlı |
| [`KATEGORI-SORU.csv`](KATEGORI-SORU.csv) | Görev 2 | 198 satır: her kategori için araştırma sorusu ve gereken kanıt |
| [`KATEGORI-SOZLUGU.md`](KATEGORI-SOZLUGU.md) | Görev 9 | Dört eksenli kategori sözlüğü — etiketlerin tanımı |
| [`KATEGORI-YETERLILIK.csv`](KATEGORI-YETERLILIK.csv) | Görev 13 | 112 hücrenin yeterlilik durumu ve boş olanların **sebep kodu** |
| [`KAYNAK-ALAN.csv`](KAYNAK-ALAN.csv) | Görev 4 | 3218 satır: hangi kaynaktan hangi alan, hangi izinli yolla alınır |
| [`KAYNAK-DEFTERI.csv`](KAYNAK-DEFTERI.csv) | Erişim laboratuvarı | 636 kaynağın erişim defteri (çekildi / kısmi / erişim yok) |
| [`KAYNAK-DEFTERI.md`](KAYNAK-DEFTERI.md) | Erişim laboratuvarı | Defterin okunabilir özeti |
| [`KAYNAK-SAGLIK.csv`](KAYNAK-SAGLIK.csv) | AS-06 | 19 kaynağın sağlığı; çalışan ve çalışmayan **birlikte** tutulur |
| [`KILAVUZ.md`](KILAVUZ.md) | Ortak | **Başlangıç noktası.** On dört görevin tamamını sırayla anlatır |
| [`NORMALIZE-BELGELER.csv`](NORMALIZE-BELGELER.csv) | Görev 11 | 591 belge — teknik normalizasyon (Faz 4 şeması) |
| [`OPENSEARCH-SABLONLARI.csv`](OPENSEARCH-SABLONLARI.csv) | Erişim laboratuvarı | Sitelerin kendi ilan ettiği arama şablonları |
| [`PAKET-ONERILERI.csv`](PAKET-ONERILERI.csv) | Görev 13 | Kategori başına Standard/Deep aday paketi ve gerekçesi |
| [`PILOT-EKSIKLER.csv`](PILOT-EKSIKLER.csv) | Görev 9 | Sözlüğün karar veremediği 3 kayıt |
| [`PILOT-KAYITLAR.csv`](PILOT-KAYITLAR.csv) | Görev 9 | 97 açılmış artefaktın etiketleri |
| [`README.md`](README.md) | Ortak | Bu dosya — klasörün haritası |
| [`SECIM-ORNEKLERI.csv`](SECIM-ORNEKLERI.csv) | Görev 5 | 73 satır: örnek ürün fikirlerinden seçilen kaynak paketleri |
| [`SINIFLANDIRMA.csv`](SINIFLANDIRMA.csv) | Görev 11 | 591 satır — yorumlayıcı sınıflandırma, teknikten **ayrı** tutulur |
| [`SITE-LISTESI.md`](SITE-LISTESI.md) | Erişim laboratuvarı | Başlangıç site listesi — her şeyin kaynağı |
| [`SOURCE-FIT-MATRIX.csv`](SOURCE-FIT-MATRIX.csv) | Görev 13 | Kategori × niyet × kaynak eşleşmeleri; her satır açılmış bir belgeye dayanır |
| [`SOURCEFIT-SEMA.md`](SOURCEFIT-SEMA.md) | Görev 13 | **Alan sözleşmesi.** Matrisin her sütununun anlamı, yedi niyet ve üç sayım kuralı |
| [`TERIM-ONBELLEGI.json`](TERIM-ONBELLEGI.json) | Görev 5 | Çeviri önbelleği — depoya işlenir, aynı sonuç tekrarlanır |
| [`URUN-KATEGORILERI.csv`](URUN-KATEGORILERI.csv) | Görev 1 | 15 ürün kategorisi ve katmanlanma kuralları |
| [`URUN-KATEGORILERI.md`](URUN-KATEGORILERI.md) | Görev 1 | Kategorilerin neden böyle ayrıldığı |
| [`VERI-ENVANTERI.csv`](VERI-ENVANTERI.csv) | Görev 10 | 636 kaynak: erişim durumu **ve** içerik durumu ayrı sütunlarda |
| [`VERI-PAKETI-ORNEKLERI.csv`](VERI-PAKETI-ORNEKLERI.csv) | Görev 14 | Hangi ürün tipi hangi soruyu hangi gerçek kayıtla cevaplıyor |
| [`VERI-SOZLUGU.md`](VERI-SOZLUGU.md) | Görev 11 | Her sütunun anlamı + bu verinin **cevaplayamadığı** sorular |
| [`adaptive_domain_pass.py`](adaptive_domain_pass.py) | Erişim laboratuvarı | Alan adı çözümleme geçişi |
| [`alternatif_kaynak.py`](alternatif_kaynak.py) | AS-01 | Alternatif arar; HTTP 200'ü ilgili içerik saymaz |
| [`as01_kaynak_kontrol.py`](as01_kaynak_kontrol.py) | AS-01 | Kaynakları bugün yeniden yoklar, kanıt artefaktını depoya yazar |
| [`build_artifact_index.py`](build_artifact_index.py) | Erişim laboratuvarı | Artefakt dizinini üretir |
| [`build_candidate_catalog.py`](build_candidate_catalog.py) | Görev 3 | Defteri kataloğa çevirir |
| [`build_category_questions.py`](build_category_questions.py) | Görev 2 | Soru–kanıt eşlemesini üretir |
| [`build_coverage_ledger.py`](build_coverage_ledger.py) | Erişim laboratuvarı | Erişim defterini üretir |
| [`build_product_categories.py`](build_product_categories.py) | Görev 1 | İki CSV'yi envanterden üretir |
| [`build_search_surfaces.py`](build_search_surfaces.py) | Erişim laboratuvarı | Arama yüzeylerini üretir |
| [`build_source_fields.py`](build_source_fields.py) | Görev 4 | Alan–izin matrisini üretir |
| [`bulk_site_access_lab.py`](bulk_site_access_lab.py) | Erişim laboratuvarı | Toplu erişim denemesi |
| [`butce_profilleri.py`](butce_profilleri.py) | Görev 7 | İki bütçe profilini tanımlar ve karşılaştırır |
| [`common_crawl_pass.py`](common_crawl_pass.py) | Erişim laboratuvarı | Common Crawl arşiv geçişi |
| [`compile_queries.py`](compile_queries.py) | Görev 6 | Şablonları çalıştırılabilir sorgulara derler |
| [`cozum_gunlugu.py`](cozum_gunlugu.py) | AS-06 | Günlüğü tutar, sağlık kayıtlarını ölçer |
| [`denetim.py`](denetim.py) | Görev 14 | Sözlük, veri seti ve eşleme tablosunu birlikte denetler; raporları üretir |
| [`deney.py`](deney.py) | Görev 8 | Ön kayıtlı ölçütlerle kontrollü deney |
| [`dosya_haritasi.py`](dosya_haritasi.py) | Ortak | README'deki bu haritayı üretir |
| [`export_by_source.py`](export_by_source.py) | Erişim laboratuvarı | Kaynak bazında dışa aktarım |
| [`fetch_opensearch_templates.py`](fetch_opensearch_templates.py) | Erişim laboratuvarı | OpenSearch şablonlarını toplar |
| [`ic_sayfa_gecisi.py`](ic_sayfa_gecisi.py) | Görev 12 | Sitemap ve ana sayfa bağlantılarından iç sayfa çeker; her aday bir arama niyetine bağlanır |
| [`kategori_sozlugu.py`](kategori_sozlugu.py) | Görev 9 | Sözlüğü ve pilot çıktıları üretir |
| [`keyword_search_pass.py`](keyword_search_pass.py) | Erişim laboratuvarı | Anahtar kelime arama geçişi |
| [`manifest-arsiv-retry-kalan.json`](manifest-arsiv-retry-kalan.json) | Erişim laboratuvarı | Yeniden denemeden sonra kalanlar |
| [`manifest-arsiv-retry.json`](manifest-arsiv-retry.json) | Erişim laboratuvarı | Arşivden yeniden denenecek kaynaklar |
| [`merge_resolved_domains.py`](merge_resolved_domains.py) | Erişim laboratuvarı | Çözülen adresleri deftere işler |
| [`normalize_belgeler.py`](normalize_belgeler.py) | Görev 11 | Ham artefaktları normalize veri kümesine çevirir |
| [`probe_hackernews_access.py`](probe_hackernews_access.py) | Erişim laboratuvarı | Hacker News özel erişim yolu |
| [`probe_site_access.py`](probe_site_access.py) | Erişim laboratuvarı | Tek kaynak erişim yoklaması |
| [`query_templates.py`](query_templates.py) | Görev 6 | Sorgu şablonlarının tanımı |
| [`resolve_missing_domains.py`](resolve_missing_domains.py) | Erişim laboratuvarı | Bulunamayan adresleri çözer |
| [`secondary_index_pass.py`](secondary_index_pass.py) | Erişim laboratuvarı | İkincil dizin geçişi |
| [`select_sources.py`](select_sources.py) | Görev 5 | Fikirden kaynak paketi seçer (deterministik) |
| [`source_fit_matrix.py`](source_fit_matrix.py) | Görev 13 | Matrisi, yeterlilik tablosunu, paketleri ve şemayı üretir |
| [`source_manifest.json`](source_manifest.json) | Ortak | 636 kaynağın kanonik kimlik ve adres listesi |
| [`summarize_site_access.py`](summarize_site_access.py) | Erişim laboratuvarı | Erişim sonuçlarını özetler |
| [`survey_common_crawl.py`](survey_common_crawl.py) | Erişim laboratuvarı | Arşivde ne var diye tarar |
| [`terim_sozlugu.py`](terim_sozlugu.py) | Görev 5 | Türkçe terimleri hedef pazarın diline çevirir |
| [`veri_envanteri.py`](veri_envanteri.py) | Görev 10 | Envanteri ve raporları üretir |

</details>
<!-- HARITA:BITIS -->

## Güncel durum

| | Kaynak |
|---|---:|
| ✅ Verisi çekildi | **534** |
| ❌ Adresi var ama veri alınamadı | 98 |
| ❌ Adresi bulunamadı | 4 |
| **Toplam** | **636** |

Veri alınamayan 98 kaynağın 35'i `robots_disallowed` — site taranmasını istemiyor
ve buna uyuluyor. Bunlar kapsam dışı sayılırsa oran **534/601 = %88.9**.

Defter bu üç durumun yanında bir ayrım daha tutar: veri alınamayanların bir
kısmında sunucuya ulaşılıp yalnızca `robots.txt` indirilebilmiş (`kismi`), bir
kısmında hiçbir dosya alınamamış (`erisim_yok`). Kullanılabilir veri ikisinde de
yok; ayrım engelin nerede olduğunu gösterir.

## Dizin haritası

| Konum | Amaç |
|---|---|
| `source_manifest.json`, `SITE-LISTESI.md` | Aday kaynak kataloğu ve resmî origin çözümlemesi |
| `KAYNAK-DEFTERI.*`, `ARTEFAKT-DIZINI.csv`, `ARAMA-YUZEYLERI.csv` | Kanonik erişim, artefact provenance ve arama-yüzeyi indeksleri |
| `results/` | Koşu sonuçları ve içerik-adresli ham artefact'lar; [açıklama](results/README.md) |
| `veriler-ornek/` | İncelenebilir, hash'li örnek içerik alt kümesi |
| [`trash/eski-raporlar/`](../../trash/eski-raporlar/) | Tarihli erişim raporları ve yeniden üretilebilir rapor çıktıları |
| `docs/pilots/` | Dar kapsamlı DuckDuckGo ve Hacker News pilot sözleşmeleri |
| `*.py`, `test_*.py` | Acquisition araçları ve offline testler |

Tarihli raporlar yalnız o koşunun gözlemidir. Güncel durum için önce kanonik
indeksleri ve ilgili koşu artefact'ını kullanın.

## Görev 1 — hangi kaynaklar tamamlandı

| Dosya | İçerik |
|---|---|
| `KAYNAK-DEFTERI.md` | Özet tablo + 636 satırlık liste |
| `KAYNAK-DEFTERI.csv` | Aynı veri, filtrelenebilir |
| `build_coverage_ledger.py` | Defteri koşu artefaktlarından üretir |

Her satırda: kaynağın adresi, adresin nasıl doğrulandığı, güven seviyesi, çekilen
yüzeyler (`root_html`, `sitemap_xml`, `rss_feed`, `entry_url`, API) ve
çekilemediyse teknik sebebi.

```bash
python3 build_coverage_ledger.py results/bulk-site-access-*.json results/common-crawl-*.json
```

## Görev 2 — eksik kaynakların verisini çekme

| Dosya | Rolü |
|---|---|
| `source_manifest.json` | 631 adres, `entry_path`'ler, anahtarsız API uçları |
| `bulk_site_access_lab.py` | Çekim motoru: robots kontrolü, çıkış güvenliği, istek bütçesi |
| `adaptive_domain_pass.py` | Wikidata P856 ile adres çözümleme |
| `resolve_missing_domains.py` / `merge_resolved_domains.py` | Çözümleme turu ve manifeste işleme |
| `secondary_index_pass.py` | Wikipedia dış bağlantıları, kendi arşivimiz, GitHub homepage |
| `common_crawl_pass.py` / `survey_common_crawl.py` | Bize kapalı sitelerin içeriğini Common Crawl arşivinden alma |
| `ARTEFAKT-DIZINI.csv` | **Hangi dosya, hangi kaynağın hangi adresinden, ne zaman alındı** |
| `build_artifact_index.py` / `export_by_source.py` | Dizin ve okunabilir klasör üretimi |

### Ham içerik nasıl saklanıyor

Ham içerik `results/raw/<sha256>.bin` olarak saklanır: ad içeriğin özetidir, bu
sayede aynı içerik iki kez inmez ve bozulma tespit edilir. 16 KB altındaki
dosyalar ayrı dosya açılmadan koşu JSON'unun içinde base64 durur.

Ad siteyi göstermediği için tek başına okunamaz; **`ARTEFAKT-DIZINI.csv` o bağı
kurar.** Her satır bir indirilen dosyanın künyesidir:

| Sütun | Örnek |
|---|---|
| `ad`, `adres` | Forbes, `https://forbes.com` |
| `yontem` | `sitemap_xml` |
| `cekilen_url` | `https://www.forbes.com/news_sitemap.xml` |
| `mime`, `bayt` | `application/xml`, 476.781 |
| `sha256`, `dosya` | `abb98e90...`, `results/raw/abb98e90....bin` |
| `sonuc` | `ok` — başarılı içerik |
| `kosu`, `tarih` | Hangi koşuda, ne zaman |

`sonuc` sütunu önemli: arşivde yalnızca başarılı içerik yok. Başarısız isteklerin
gövdesi de diske yazılmış olabilir (kısmen inen `response_too_large` yanıtı, bot
koruma sayfası). Bunlar da dizine alınır ama `sonuc` alanı onları `ok` olanlardan
ayırır — aksi hâlde arşivde kime ait olduğu okunamayan dosyalar kalırdı.

`export_by_source.py` aynı veriyi site adıyla düzenlenmiş `veriler/<Kaynak>/`
klasörlerine çıkarır; her klasörde `_kaynak.json` kaynağın adını, adresini,
durumunu ve her dosyanın hangi URL'den ne zaman alındığını taşır.

### İçeriği görmek isteyenler için

Koşu JSON'ları ve bu checkout'a dahil edilmiş ham artefact'lar `results/` altında
tutulur. Bir yayındaki tam corpus'un mevcut olduğu varsayılmaz: kullanılabilir
artefact, hash ve koşu bağını daima `ARTEFAKT-DIZINI.csv` ile doğrulayın. Verinin
okunabilir örneklerini görmek için **`veriler-ornek/`** klasörü tutulur: 252
kaynaktan seçilmiş gerçek içerik alt kümesi.

Seçim rastgele değil kurallıdır — yalnızca içerik yüzeyleri (robots.txt hariç),
başarılı istekler, dosya başına 90 KB ve toplam 5 MB sınırıyla:

```bash
python3 export_by_source.py --only-fetched --out veriler-ornek \
  --methods "root_html,entry_url,sitemap_xml,rss_feed,common_crawl_warc" \
  --max-file-bytes 90000 --max-total-bytes 5000000
```

Tam arşiv dışarıdan geri yüklenecek veya yeniden üretilecekse aynı komut sınır
olmadan çalıştırılır; sonuç her zaman yeni bir koşu, tarih ve hash manifestiyle
kaydedilmelidir.

## Görev 3 — anahtar kelime ile arama

Genel web araması ölçüldü ve kapalı çıktı: DuckDuckGo 12 sorgudan sonra kesiyor
(546 sorguda 534 `origin_circuit_open`), Mojeek ve Marginalia robots.txt'te
`/search` yolunu yasaklıyor, Brave API Şubat 2026'da ücretliye geçti.

Bunun yerine **her kaynağın kendi arama yüzeyi** kataloglandı.

| Dosya | İçerik |
|---|---|
| `ARAMA-YUZEYLERI.csv` | 578 kaynak için hangi yolla sorulacağı |
| `build_search_surfaces.py` | Kataloğu artefaktlardan üretir (ağ isteği yok) |
| `keyword_search_pass.py` | Kelimeyi alır, doğru yolu seçer, sorar, sonucu arşive yazar |

| Yol | Kaynak | Ne yapılır |
|---|---:|---|
| `opensearch` | 36 | Site arama şablonunu kendisi ilan ediyor |
| `site_search` | 84 | Sayfadan çıkarılan `?q=` kalıbı |
| `api` | 13 | Anahtarsız resmî API |
| `local_index` | 183 | Sitemap'ten toplanan 339.488 URL'de arama |
| `fulltext` | 217 | İndirilmiş sayfa metninde arama |
| `yok` | 45 | Hiçbir yüzey bulunamadı |

**636 kaynağın 533'üne** anahtar kelimeyle sorulabiliyor: 133'üne canlı sorgu,
400'üne kendi verimizde arama.

```bash
python3 build_search_surfaces.py                      # katalog + URL dizini
python3 keyword_search_pass.py "market intelligence"  # yalnızca yerel arama
python3 keyword_search_pass.py "market intelligence" --live --limit 40
```

Örnek: arXiv'in ana sayfasındaki `<form action="https://arxiv.org/search">`
formundan `arxiv.org/search?query={kelime}` kalıbı çıkarıldı. Katalog yolu
gösterir; çekim aşaması politikayı ayrıca kontrol eder — arXiv `/search` yolunu
robots.txt ile kapattığı için sorgu `robots_disallowed` ile durur. İkisi ayrı
bilgidir ve ayrı kaydedilir.

## Testler

```bash
python3 -m unittest discover -s . -p "test_*.py"
```

## Politika

- Her origin için `robots.txt` preflight yapılır; `robots.txt` yoksa (404/410)
  RFC 9309 gereği kısıtlama yok sayılır, 401/403 ise yasak sayılır.
- Bot koruması aşılmaz: User-Agent rotasyonu, CAPTCHA çözme ve tarayıcı taklidi
  yoktur. `robots_disallowed` kaynaklar hiç denenmez.
- Common Crawl da robots.txt'e uyduğu için arşiv yolu bu ayrımı korur; robots ile
  yasaklı kaynaklar arşivde de yoktur.
- Arşivden gelen içerik `common_crawl_warc` yöntemiyle işaretlenir, canlı veriyle
  karıştırılmaz.
