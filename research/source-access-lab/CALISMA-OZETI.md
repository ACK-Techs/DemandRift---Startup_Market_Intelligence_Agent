# Kaynak Erişim Çalışması — Özet

**Hazırlayan:** Ayselin Aydoğdu
**Kapsam:** `research/source-access-lab/` — DemandRift'in 636 aday veri kaynağı

Görev kartındaki üç madde tamamlandı.

---

## 1. Hangi siteler tamamlandı, hangileri eksik

636 kaynağın tamamı için erişim durumu tek bir deftere bağlandı. Sayılar elle
sayılmadı; koşu artefaktlarından türetiliyor ve `build_coverage_ledger.py` ile
aynı dosyalardan yeniden üretildiğinde aynı sonucu veriyor.

Dört durum ayrı tutuldu, çünkü "adresini biliyoruz" ile "verisi elimizde" aynı
şey değil:

| Durum | Anlamı |
|---|---|
| ✅ Çekildi | Ana sayfa, sitemap, RSS veya API'den içerik indi |
| ⚠️ Kısmi | Sunucuya ulaşıldı ama yalnızca robots.txt alındı |
| ❌ Adres var, erişilemedi | Hiçbir dosya alınamadı |
| ❌ Adres yok | Resmî adres tespit edilemedi |

Her kaynak için adresi, adresin nasıl doğrulandığı, güven seviyesi, çekilen
yüzeyler ve çekilemediyse teknik sebebi kayıtlı.

**Çıktı:** `KAYNAK-DEFTERI.md` (okunabilir tablo), `KAYNAK-DEFTERI.csv`
(filtrelenebilir).

---

## 2. Eksik siteler için veri çekme

| | Başlangıç | Şimdi |
|---|---:|---:|
| Toplam kaynak | 636 | 636 |
| **Adresi bulunan** | 258 (%40.6) | **631 (%99.2)** |
| **Verisi çekilen** | 212 (%33.3) | **534 (%84.0)** |
| Kısmi (yalnız robots.txt) | 25 | 44 |
| Adres var, erişilemedi | 21 | 54 |
| Adres yok | 378 | 4 |

Çekilemeyen 98 kaynağın **35'i** `robots_disallowed` — site taranmasını istemiyor
ve buna uyuluyor (Reddit, X, LinkedIn, Instagram, Google Search). Bunlar kapsam
dışı sayılırsa oran **534/601 = %88.9**.

**Adres bulma.** Sırayla altı yöntem denendi: Wikidata resmî site kaydı, isimden
aday domain üretme, ebeveyn markadan türetme, Wikipedia dış bağlantıları, daha
önce indirdiğimiz sayfaların bağlantıları ve GitHub proje ana sayfaları.
Otomatik yöntemlerin bulamadığı 59 adres elle önerilip **çağrılarak doğrulandı**
— dönen sayfanın başlığı kaynağın adını taşımıyorsa kabul edilmedi. Bu sırada 20
yanlış adres yakalanıp düzeltildi (CORE için DC Comics'in sitesi, FRED için
Brezilya'daki alakasız bir site gibi).

**Veri çekme.** Kazancın büyük kısmı yeni adres bulmaktan değil, çekim
kurallarındaki hataları düzeltmekten geldi: robots.txt'i olmayan siteler
atlanıyordu (oysa dosyanın yokluğu kısıtlama olmadığı anlamına gelir), bot
koruması görülünce tüm site kapatılıp sitemap ve RSS hiç denenmiyordu, boyut ve
zaman aşımı sınırları düşüktü.

Bize kapalı siteler için **Common Crawl arşivi** kullanıldı: bot koruması olan
siteler bize sayfa vermiyor ama arşivde içerikleri var. Bu yol politika ihlali
içermiyor — Common Crawl da robots.txt'e uyduğu için taranması yasak kaynaklar
arşivde de yok. Arşivden gelen içerik ayrı işaretlendi, canlı veriyle
karıştırılmıyor.

**Çıktı:** `ARTEFAKT-DIZINI.csv` — indirilen her dosyanın hangi kaynağın hangi
adresinden, ne zaman ve kaç bayt alındığı. `veriler-ornek/` klasöründe 252
kaynağın gerçek içeriği örnek olarak duruyor.

---

## 3. Anahtar kelime ile arama

**Önce mevcut yol ölçüldü.** Elimizdeki pilot bu işi DuckDuckGo üzerinden
kurgulamıştı; ölçüm o yolun kapalı olduğunu gösterdi:

| Yol | Sonuç |
|---|---|
| DuckDuckGo | 546 sorgunun 534'ü düştü — 12 sorgudan sonra erişim kesiliyor |
| Mojeek, Marginalia | robots.txt'te arama yolu yasak |
| Brave Search API | Şubat 2026'da ücretsiz kademe kaldırılmış |

Yani tek bir genel arama motoruna dayanmak mümkün değil.

**İzlenen yol: her kaynağa kendi diliyle sormak.** Her kaynağın arama yüzeyi,
daha önce indirdiğimiz sayfaların içinden çıkarıldı — bunun için ek ağ isteği
harcanmadı:

| Yol | Kaynak | Nasıl bulundu |
|---|---:|---|
| `opensearch` | 36 | Site arama şablonunu sayfasında ilan ediyor |
| `site_search` | 84 | Sayfadaki arama formundan çıkarılan kalıp |
| `api` | 13 | Anahtarsız resmî API ucu |
| `local_index` | 183 | Sitemap'lerden toplanan 339.488 URL |
| `fulltext` | 217 | İndirilmiş sayfa metni |

İlk üçü **siteye canlı sorgu** (133 kaynak), son ikisi **kendi verimizde arama**
(400 kaynak). Toplamda 636 kaynağın **533'üne** anahtar kelimeyle sorulabiliyor.

Örnek: arXiv'in ana sayfasındaki arama formundan
`arxiv.org/search?query={kelime}` kalıbı çıkarıldı. Katalog yolu gösterir, çekim
aşaması politikayı ayrıca kontrol eder — arXiv bu yolu robots.txt ile kapattığı
için sorgu orada durur. İkisi ayrı bilgi olarak kaydediliyor.

**Çalışan araç var.** `keyword_search_pass.py` kelimeyi alır, katalogdan doğru
yolu seçer ve sorar. Deneme: "market intelligence" 40 kaynağa soruldu, 38'inden
sonuç geldi. Canlı sorgular mevcut çekim motoru üzerinden atılıyor, böylece
robots kontrolü ve kayıt tutma tek yerde kalıyor.

**Çıktı:** `ARAMA-YUZEYLERI.csv` — 578 kaynak için hangi yolla sorulacağı.
