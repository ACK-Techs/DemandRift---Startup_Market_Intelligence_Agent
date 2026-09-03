# Kaynak Erişim Çalışması — Özet

**Hazırlayan:** Ayselin Aydoğdu
**Kapsam:** `research/source-access-lab/` — DemandRift'in 636 aday veri kaynağı

Görev kartındaki üç madde tamamlandı.

---

## 1. Hangi siteler tamamlandı, hangileri eksik

Bir kaynağın "tamamlandı" sayılması iki aşamadan geçiyor ve her ikisi de ayrı
başarısız olabiliyor:

1. **Adres bulma** — kaynağın resmî web adresi tespit ediliyor mu?
2. **Veri çekme** — o adresten gerçekten içerik indirilebiliyor mu?

Bu ayrım önemli, çünkü bir sitenin adresini bilmek verisinin elimizde olduğu
anlamına gelmiyor. Örneğin GitHub'ın adresi baştan beri biliniyordu ama bot
koruması yüzünden sayfası alınamıyordu.

Buna göre 636 kaynağın durumu:

| | Kaynak |
|---|---:|
| ✅ Verisi çekildi | **534** |
| ❌ Adresi var ama veri alınamadı | 98 |
| ❌ Adresi bile bulunamadı | 4 |

Defterde bu üç durumun yanında bir ayrım daha tutuluyor: veri alınamayan
kaynakların bir kısmında sunucuya ulaşılıp yalnızca `robots.txt` indirilebilmiş,
bir kısmında hiçbir dosya alınamamış. Analiz için kullanılabilir veri her iki
durumda da yok, ama engelin nerede olduğunu gösterdiği için ayrı kaydediliyor.

Sayılar elle sayılmadı; koşu artefaktlarından türetiliyor ve
`build_coverage_ledger.py` ile aynı dosyalardan yeniden üretildiğinde aynı
sonucu veriyor. Her kaynak için adresi, adresin nasıl doğrulandığı, güven
seviyesi, çekilen yüzeyler ve çekilemediyse teknik sebebi kayıtlı.

**Çıktı:** `KAYNAK-DEFTERI.md` (okunabilir tablo), `KAYNAK-DEFTERI.csv`
(filtrelenebilir).

---

## 2. Eksik siteler için veri çekme

### Adres bulma

| | Kaynak |
|---|---:|
| Toplam | 636 |
| **Adresi bulunan** | **631** |
| Adresi bulunamayan | 5 |

Bulunamayan 5 kaynağın gerekçesi:

| Kaynak | Neden |
|---|---|
| Amazon Reviews, Similarweb Digital Marketing Intelligence, OPPO App Market | Bağımsız site değil, bir markanın alt sayfası; denenen yollar 404 döndü |
| Ankara Büyükşehir Açık Veri Portalı | Adres bağlantı vermiyor |
| Slant | Otomatik çözümleme alakasız bir siteyi verdi, kayıt geri alındı |

Ebeveyn markanın kökü (`amazon.com` gibi) adres olarak yazılabilirdi ama
yazılmadı — o bir adres değil yer tutucu olurdu.

**Yöntem:** Sırayla Wikidata resmî site kaydı, isimden aday domain üretme,
ebeveyn markadan türetme, Wikipedia dış bağlantıları, daha önce indirdiğimiz
sayfaların bağlantıları ve GitHub proje ana sayfaları denendi. Otomatik
yöntemlerin bulamadığı 59 adres elle önerilip çağrılarak doğrulandı; dönen
sayfanın başlığı kaynağın adını taşımıyorsa kabul edilmedi. Bu sırada 20 yanlış
adres yakalanıp düzeltildi (CORE için DC Comics'in sitesi, FRED için Brezilya'da
alakasız bir site gibi).

### Veri çekme

| | Kaynak |
|---|---:|
| Adresi olan | 631 |
| **Verisi çekilen** | **534** |
| Çekilemeyen | 98 |

Çekilemeyen 98 kaynağın gerekçesi:

| Neden | Kaynak | Açıklama |
|---|---:|---|
| Site taranmasını yasaklıyor | 35 | robots.txt izin vermiyor, uyuluyor (Reddit, X, LinkedIn, Instagram, Google Search) |
| Bot koruması | 31 | Doğrulama duvarı; sunucu isteğimizi reddediyor |
| Sunucu erişimi reddetti | 12 | Origin doğrudan kapatıyor |
| Ağ hatası | 13 | Zaman aşımı, SSL sertifika hatası, bağlantı kurulamıyor |
| Kota aşımı, bozuk yanıt, diğer | 7 | Geçici ya da tekil sebepler |

Bunların 35'i kalıcı olarak kapsam dışı: site taranmasını istemiyor. O 35 hariç
tutulursa oran **534/601 = %88.9**.

**Yöntem:** Kazancın büyük kısmı yeni adres bulmaktan değil, çekim
kurallarındaki hataları düzeltmekten geldi — robots.txt'i olmayan siteler
atlanıyordu (dosyanın yokluğu kısıtlama olmadığı anlamına gelir), bot koruması
görülünce tüm site kapatılıp sitemap ve RSS hiç denenmiyordu, boyut ve zaman
aşımı sınırları düşüktü.

Bize kapalı siteler için **Common Crawl arşivi** kullanıldı: bot koruması olan
siteler bize sayfa vermiyor ama arşivde içerikleri var. Bu yol politika ihlali
içermiyor — Common Crawl da robots.txt'e uyduğu için taranması yasak kaynaklar
arşivde de yok. Arşivden gelen içerik ayrı işaretlendi.

**Çıktı:** `ARTEFAKT-DIZINI.csv` — indirilen her dosyanın hangi kaynağın hangi
adresinden ne zaman alındığı. `veriler-ornek/` klasöründe 252 kaynağın gerçek
içeriği örnek olarak duruyor.

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
