# Veri Envanteri ve Kapsama Raporu

**Hazırlayan:** Ayselin Aydoğdu  
**Üretim:** `veri_envanteri.py` — elle yazılmaz, koddan üretilir  
**Kanonik kaynak:** 636 (`source_manifest.json`)

> **`erişildi` karar kanıtı değildir.** Erişim durumu, kaynağın yanıt
> verdiğini gösteren bir snapshot'tır; üretime hazır veri ya da araştırma
> sorusuna uygun kanıt anlamına gelmez. İçerik durumu ayrı bir sütundur.

## 1. Erişim durumu — deftere göre

| Durum | Kaynak |
|---|---:|
| `cekildi` | 534 |
| `erisim_yok` | 54 |
| `kismi` | 44 |
| `adres_yok` | 4 |

## 2. İçerik durumu — bu checkout'ta dosya açılarak

Erişim durumundan **bağımsız** ölçülür: dosya gerçekten var mı, içinde ne var.

| Durum | Kaynak | Anlamı |
|---|---:|---|
| `gercek-icerik` | 284 | Görünür metin taşıyan sayfa |
| `dosya-yok` | 171 | Bu checkout'ta açılabilir dosya yok |
| `arsiv` | 83 | Common Crawl kopyası; canlı değil |
| `js-kabugu` | 44 | HTTP 200 ve büyük gövde ama görünür metin yok |
| `aday-kesif` | 22 | Sitemap/XML; **kanıt değil**, aday URL sinyali |
| `politika` | 14 | robots.txt; erişim kuralı, araştırma malzemesi değil |
| `besleme` | 9 | RSS; başlık ve özet taşır, tam içerik taşımaz |
| `api-yaniti` | 9 | Yapılandırılmış kayıt — en güvenilir |

**465 kaynakta açılabilir dosya var**; kalan 171 kaynakta yok.

## 2b. Erişim durumu × içerik durumu

Raporun en önemli tablosu budur: **erişim etiketi ile elde gerçekten ne
olduğu aynı şey değildir.**

| Erişim | `api-yaniti` | `gercek-icerik` | `besleme` | `arsiv` | `js-kabugu` | `aday-kesif` | `politika` | `dosya-yok` |
|---|---|---|---|---|---|---|---|---|
| `cekildi` | 9 | 284 | 9 | 83 | 44 | 22 | 2 | 81 |
| `erisim_yok` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 54 |
| `kismi` | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 32 |
| `adres_yok` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 |

`cekildi` etiketli **534** kaynaktan yalnız **284**'ünde
görünür metin taşıyan içerik var. **81** kaynakta ise bu checkout'ta
açılabilir tek dosya yok — etiket erişimi anlatıyor, elde olanı değil.

## 3. İncelendi durumu

| | Kaynak |
|---|---:|
| Fiilen açılıp incelendi (DR-L02) | 95 |
| Açılabilir ama henüz incelenmedi | 370 |
| Açılacak dosyası yok | 171 |

İncelenmiş sayılan her kaynak `PILOT-KAYITLAR.csv`'de artefakt hash'iyle
kayıtlıdır. **Elde olmayan dosya incelenmiş gösterilmez.**

## 3b. DR-L02 sözlüğüyle ilişki

Bu envanter mevcut sınıflandırmayı **yeniden yazmaz, doğrular.** İki
çıktı farklı eksenlerde durur ve karıştırılmamalıdır:

| | Sorduğu soru |
|---|---|
| `PILOT-KAYITLAR.csv` · `belge_turu` | Bu dosya **ne tür bir belge**? |
| `VERI-ENVANTERI.csv` · `icerik_durumu` | Bu dosyadan **metin çıkarılabiliyor mu**? |

Bir ana sayfa hem `ana-sayfa` (belge türü) hem `js-kabugu` (içerik
durumu) olabilir: türü ana sayfadır, ama tarayıcıda üretildiği için
metni alınamaz. Çelişki değil, iki ayrı ölçüdür.

Doğrulama: pilotta açılan 95 kaynağın tamamı bu envanterde var ve
**envanterin 'dosyası yok' dediği hiçbir kaynak pilotta açılmış
görünmüyor.**

## 4. Kaynak ailesi bazında kapsama

| Kaynak ailesi | Toplam | Açılabilir | İncelendi | Bekleyen |
|---|---:|---:|---:|---:|
| (aile atanmamış) | 16 | 12 | 0 | 12 |
| Akademik araştırma ve bilimsel yayınlar | 33 | 20 | 5 | 15 |
| Anket | 24 | 20 | 3 | 17 |
| DNS | 30 | 11 | 3 | 8 |
| Dijital ürün ve şablon pazar yerleri | 6 | 6 | 3 | 3 |
| Domain | 30 | 11 | 3 | 8 |
| Eğitim dikeyi | 17 | 14 | 3 | 11 |
| Finans ve fintech dikeyi | 26 | 19 | 3 | 16 |
| Fiyat | 20 | 19 | 4 | 15 |
| Gayrimenkul ve inşaat dikeyi | 18 | 12 | 3 | 9 |
| Genel web arama ve keşif | 16 | 11 | 3 | 8 |
| Haber | 30 | 21 | 4 | 17 |
| Kamu verisi ve istatistik | 25 | 16 | 3 | 13 |
| Kitle fonlaması platformları | 2 | 1 | 1 | 0 |
| Mobil uygulama mağazaları | 13 | 7 | 3 | 4 |
| Oyun dikeyi | 17 | 10 | 3 | 7 |
| Patent ve marka | 13 | 6 | 3 | 3 |
| Regülasyon ve hukuk kaynakları | 28 | 20 | 3 | 17 |
| Reklam kütüphaneleri ve pazarlama sinyalleri | 16 | 13 | 3 | 10 |
| SEO | 24 | 23 | 3 | 20 |
| SaaS | 25 | 18 | 3 | 15 |
| Sağlık ve biyoteknoloji dikeyi | 17 | 11 | 3 | 8 |
| Seyahat | 22 | 18 | 3 | 15 |
| Sosyal ağlar ve açık topluluklar | 24 | 17 | 3 | 14 |
| Tarayıcı | 25 | 23 | 3 | 20 |
| Trafik | 24 | 23 | 3 | 20 |
| Türkiye startup ve teknoloji ekosistemi | 22 | 15 | 3 | 12 |
| Yapay zekâ modeli | 24 | 16 | 4 | 12 |
| Yazılım geliştirici ve teknik topluluklar | 34 | 27 | 6 | 21 |
| Yeme-içme ve teslimat dikeyi | 17 | 11 | 3 | 8 |
| Yerel işletme | 23 | 15 | 4 | 11 |
| anahtar kelime ve trend | 24 | 23 | 3 | 20 |
| basın ve sektör yayınları | 30 | 21 | 4 | 17 |
| birincil doğrulama ve kullanıcı araştırması platformları | 24 | 20 | 3 | 17 |
| e-ticaret ve CMS eklenti mağazaları | 25 | 23 | 3 | 20 |
| harita ve hizmet dizinleri | 23 | 15 | 4 | 11 |
| konaklama ve mobilite dikeyi | 22 | 18 | 3 | 15 |
| sertifika ve web footprint | 30 | 11 | 3 | 8 |
| teknoloji ve pazar sinyali karşılaştırma kaynakları | 20 | 19 | 4 | 15 |
| veri seti ve agent ekosistemi | 24 | 16 | 4 | 12 |
| yatırım ve startup verisi | 28 | 26 | 4 | 22 |
| yazılım ve hizmet inceleme siteleri | 25 | 18 | 3 | 15 |
| Ürün lansmanı ve startup toplulukları | 24 | 20 | 3 | 17 |
| İş ilanları ve yetenek talebi | 24 | 17 | 3 | 14 |
| Şirket | 28 | 26 | 4 | 22 |

## 5. İşlenemeyen kayıtlar

Toplam **754** artefakt kaydı işlenemedi. Silinmediler;
`ENVANTER-ISLENEMEYEN.csv` dosyasında nedeniyle duruyorlar.

| Neden | Kayıt |
|---|---:|
| gövde saklanmamış (saklama=kosu_json_icinde) | 696 |
| dizinde 'dosya' yazıyor ama bu checkout'ta yok | 58 |

