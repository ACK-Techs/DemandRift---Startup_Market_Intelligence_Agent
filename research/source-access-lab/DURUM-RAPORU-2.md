# DemandRift — Kaynak Erişim Durum Raporu

**Hazırlanma tarihi:** 2026-09-02  
**Hazırlayan:** Ayselin Aydoğdu  
**Kapsam:** `research/source-access-lab/` klasörü — DemandRift'in Faz 3 (Acquisition/veri toplama) altyapısı için araştırılan 636 aday veri kaynağı  
**Görev bağlantısı:** DemandRift görev kartındaki "hangi sitelerin çekilip tamamlandığının netleştirilmesi" maddesinin çıktısıdır.

### Rapordaki sayıların dayandığı koşu (kanıt referansı)

Bu rapordaki her sayı aşağıdaki tek koşunun artefaktından türetilmiştir; elle sayım yapılmamıştır.

| Alan | Değer |
|---|---|
| `run_id` | `bulk-live-1786393178` |
| `manifest_id` | `bulk-source-access-lab-v1` |
| Koşu zamanı | `2026-08-10T20:19:38.860451+00:00` |
| İstek bütçesi | 214 / 1500 (site başına en fazla 6) |
| Sonuç dosyası | `results/bulk-site-access-live-20260810T203700Z.json` |
| Domain durumu | `source_manifest.json` |
| Çapraz kontrol | `SITE-ACCESS-SUMMARY.md`, `results/adaptive-domain-pass-*.json` |

> `AGENTS.md`: *"Conversation memory is not completion evidence; run/result artifacts are."* Rapor bu kurala uyacak şekilde koşuya sabitlenmiştir; aynı artefaktlardan yeniden üretildiğinde aynı sayıları vermelidir.

---

## 1. Bu rapor neyi amaçlıyor

DemandRift'in araştırma motoru, bir startup fikrini doğrulamak için 636 farklı web kaynağından (arama motorları, geliştirici platformları, pazar yerleri, resmi istatistik kurumları, haber siteleri vb.) veri toplamayı planlıyor. Bu kaynakların tam listesi `SITE-LISTESI.md` dosyasında 30 kategori altında tutuluyor.

Daha önce bu kaynaklara erişim denemesi yapılmış (`bulk_site_access_lab.py` ve `adaptive_domain_pass.py` script'leri ile), ancak hangi kaynağın gerçekten tamamlandığı, hangisinin hâlâ eksik olduğu net bir dokümanda toplanmamıştı — bilgi farklı JSON dosyalarına dağılmış durumdaydı. Bu rapor, o dağınık veriyi tek bir okunabilir kaynakta birleştirip görev kartındaki ilk maddeyi ("hangi siteler tamamlandı, hangileri eksik") kesin biçimde cevaplıyor.

## 2. Bir kaynağın "tamamlandı" sayılması için gereken iki aşama

Bir web kaynağından veri çekmek tek adımda olmuyor, iki ayrı aşamadan geçiyor ve her aşama ayrı ayrı başarısız olabiliyor. Bu yüzden rapordaki durumlar da bu iki aşamaya göre ayrıldı:

**Aşama A — Domain çözümleme (resolution):** Önce kaynağın *gerçek, resmi web adresinin* ne olduğu tespit ediliyor. Örneğin "Product Hunt" adının karşılığının `producthunt.com` olduğunu doğrulamak bu aşamaya giriyor. Bu aşama `source_manifest.json` dosyasındaki `resolution_status` alanıyla izleniyor.

**Aşama B — Fetch (gerçek veri çekimi):** Domain doğrulandıktan sonra, o adresten fiilen bir içerik indiriliyor (ana sayfa HTML'i, sitemap.xml, RSS beslemesi gibi). Bu aşama `results/bulk-site-access-live-*.json` dosyasındaki `fetched_artifact_count` alanıyla izleniyor.

Bu ayrımı yapmak önemli, çünkü bir kaynağın domaininin bilinmesi onun verisinin de çekildiği anlamına gelmiyor. Örneğin GitHub için domain doğrulanmış ve `robots.txt` dosyası başarıyla indirilmiş, ama asıl sayfa içeriği (`root_html`) `response_too_large` nedeniyle alınamamış. Yani GitHub'ı basitçe "tamamlandı" diye işaretlemek yanıltıcı olurdu — bu yüzden rapor dört durumlu bir sınıflandırma kullanıyor:

| Durum | Ne anlama geliyor | Örnek |
|---|---|---|
| ✅ **Tamam** | Domain doğrulanmış VE asıl içerik (ana sayfa, sitemap veya RSS) başarıyla indirilmiş. Bu kaynak üzerinde ileride analiz/normalizasyon yapılabilir. | AFRINIC, ARIN, Associated Press |
| ⚠️ **Kısmi** | Domain doğrulanmış ama yalnızca `robots.txt` (erişim kuralları dosyası) indirilebilmiş, asıl içerik henüz çekilememiş. Teknik olarak "erişim var" ama elde kullanılabilir veri yok. | GitHub, Reddit, Hugging Face |
| ❌ **Eksik — domain yok** | Sitenin resmi web adresi henüz otomatik olarak tespit edilememiş. Bu kaynaklar için fetch denemesi hiç başlamamış. | Brave Search, Exa, Yandex |
| ❌ **Eksik — fetch başarısız** | Domain biliniyor ama erişim denemesi `robots.txt` aşamasında düşmüş. | Stack Overflow, PubMed, Kaggle |

> **Not:** Reddit ve Hugging Face, robots.txt dışında artefact üretmediği için ⚠️ Kısmi'dir; "Tamam" örneği olarak kullanılmamalıdır.

## 3. Rapor nasıl üretildi (izlenen adımlar)

| # | Adım | İncelenen dosya | Hangi soruyu cevapladı |
|---|---|---|---|
| 1 | Kapsamı belirleme | `SITE-LISTESI.md` | Toplamda kaç kaynak var, hangi kategorilere ayrılıyor? (636 benzersiz kaynak, 30 kategori, 683 liste satırı) |
| 2 | Domain durumu | `source_manifest.json` → `resolution_status` | Kaç kaynağın resmi adresi biliniyor? (90 biliniyor / 546 bilinmiyor) |
| 3 | Gerçek veri çekimi | `bulk-site-access-live-*.json` → `fetched_artifact_count` | Domaini bilinen 90 kaynaktan kaçından *gerçekten* içerik indirilebilmiş? Sadece robots.txt mi, yoksa asıl içerik mi? |
| 4 | Güncellik kontrolü | `adaptive-domain-pass-*.json` → `resolution` | Eksik 546 kaynağı çözmek için sonradan deneme yapılmış mı? (İki koşuda da 0 yeni kaynak — sebebi bölüm 7) |
| 5 | **Fetch tekrarı kontrolü** | `adaptive-domain-pass-*.json` → `access_run` | Adaptive koşular fetch'i de yeniden çalıştırmış; sonuçlar değişmiş mi? (Bölüm 6.2) |
| 6 | **Bağımsız üretimle karşılaştırma** | `SITE-ACCESS-SUMMARY.md` → "Yöntem oranları" | Aynı koşudan deterministik üretilmiş ikinci doküman aynı sayıları veriyor mu? (Bölüm 6.1) |
| 7 | **Artefact mutabakatı** | `results/raw/` + `immutable_raw_ref` | Rapordaki artefact sayısı diskteki dosyalarla birebir eşleşiyor mu? (Bölüm 6.3) |
| 8 | Depo kontrolü | `git fetch` + `git branch -r --merged` | GitHub'da push edilmemiş, gizli bir ilerleme var mı? (Yok — `main` origin ile aynı, `batuhan/frontend-ui` zaten merge edilmiş) |

---

## 4. Genel Sonuç

| Durum | Kaynak Sayısı | Oran |
|---|---:|---:|
| ✅ Tamam | 37 | %5.8 |
| ⚠️ Kısmi | 24 | %3.8 |
| ❌ Eksik (domain yok) | 546 | %85.8 |
| ❌ Eksik (fetch başarısız) | 29 | %4.6 |
| **Toplam** | **636** | **%100** |

**Yorum:** 636 kaynaktan yalnızca **37 tanesi** (%5.8) gerçek anlamda tamamlanmış durumda — yani hem domaini biliniyor hem de üzerinden kullanılabilir içerik çekilmiş. **24 kaynak** kısmi durumda (erişim var ama veri yok), geri kalan **575 kaynak** ise hiç veri üretmemiş. Özetle işin **%5.8'i tamamlanmış, %94.2'i hâlâ yapılması gerekiyor.**

Eksik kaynakların büyük çoğunluğu (546 / 636 ≈ %86) daha ilk aşamada, yani domain bile bulunamadan takılı kalmış durumda. Teknik sebebi bölüm 7'de ayrıca ele alınmıştır.

### 4.1 Faz 3 kabul kriterine göre durum ayrıştırması

[Faz3-Plan.md](../../Faz3-Plan.md) kabul kriteri şunu şart koşuyor: *"`partial`, `rate_limited`, `blocked_by_policy` ve `failed` durumları birbirinden ayrılmalıdır."* Tek bir "Eksik" kovası bu kriteri karşılamadığı için, başarısızlıklar koşunun kendi `stop_reason` alanına göre ayrıştırılmıştır.

**❌ Eksik — fetch başarısız (29 kaynak).** Tamamı `robots_preflight` aşamasında düşmüş; hiçbirinde asıl içerik denemesine sıra gelmemiş.

| Teknik sebep | Kaynak | Faz 3 durumu | Yorum |
|---|---:|---|---|
| `challenge` | 14 | `blocked_by_policy` | Bot koruması / doğrulama duvarı — gerçek engel, farklı strateji gerekir |
| `network_error:OSError` | 8 | `failed` | Ağ hatası — muhtemelen geçici, yeniden denemeye değer |
| `source_unavailable` | 5 | `failed` | Kaynak ulaşılamaz — muhtemelen geçici |
| `rate_limited` | 2 | `rate_limited` | Kota aşımı — bekleyip yeniden denenebilir |

> **2. görev için doğrudan çıkarım:** 8 + 5 + 2 = **15 kaynak muhtemelen sadece yeniden deneme ile** kurtarılabilir. Kalan 14 `challenge` kaynağı ise gerçek bot koruması ardında; bunlar için resmî API veya farklı erişim yolu aranmalıdır.

**⚠️ Kısmi (24 kaynak).** Faz 3 terminolojisinde tamamı `partial`. Asıl içeriğin neden alınamadığı:

| Teknik sebep | Kaynak | Engel kaynağın mı, bizim tarafın mı? |
|---|---:|---|
| `response_too_large` | 8 | **Bizim taraf** — runner boyut limiti; limit yükseltilerek çözülebilir |
| `challenge` | 8 | Kaynak — bot koruması |
| `robots_disallowed` | 5 | Kaynak — robots.txt politikası; saygı gösterilmeli |
| `origin_denied` | 2 | Kaynak — origin reddi |
| `redirect_limit_exceeded` | 1 | **Bizim taraf** — yönlendirme limiti |

> 9 Kısmi kaynak, karşı tarafın engeli yüzünden değil **kendi runner limitlerimiz** yüzünden eksik. Bunlar 2. görevde en ucuz kazanç.

---

## 5. Kategori Bazında Dağılım

*Not: Bazı kaynaklar (Hacker News, Product Hunt, Wellfound vb.) birden fazla kategoride yer aldığı için satır toplamları genel toplamdan fazladır: liste 683 satır içerir, bunlar 636 benzersiz kaynağa karşılık gelir. Kategori tablosu yalnızca dağılımı görmek içindir; bölüm 4'teki genel toplam benzersiz 636 kaynağa göre hesaplanmıştır.*

| Kategori | Toplam | ✅ Tamam | ⚠️ Kısmi | ❌ Eksik |
|---|---:|---:|---:|---:|
| Genel web arama ve keşif | 16 | 0 | 0 | 16 |
| Yazılım geliştirici ve teknik topluluklar | 34 | 8 | 3 | 23 |
| Ürün lansmanı ve startup toplulukları | 24 | 0 | 0 | 24 |
| Sosyal ağlar ve açık topluluklar | 24 | 2 | 5 | 17 |
| Mobil uygulama mağazaları | 13 | 0 | 2 | 11 |
| Tarayıcı, e-ticaret ve CMS eklenti mağazaları | 25 | 1 | 1 | 23 |
| SaaS, yazılım ve hizmet inceleme siteleri | 25 | 0 | 3 | 22 |
| E-ticaret ve fiziksel ürün pazar yerleri | 24 | 0 | 2 | 22 |
| Domain, DNS, sertifika ve web footprint | 30 | 7 | 3 | 20 |
| Trafik, SEO, anahtar kelime ve trend | 24 | 0 | 0 | 24 |
| Reklam kütüphaneleri ve pazarlama sinyalleri | 16 | 0 | 0 | 16 |
| Şirket, yatırım ve startup verisi | 28 | 1 | 0 | 27 |
| İş ilanları ve yetenek talebi | 24 | 0 | 0 | 24 |
| Yerel işletme, harita ve hizmet dizinleri | 23 | 1 | 0 | 22 |
| Akademik araştırma ve bilimsel yayınlar | 33 | 6 | 0 | 27 |
| Kamu verisi ve istatistik | 25 | 4 | 0 | 21 |
| Regülasyon ve hukuk kaynakları | 28 | 0 | 1 | 27 |
| Patent ve marka | 13 | 0 | 0 | 13 |
| Sağlık ve biyoteknoloji dikeyi | 17 | 1 | 0 | 16 |
| Finans ve fintech dikeyi | 26 | 4 | 1 | 21 |
| Eğitim dikeyi | 17 | 0 | 0 | 17 |
| Gayrimenkul ve inşaat dikeyi | 18 | 0 | 0 | 18 |
| Seyahat, konaklama ve mobilite dikeyi | 22 | 1 | 0 | 21 |
| Yeme-içme ve teslimat dikeyi | 17 | 0 | 0 | 17 |
| Oyun dikeyi | 17 | 1 | 2 | 14 |
| Yapay zekâ modeli, veri seti ve agent ekosistemi | 24 | 3 | 2 | 19 |
| Haber, basın ve sektör yayınları | 30 | 1 | 1 | 28 |
| Anket, birincil doğrulama ve kullanıcı araştırması platformları | 24 | 0 | 0 | 24 |
| Fiyat, teknoloji ve pazar sinyali karşılaştırma kaynakları | 20 | 0 | 2 | 18 |
| Türkiye startup ve teknoloji ekosistemi | 22 | 0 | 1 | 21 |

---

## 6. Bağımsız Doğrulama

Rapordaki sınıflandırma tek bir dosyadan türetildiği için üç ayrı yoldan çapraz kontrol edilmiştir.

### 6.1 `SITE-ACCESS-SUMMARY.md` ile karşılaştırma

Bu doküman aynı koşudan (`bulk-live-1786393178`) deterministik olarak üretilmiş, bağımsız bir render'dır. "Yöntem oranları" tablosu şunları veriyor:

| Yöntem | Artefact üreten kaynak | Bu rapordaki karşılığı |
|---|---:|---|
| `robots_preflight` | 61 | 37 Tamam + 24 Kısmi = 61 ✓ |
| `root_html` | 33 | içerik yüzeyi |
| `sitemap_xml` | 18 | içerik yüzeyi |
| `rss_feed` | 2 | içerik yüzeyi |
| **içerik yüzeyleri birleşimi** | **37** | **37 Tamam ✓** |

Üç içerik yönteminin kaynak kümesi birleşimi tam olarak 37 çıkıyor ve bu rapordaki ✅ Tamam sayısıyla birebir örtüşüyor.

### 6.2 Adaptive koşuların `access_run` bloğu

`adaptive-domain-pass-*.json` dosyaları yalnızca domain çözümleme yapmıyor; içlerindeki `access_run` bloğu, çözülmüş 90 kaynak için **fetch'i yeniden çalıştırıyor**. Bu bağımsız iki koşu ayrı ayrı sınıflandırıldığında:

| Koşu | ✅ Tamam | ⚠️ Kısmi | ❌ Fetch başarısız | Bu raporla farkı |
|---|---:|---:|---:|---:|
| Ana koşu (`bulk-live-1786393178`) | 37 | 24 | 29 | — |
| Adaptive 1. kosu | 37 | 24 | 29 | **0 kaynakta fark** |
| Adaptive 2. kosu | 37 | 24 | 29 | **0 kaynakta fark** |

Üç canlı koşunun üçü de aynı sonucu veriyor; tek bir kaynakta bile sınıf değişikliği yok. Sayılar tekrarlanabilir.

### 6.3 Artefact / ham dosya mutabakatı

Bu koşuda üretilen artefactlar:

```text
114 artefact = 72 inline (robots.txt vb.) + 42 ham dosya (results/raw/)
                → 61 çözülmüş kaynağa dağılıyor
```

Referans verilen 42 dosyanın **tamamı** diskte mevcut, eksik yok.

> **Önemli uyarı:** `results/raw/` klasöründe toplam 134 dosya var, ancak bunların yalnızca 42'si bu koşuya ait; geri kalanı adaptive koşularla paylaşılıyor. Bu yüzden "134 dosya var" ifadesi tek başına bu rapordaki 37/24 ayrımını doğrulamaz — doğru mutabakat yukarıdaki 72+42 ayrışmasıdır.

---

## 7. Teknik Engel: 546 kaynağın domaini neden çözülemedi

Eksik kaynakların %86'sı domain aşamasında takılı. `adaptive_domain_pass.py` bunu çözmek için iki kez çalıştırılmış, ikisi de **0 yeni kaynak** çözmüş. Ancak iki koşunun sebebi farklı:

| Koşu | Sonuç dağılımı |
|---|---|
| 1. koşu (`adaptive-domain-pass-live-20260811T003600Z`) | `wikidata_batch_error:RuntimeError` = 546 |
| 2. koşu (`adaptive-domain-pass-r2-live-20260811T005000Z`) | `rate_limited` = 536, `origin_circuit_open` = 6, `mediawiki_ambiguous_exact_label` = 3, `mediawiki_no_exact_label` = 1 |

**1. koşu** rate limit değil, Wikidata SPARQL batch çağrısındaki bir `RuntimeError` yüzünden 546 kaynağın hepsinde düşmüş.

**2. koşu**'da asıl mekanizma şu: [adaptive_domain_pass.py:462](adaptive_domain_pass.py#L462) ve [:508](adaptive_domain_pass.py#L508) satırlarındaki `fallback_stopped` mandalı, ilk `rate_limited` cevabında `True` oluyor ve koşu boyunca **hiç sıfırlanmıyor**:

```python
if reason in {"rate_limited", "challenge", "origin_circuit_open"} or (...):
    fallback_stopped, fallback_stop_reason = True, reason
```

Bu mandal açıldıktan sonra kalan bütün kaynaklar **hiç denenmeden** aynı etiketle işaretleniyor. Kanıtı istek sayaçlarında: 546 kaynak için toplam yalnızca 3 ve 14 network transaction yapılmış (bütçe 1500). Yani 536 kaynağın `rate_limited` görünmesi, o kaynakların gerçekten kota yemesi değil, **mandalın etiketini miras almaları** demek.

> **Not:** `origin_circuit_open` (devre kesici) etiketi yalnızca 6 kaynakta görünüyor. Asıl sorun devre kesici değil, yukarıdaki sıfırlanmayan mandaldır. `bulk_site_access_lab.py` içindeki `Circuit` sınıfına cooldown eklemek bu mandalı çözmez — mandal circuit'ten bağımsız, sadece `reason` string'ine bakar.

Bu, görev kartının ikinci maddesi ("eksik siteler için verileri çekmek") kapsamında çözülmesi gereken birincil teknik engeldir.

---

## 8. Kaynak Bazında Ayrıntılı Liste

Her satırda kaynağın durumu ve koşunun ürettiği teknik sebep yer alır.

### Genel web arama ve keşif

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Brave Search | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Exa | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Search | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Bing | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| DuckDuckGo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Yahoo Search | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Yandex | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Mojeek | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Kagi | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SearXNG | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Tavily | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SerpAPI | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Serper | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Scale SERP | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| DataForSEO | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Firecrawl | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Yazılım geliştirici ve teknik topluluklar

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| GitHub | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: yanıt, runner boyut limitini aştı |
| GitLab | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: origin erişimi reddetti |
| Bitbucket | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: yanıt, runner boyut limitini aştı |
| SourceForge | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| Codeberg | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| Hacker News | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| Stack Overflow | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| Stack Exchange | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| Server Fault | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| Super User | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| Ask Ubuntu | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| Software Engineering Stack Exchange | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Dev.to | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, RSS beslemesi |
| Hashnode | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Lobsters | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: ağ hatası (bağlantı kurulamadı) |
| Indie Hackers | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| DZone | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| InfoQ | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Slashdot | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| CodeProject | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Replit Community | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Docker Hub | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| npm | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| PyPI | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| RubyGems | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| crates.io | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| Maven Central | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| NuGet Gallery | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Packagist | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Homebrew Formulae | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Libraries.io | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Open VSX Registry | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Visual Studio Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| JetBrains Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Ürün lansmanı ve startup toplulukları

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Product Hunt | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| BetaList | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Uneed | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Microlaunch | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Peerlist | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Launching Next | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Startup Stash | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SaaSHub | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| AlternativeTo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Slant | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| There's An AI For That | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Futurepedia | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Toolify | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| G2 Track | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| AppSumo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| PitchWall | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Fazier | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| HackerNoon | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| GrowthHackers | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Starter Story | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Failory | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Y Combinator Companies | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Wellfound | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| F6S | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Sosyal ağlar ve açık topluluklar

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Reddit | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: robots.txt bu yolu yasaklıyor |
| X | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Mastodon | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Bluesky | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| Threads | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Facebook | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Instagram | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TikTok | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| YouTube | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: yanıt, runner boyut limitini aştı |
| LinkedIn | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: robots.txt bu yolu yasaklıyor |
| Pinterest | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: robots.txt bu yolu yasaklıyor |
| Tumblr | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Quora | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Medium | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: bot koruması / doğrulama duvarı |
| Substack | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Discord | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Slack | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Telegram | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Discourse | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Groups.io | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Lemmy | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Hacker News | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| Product Hunt | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| Indie Hackers | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Mobil uygulama mağazaları

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Apple App Store | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: yanıt, runner boyut limitini aştı |
| Google Play Store | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: yanıt, runner boyut limitini aştı |
| Huawei AppGallery | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Samsung Galaxy Store | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Amazon Appstore | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Microsoft Store | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Xiaomi GetApps | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| OPPO App Market | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| vivo App Store | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Aptoide | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| F-Droid | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: ağ hatası (bağlantı kurulamadı) |
| APKMirror | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Uptodown | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Tarayıcı, e-ticaret ve CMS eklenti mağazaları

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Chrome Web Store | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: yanıt, runner boyut limitini aştı |
| Firefox Add-ons | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| Microsoft Edge Add-ons | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Safari Extensions | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Opera Add-ons | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Shopify App Store | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| WooCommerce Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| WordPress Plugin Directory | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: ağ hatası (bağlantı kurulamadı) |
| Wix App Market | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Squarespace Extensions | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| BigCommerce App Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Webflow Apps | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Atlassian Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Salesforce AppExchange | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| HubSpot App Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Slack Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Zoom App Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Microsoft AppSource | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Workspace Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| monday.com Apps Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Notion Integrations | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Zapier App Directory | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Make Apps Directory | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Airtable Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Canva Apps Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### SaaS, yazılım ve hizmet inceleme siteleri

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| G2 | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: bot koruması / doğrulama duvarı |
| Capterra | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: bot koruması / doğrulama duvarı |
| GetApp | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Software Advice | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TrustRadius | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Gartner Peer Insights | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| PeerSpot | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SourceForge Reviews | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Crozdesk | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Serchen | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| FinancesOnline | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SaaSworthy | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SoftwareSuggest | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Tekpon | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Trustpilot | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: robots.txt bu yolu yasaklıyor |
| Sitejabber | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ConsumerAffairs | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Better Business Bureau | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Reviews.io | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Feefo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ProvenExpert | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Reviews | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Yelp | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Tripadvisor | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Glassdoor | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### E-ticaret ve fiziksel ürün pazar yerleri

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Amazon | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: yanıt, runner boyut limitini aştı |
| eBay | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| Etsy | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: bot koruması / doğrulama duvarı |
| Walmart | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| AliExpress | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Alibaba | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Temu | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Trendyol | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Hepsiburada | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| n11 | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Çiçeksepeti | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Pazarama | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Sahibinden | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Facebook Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Kickstarter | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| Indiegogo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Gumroad | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Lemon Squeezy | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Creative Market | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Envato Market | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ThemeForest | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| CodeCanyon | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Etsy Reviews | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Amazon Reviews | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Domain, DNS, sertifika ve web footprint

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| ICANN Lookup | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: kaynak ulaşılamaz |
| IANA | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| RDAP.org | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: kaynak ulaşılamaz |
| Verisign RDAP | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ARIN | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| RIPE NCC | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, RSS beslemesi |
| APNIC | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: bot koruması / doğrulama duvarı |
| LACNIC | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| AFRINIC | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| crt.sh | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: ağ hatası (bağlantı kurulamadı) |
| Censys | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Shodan | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| SecurityTrails | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| DNSdumpster | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| DNSlytics | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ViewDNS.info | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| WhoisXML API | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| DomainTools | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| BuiltWith | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Wappalyzer | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Similarweb | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Wayback Machine | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: kaynak ulaşılamaz |
| Common Crawl | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| urlscan.io | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: bot koruması / doğrulama duvarı |
| VirusTotal | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: bot koruması / doğrulama duvarı |
| Netcraft | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| HTTP Archive | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Cloudflare Radar | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| Mozilla Observatory | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: ağ hatası (bağlantı kurulamadı) |
| Google Transparency Report | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Trafik, SEO, anahtar kelime ve trend

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Google Trends | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Keyword Planner | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Search Console | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Bing Webmaster Tools | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Ahrefs | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Semrush | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Moz | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Similarweb | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Ubersuggest | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Mangools | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SE Ranking | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SpyFu | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Majestic | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Sistrix | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Serpstat | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Keyword Tool | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| AnswerThePublic | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Exploding Topics | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Glimpse | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Trend Hunter | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Think with Google | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SparkToro | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| BuzzSumo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Dataset Search | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Reklam kütüphaneleri ve pazarlama sinyalleri

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Meta Ad Library | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Ads Transparency Center | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TikTok Creative Center | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| LinkedIn Ad Library | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Pinterest Ads Repository | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Snapchat Ads Gallery | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| X Ads Transparency Center | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Moat | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Pathmatics | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Sensor Tower | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| data.ai | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| AppMagic | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SocialPeta | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| BigSpy | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Adbeat | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Similarweb Digital Marketing Intelligence | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Şirket, yatırım ve startup verisi

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Crunchbase | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| PitchBook | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Tracxn | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Dealroom | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| CB Insights | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| PrivCo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Craft.co | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Owler | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ZoomInfo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Apollo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Clearbit | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| People Data Labs | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| OpenCorporates | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SEC EDGAR | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| Companies House | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| European e-Justice Business Registers | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Türkiye Ticaret Sicili Gazetesi | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| MERSİS | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| KAP | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| AngelList | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Wellfound | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Y Combinator Companies | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Techstars Companies | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| 500 Global Companies | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Seed-DB | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Republic | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Seedrs | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Crowdcube | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### İş ilanları ve yetenek talebi

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| LinkedIn Jobs | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Indeed | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Glassdoor | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Wellfound | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ZipRecruiter | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Monster | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SimplyHired | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Jooble | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Jobs | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Greenhouse Job Boards | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Lever Jobs | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Ashby Jobs | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Workable Jobs | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SmartRecruiters | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Remote OK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| We Work Remotely | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| FlexJobs | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Otta | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Welcome to the Jungle | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Kariyer.net | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Yenibiris | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Secretcv | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Eleman.net | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| İşkur | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Yerel işletme, harita ve hizmet dizinleri

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Google Maps | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Apple Maps | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Bing Maps | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| OpenStreetMap | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| Yelp | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Foursquare | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Tripadvisor | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Yellow Pages | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Yandex Maps | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| HERE WeGo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| MapQuest | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TomTom | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Business Profile | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Facebook Pages | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Nextdoor | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Thumbtack | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Angi | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Houzz | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Treatwell | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Fresha | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Booksy | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Armut | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Sahibinden Hizmetler | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Akademik araştırma ve bilimsel yayınlar

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Google Scholar | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Semantic Scholar | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| OpenAlex | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| Crossref | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| CORE | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| BASE | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Lens.org | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Dimensions | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Scopus | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Web of Science | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| PubMed | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: ağ hatası (bağlantı kurulamadı) |
| PubMed Central | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: ağ hatası (bağlantı kurulamadı) |
| Europe PMC | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| arXiv | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| bioRxiv | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: kota aşımı (rate limit) |
| medRxiv | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| SSRN | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ResearchGate | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Academia.edu | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| IEEE Xplore | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ACM Digital Library | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SpringerLink | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ScienceDirect | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Wiley Online Library | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Nature | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| PLOS | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| DOAJ | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| Zenodo | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| Figshare | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| OSF | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Dryad | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Kaggle | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: kaynak ulaşılamaz |
| Papers with Code | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Kamu verisi ve istatistik

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| World Bank Open Data | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| OECD Data | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: kaynak ulaşılamaz |
| IMF Data | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| United Nations Data | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Eurostat | ✅ Tamam | çekildi ve tamamlandı — sitemap.xml |
| data.europa.eu | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| Data.gov | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| US Census Bureau | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Bureau of Labor Statistics | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Federal Reserve Economic Data | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| WHO Global Health Observatory | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| OECD Health Statistics | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Our World in Data | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TÜİK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TCMB EVDS | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| T.C. Sanayi ve Teknoloji Bakanlığı | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| T.C. Ticaret Bakanlığı | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| T.C. Sağlık Bakanlığı | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| T.C. Resmî Gazete | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Türkiye Açık Veri Portalı | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| İstanbul Büyükşehir Belediyesi Açık Veri Portalı | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Ankara Büyükşehir Belediyesi Açık Veri Portalı | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| data.gov.uk | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| INSEE | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Destatis | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Regülasyon ve hukuk kaynakları

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| T.C. Resmî Gazete | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Mevzuat Bilgi Sistemi | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| KVKK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Rekabet Kurumu | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| BTK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| BDDK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SPK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TCMB | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TİTCK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Sağlık Bakanlığı | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| MASAK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Gelir İdaresi Başkanlığı | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| EUR-Lex | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| European Commission | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| European Data Protection Board | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| European Medicines Agency | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| European Banking Authority | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| European Securities and Markets Authority | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Federal Register | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: origin erişimi reddetti |
| Regulations.gov | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| U.S. Federal Trade Commission | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| U.S. Food and Drug Administration | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| U.S. Securities and Exchange Commission | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Consumer Financial Protection Bureau | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| UK Legislation | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| UK Financial Conduct Authority | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| UK Information Commissioner's Office | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Competition and Markets Authority | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Patent ve marka

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Google Patents | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| USPTO Patent Center | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| USPTO Trademark Search | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| WIPO PATENTSCOPE | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| WIPO Global Brand Database | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Espacenet | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| European Patent Office | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| EUIPO | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Türk Patent ve Marka Kurumu | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Lens.org Patents | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| FreePatentsOnline | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Justia Patents | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| The Trademark Search Company | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Sağlık ve biyoteknoloji dikeyi

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| PubMed | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: ağ hatası (bağlantı kurulamadı) |
| ClinicalTrials.gov | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: ağ hatası (bağlantı kurulamadı) |
| WHO | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| U.S. Food and Drug Administration | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| European Medicines Agency | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TİTCK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Cochrane Library | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| NICE | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| CDC | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ECDC | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Orphanet | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| DrugBank | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| OpenFDA | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| DailyMed | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| MedlinePlus | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| HealthData.gov | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Global Health Data Exchange | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Finans ve fintech dikeyi

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| SEC EDGAR | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| KAP | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TCMB EVDS | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| BDDK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SPK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| MASAK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Federal Reserve | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| FRED | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| World Bank | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| IMF | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: yönlendirme limiti aşıldı |
| European Central Bank | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| European Banking Authority | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Bank for International Settlements | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Financial Conduct Authority | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Companies House | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Open Banking UK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Nasdaq | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| NYSE | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Borsa İstanbul | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Yahoo Finance | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Finance | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Investing.com | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TradingView | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| CoinMarketCap | ✅ Tamam | çekildi ve tamamlandı — sitemap.xml |
| CoinGecko | ✅ Tamam | çekildi ve tamamlandı — sitemap.xml |
| DefiLlama | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Eğitim dikeyi

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| U.S. Department of Education | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| National Center for Education Statistics | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| UNESCO Institute for Statistics | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| OECD Education | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| YÖK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| YÖK Atlas | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| MEB | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ÖSYM | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Coursera | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| edX | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Udemy | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Skillshare | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Class Central | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| FutureLearn | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Khan Academy | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| G2 Education Software | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Capterra Education Software | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Gayrimenkul ve inşaat dikeyi

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Zillow | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Redfin | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Realtor.com | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Trulia | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Rightmove | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Zoopla | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Idealista | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Immobiliare.it | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Seloger | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ImmobilienScout24 | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Sahibinden Emlak | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Hepsiemlak | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Emlakjet | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Endeksa | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Tapu ve Kadastro Genel Müdürlüğü | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TÜİK Konut İstatistikleri | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| RICS | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| U.S. Census Building Permits | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Seyahat, konaklama ve mobilite dikeyi

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Booking.com | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Airbnb | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Expedia | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Hotels.com | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Agoda | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Tripadvisor | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Skyscanner | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Kayak | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Travel | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Hostelworld | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Vrbo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| GetYourGuide | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Viator | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Rome2Rio | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Uber | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Lyft | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Bolt | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| BlaBlaCar | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Moovit | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| OpenStreetMap | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| FlightAware | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Flightradar24 | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Yeme-içme ve teslimat dikeyi

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Google Maps | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Yelp | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Tripadvisor | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| OpenTable | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Foursquare | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Uber Eats | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| DoorDash | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Grubhub | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Deliveroo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Just Eat | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Yemeksepeti | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Getir | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Trendyol Yemek | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Migros Yemek | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Zomato | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TheFork | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Michelin Guide | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Oyun dikeyi

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Steam | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: yanıt, runner boyut limitini aştı |
| Epic Games Store | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| GOG | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| itch.io | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| PlayStation Store | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Xbox Store | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Nintendo eShop | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Twitch | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| YouTube Gaming | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SteamDB | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| VG Insights | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Newzoo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Game Developer | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Metacritic | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| OpenCritic | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Reddit | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: robots.txt bu yolu yasaklıyor |
| BoardGameGeek | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |

### Yapay zekâ modeli, veri seti ve agent ekosistemi

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Hugging Face | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: bot koruması / doğrulama duvarı |
| GitHub | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: yanıt, runner boyut limitini aştı |
| Papers with Code | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| arXiv | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| OpenRouter | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML |
| Replicate | ✅ Tamam | çekildi ve tamamlandı — ana sayfa HTML, sitemap.xml |
| Together AI | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Artificial Analysis | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| LMSYS Chatbot Arena | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Stanford HELM | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Kaggle | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: kaynak ulaşılamaz |
| Google Dataset Search | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| AWS Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Azure Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Cloud Marketplace | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| LangChain Integrations | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| LlamaIndex Integrations | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Smithery | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Glama | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| MCP.so | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| PulseMCP | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Composio | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Zapier | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Make | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Haber, basın ve sektör yayınları

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Google News | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Bing News | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Reuters | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: robots.txt bu yolu yasaklıyor |
| Associated Press | ✅ Tamam | çekildi ve tamamlandı — sitemap.xml |
| Bloomberg | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Financial Times | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| The Wall Street Journal | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| CNBC | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TechCrunch | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| The Verge | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Wired | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Ars Technica | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| VentureBeat | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Business Insider | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Forbes | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Fast Company | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Harvard Business Review | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| MIT Technology Review | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Sifted | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| EU-Startups | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Crunchbase News | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Axios | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Rest of World | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Webrazzi | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| egirişim | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| StartupCentrum | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Bloomberg HT | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Ekonomim | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Dünya | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Anadolu Ajansı | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Anket, birincil doğrulama ve kullanıcı araştırması platformları

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Typeform | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Forms | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SurveyMonkey | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Tally | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Jotform | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Qualtrics | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| User Interviews | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Respondent | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Prolific | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| UserTesting | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| UserZoom | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Maze | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Lookback | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| dscout | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Wynter | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| PickFu | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Pollfish | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Centiment | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Great Question | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Sprig | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Hotjar | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Microsoft Clarity | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| UsabilityHub | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Lyssna | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Fiyat, teknoloji ve pazar sinyali karşılaştırma kaynakları

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| G2 | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: bot koruması / doğrulama duvarı |
| Capterra | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: bot koruması / doğrulama duvarı |
| GetApp | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| SaaSworthy | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Vendr | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Tropic | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Vertice | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Sastrify | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Cloudorado | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| CloudPrice | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Vantage | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Infracost | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| AWS Pricing Calculator | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Azure Pricing Calculator | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Google Cloud Pricing Calculator | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Product Hunt | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: bot koruması / doğrulama duvarı |
| AppSumo | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| StackShare | ❌ Eksik | çekilemedi — robots.txt aşamasında durdu: kota aşımı (rate limit) |
| BuiltWith | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Wappalyzer | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

### Türkiye startup ve teknoloji ekosistemi

| Kaynak | Durum | Teknik ayrıntı |
|---|---|---|
| Webrazzi | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| egirişim | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| StartupCentrum | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| StartupMarket | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| startups.watch | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Türkiye Girişimcilik Vakfı | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TÜBİTAK | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| KOSGEB | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Bilişim Vadisi | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Teknopark İstanbul | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| İTÜ Çekirdek | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| ODTÜ Teknokent | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Yıldız Teknopark | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TÜSİAD | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| TOBB | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Endeavor Türkiye | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Keiretsu Forum Türkiye | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Galata Business Angels | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Arya Women Investment Platform | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| Founder Institute Türkiye | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |
| LinkedIn | ⚠️ Kısmi | kısmen çekildi — yalnızca robots.txt; asıl içerik engeli: robots.txt bu yolu yasaklıyor |
| Meetup | ❌ Eksik | çekilmedi — resmî domain otomatik tespit edilemedi |

---

## 9. Bu raporun bitirdiği ve bitirmediği iş

**Bitti (görev maddesi 1):** 636 kaynağın her biri için durum, sebebiyle birlikte netleştirildi; sayılar üç bağımsız koşu ve iki ayrı dokümanla doğrulandı.

**Sıradaki iş (görev maddesi 2 — eksik siteler için veri çekimi), öncelik sırasıyla:**

| # | İş | Etkilenen kaynak | Neden öncelikli |
|---:|---|---:|---|
| 1 | `adaptive_domain_pass.py` mandal hatasını düzeltmek | 546 | Tek hata, kaynakların %86'sını kilitliyor |
| 2 | Runner limitlerini yükseltmek (`response_too_large`, redirect) | 9 | Karşı taraf engellemiyor, kendi limitimiz |
| 3 | Geçici hataları yeniden denemek | 15 | Muhtemelen kalıcı engel değil |
| 4 | `challenge` kaynakları için resmî API/alternatif yol | 22 | Gerçek bot koruması, ayrı strateji gerekir |
| 5 | `robots_disallowed` kaynaklarını kapsam dışına almak | 5 | Politika gereği çekilmemeli, "eksik" sayılmamalı |

**Görev maddesi 3 (anahtar kelime ile arama)** bu raporun kapsamı dışındadır; `ACQUISITION-METHODS.md` ve `results/duckduckgo-*.json` pilotları o maddenin başlangıç noktasıdır.
