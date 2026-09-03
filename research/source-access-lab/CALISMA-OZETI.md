# Kaynak Erişim Çalışması — Özet

**Hazırlayan:** Ayselin Aydoğdu
**Kapsam:** `research/source-access-lab/` — DemandRift'in 636 aday veri kaynağı
**Görev kartı:** *"Repoyu çekip, dokümanlarda bulunan sitelerin hangilerinin çekilip
tamamlandığını netleştirmek, kalan eksik siteler için verileri çekmek ve anahtar
kelimeler ile arama yapabilmenin yollarını bulmak."*

Üç madde de tamamlandı. Bu belge ne yapıldığını ve nerede durduğunu özetler;
ayrıntı `README.md` ve çıktı dosyalarındadır.

---

## Sonuç tablosu

| Ölçüt | Başlangıç | Şimdi |
|---|---:|---:|
| Adresi bulunan kaynak | 258 (%40.6) | **631 (%99.2)** |
| İçeriği çekilen kaynak | 212 (%33.3) | **534 (%84.0)** |
| Anahtar kelimeyle sorgulanabilen | — | **533 (%83.8)** |

Çekilemeyen 98 kaynağın **35'i** `robots_disallowed` — site taranmasını istemiyor
ve buna uyuluyor (Reddit, X, LinkedIn, Instagram, Google Search). Bunlar kapsam
dışı sayılırsa gerçek oran **534/601 = %88.9**.

---

## Görev 1 — hangi siteler tamamlandı, hangileri eksik

**Yapılan:** 636 kaynağın tamamı için durum, artefaktlardan türetilen tek bir
deftere bağlandı. Elle sayım yok; defter `build_coverage_ledger.py` ile aynı
koşu dosyalarından yeniden üretildiğinde aynı sayıları verir.

**Dört durum ayrı tutuluyor**, çünkü "domaini biliyoruz" ile "verisi elimizde"
aynı şey değil:

| Durum | Kaynak | Anlamı |
|---|---:|---|
| ✅ Çekildi | 534 | Ana sayfa, sitemap, RSS veya API'den içerik indi |
| ⚠️ Kısmi | 44 | Sunucuya ulaşıldı ama yalnızca robots.txt alındı |
| ❌ Adres var, erişilemedi | 54 | Hiçbir dosya alınamadı |
| ❌ Adres yok | 4 | Resmî adres tespit edilemedi |

**Çıktı:** `KAYNAK-DEFTERI.md` (okunabilir), `KAYNAK-DEFTERI.csv` (filtrelenebilir).
Her satırda kaynağın adresi, adresin nasıl doğrulandığı, güven seviyesi, çekilen
yüzeyler ve çekilemediyse teknik sebebi var.

---

## Görev 2 — eksik siteler için veri çekme

**Adres bulma (258 → 631).** Sırayla altı yöntem denendi: Wikidata P856, isimden
aday domain üretme, ebeveyn marka türetme, Wikipedia dış bağlantıları, kendi
indirdiğimiz sayfaların bağlantıları, GitHub proje ana sayfaları. Otomatik
yöntemlerin bulamadığı 59 adres elle önerilip **çağrılarak doğrulandı** — dönen
sayfanın başlığı kaynağın adını taşımıyorsa kabul edilmedi.

**Veri çekme (212 → 534).** Buradaki asıl bulgu şu: kazancın büyük kısmı yeni
adres bulmaktan değil, **kendi kurallarımızdaki hataları düzeltmekten** geldi.
Altı ayrı yerde kendimizi engelliyormuşuz:

| Hata | Etkilenen |
|---|---:|
| robots.txt yoksa (404) siteyi tamamen atlıyorduk — RFC 9309'a göre "dosya yok" = "kısıtlama yok" | 16 |
| robots.txt yerine HTML sayfası dönen siteleri "yasak" sayıyorduk | 12 |
| Bot koruması görünce devre kesici tüm origin'i kapatıyor, sitemap ve feed hiç denenmiyordu | 18 |
| Origin başına istek kotası plandan bağımsız sabitti | 17 |
| Yanıt boyutu tavanı (2 MB) ve okuma zaman aşımı (10 sn) düşüktü | 13 |
| Wikidata'nın `http://` tuttuğu adresler atılıyordu | — |

Ayrıca **20 yanlış adres** yakalanıp düzeltildi: CORE için DC Comics'in
(`dc.com`), Dryad için başka bir sitenin, FRED için Brezilya'daki bir sitenin
verisi çekilmiş. Bunlar "çekildi" hanesinde duruyordu ama yanlış siteden.

**Bize kapalı siteler için Common Crawl arşivi.** Bot koruması olan siteler bize
sayfa vermiyor ama Common Crawl'ın tarayıcısına vermiş olabiliyor. Ölçüm: 167
kaynağın 95'inde arşivde içerik var. Bu yol politika ihlali içermiyor — Common
Crawl da robots.txt'e uyar, bu yüzden `robots_disallowed` kaynaklar arşivde de
yok. Arşivden gelen içerik `common_crawl_warc` yöntemiyle işaretlenir, canlı
veriyle karıştırılmaz.

**Çıktı:** `ARTEFAKT-DIZINI.csv` — indirilen 1.984 dosyanın künyesi: hangi
kaynağın hangi adresinden, ne zaman, kaç bayt, hangi koşuda alındı, başarılı mı.

---

## Görev 3 — anahtar kelime ile arama

**Önce ölçüm.** Mevcut pilot (`ACQUISITION-METHODS.md`) bu işi DuckDuckGo
üzerinden kurgulamıştı. O yol ölçüldü ve kapalı çıktı:

| Yol | Ölçüm |
|---|---|
| DuckDuckGo | 546 sorguda 534'ü `origin_circuit_open` — 12 sorgudan sonra kesiyor |
| Mojeek, Marginalia | robots.txt'te `/search` yolu yasak |
| Brave Search API | Şubat 2026'da ücretsiz kademe kaldırıldı ($5/1000 istek, kart zorunlu) |

**Bunun yerine her kaynağın kendi arama yüzeyi kataloglandı.** Tek bir arama
motoruna bağlı kalmak yerine, her kaynağa kendi diliyle sorulur:

| Yol | Kaynak | Örnek |
|---|---:|---|
| `opensearch` | 36 | Site arama şablonunu makine okunur ilan ediyor |
| `site_search` | 84 | `arxiv.org/search?query={kelime}` |
| `api` | 13 | GitHub, Stack Exchange, npm, Figshare |
| `local_index` | 183 | Sitemap'ten toplanan 339.488 URL'de arama |
| `fulltext` | 217 | İndirilmiş sayfa metninde arama |

İlk üçü **siteye canlı sorgu** (133 kaynak), son ikisi **kendi verimizde arama**
(400 kaynak). Yüzeyler indirdiğimiz sayfalardan çıkarıldı, ağ isteği harcanmadı.

**Çalışan araç var.** `keyword_search_pass.py` kelimeyi alır, katalogdan yolu
seçer, sorar. Deneme: "market intelligence" 40 kaynağa soruldu, **38'inden sonuç
geldi**. Canlı sorgular yeni bir ağ kodu ile değil mevcut çekim motoru üzerinden
atılıyor, böylece robots kontrolü ve artefakt saklama tek yerde kalıyor.

**Çıktı:** `ARAMA-YUZEYLERI.csv` — 578 kaynak için hangi yolla sorulacağı.

---

## Depoya ne yükleniyor, boyut sorunu var mı

Hayır. Ham içeriğin tamamı depoya alınmıyor:

| Ne | Boyut | Depoya |
|---|---:|---|
| Çıktı dosyaları (defter, dizin, katalog) | 570 KB | ✅ |
| Kod (12 modül) + testler (7 dosya, 204 test) | 400 KB | ✅ |
| `source_manifest.json` | 228 KB | ✅ |
| `veriler-ornek/` — 252 kaynağın gerçek içeriği | 5 MB | ✅ |
| **Bu çalışmanın eklediği toplam** | **~7 MB** | |
| `results/` — ham arşiv + koşu çıktıları | 792 MB | ❌ |
| `veriler/` — tam içerik, site adıyla | 220 MB | ❌ |

Dışarıda kalanların hepsi **yeniden üretilebilir**; ayrıca neyin çekildiği
`ARTEFAKT-DIZINI.csv` üzerinden görülüyor. İçeriğin neye benzediğini görmek için
`veriler-ornek/` klasörü yeterli.

> **Not:** Depoda daha önceki bir commit'ten kalan 36 MB ham dosya var (145 dosya,
> adları sha256). Onlara dokunulmadı — ortak repo, ekip kararı. İstenirse
> `git rm --cached` ile takipten çıkarılabilir; dosyalar diskte kalır. Bu
> çalışmada o dosyaların hangi kaynağa ait olduğu dizine işlendi, yani artık
> okunabilir durumdalar.

---

## Kalan işler

| # | İş | Etkilenen | Not |
|---:|---|---:|---|
| 1 | `robots_disallowed` kaynakları "kapsam dışı" olarak etiketlemek | 35 | Sayı kazandırmaz, oranı doğru gösterir |
| 2 | Resmî API katmanını genişletmek | ~37 | Bot korumalı kaynakların API'si olanlar |
| 3 | `DURUM-RAPORU-2.md`'yi güncellemek | — | İçindeki sayılar başlangıç durumuna ait |
| 4 | Tam metin aramasını `keyword_search_pass.py`'ye eklemek | 217 | Şu an ayrı çalışıyor |
