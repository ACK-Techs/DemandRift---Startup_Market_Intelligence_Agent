# Ürün Kategorileri — kaynak seçimini değiştiren ayrım

Bir yazılım ürünü için pazar analizi yapılırken 636 kaynağın hepsine bakmak
anlamsız: fitness uygulaması araştırırken SEC şirket raporlarına, kurumsal
faturalama yazılımı araştırırken App Store yorumlarına ihtiyaç yok. Bu belge
ürünleri, **hangi kaynaklara bakılacağını gerçekten değiştiren** kategorilere
ayırır.

## Kategorinin gerçek olup olmadığını sınayan kural

> Kategori yalnız etiket olmamalı; farklı araştırma niyeti veya kaynak paketi
> doğurmalıdır.

Uygulanabilir hâli: **iki ürün farklı kategorideyse, ilk bakılacak kaynak
listeleri de farklı olmalıdır.**

| Ürün çifti | Kaynak paketi | Sonuç |
|---|---|---|
| Fitness uygulaması ↔ Meditasyon uygulaması | İkisi de App Store, Play Store, Sensor Tower | Aynı kategori — "fitness" bir konu, kategori değil |
| Fitness uygulaması ↔ B2B faturalama yazılımı | Biri app store'lar, diğeri G2/Capterra/LinkedIn Jobs | Ayrı kategori ✓ |
| React ile yazılmış SaaS ↔ Vue ile yazılmış SaaS | Aynı kaynaklar | Kategori değil |

Bu kurala göre teknoloji yığını, fiyatlandırma modeli ve şirket büyüklüğü gibi
ayrımlar kategori üretmez — kaynak listesini değiştirmezler.

## Kategoriler nereden türetildi

Havadan tanımlanmadı. `SITE-LISTESI.md` 636 kaynağı zaten 30 başlık altında
tutuyor; her başlığa **"hangi ürün tipine hizmet ediyor"** diye soruldu ve üç
gruba ayrıldı:

| Grup | Başlık | Kaynak | Neden |
|---|---:|---:|---|
| **Ortak** | 12 | 283 | Her üründe kullanılır (haber, arama motorları, trend, patent, şirket verisi). Ayırt etmediği için kategori olamaz |
| **Kategori** | 10 | 224 | Ürünün nerede yaşadığını ya da kimin satın aldığını belirler |
| **Ek** | 8 | 165 | Dikey ve bölge. Tek başına yetmez: "sağlık ürünü" demek mobil mi web mi olduğunu söylemez |

Üç başlık tek kategoride birleşti — SaaS inceleme siteleri, fiyat karşılaştırma
ve iş ilanları hep birlikte **B2B web yazılımı** araştırmasını besliyor. Ayrı
kategori yapılsalardı üçü de aynı ürün tipini işaret ederdi, yani kuralı
çiğnerlerdi.

## Ana kategoriler

Ürün bunlardan **birine** girer. Sayılar: kategoriye özel kaynak / verisi
çekilmiş olan.

| Kategori | Tanım | Kaynak | Çekildi |
|---|---|---:|---:|
| **Mobil tüketici uygulaması** | Uygulama mağazaları üzerinden dağıtılan uygulama | 13 | 11 |
| **B2B web yazılımı** | İşletmelerin abonelikle kullandığı web yazılımı | 64 | 53 |
| **Geliştirici aracı / kütüphane** | Paket, SDK, CLI ya da altyapı aracı | 34 | 30 |
| **Eklenti / entegrasyon** | Var olan bir platformun üzerine kurulan eklenti | 25 | 25 |
| **Yapay zekâ ürünü / agent** | Model, veri seti, agent ya da YZ altyapısı | 24 | 22 |
| **E-ticaret / fiziksel ürün** | Pazar yerlerinde satılan ürün ve onu destekleyen yazılım | 24 | 19 |
| **Oyun** | Dijital dağıtım platformlarında yayınlanan oyun | 17 | 12 |
| **Yerel hizmet ürünü** | Belirli bir coğrafyada işletme/tüketiciye hizmet veren ürün | 23 | 17 |

Her kategoriye ayrıca **283 kaynaklık ortak havuz** eklenir.

Kategoriler birbirinden ayrık: 224 çekirdek kaynaktan yalnızca 3'ü iki
kategoride birden geçiyor (Tripadvisor ve Yelp hem B2B hem yerel hizmette,
GitHub hem geliştirici aracı hem yapay zekâ ürününde). Bu örtüşmeler meşru —
o kaynaklar gerçekten iki araştırmayı da besliyor.

## Kategori seçim kuralı

Bir ürün birden fazla kategoriye uyabilir. On gerçek ürün fikriyle sınandığında
sekizi tek kategoriye düştü, ikisi kararsız kaldı:

| Ürün | Kararsızlık |
|---|---|
| Mobil bulmaca oyunu | `oyun` mu `mobil-uygulama` mı? |
| Yerel esnaf için randevu uygulaması | `yerel-hizmet` mi `mobil-uygulama` mı? |

Bu bir çelişki değil, **katman** durumu: mobil oyun için hem tür doygunluğunu
gösteren oyun kaynakları (SteamDB, Metacritic) hem dağıtımı gösteren mağaza
kaynakları gerekli. Kural şu:

> **Ana kategori, araştırmanın ayırt edici sorusunu cevaplayandır.** İkinci
> kategorinin çekirdek paketi *katman* olarak eklenir.

| Ürün | Ana kategori | Katman | Toplam çekirdek |
|---|---|---|---:|
| Mobil bulmaca oyunu | `oyun` (tür doygun mu, oyuncu ne ödüyor) | `mobil-uygulama` | 30 |
| Yerel esnaf randevu uygulaması | `yerel-hizmet` (işletme yoğunluğu, fiyatlar) | `mobil-uygulama` | 36 |

Katman olabilecek kategoriler `URUN-KATEGORILERI.csv` içindeki
`katman_olabilir` sütununda işaretli: `mobil-uygulama`, `eklenti-entegrasyon` ve
`yapay-zeka-urunu`. Bunlar dağıtım/teknoloji katmanı olduğu için başka bir
kategorinin üstüne binebiliyor — bir ürün hem "B2B web yazılımı" hem "yapay zekâ
ürünü" olabilir. Diğer beş kategori (b2b-web-yazilimi, gelistirici-araci,
eticaret-fiziksel-urun, oyun, yerel-hizmet) birbirinin üstüne binmez; ürün
bunlardan yalnız birine girer.

## Ek paketler

Kategori değil; ana kategorinin üstüne eklenir.

| Ek | Kaynak | Ne zaman eklenir |
|---|---:|---|
| Sağlık | 17 | Ürün sağlık, tıp ya da biyoteknoloji alanındaysa |
| Fintech | 26 | Finans, ödeme ya da bankacılık alanındaysa |
| Eğitim | 17 | Eğitim ya da öğrenme alanındaysa |
| Gayrimenkul | 18 | Gayrimenkul ya da inşaat alanındaysa |
| Seyahat | 22 | Seyahat, konaklama ya da mobilite alanındaysa |
| Yeme-içme | 17 | Yeme-içme ya da teslimat alanındaysa |
| Regüle sektör | 28 | Yasal düzenlemeye tabi bir alandaysa |
| Türkiye pazarı | 22 | Türkiye pazarı hedefleniyorsa |

## Nasıl kullanılır

**Örnek 1 — "Diyabet hastaları için mobil takip uygulaması"**

| Katman | Kaynak |
|---|---:|
| Kategori: mobil uygulama | 13 |
| Ek: sağlık | 17 |
| Ortak havuz | 283 |

Önce bakılacak: **30 kaynak** (App Store, Play Store, Sensor Tower,
ClinicalTrials.gov, FDA…). Geri kalanı destekleyici.

**Örnek 2 — "Muhasebeciler için fatura yazılımı"**

| Katman | Kaynak |
|---|---:|
| Kategori: B2B web yazılımı | 64 |
| Ek: fintech + regüle sektör | 54 |
| Ortak havuz | 283 |

Önce bakılacak: **118 kaynak** (G2, Capterra, LinkedIn Jobs, SPK, BDDK…).
App Store'a hiç bakılmıyor.

İki örnekte de bakılan yerler tamamen farklı — kategorinin "etiket olmaması"
bunu ifade ediyor.

## Çıktı dosyaları

| Dosya | İçerik |
|---|---|
| `URUN-KATEGORILERI.csv` | Kategori başına bir satır: tanım, araştırma niyeti, kaynak sayıları |
| `KATEGORI-KAYNAK.csv` | 674 satır — hangi kategori, hangi kaynak, rolü, ne sağladığı, hangi aramanın yapılacağı, o kaynağın gerçek durumu |
| `build_product_categories.py` | İkisini `SITE-LISTESI.md` + kaynak defteri + arama kataloğundan üretir |

`KATEGORI-KAYNAK.csv` bir satırı şöyle okunur:

> **mobil-uygulama** kategorisi için **Google Play Store** bir **çekirdek**
> kaynaktır; oradan **uygulama listeleri, kullanıcı yorumları, puan dağılımı**
> alınır, arama **`{urun} app`** kalıbıyla yapılır. Kaynağın durumu **çekildi**,
> arama yolu **opensearch**.

`{urun}` kullanıcının fikriyle değiştirilir: "fitness" denirse `fitness app`,
"meditasyon" denirse `meditation app`.

Son üç sütun (`durum`, `adres`, `arama_yolu`) kaynak defterinden ve arama
kataloğundan geliyor. Kategoriyi etiket olmaktan çıkaran şey bu: satırda
kaynağın gerçekten çalışıp çalışmadığı ve nasıl sorgulanacağı yazılı.

```bash
python3 build_product_categories.py
```
