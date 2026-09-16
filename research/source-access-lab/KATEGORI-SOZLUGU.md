# Kategori Sözlüğü v1

**Hazırlayan:** Ayselin Aydoğdu  
**Üretim:** `kategori_sozlugu.py` — elle yazılmaz, koddan üretilir  
**Pilot kayıt:** 97 · **Kaynak ailesi:** 32 · **Eksik kaydı:** 3

Bu sözlük dört ekseni **ayrı** tutar. Karıştırılmaları sistematik hataya
yol açar: bir inceleme sitesi (kaynak ailesi) hem B2B SaaS hem
data/analytics ürünü (ürün tipi) araştırmasında kullanılır; elimizdeki
dosya bir ana sayfaysa (belge türü) hiçbir soru (araştırma niyeti) için
kanıt üretmez. Üç eksen ayrı olmadan bu cümle kurulamaz.

**Temel kural:** hiçbir etiket site adına bakarak verilmez. Her etiket
ya açılmış bir artefakta ya da açık bir eksik-veri kaydına bağlıdır.

---

## Eksen 1 — Ürün tipi

Kaynak: kanonik görev metni (`tasks/ayselin-task/README.md`, T01).

### `b2b-saas` — B2B SaaS

**Tanım:** İşletmelerin abonelikle kullandığı, kurumsal satın almaya konu web yazılımı

- **Dahil:** CRM, faturalama, İK yazılımı, proje yönetimi
- **Hariç:** Bireysel kullanıcıya satılan mobil uygulama; ücretsiz açık kaynak kütüphane
- **Hedef kullanıcı:** İşletme; satın alma kararı departman ya da yönetim düzeyinde
- **Satın alma:** Abonelik, koltuk başına ya da kullanım bazlı

### `developer-tool` — Developer tool / API / agent

**Tanım:** Geliştiricinin kendi ürününe kattığı kütüphane, SDK, API ya da agent

- **Dahil:** npm paketi, ödeme API'si, model/agent altyapısı, CLI aracı
- **Hariç:** Son kullanıcıya satılan uygulama; geliştiricilerin kullandığı ama ürüne girmeyen SaaS
- **Hedef kullanıcı:** Geliştirici; karar çoğu zaman teknik ekipte
- **Satın alma:** Ücretsiz/açık kaynak, kullanım bazlı ya da kurumsal lisans

### `consumer-mobile-web` — Consumer mobile / web ürünü

**Tanım:** Son kullanıcıya doğrudan sunulan mobil uygulama ya da web ürünü

- **Dahil:** Sağlık takip uygulaması, bulmaca oyunu, not tutma uygulaması
- **Hariç:** İşletmeye satılan panel; geliştirici kütüphanesi
- **Hedef kullanıcı:** Birey; karar tek kişide
- **Satın alma:** Ücretsiz, uygulama içi satın alma ya da bireysel abonelik

### `marketplace` — Two-sided marketplace

**Tanım:** Arz ve talebi buluşturan, iki taraflı ağ etkisi olan platform

- **Dahil:** Freelancer platformu, ikinci el pazar yeri, eklenti mağazası
- **Hariç:** Tek taraflı e-ticaret mağazası; yalnız içerik yayınlayan site
- **Hedef kullanıcı:** İki ayrı taraf; her biri ayrı araştırma gerektirir
- **Satın alma:** Komisyon, listeleme ücreti

### `local-service` — Local-service platform

**Tanım:** Belirli bir coğrafyada hizmet arz ve talebini eşleştiren ürün

- **Dahil:** Randevu sistemi, usta bulma, yerel teslimat
- **Hariç:** Coğrafyadan bağımsız SaaS; küresel pazar yeri
- **Hedef kullanıcı:** Yerel işletme ve o bölgedeki tüketici
- **Satın alma:** Abonelik ya da işlem başına komisyon

### `ecommerce-enablement` — E-commerce enablement

**Tanım:** E-ticareti mümkün kılan yazılım; ürünü kendisi satmaz

- **Dahil:** Mağaza altyapısı, ödeme/kargo entegrasyonu, stok yönetimi
- **Hariç:** Fiziksel ürün satan mağazanın kendisi
- **Hedef kullanıcı:** Satıcı işletme
- **Satın alma:** Abonelik ya da işlem yüzdesi

### `data-analytics` — Data / analytics ürünü

**Tanım:** Veri toplayan, işleyen ya da ölçüm sunan ürün

- **Dahil:** Trafik analitiği, pazar istihbaratı, BI paneli
- **Hariç:** Veriyi yalnız kendi işinde kullanan operasyonel yazılım
- **Hedef kullanıcı:** Analist, pazarlamacı, yönetim
- **Satın alma:** Abonelik, veri hacmi bazlı

### `regulated-vertical` — Regüle dikey yazılım

**Tanım:** Yasal düzenlemeye tabi bir alanda çalışan yazılım

- **Dahil:** Sağlık kaydı yazılımı, fintech, hukuk teknolojisi
- **Hariç:** Aynı sektöre satılan ama düzenlemeye tabi olmayan araç
- **Hedef kullanıcı:** Düzenlemeye tabi kurum
- **Satın alma:** Kurumsal lisans; uyum maliyeti ayrı kalem

**Çoklu etiket:** Bir fikir birden fazla ürün tipine uyabilir. Ana tip araştırmanın ayırt edici sorusunu cevaplayandır; diğeri katman olarak eklenir (görev 1'in katman kuralı). Örnek: mobil bulmaca oyunu → ana tip consumer, dağıtım katmanı app store.

**Belirsiz durumu:** Fikir hiçbir tipe bağlanamıyorsa 'belirlenemedi' yazılır ve iş durur. Sessizce bir varsayılana düşmek bütün seçimi yanlış yapar.

### Görev 1 kategorileriyle eşleme

| Görev 1 kategorisi | Ürün tipi | Not |
|---|---|---|
| `b2b-web-yazilimi` | `b2b-saas` | — |
| `eklenti-entegrasyon` | `marketplace` | Eklenti ürünü ile eklenti mağazası farklı şeyler; ürün tipi olarak marketplace'e eşlendi, doğrulanmalı |
| `gelistirici-araci` | `developer-tool` | — |
| `mobil-uygulama` | `consumer-mobile-web` | — |
| `oyun` | `consumer-mobile-web` | Kanonik listede ayrı oyun tipi yok; consumer'a eşlendi ama kaynak paketi belirgin şekilde farklı |
| `yapay-zeka-urunu` | `developer-tool` | — |
| `yerel-hizmet` | `local-service` | — |

Kanonik listede `oyun` ve `eklenti-entegrasyon` için ayrı tip yok;
ikisi de eşlendi ama kaynak paketleri belirgin biçimde farklı.
**Mentöre sorulacak nokta budur.**

---

## Eksen 2 — Kaynak ailesi

Kaynağın ne tür bir yayın olduğu. Ürün tipiyle **karıştırılmaz**: bir
aile birden çok ürün tipine hizmet eder ve bu bir hata değildir.

Envanterde 32 aile var;
tanımları `KATEGORI-KAYNAK.csv`'nin `kaynak_grubu` sütununda.

**Çoklu etiket:** Bir kaynak birden fazla aileye ait olabilir ve bu bir hata değildir: G2 hem inceleme sitesi hem fiyat karşılaştırma kaynağıdır. Tüm aileler kaydedilir, biri seçilmez.

**Belirsiz durumu:** Kaynak hiçbir aileye atanamıyorsa 'atanmamis' yazılır; kaynak silinmez, envanterde kalır.

---

## Eksen 3 — Belge türü

Elimizdeki **dosyanın** ne olduğu. Ancak açarak bilinir.

| Tür | Tanım | Kanıt kuralı | Araştırma değeri |
|---|---|---|---|
| `ana-sayfa` | Kaynağın kök ya da tanıtım sayfası; kayıt listesi taşımaz | URL yolu kök, JSON-LD yalnız Organization/WebSite, liste işareti yok | Kaynağın varlığını doğrular; ölçüm kanıtı üretmez |
| `liste-sayfasi` | Birden çok kaydı sıralayan dizin ya da kategori sayfası | En az 5 itemListElement girdisi. Tek bir ItemList yeterli değildir: gezinme menüleri de ItemList olarak işaretlenir | Arz yoğunluğu ve rakip listesi için kullanılabilir |
| `kayit-sayfasi` | Tek bir ürün, uygulama ya da işletmenin sayfası | JSON-LD Product/SoftwareApplication/LocalBusiness tekil nesne | Puan, fiyat ve sağlayıcı alanları buradan gelir |
| `inceleme-sayfasi` | Kullanıcı yorumlarının gövdesini taşıyan sayfa | En az 3 Review nesnesi. Tek bir Review pazarlama sayfasındaki müşteri görüşü olabilir; yorum gövdesi sayılmaz | Şikâyet ve memnuniyet kanıtı |
| `fiyatlandirma-sayfasi` | Katman ve fiyatların yayımlandığı sayfa | URL yolunda pricing/plans, ya da fiyat DEĞERİ taşıyan en az 2 Offer. Pazarlama sayfaları tek bir boş Offer gömer | Ödeme isteği ve fiyat bandı |
| `dokumantasyon` | Teknik kullanım belgesi, API referansı | URL yolunda docs/documentation/reference/api | Yetenek ve entegrasyon maliyeti |
| `yazi` | Haber, blog ya da makale | JSON-LD Article/NewsArticle/BlogPosting | Olay ve duyuru kanıtı; ölçüm değil |
| `besleme` | RSS/Atom akışı; başlık ve özet taşır, tam içerik taşımaz | Yöntem rss_feed; item/entry etiketleri | Tarih ve başlık; içerik için bağlantıya gidilir |
| `arama-sonucu` | Sorgu sonucu sayfası | URL'de q=/search parametresi | ADAY KEŞİF — kanıt değil; hedef içerik ayrıca çekilir |
| `sitemap` | Site haritası; yalnız adres listesi | Yöntem sitemap_xml; <loc> etiketleri | ADAY KEŞİF — kanıt değil |
| `politika-dosyasi` | robots.txt gibi erişim politikası belgesi | Yöntem robots_preflight | Erişim kuralı; araştırma malzemesi değil |
| `api-yaniti` | Yapılandırılmış API cevabı | MIME application/json ve tanınan anahtarlar | En güvenilir alan kaynağı |
| `belirsiz` | Açıldı ama türü belirlenemedi | Hiçbir kural eşleşmedi; ham sinyaller kayda geçer | Kullanılmaz; elle incelenmeli |

**Kök yolu kuralı.** Kök yoldaki bir sayfa varsayılan olarak ana
sayfadır. Pazarlama ana sayfaları kendilerini tarif eden JSON-LD gömer:
kendi ürününü `Product`, kendi müşteri görüşünü `Review`, kendi haberini
`Article` olarak. Bunları kayıt ya da inceleme sayfası saymak, kabul
kriterinin yasakladığı şeydir. Kök yol ancak listelenmiş kayıtlara dair
güçlü kanıt varsa ezilir: en az 5 `itemListElement` ya da 10 `Review`.

Ana sayfa her zaman `/` değildir: `base.com/en-US/home/` ve
`bigspy.com/en` de kök sayılır — dil/bölge öneki ve `home`/`index`
segmentleri atıldıktan sonra yol boşsa kök kabul edilir.

**Çoklu etiket:** Bir belge birden fazla türe uyabilir. Birincil tür BELGE_TURU_SIRASI'ndaki ilk eşleşendir; diğerleri 'ikincil_belge_turu' alanında saklanır, atılmaz.

**Belirsiz durumu:** Dosya açıldı ama hiçbir kural eşleşmediyse 'belirsiz' yazılır ve ham sinyaller kayda geçer. Tahmin edilmez.

---

## Eksen 4 — Araştırma niyeti

Görev 2'de tanımlanan 14 soru bu eksendir; `KATEGORI-SORU.csv`'den okunur,
burada yeniden tanımlanmaz. Ayrı eksen olmasının sebebi: aynı belge türü
farklı niyetlere farklı değer taşır. Bir inceleme sayfası `sikayet-ne`
için birincil kanıt, `giris-engeli` için değersizdir.

**Çoklu etiket:** Bir belge birden fazla niyete hizmet edebilir. Niyet belgeye değil, belge × soru çiftine bağlanır.

**Belirsiz durumu:** Belgenin hangi soruya hizmet ettiği belirsizse niyet atanmaz; belge kayıtta kalır, kanıt sayılmaz.

---

## Pilot sonucu

| Belge türü | Kayıt |
|---|---:|
| `ana-sayfa` | 72 |
| `belirsiz` | 13 |
| `api-yaniti` | 6 |
| `politika-dosyasi` | 2 |
| `besleme` | 2 |
| `sitemap` | 1 |
| `fiyatlandirma-sayfasi` | 1 |

**97 kayıttan 72'i ana sayfa.** Yalnızca
**9 kayıt** ölçüm kanıtı üretiyor.

Bu, kabul kriterinin doğrudan karşılığıdır: içerik bulunmayan yerde
yorum ya da fiyat verisi varsayılmaz. Envanterdeki kaynakların çoğuna
erişildi ama elimizdeki dosya kaynağın ana sayfasıdır; alanı taşıyan iç
sayfa çekilmemiştir.

## Eksik kayıtları

| Kaynak ailesi | İstenen | Bulunan | Neden |
|---|---:|---:|---|
| Kitle fonlaması platformları | 3 | 1 | ailedeki kaynakların açılabilir artefaktı yok; erişilemedi ya da yalnız politika dosyası indi |
| (yüzey temsili: packagist_package_list) | 1 | 0 | gövde saklanmamış (saklama=kosu_json_icinde, bayt=0); elde yalnız sha256 7d6b5d1eac7367ff ve URL https://packagist.org/packages/list.json?vendor=symfony var — açılacak içerik yok |
| (yüzey temsili: wayback_availability) | 1 | 0 | gövde saklanmamış (saklama=kosu_json_icinde, bayt=0); elde yalnız sha256 9136bff3182180fc ve URL https://archive.org/wayback/available?url=example.com var — açılacak içerik yok |

