# Kaynak Erişim Laboratuvarı

DemandRift'in araştırma motoru 636 web kaynağından veri toplamayı planlıyor. Bu
klasör üç soruyu cevaplıyor: **hangi kaynaklar tamamlandı**, **eksik olanların
verisi nasıl çekildi**, ve **bir anahtar kelime bu kaynaklara nasıl sorulur**.

Bütün sayılar artefaktlardan üretilir, elle sayım yoktur; her çıktı dosyası
kendi script'iyle yeniden üretilebilir.

> Çalışmanın özeti, sayıların gerekçeleri ve izlenen yol için:
> **[CALISMA-OZETI.md](CALISMA-OZETI.md)**. Bu dosya klasörün nasıl kullanılacağını
> anlatır.

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

Ham içeriğin tamamı (225 MB) ve koşu çıktıları `.gitignore` ile depoya alınmaz:
yeniden üretilebilirler ve neyin çekildiği `ARTEFAKT-DIZINI.csv` üzerinden
görülür. Ancak verinin neye benzediğini görmek için **`veriler-ornek/`** klasörü
depoda tutulur: 252 kaynağın gerçek içeriği, 5 MB.

Seçim rastgele değil kurallıdır — yalnızca içerik yüzeyleri (robots.txt hariç),
başarılı istekler, dosya başına 90 KB ve toplam 5 MB sınırıyla:

```bash
python3 export_by_source.py --only-fetched --out veriler-ornek \
  --methods "root_html,entry_url,sitemap_xml,rss_feed,common_crawl_warc" \
  --max-file-bytes 90000 --max-total-bytes 5000000
```

Tam arşiv için aynı komut sınırsız çalıştırılır (`veriler/`, 534 kaynak, 225 MB).

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
