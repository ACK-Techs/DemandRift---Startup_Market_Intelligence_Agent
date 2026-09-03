# Pazar Analizi Kılavuzu

**Hazırlayan:** Ayselin Aydoğdu

DemandRift, geliştirilebilecek bir yazılım ürünü için pazar analizi yapacak.
Bunun için üç şeyin belirlenmesi gerekiyordu: hangi sitelerin kategori olarak ne
sağladığı, hangi verilerinin kullanılacağı ve hangi aramaların yapılacağı.

Bu kılavuz, o işi görev görev anlatır. Her görev bittikçe buraya bir bölüm
eklenir.

---

# Görev 1 — Ürün kategorilerini belirlemek

**İstenen:** Araştırılacak yazılım ürünlerini, kaynak seçimini gerçekten
etkileyen ayrık kategorilere bölmek. Kategori yalnız etiket olmamalı; farklı
araştırma niyeti veya kaynak paketi doğurmalıdır.

## 1.1 Problem

Elimizde 636 kaynak var ve hepsi her ürün için anlamlı değil:

| Ürün fikri | İşe yarayan kaynak | İşe yaramayan |
|---|---|---|
| Fitness uygulaması | App Store, Play Store, Sensor Tower | SEC EDGAR, Espacenet patent veritabanı |
| Kurumsal fatura yazılımı | G2, Capterra, LinkedIn Jobs | App Store, Play Store |

Aynı 636 kaynak, iki ürün için tamamen farklı alt kümeler. Kategori tanımlamanın
amacı bu alt kümeleri önceden belirlemek.

## 1.2 Kategorinin gerçek olup olmadığını sınayan kural

Görev kartındaki "kategori yalnız etiket olmamalı" şartını uygulanabilir bir
kurala çevirdik:

> **İki ürün farklı kategorideyse, ilk bakılacak kaynak listeleri de farklı
> olmalıdır.**

Bu kurala göre:

| Ürün çifti | Kaynak paketi | Sonuç |
|---|---|---|
| Fitness uygulaması ↔ Meditasyon uygulaması | İkisi de App Store, Play Store, Sensor Tower | **Aynı** kategori — "fitness" bir konu, kategori değil |
| Fitness uygulaması ↔ B2B fatura yazılımı | Biri app store'lar, diğeri G2/Capterra | **Ayrı** kategori ✓ |
| React ile yazılmış SaaS ↔ Vue ile yazılmış SaaS | Aynı kaynaklar | Kategori değil |

Buradan çıkan sonuç: teknoloji yığını, fiyatlandırma modeli ve şirket büyüklüğü
gibi ayrımlar kategori üretmez, çünkü kaynak listesini değiştirmezler.

## 1.3 Kategorileri nereden türettik

Havadan tanımlamadık. `SITE-LISTESI.md` dosyası 636 kaynağı zaten **30 başlık**
altında tutuyordu (bu dosya projede önceden vardı). Her başlığa tek bir soru
sorduk: **"Bu başlık hangi ürün tipine hizmet ediyor?"**

Cevaplar üç gruba ayrıldı:

| Grup | Başlık | Kaynak | Neden bu grupta |
|---|---:|---:|---|
| **Ortak** | 12 | 283 | Her üründe kullanılır (haber, arama motorları, trend, patent, şirket verisi). Hiçbir ürünü diğerinden ayırmadığı için kategori olamaz |
| **Kategori** | 10 | 224 | Ürünün nerede yaşadığını ya da kimin satın aldığını belirler |
| **Ek** | 8 | 167 | Dikey ve bölge. Tek başına yetmez: "sağlık ürünü" demek mobil mi web mi olduğunu söylemez |

**Neden 30 kategori yapmadık:** Üç sebeple. Birincisi, 12 başlık hiçbir ürünü
ayırt etmiyor (283 kaynak) — ortak havuzdurlar. İkincisi, bazı başlıklar aynı
ürün tipine hizmet ediyor: SaaS inceleme siteleri, fiyat karşılaştırma ve iş
ilanları üçü birden **B2B web yazılımı** araştırmasını besliyor; ayrı kategori
yapılsalardı aynı ürünü işaret ederlerdi ve kuralı çiğnerlerdi. Üçüncüsü, dikey
başlıklar tek başına yetmiyor.

## 1.4 Sonuç: 8 ana kategori

Ürün bunlardan birine girer. Sayılar: kategoriye özel kaynak / verisi çekilmiş
olan.

| Kategori | Tanım | Kaynak | Çekildi |
|---|---|---:|---:|
| `mobil-uygulama` | Uygulama mağazaları üzerinden dağıtılan uygulama | 13 | 11 |
| `b2b-web-yazilimi` | İşletmelerin abonelikle kullandığı web yazılımı | 64 | 53 |
| `gelistirici-araci` | Paket, SDK, CLI ya da altyapı aracı | 34 | 30 |
| `eklenti-entegrasyon` | Var olan bir platformun üzerine kurulan eklenti | 25 | 25 |
| `yapay-zeka-urunu` | Model, veri seti, agent ya da YZ altyapısı | 24 | 22 |
| `eticaret-fiziksel-urun` | Pazar yerlerinde satılan ürün ve destekleyen yazılım | 24 | 19 |
| `oyun` | Dijital dağıtım platformlarında yayınlanan oyun | 17 | 12 |
| `yerel-hizmet` | Belirli bir coğrafyada hizmet veren ürün | 23 | 17 |

Her kategoriye ayrıca **283 kaynaklık ortak havuz** eklenir (236'sının verisi
çekilmiş).

## 1.5 Sonuç: 8 ek paket

Bunlar kategori değil; ana kategorinin üstüne eklenir.

| Ek | Kaynak | Çekildi | Ne zaman eklenir |
|---|---:|---:|---|
| `saglik` | 17 | 14 | Sağlık, tıp ya da biyoteknoloji alanındaysa |
| `fintech` | 26 | 23 | Finans, ödeme ya da bankacılık alanındaysa |
| `egitim` | 17 | 16 | Eğitim ya da öğrenme alanındaysa |
| `gayrimenkul` | 18 | 15 | Gayrimenkul ya da inşaat alanındaysa |
| `seyahat` | 22 | 19 | Seyahat, konaklama ya da mobilite alanındaysa |
| `yeme-icme` | 17 | 10 | Yeme-içme ya da teslimat alanındaysa |
| `regule-sektor` | 28 | 23 | Yasal düzenlemeye tabi bir alandaysa |
| `turkiye-pazari` | 22 | 16 | Türkiye pazarı hedefleniyorsa |

## 1.6 Kategoriler gerçekten ayrık mı — ölçüm

İddia etmek yerine ölçtük. Her kategorinin çekirdek kaynak kümesini alıp ikili
kesişimlere baktık. **224 çekirdek kaynakta yalnızca 3 örtüşme** çıktı:

| Örtüşen kaynak | Hangi iki kategori | Meşru mu |
|---|---|---|
| Tripadvisor, Yelp | B2B web yazılımı ↔ Yerel hizmet | Evet, ikisi de bu siteleri kullanır |
| GitHub | Geliştirici aracı ↔ Yapay zekâ ürünü | Evet, YZ projeleri de GitHub'da |

Bu ölçüm testle korunuyor: iki kategorinin çekirdeği %25'ten fazla örtüşürse
test düşer. Yani kural belgede kalan bir temenni değil, kodda zorlanan bir şart.

## 1.7 Bir ürün iki kategoriye uyarsa — katman kuralı

Taksonomiyi 10 gerçek ürün fikriyle sınadık. Sekizi tek kategoriye düştü, ikisi
kararsız kaldı:

| Ürün | Kararsızlık |
|---|---|
| Mobil bulmaca oyunu | `oyun` mu `mobil-uygulama` mı? |
| Yerel esnaf için randevu uygulaması | `yerel-hizmet` mi `mobil-uygulama` mı? |

Bu bir çelişki değil **katman** durumu: mobil oyun için hem tür doygunluğunu
gösteren oyun kaynakları (SteamDB, Metacritic) hem dağıtımı gösteren mağaza
kaynakları gerekli. Eklenen kural:

> **Ana kategori, araştırmanın ayırt edici sorusunu cevaplayandır.** İkinci
> kategorinin çekirdek paketi *katman* olarak eklenir.

| Ürün | Ana kategori | Katman | Toplam çekirdek |
|---|---|---|---:|
| Mobil bulmaca oyunu | `oyun` (tür doygun mu, oyuncu ne ödüyor) | `mobil-uygulama` | 30 |
| Yerel esnaf randevu uygulaması | `yerel-hizmet` (işletme yoğunluğu, fiyatlar) | `mobil-uygulama` | 36 |

Kural modele işlendi: `katman_olabilir` sütunu hangi kategorilerin başkasının
üstüne binebileceğini söyler.

- **Katman olabilenler (3):** `mobil-uygulama`, `eklenti-entegrasyon`,
  `yapay-zeka-urunu` — üçü de dağıtım ya da teknoloji katmanı
- **Binmeyenler (5):** `b2b-web-yazilimi`, `gelistirici-araci`,
  `eticaret-fiziksel-urun`, `oyun`, `yerel-hizmet`

## 1.8 Üretilen dosyalar

### `URUN-KATEGORILERI.csv` — 16 satır

Kategori başına tek satır. Örnek:

```
kategori          mobil-uygulama
tur               kategori
ad                Mobil tüketici uygulaması
tanim             Son kullanıcıya uygulama mağazaları üzerinden dağıtılan uygulama
arastirma_niyeti  İndirme hacmi, kullanıcı şikâyetleri, rakip fiyatlandırma
ne_zaman          Ürün bu dağıtım/alıcı tipindeyse
katman_olabilir   evet
cekirdek_kaynak   13
cekirdek_cekilen  11
ortak_kaynak      283
ortak_cekilen     236
```

Ek satırında `tur` alanı farklıdır ve `ortak_kaynak` sıfırdır — ek paket ana
kategoriye eklendiği için ortak havuz zaten oradan gelir:

```
kategori          saglik
tur               ek
ne_zaman          Ürün sağlık, tıp ya da biyoteknoloji alanındaysa
cekirdek_kaynak   17
ortak_kaynak      0
```

### `KATEGORI-KAYNAK.csv` — 674 satır

Asıl iş burada. Her satır bir kategori↔kaynak eşleşmesidir ve soldan sağa cümle
kurar.

**Kategoriye özel bir kaynak:**

```
hedef         mobil-uygulama
hedef_turu    kategori
kaynak_grubu  Mobil uygulama mağazaları
kaynak        Google Play Store
rol           cekirdek
ne_saglar     Uygulama listeleri, kullanıcı yorumları, puan dağılımı
hangi_arama   {urun} app; {urun} tracker; best {urun} apps
durum         cekildi
adres         https://play.google.com
arama_yolu    opensearch
```

Okunuşu: *mobil-uygulama kategorisi için Google Play Store bir çekirdek
kaynaktır; oradan uygulama listeleri ve kullanıcı yorumları alınır, arama
`{urun} app` kalıbıyla yapılır. Kaynağın verisi çekilmiş durumda ve opensearch
yoluyla sorgulanabiliyor.*

**Çalışmayan bir kaynak da listede kalır, işaretlenir:**

```
kaynak        LinkedIn Jobs
rol           cekirdek
hangi_arama   {urun} specialist; {urun} developer
durum         kismi
arama_yolu    yok
```

LinkedIn Jobs B2B araştırması için çekirdek bir kaynak ama verisi alınamıyor.
Silmek yerine işaretlemek doğru: sistem bunu görüp alternatife yönelebilir.

**Ek paket kaynağı ve ortak havuz kaynağı:**

```
hedef  saglik    kaynak  ClinicalTrials.gov   rol  ek            hangi_arama  {urun}; {urun} clinical
hedef  ortak     kaynak  TechCrunch           rol  destekleyici  hangi_arama  {urun} funding; {urun} market
```

### Diğer dosyalar

| Dosya | Rolü |
|---|---|
| `URUN-KATEGORILERI.md` | Kategorilerin gerekçesi ve kullanımı |
| `build_product_categories.py` | İki CSV'yi envanterden üretir |
| `test_build_product_categories.py` | 13 test |

## 1.9 Kategoriyi "etiket" olmaktan çıkaran üç şey

**1. Her satırda kaynağın gerçek durumu var.** Sıradan bir kategori listesi
"mobil-uygulama → App Store, Play Store" der ve orada biter; o kaynaklara
erişilebiliyor mu belli olmaz. Bizimkinde son üç sütun (`durum`, `adres`,
`arama_yolu`) kaynak defterinden ve arama kataloğundan geliyor. Somut fark:
`mobil-uygulama` kategorisinde 13 kaynak var ama 11'i çalışıyor.

**2. Arama kalıpları tanımlı.** Görev, "hangi aramaların yapılacağını"
belirlemeyi de istiyordu. Her kaynak grubuna `{urun}` yer tutuculu kalıp
yazıldı:

| Kaynak grubu | Kalıp | "fitness" için |
|---|---|---|
| Mobil uygulama mağazaları | `{urun} app; {urun} tracker` | `fitness app` |
| SaaS inceleme siteleri | `{urun} software; {urun} alternatives` | `fitness software` |
| İş ilanları | `{urun} specialist; {urun} developer` | `fitness specialist` |
| Sağlık dikeyi | `{urun}; {urun} clinical` | `fitness clinical` |

Kalıplar gruba göre değişiyor, çünkü aynı kelimeyi her yere aynı şekilde sormak
yanlış: App Store'a "fitness app" denir, iş ilanı sitesine "fitness specialist".

**3. Ayrıklık ölçülüyor ve testle korunuyor.** 1.6'daki ölçüm bir kereye mahsus
değil; test ileride kategori eklendiğinde de çalışır.

## 1.10 Uçtan uca iki örnek

**"Diyabet hastaları için mobil takip uygulaması"**

| Katman | Kaynak |
|---|---:|
| Kategori: `mobil-uygulama` | 13 |
| Ek: `saglik` | 17 |
| Ortak havuz | 283 |

Önce bakılacak **30 kaynak**: App Store, Play Store, Sensor Tower,
ClinicalTrials.gov, FDA. Aramalar: `diyabet app`, `diyabet tracker`,
`diyabet clinical`.

**"Muhasebeciler için fatura yazılımı"**

| Katman | Kaynak |
|---|---:|
| Kategori: `b2b-web-yazilimi` | 64 |
| Ek: `fintech` + `regule-sektor` | 54 |
| Ortak havuz | 283 |

Önce bakılacak **118 kaynak**: G2, Capterra, LinkedIn Jobs, SPK, BDDK.
App Store'a hiç bakılmıyor. Aramalar: `fatura software`,
`fatura alternatives`, `fatura specialist`, `fatura mevzuat`.

İki örnekte de bakılan yerler tamamen farklı — kategorinin etiket olmaması
bunu ifade ediyor.

## 1.11 Yeniden üretim

```bash
python3 build_product_categories.py
python3 -m unittest test_build_product_categories
```

Kaynak listesi değişirse iki CSV yeniden üretilir. `SITE-LISTESI.md`'ye
sınıflandırılmamış yeni bir başlık eklenirse script hata verip durur — sessizce
ortak havuza atmak yanlış olurdu, kategoriye mi ek mi olduğu karardır ve elle
verilmelidir.

---

# Görev 2

*(Görev tamamlandığında bu bölüm doldurulacak.)*
