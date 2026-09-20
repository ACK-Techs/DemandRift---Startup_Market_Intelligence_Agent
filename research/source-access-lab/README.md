# Kaynak Erişim Laboratuvarı

**Sahip:** Ayselin Aydoğdu · **Görev:** [`tasks/ayselin-task/`](../../tasks/ayselin-task/)

Bu klasör üç ayrı çalışmayı barındırıyor. Üçü de aynı 636 kaynaklı envanteri
kullanıyor ama farklı soruları cevaplıyorlar.

| | Soru | Anlatı |
|---|---|---|
| **A. Erişim laboratuvarı** | Bu kaynaklara ulaşabiliyor muyuz, ne indi? | [Çalışmanın söyledikleri](#çalışmanın-söyledikleri) |
| **B. Araştırma tasarımı** | Bir ürün fikri geldiğinde hangi kaynağa ne sorulur? | [`KILAVUZ.md`](KILAVUZ.md) |
| **C. Veri çalışması** | Bu checkout'ta gerçekten ne var, nasıl normalize edildi? | [`KAPSAMA-RAPORU.md`](KAPSAMA-RAPORU.md) · [`VERI-SOZLUGU.md`](VERI-SOZLUGU.md) |

### Nereden başlamalı

1. **[`KILAVUZ.md`](KILAVUZ.md)** — on dört görevin tamamı sırayla. Her bölümde
   problem, izlenen yol, sonuç ve gerçek CSV satır örnekleri var.
2. **Aşağıdaki harita** — hangi dosyanın hangi görevin çıktısı olduğu.
3. Tek bir görevi incelemek için haritadan o görevin bloğuna bakın; çıktı
   dosyaları ve onları üreten script orada birlikte durur.

<!-- HARITA:BASLANGIC -->
## Hangi dosya hangi görev

Klasörde 110 dosya var ve GitHub bunları alfabetik sıralıyor.
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

<details>
<summary><b>Alfabetik dizin</b> — GitHub'ın gösterdiği sırayla, dosyadan göreve</summary>

| Dosya | Görev | Ne olduğu |
|---|---|---|
| [`.gitignore`](.gitignore) | Ortak | İndirilen 721 MB ham artefaktı depo dışında tutar |
| [`ADAY-KATALOG.csv`](ADAY-KATALOG.csv) | Görev 3 | 636 kaynağın aday kataloğu — erişim defterinden türer |
| [`ARAMA-YUZEYLERI.csv`](ARAMA-YUZEYLERI.csv) | Erişim laboratuvarı | Her kaynağın izinli arama yüzeyleri |
| [`ARTEFAKT-DIZINI.csv`](ARTEFAKT-DIZINI.csv) | Erişim laboratuvarı | Hangi kaynak hangi dosyaya karşılık geliyor — izlenebilirliğin temeli |
| [`BELGE-ILISKILERI.csv`](BELGE-ILISKILERI.csv) | Görev 11 | 98 tekrar ilişkisi — tekrarlar silinmez, ilişkilendirilir |
| [`BUTCE-KARSILASTIRMA.csv`](BUTCE-KARSILASTIRMA.csv) | Görev 7 | Ücretsiz ve premium profillerin farkı — 6 satır |
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

---

## Çalışmanın söyledikleri

Harita dosyaların nerede olduğunu söyler; bu bölüm ne bulduğumuzu.

### A — Erişim: `çekildi` bir snapshot'tır, kanıt değil

| | Kaynak |
|---|---:|
| Verisi çekildi | **534** |
| Kısmi | 44 |
| Adresi var, veri alınamadı | 54 |
| Adresi bulunamadı | 4 |
| **Toplam** | **636** |

`çekildi`, en az bir içerik yüzeyinin alındığını gösterir; tek başına araştırma
sorusuna uygun, güncel ya da alıntılanabilir karar kanıtı anlamına gelmez.

### B — Tasarım: fikirden sorguya kadar tek zincir

```text
ürün fikri → kategori → araştırma sorusu → gerekli kanıt → kaynak ailesi
          → kaynak yeteneği → veri alanı → sorgu şablonu → bütçe/fallback
```

Her çıktı bir script tarafından üretilir; **elle yazılmış sayı yoktur.**

### C — Veri: erişim etiketi ile elde olan aynı şey değil

534 kaynak `cekildi` diyor. Dosyalar açılınca:

| İçerik durumu | Kaynak | |
|---|---:|---|
| `gercek-icerik` | 305 | Görünür metin taşıyan sayfa |
| `dosya-yok` | 141 | Bu checkout'ta açılabilir dosya yok |
| `arsiv` | 81 | Common Crawl kopyası, canlı değil |
| `aday-kesif` | 42 | Sitemap — kanıt değil |
| `js-kabugu` | 38 | Büyük HTML ama görünür metin yok |
| `politika` | 12 | robots.txt |
| `api-yaniti` / `besleme` | 10 + 7 | Yapılandırılmış yanıt ve RSS |

İlk normalize koşusunda **591 belgenin 42'si** ölçüm kanıtı üretiyordu ve
kanıt üretmeyenlerin 350'si ana sayfaydı. Sebep engellenme değil, toplama
tasarımıydı: erişim laboratuvarı kaynak başına birkaç istek atıyordu, çünkü
cevapladığı soru "ulaşabiliyor muyuz" idi.

İç sayfa geçişi (Görev 12) bunu kapattı — aday adresler zaten diskte olan
sitemap ve ana sayfalardan okundu, yeni keşif isteği atılmadı:

| | Önce | Sonra |
|---|---:|---:|
| Normalize belge | 591 | **1249** |
| Ölçüm kanıtı üreten | 42 | **145** |
| Çıkarılan fiyat | 27 | **56** |

### D — Eşleşme: hangi kategori, hangi soru, hangi kaynak

[`SOURCE-FIT-MATRIX.csv`](SOURCE-FIT-MATRIX.csv) 395 eşleşme taşır ve her
satırı açılmış bir belgeye dayanır. 16 kategori × 7 arama niyeti = 112 hücre:

| Durum | Hücre |
|---|---:|
| Yeterli (2+ bağımsız grup) | 47 |
| Zayıf (tek grup) | 28 |
| Boş (gap) | 37 |

Boş hücrelerin hiçbiri "bu pazarda talep yok" demez; her biri bir **sebep
kodu** taşır: `yontem-disi` (16), `yuzey-bulunamadi` (21). Bir test, gap
açıklamalarının pazar sonucu iddia etmediğini doğruluyor.

Kural: **elde olmayan dosya incelenmiş gösterilmez.** Bir test, pilotta açılmış
her kaynağın envanterde gerçekten dosyası olduğunu doğruluyor.

---

## İndirilen ham içerik

`results/raw/` altında 2323 artefakt (721 MB) var ve `.gitignore` ile depo
dışında tutulur. Her artefakt sha256 ile adlandırılmıştır;
[`ARTEFAKT-DIZINI.csv`](ARTEFAKT-DIZINI.csv) hangi kaynağın hangi dosyaya
karşılık geldiğini gösterir, böylece her sayı izlenebilir kalır.
Ayrıntı: [`results/README.md`](results/README.md).

Raporlar [`docs/reports/`](docs/reports/), pilot çalışmalar
[`docs/pilots/`](docs/pilots/) altında.

---

## Testler

```bash
cd research/source-access-lab
python3 -m unittest discover -s . -p 'test_*.py'
```

541 test. Testler yalnız kodu değil, **kuralları** korur: robots yasaklı
kaynağın hiçbir profilde seçilmemesi, aday keşfin ölçüm kanıtı sayılmaması,
tarihi olmayan belgeye tarih yazılmaması, etkileşim sayısının talep kanıtı
diye etiketlenmemesi ve yukarıdaki haritada sahipsiz dosya kalmaması gibi.

## Politika

Bu çalışma boyunca değişmeyen kurallar:

- **Bot koruması aşılmaz.** Tarayıcı taklidi, User-Agent rotasyonu ve CAPTCHA
  çözme yoktur. Site bizi bot olarak tanıyıp reddediyorsa bu bir karardır.
- **robots.txt bağlayıcıdır.** Her origin için ön kontrol yapılır; RFC 9309
  uyarınca 404/410 kısıt yok, 401/403 tam yasak sayılır.
- **Arşiv canlı veriyle karıştırılmaz.** Common Crawl'dan gelen içerik
  `common_crawl_warc` olarak işaretlenir.
- **Erişim, kanıt demek değildir.** Sitemap ve arama sonucu aday keşiftir;
  içerik bulunmayan yerde yorum ya da fiyat verisi varsayılmaz.
