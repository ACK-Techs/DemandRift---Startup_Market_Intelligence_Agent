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
| **Ortak** | 12 | 291 | Her üründe kullanılır (haber, arama motorları, trend, patent, şirket verisi). Hiçbir ürünü diğerinden ayırmadığı için kategori olamaz |
| **Kategori** | 9 | 197 | Ürünün nerede yaşadığını ya da kimin satın aldığını belirler |
| **Ek** | 8 | 159 | Dikey ve bölge. Tek başına yetmez: "sağlık ürünü" demek mobil mi web mi olduğunu söylemez |
| **Kapsam dışı** | 1 | 16 | Fiziksel ürün pazar yerleri. Gerekçesi 1.4'ün sonunda |

**Neden 30 kategori yapmadık:** Üç sebeple. Birincisi, 12 başlık hiçbir ürünü
ayırt etmiyor (291 kaynak) — ortak havuzdurlar. İkincisi, bazı başlıklar aynı
ürün tipine hizmet ediyor: SaaS inceleme siteleri, fiyat karşılaştırma ve iş
ilanları üçü birden **B2B web yazılımı** araştırmasını besliyor; ayrı kategori
yapılsalardı aynı ürünü işaret ederlerdi ve kuralı çiğnerlerdi. Üçüncüsü, dikey
başlıklar tek başına yetmiyor.

## 1.4 Sonuç: 7 ana kategori

Ürün bunlardan birine girer. Sayılar: kategoriye özel kaynak / verisi çekilmiş
olan.

| Kategori | Tanım | Kaynak | Çekildi |
|---|---|---:|---:|
| `mobil-uygulama` | Uygulama mağazaları üzerinden dağıtılan uygulama | 13 | 11 |
| `b2b-web-yazilimi` | İşletmelerin abonelikle kullandığı web yazılımı | 64 | 53 |
| `gelistirici-araci` | Paket, SDK, CLI ya da altyapı aracı | 34 | 30 |
| `eklenti-entegrasyon` | Var olan bir platformun üzerine kurulan eklenti | 25 | 25 |
| `yapay-zeka-urunu` | Model, veri seti, agent ya da YZ altyapısı | 24 | 22 |
| `oyun` | Dijital dağıtım platformlarında yayınlanan oyun | 17 | 12 |
| `yerel-hizmet` | Belirli bir coğrafyada hizmet veren ürün | 23 | 17 |

Her kategoriye ayrıca **291 kaynaklık ortak havuz** eklenir (243'ünün verisi
çekilmiş).

### Çıkarılan kategori

Liste mentör değerlendirmesinden geçti (2026-09-04). Başlangıçta sekizinci bir
kategori vardı — `eticaret-fiziksel-urun`, pazar yerlerinde satılan fiziksel
ürün — ve **1.2'deki kuralı geçemediği için çıkarıldı.** Gerekçe: e-ticarette
fiziksel ürün için yapılan iş pazar analizi değil, fiyat arbitrajıdır; aynı ürün
farklı sitede farklı fiyata satılmaya çalışılır. Ortada araştırılacak ayrı bir
pazar yoktur, dolayısıyla ayrı bir araştırma niyeti de doğurmaz.

Kategoriye bağlı 16 fiziksel pazar yeri (Trendyol, Amazon, eBay, Temu…) kategori
haritasından çıktı. Envanterde ve `ADAY-KATALOG.csv`'de duruyorlar; yalnızca
"şu ürün tipini araştırırken buraya bak" etiketleri kalktı.

Aynı başlık altında duran 8 kaynak ise **ortak havuza taşındı**, çünkü fiziksel
ürün satmıyorlar:

| Kaynak | Neden kaldı |
|---|---|
| Gumroad, Lemon Squeezy | Bağımsız yazılımcının kendi ürününü sattığı yer — fiyat kanıtı |
| CodeCanyon, ThemeForest, Envato Market, Creative Market | Kod, tema ve eklenti satışı — doğrudan yazılım ürünü |
| Kickstarter, Indiegogo | Destekçi sayısı ve toplanan tutar, "talep var mı"nın en doğrudan kanıtı |

Başlık silinmedi, `kapsam-disi` olarak gerekçesiyle işaretlendi — karar dosyada
görünür kalsın diye.

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
kesişimlere baktık. **197 çekirdek kaynakta yalnızca 3 örtüşme** çıktı:

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
- **Binmeyenler (4):** `b2b-web-yazilimi`, `gelistirici-araci`, `oyun`,
  `yerel-hizmet`

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
ortak_kaynak      291
ortak_cekilen     243
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

### `KATEGORI-KAYNAK.csv` — 658 satır

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
| Ortak havuz | 291 |

Önce bakılacak **30 kaynak**: App Store, Play Store, Sensor Tower,
ClinicalTrials.gov, FDA. Aramalar: `diyabet app`, `diyabet tracker`,
`diyabet clinical`.

**"Muhasebeciler için fatura yazılımı"**

| Katman | Kaynak |
|---|---:|
| Kategori: `b2b-web-yazilimi` | 64 |
| Ek: `fintech` + `regule-sektor` | 54 |
| Ortak havuz | 291 |

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

# Görev 2 — Soruları ve kanıtlarını tanımlamak

**İstenen:** Her ürün kategorisinde hangi soruların cevaplanacağını ve hangi
kanıtın bu soruyu gerçekten desteklediğini tanımlamak.

## 2.1 Problem

Görev 1 **nereye bakılacağını** söylüyordu. Ama kaynağa ulaşmak tek başına
analiz üretmiyor: gelen veriyi hangi soruyu cevaplamak için kullandığın ve o
verinin o soruyu gerçekten cevaplayıp cevaplamadığı belirsiz kalıyordu.

Görev cümlesindeki kritik kelime **"gerçekten"**. Konuyla ilgili görünen her
veri kanıt değildir:

**Soru: "Bu pazarda talep var mı?"**

| Aday kanıt | Gerçekten destekliyor mu |
|---|---|
| TechCrunch'ta "bu pazar büyüyor" diyen haber | ❌ Yazarın kanaati, ölçüm değil |
| Google Trends'te aramanın 2 yılda 3 katına çıkması | ✅ Ölçülebilir, tarihli, tekrar üretilebilir |
| App Store'da 50 rakibin 10.000'den fazla yorum alması | ✅ İnsanlar indirip yorum yazmış — davranış |
| Yatırımcı blogunda "büyük fırsat" denmesi | ❌ Kanaat |

İkisi de aynı soruyla ilgili ama biri **ölçüm**, diğeri **kanaat**. Görev tam
olarak bu ayrımı yapmayı istiyor.

## 2.2 İzlenen yol

**Adım 1 — Soru seti: ortak çekirdek + kategoriye özel.**
Görev cümlesi "her ürün kategorisinde hangi sorular" diyor. Bunu tamamen ayrı
soru listeleri olarak değil, görev 1'deki yapının aynısıyla kurduk: ortak
çekirdek + kategoriye özel ek. Sebebi, pazar doğrulamasının bazı sorularının
evrensel olması — "talep var mı", "rakipler kim", "para ödeyecekler mi" mobil
uygulamada da geçerli, geliştirici aracında da. Bunları kategoriye göre farklı
yazmak yapay olurdu.

**8 ortak soru:** talep var mı, rakip kim, doygun mu, ödeme isteği, talep yönü,
şikâyet ne, giriş engeli, ulaşılabilir mi.

**6 kategoriye özel soru** — başka kategoride sorulsa anlamsız kalır:

| Soru | Hangi kategoride | Neden başka yerde yok |
|---|---|---|
| Platform politikası izin veriyor mu? | mobil, eklenti, oyun | Mağaza onayı; web SaaS'ta böyle bir kapı yok |
| Lisans modeli benimsenmeyi engelliyor mu? | geliştirici aracı, YZ | Açık kaynak beklentisi sadece burada belirleyici |
| Platform bu işlevi kendi ekler mi? | eklenti | Shopify eklentiyi kopyalayabilir |
| Çalıştırma maliyeti sürdürülebilir mi? | YZ, e-ticaret | Çıkarım/komisyon maliyeti birim ekonomiyi belirler |
| Coğrafi yoğunluk yeterli mi? | yerel hizmet | Bir şehirde çalışan model diğerinde çalışmayabilir |
| Ürün keşfedilebilir mi? | mobil, oyun | Katalog büyüklüğü görünürlüğü engeller |

**Adım 2 — Kanıtı soruya değil, soru × kaynak grubu ikilisine bağladık.**
Bu, işin can alıcı kararıydı. "Pazar doygun mu" sorusunun tek bir cevabı yok;
kategoriye göre tamamen farklı ölçümle cevaplanıyor. Kanıtı kaynak grubunun
özelliği olarak tanımlayınca kategori kendi gruplarından kanıtı devralıyor ve
kategori×soru kombinasyonları elle yazılmıyor, türetiliyor.

**Adım 3 — Her kanıt satırına "zayıf alternatif" alanı koyduk.**
"Gerçekten destekleyen" demek, **desteklemeyeni de işaretlemek** demek. Bu alan
olmadan ayrım kâğıt üzerinde kalırdı.

## 2.3 Ölçüm bir eksik ortaya çıkardı

İlk üretimde 111 satır çıktı ve iş bitmiş göründü. Ama şu soru soruldu: **bu
kategori ve soru sayısıyla 636 kaynağın hepsi işe koşuluyor mu?**

Ölçüm bunu gösterdi:

| | İlk hâli |
|---|---:|
| Bir soruya kanıt olan kaynak | 345 (%54) |
| Hiçbir soruya bağlanmayan | 291 (%46) |
| Bunlardan verisi çekilmiş olan | 243 |

Yani envanterin yarısı boştaydı — üstelik verisi elimizdeyken. Kategori ve soru
sayısı yeterliydi, **bağlantılar eksik kurulmuştu**. İki sebep vardı:

**Sebep 1 — Ek paketler hiç soru üretmiyordu (167 kaynak).** Script yalnızca 8
kategoriyi dolaşıyordu. Oysa "diyabet uygulaması" araştırılırken sağlık
kaynaklarına da sorulmalı. Her ek pakete cevapladığı sorular bağlandı: sağlık
`giriş engeli` ve `talep var mı`, fintech `giriş engeli` ve `rakip kim`, Türkiye
paketi `rakip kim` ve `talep yönü`.

**Sebep 2 — Ortak havuzun dört grubuna kanıt tanımlanmamıştı (124 kaynak).**

| Grup | Hangi soruya | Kanıt |
|---|---|---|
| Haber ve sektör yayınları | `rakip kim` | Yatırım ve satın alma haberleri — tarihli, doğrulanabilir olay |
| Akademik yayınlar | `giriş engeli` | Yayın yoğunluğu — çok yayın az ürün varsa teknik engel var |
| Ürün lansmanı toplulukları | `rakip kim` | Son 12 aydaki lansmanlar — yeni girenleri erken gösterir |
| Domain, DNS ve web izleri | `rakip kim` | Alan adı kayıt tarihi — rakibin ne zaman başladığı |

Düzeltme sonrası:

| | Sonuç |
|---|---:|
| Satır sayısı | 111 → **198** |
| Bir soruya kanıt olan kaynak | 345 → **580 (%94)** |
| Boşta kalan | 291 → **40** |

Kalan 40 kaynak **kasıtlı olarak** dışarıda:

| Grup | Kaynak | Neden kanıt değil |
|---|---:|---|
| Genel web arama | 16 | Arama motoru kanıt üretmez, kanıta ulaştırır — araçtır |
| Anket platformları | 24 | Birincil araştırma altyapısı; fikir doğrulandıktan sonra kendi verini toplamak için |

Bu oran testle korunuyor: envanterin %90'ından azı bir soruya bağlıysa test
düşer.

## 2.4 Sonuç

### Kategori başına soru ve kanıt

| Kategori | Soru | Kanıt satırı |
|---|---:|---:|
| `mobil-uygulama` | 10 | 28 |
| `b2b-web-yazilimi` | 8 | 31 |
| `gelistirici-araci` | 9 | 26 |
| `eklenti-entegrasyon` | 10 | 25 |
| `yapay-zeka-urunu` | 10 | 25 |
| `oyun` | 10 | 24 |
| `yerel-hizmet` | 9 | 24 |

Ek paketler ayrıca 15 satır üretiyor (paket başına 1-2 soru).

### Aynı soru, farklı kanıt

Bu tablo görev 1'deki kategori ayrımının neden gerekli olduğunu gösteriyor.
**"Pazar doygun mu?"** her kategoride sorulur ama:

| Kategori | Kanıt |
|---|---|
| `mobil-uygulama` | İlk 20'nin yorum sayısı dağılımı ve son güncelleme tarihleri |
| `gelistirici-araci` | İndirmenin ilk 3 pakette toplanma oranı |
| `b2b-web-yazilimi` | Ürün sayısı ile yorum sayısının dağılımı; ilk 5'in payı |
| `oyun` | Türdeki oyun sayısı, eşzamanlı oyuncu dağılımı |
| `eklenti-entegrasyon` | Kurulumun ilk 5 eklentide toplanma oranı |
| `yerel-hizmet` | Bölgedeki sağlayıcı sayısı, yorumun ilk 10'da toplanması |
| `yapay-zeka-urunu` | Entegrasyon dizinlerindeki benzer araç sayısı ve güncellik |

Kategori olmasaydı bu sorunun tek ve belirsiz bir cevabı olurdu.

## 2.5 Üretilen dosya

### `KATEGORI-SORU.csv` — 198 satır

Tek satırın tamamı:

```
kategori            mobil-uygulama
soru_id             talep-var-mi
soru                Bu ürüne gerçekten talep var mı?
soru_turu           ortak
neden_onemli        Talep yoksa diğer soruların cevabı önemsizdir; ilk elenme noktası budur
kanit_turu          Kategorideki uygulama sayısı ve ilk 20'nin toplam yorum hacmi
kanit_kaynak_grubu  Mobil uygulama mağazaları
kanit_kaynak_rolu   kategori
ornek_kaynaklar     APKMirror, Apple App Store, Aptoide, F-Droid
kaynak_sayisi       13
calisan_kaynak      11
neden_gecerli       Yorum ancak indirip kullandıktan sonra yazılır; iddia değil davranıştır
zayif_alternatif    Uygulama sayısı tek başına — 50 uygulamanın 45'i terk edilmiş olabilir
```

Okunuşu: *mobil uygulama araştırırken "talep var mı" sorusu, mağazalardaki
uygulama sayısı ve ilk 20'nin yorum hacmiyle cevaplanır. Bu geçerli bir kanıttır
çünkü yorum ancak kullandıktan sonra yazılır. Uygulama sayısına tek başına
bakmak yanıltır.*

**Dosya neden 14 değil 198 satır:** bir soru tek kanıtla kapanmıyor. Yukarıdaki
soru aynı kategoride üç ayrı satır üretiyor — biri kategoriye özel kaynaktan,
ikisi ortak havuzdan:

```
kategori  soru_id       kanit_kaynak_grubu              kanit_kaynak_rolu  calisan_kaynak
────────  ────────────  ──────────────────────────────  ─────────────────  ──────────────
mobil-…   talep-var-mi  Mobil uygulama mağazaları       kategori           11
mobil-…   talep-var-mi  Trafik, SEO, anahtar kelime     ortak              23
mobil-…   talep-var-mi  Kamu verisi ve istatistik       ortak              21
```

Üçü farklı yerden bakıyor: mağaza yorumu davranışı ölçer, arama hacmi niyeti
ölçer, resmî istatistik kitle büyüklüğünü ölçer. Biri boş çıkarsa diğer ikisi
soruyu yine cevaplayabilir — kanıt tek kaynağa bağlı kalmıyor.

Son iki alan görev cümlesindeki "gerçekten destekleyen" şartının karşılığıdır.
Kanıt gibi görünüp olmayanlar her satırda açıkça işaretli: blog yazıları, anket
"öderim" cevapları, ortalama puanlar, satıcının kendi iddiaları, liste fiyatları.

### Diğer dosyalar

| Dosya | Rolü |
|---|---|
| `build_category_questions.py` | Soruları, kanıtları ve eşleşmeyi üretir |
| `test_build_category_questions.py` | 12 test |

Script kanıtı olmayan soruyu bildirip listeler — kanıtsız soru cevaplanamayan
sorudur, sessizce geçilmez. İlk koşuda 13 soru kanıtsız çıktı ve hepsi
dolduruldu.

## 2.6 Yeniden üretim

```bash
python3 build_category_questions.py
python3 -m unittest test_build_category_questions
```

Testler üç şeyi korur: aynı sorunun kategoriye göre farklı kanıt aldığını,
her satırın zayıf alternatif taşıdığını ve envanterin %90'ından fazlasının bir
soruya bağlı kaldığını.

---

# Görev 3 — Defteri aday kataloğa dönüştürmek

**İstenen:** Mevcut kaynak defterini ürün araştırması için anlamlı bir aday
kataloğa dönüştürmek; aynı host/farklı marka, discovery yüzeyi ve gerçek veri
yüzeyi ayrımını görünür kılmak.

## 3.1 Problem: defter erişim kaydıdır, katalog değildir

`KAYNAK-DEFTERI.csv` şu soruyu cevaplıyor: **"Bu adrese ulaşabildik mi, ne
indi?"** Sütunları teknik — durum, çekilen yüzeyler, engel sebebi. Bu, çekim
işini yönetmek için doğru dosya.

Ama ürün araştırması yapan biri başka bir şey soruyor: **"Bu kaynak benim
araştırmama ne katıyor?"** Bunun cevabı defterde yok. Kaynağın hangi kategoride
olduğu, kaç soruya kanıt verdiği, elindeki verinin gerçekten kullanılabilir olup
olmadığı — hiçbiri görünmüyor.

Defter silinmedi, üstüne bir katman kondu. `ADAY-KATALOG.csv` defterin 636
satırını alır ve her satıra araştırma açısından anlamlı alanlar ekler.

## 3.2 Aynı host / farklı marka

Defterde bunlar dört ayrı kaynak olarak duruyordu:

```
Bing                  → https://www.bing.com
Bing News             → https://www.bing.com
Bing Maps             → https://www.bing.com
Bing Webmaster Tools  → https://www.bing.com
```

Marka olarak gerçekten ayrılar — Bing News haber sorgular, Bing Maps yer
sorgular, farklı sorulara cevap verirler. Ama **teknik olarak tek bir site.**

Bu ayrım görünmezse üç şey ters gider:

1. Sistem aynı siteye dört kez istek atar
2. Sitenin kotasını dört kat hızlı tüketir
3. Aynı veriyi dört ayrı kaynaktan gelmiş gibi sayar — **sahte doğrulama**

Üçüncüsü en tehlikelisi: "dört kaynak da aynı şeyi söylüyor" demek, aslında tek
bir siteyi dört kez okumaksa, kanıt gücü olduğundan yüksek görünür.

**Ölçüm:** 631 adresli kaynak var ama yalnızca **596 benzersiz host**. Yani **60
marka, 25 host'u paylaşıyor.**

| Host | Marka | Kimler |
|---|---:|---|
| google.com | 6 | Finance, Jobs, Maps, Reviews, Search Console, Transparency Report |
| bing.com | 4 | Bing, Maps, News, Webmaster Tools |
| g2.com | 3 | G2, G2 Track, G2 Education Software |
| linkedin.com | 3 | LinkedIn, Jobs, Ad Library |
| facebook.com | 3 | Facebook, Marketplace, Pages |
| sahibinden.com | 3 | Sahibinden, Emlak, Hizmetler |

**Çözüm:** Markalar birleştirilmedi — ayrı kalmaları doğru, çünkü farklı
soruları cevaplıyorlar. Sadece paylaşım görünür kılındı. Her satırda üç alan
var:

```
host                bing.com
host_marka_sayisi   4
host_kardesleri     Bing, Bing Maps, Bing Webmaster Tools
```

Artık sistem "Bing News'a soracağım" dediğinde üç kardeşi olduğunu ve
isteklerin tek kotadan gittiğini görüyor.

## 3.3 Discovery yüzeyi / gerçek veri yüzeyi

Defterde bütün yüzeyler aynı sütunda yan yana duruyordu:

```
Bloomberg | sitemap_xml
Coursera  | root_html
GitHub    | robots_preflight
```

Üçü de "bir şeyler indi" demek ama araştırma değerleri tamamen farklı:

| Yüzey | Ne taşır | Rolü |
|---|---|---|
| `root_html`, `entry_url`, `common_crawl_warc`, API yanıtları | Sayfanın kendisi | **veri** |
| `sitemap_xml` | Sayfa adresleri listesi | **keşif** — nereye bakılacağını söyler |
| `rss_feed` | Başlık ve özet | **karma** — kısmi veri |
| `robots_preflight` | Erişim kuralları | **politika** — araştırma malzemesi değil |

Her kaynak, elindeki en güçlü yüzeye göre sınıflandırıldı:

| Araştırma değeri | Kaynak | Anlamı |
|---|---:|---|
| `veri-var` | **483** | Gerçek içerik elimizde |
| `kismi-veri` | 9 | RSS — başlık ve özet var |
| `yalniz-kesif` | **42** | Sadece sitemap — nereye bakılacağı belli, veri yok |
| `yalniz-politika` | 44 | Sadece robots.txt |
| `bos` | 58 | Hiçbir şey |

## 3.4 Ayrımın ortaya çıkardığı düzeltme

Bu, görevin en önemli sonucu. **Defter "534 kaynak çekildi" diyor.** Katalog
aynı 534'ü ayrıştırınca:

```
534 "çekildi"
  ├── 483  veri-var       ← gerçekten veri
  ├──   9  kismi-veri     ← RSS özeti
  └──  42  yalniz-kesif   ← SADECE SİTEMAP
```

O 42 kaynağın arasında **Bloomberg, CNBC, Booking.com, Business Insider,
Associated Press, bioRxiv, Nature, GitLab** var.

Ne olmuş: bot koruması ana sayfayı vermemiş, ama sitemap'i almışız. Yani
*"Bloomberg'de şu sayfalar var"* biliyoruz — sitemap'lerde toplam 97.487 adres
duruyor — ama **o sayfaların içeriği elimizde değil.**

Defterin "çekildi" demesi teknik olarak yanlış değildi: bir içerik yüzeyi indi.
Ama araştırma açısından yanıltıyordu. Bloomberg'den veri toplandığını sanırsın,
oysa elimizde yalnızca içindekiler listesi var.

Görevin *"discovery yüzeyi ve gerçek veri yüzeyi ayrımını görünür kılmak"*
demesinin sebebi tam olarak bu.

## 3.5 Üretilen dosya

### `ADAY-KATALOG.csv` — 636 satır

Her kaynak için bir satır. İki örnek:

**Host paylaşan bir marka:**

```
ad                   Bing News
adres                https://www.bing.com
host                 bing.com
host_marka_sayisi    4
host_kardesleri      Bing, Bing Maps, Bing Webmaster Tools
arastirma_degeri     veri-var
veri_yuzeyi          root_html
kesif_yuzeyi         sitemap_xml
kategoriler          ortak
kaynak_rolu          destekleyici
cevapladigi_soru     2
durum                cekildi
arama_yolu           site_search
```

**Yalnız keşif yüzeyi olan bir kaynak:**

```
ad                   Bloomberg
host                 bloomberg.com
host_marka_sayisi    1
arastirma_degeri     yalniz-kesif      ← uyarı burada
veri_yuzeyi          (boş)
kesif_yuzeyi         sitemap_xml
kategoriler          ortak
cevapladigi_soru     2
durum                cekildi           ← defter böyle diyor
```

Son iki satır dikkat çekici: `durum` ile `arastirma_degeri` yan yana duruyor.
Biri teknik gerçeği söylüyor (bir yüzey indi), diğeri araştırma gerçeğini
(içerik yok). Çelişki değil, iki farklı soru.

Katalog ayrıca görev 1 ve 2'yi bağlıyor: `kategoriler`, `kaynak_rolu` ve
`cevapladigi_soru` sütunları her kaynağın araştırma zincirindeki yerini
gösteriyor.

### Diğer dosyalar

| Dosya | Rolü |
|---|---|
| `build_candidate_catalog.py` | Kataloğu defter, dizin ve kategori dosyalarından üretir |
| `test_build_candidate_catalog.py` | 14 test |

Testler üç şeyi korur: sitemap'in keşif sayıldığını (veri değil), host
paylaşımının karşılıklı olduğunu (A B'yi kardeş görüyorsa B de A'yı görmeli) ve
defterin "çekildi" sayısının katalogda üçe ayrıldığını — yani katalog defteri
bozmuyor, ayrıştırıyor.

## 3.6 Yeniden üretim

```bash
python3 build_candidate_catalog.py
python3 -m unittest test_build_candidate_catalog
```

Dört dosya zincirleme bağlı olduğu için yeni veri çekildiğinde sıra şudur:

```bash
python3 build_coverage_ledger.py results/bulk-site-access-*.json results/common-crawl-*.json
python3 build_artifact_index.py
python3 build_product_categories.py
python3 build_category_questions.py
python3 build_candidate_catalog.py
```

Üçü de aynı defteri okuduğu için bütün sayılar tutarlı şekilde güncellenir.

---

# Görev 4 — Hangi alan, hangi izinli yol

**İstenen:** "Bu siteden veri çekilir" yerine, her kaynağın hangi anlamlı alanı
hangi izinli yolla sağlayabileceğini belirlemek.

## 4.1 Problem: "veri-var" ne söylemiyor

Görev 3'ün çıktısı `ADAY-KATALOG.csv`, 483 kaynak için `arastirma_degeri =
veri-var` diyor. Bu cümle kendi sorusuna doğru cevap veriyor — bir yüzey yanıt
verdi mi. Ama araştırmayı çalıştırmak için üç şeyi cevapsız bırakıyor:

**Hangi alan?** "Veri" bir şey söylemez. Araştırma fiyat, yorum sayısı, puan,
indirme adedi gibi **adı olan, tabloya konabilen** birimlerle yapılır. Görev
2'de kanıtı tanımlarken bu alanlar zaten ima edilmişti — *"ilk 20'nin toplam
yorum hacmi"* cümlesi `yorum_sayisi` alanını işaret eder.

**Hangi yol?** Aynı kaynak API'den, arama ucundan, HTML'den ya da arşiv
kopyasından gelebilir. Alan aynı olsa bile yol değişince tazelik ve maliyet
değişir.

**İzinli mi?** Kritik kelime budur. Bir yolun **çalışması** ile o yolu
**kullanma hakkımızın olması** aynı şey değildir.

## 4.2 Anlamlı alan: kontrollü sözlük

27 alanlık kapalı bir sözlük tanımlandı. Her alan bir tür ve bir gerekçe taşır:

```
urun_sayisi      sayi    Kategoride kaç ürün listeleniyor — arz yoğunluğu
yorum_sayisi     sayi    Kullanıcı yorumu adedi — kullanım davranışının izi
puan             sayi    Ortalama değerlendirme puanı
fiyat            para    Tekil ürün fiyatı
indirme_sayisi   sayi    İndirme ya da kurulum adedi
son_guncelleme   tarih   İçeriğin en son değiştiği tarih — canlılık göstergesi
...
```

**Sözlüğün kapalı olması "anlamlı" olmanın ikinci şartıdır.** Bir kaynak
`yorum_sayisi`, diğeri `review_count` derse iki kaynak birleştirilemez ve
karşılaştırma yapılamaz. Alan adı bu listenin dışına çıkamaz; test bunu korur.

Alanlar kaynak başına elle yazılmadı, **31 kaynak grubundan türetildi** — görev
2'deki kanıt da gruba bağlıydı, böylece iki dosya aynı eksende kalıyor ve
envanter büyüdüğünde tek yerde güncelleniyor.

**Alan ataması görev 2'nin kanıt tanımını izler.** Görev 2 akademik kaynaklar
için *"konudaki yıllık yayın sayısının eğrisi"*, sosyal ağlar için
*"topluluklar ve üye sayıları"*, haber kaynakları için *"yatırım turlarının
yıllara göre sayısı"* diyor; bu gruplar sayılabilir alan taşır. Regülasyon
kaynakları taşımaz — kanıtı bağlayıcı metindir, sayı değil. İki test bu ayrımı
korur.

**Grup adı her zaman içeriğini doğru anlatmaz.** "Yazılım geliştirici ve teknik
topluluklar" başlığı üç ayrı türü birlikte tutuyor: paket kayıtları (npm, PyPI),
soru-cevap siteleri (Stack Overflow) ve kod barındırma (GitHub). Grup alanlarını
olduğu gibi uygulamak *"Stack Overflow paket bağımlılığı sayısı veriyor"* demek
olurdu. Bu kaynaklar grup listesi yerine kendi listesini kullanır.

## 4.3 İzinli yol: çalışmak ile hakkımız olmak

İzin evet/hayır değil, beş sınıf:

| Sınıf | Ne demek | Satır |
|---|---|---:|
| `api-acik` | Belgelenmiş API ucu; programatik erişim için tasarlanmış yol | 83 |
| `robots-izinli` | robots.txt ön kontrolünden geçti, içerik canlı indirildi | 2125 |
| `arsiv-kopyasi` | Yalnız Common Crawl kopyası; arşiv robots'a uyar, veri güncel değil | 482 |
| `yol-yok` | Sorgulanabilir bir yol bulunamadı | 338 |
| `yasak` | robots.txt bu kaynağı kapatıyor — denenmedi | 190 |

Sıralama önemli: `yasak` her şeyi geçer. Bir kaynağın API'si olsa bile robots
kapatıyorsa sınıf `yasak` kalır, çünkü sayfanın inebiliyor olması izin vermez.

## 4.4 Doğrulama: dosyaların içine bakmak

Alanın o kaynaktan geldiği iddia edilmedi, **indirilmiş artefaktların içine
bakıldı.** Dört yerden kanıt toplandı:

| Kanıt kaynağı | Örnek iz |
|---|---|
| API yanıtındaki anahtarlar | `api:downloads`, `api:last_activity_date` |
| HTML içindeki schema.org JSON-LD | `json-ld:aggregateRating`, `json-ld:offers` |
| RSS etiketleri | `rss:pubDate`, `rss:category` |
| Sitemap | `sitemap:lastmod` |

Güven iki değerli ve ikisi asla karıştırılmıyor:

- **`dogrulandi`** — alan artefaktın içinde görüldü. Satır her zaman
  `dogrulama_izi` taşır; iddia izi sürülebilir.
- **`beyan`** — alan kaynak grubunun doğası gereği bekleniyor ama gösterilemedi.
  Satır her zaman `neden_dogrulanmadi` taşır.

`beyan` **"bu alan orada yok" demek değildir** — "bakılamadı" demektir.
Doğrulama tek yönlüdür: bulmak kanıtlar, bulamamak kanıtlamaz.

**Sitenin kendini tarif ettiği veri, araştırma kanıtı sayılmaz.** Bir kaynağın
ana sayfasında kendi uygulamasının mağaza puanını schema.org ile yayınlaması
yaygındır; bu, o sitede **listelenen** bir kaydın puanı değildir. Araştırmaya
gereken ikincisidir. Bu yüzden `Organization`, `WebSite`, `MobileApplication`
gibi kendini tarif eden nesnelerden yalnızca kimlik alanları doğrulanır, ölçüm
alanı doğrulanmaz. İç içe değer nesneleri (`AggregateRating`, `Offer`) üst
bağlamı ezmez — bir uygulamanın içindeki puan hâlâ o uygulamanın puanıdır.

## 4.5 Ölçüm

Alanlar iki gruba ayrılıp doğrulama oranına bakıldı:

| | Doğrulanan | Oran |
|---|---|---:|
| Etiket/kimlik alanı (url, başlık, tarih) | 243/1830 | **%13** |
| Ölçüm alanı (puan, yorum, fiyat, indirme) | 10/1388 | **%0.7** |

Sitelere ulaşabildiğimiz ve adlarını, bağlantılarını, tarihlerini alabildiğimiz
gösterilebiliyor; görev 2'nin kanıt dediği sayıları alabildiğimiz henüz
gösterilemiyor.

Sebebi ölçülebilir durumda: indirilen sayfaların **453'ü ana sayfa, 82'si iç
sayfa.** App Store'un ana sayfasında yorum sayısı yoktur; o alanı taşıyan
kategori sayfası çekilmemiştir. Hangi iç sayfanın çekileceği ancak hangi alanın
gerektiği tanımlandıktan sonra bilinebilirdi; bu görev o tanımı üretiyor.

**Oranın karşılığı bir kapasite tablosudur:**

| | Kaynak |
|---|---:|
| Envanter | 636 |
| Kategori haritasında | 620 |
| Ölçüm alanı beklenen | 584 |
| **Ölçüm alanı + izinli yol** | **404 (%64)** |

O 404 kaynağın **214'ünün sitemap'i**, **37'sinin API/OpenSearch ucu** var —
nasıl sorulacağı biliniyor, çoğunda nereye gidileceği de biliniyor.

Böylece belirsiz bir "veri-var" cümlesi, **adresli bir çekim listesine**
dönüştü: `beyan` satırlarının her biri "şu sayfa çekilirse şu alan doğrulanır"
bilgisini taşır.

## 4.6 Sınırın nerede olduğu

Yalnız arşiv kopyası bulunan kaynaklar için sınırın erişilebilirlikten mi yoksa
politikadan mı geldiği ölçüldü. Bot koruması kaydı bulunmayan 73 kaynak için
canlı çekim yeniden denendi.

Sonuç: 4 kaynaktan içerik alındı. Kalanlarda **44 kez `challenge`**, 23 kez
`origin_circuit_open` kaydedildi — siteler robots.txt'yi okumamıza izin veriyor
ama içerik isteğini bot koruması ile karşılıyor.

Bu, o kaynakların neden yalnızca arşivde bulunduğunu açıklıyor: Common Crawl'ın
tarayıcısı yıllardır tanınan bir tarayıcıdır. Aradaki farkı kapatmanın tek yolu
tarayıcı taklidi olurdu — site bizi bot olarak tanıyıp reddediyorsa kendimizi
tarayıcı gibi göstermek tespit atlatmadır ve yapılmadı.

**404 bir teknik yetersizlik sınırı değil, erişim politikası sınırıdır.**

## 4.7 Üretilen dosya

### `KAYNAK-ALAN.csv` — 3218 satır

Satır birimi artık kaynak değil, **(kaynak, alan)** ikilisi. 620 kaynak, 27 alan.

**API'den doğrulanmış — en güçlü hâli:**

```
ad                 npm
alan               indirme_sayisi
alan_turu          sayi
kaynak_grubu       Yazılım geliştirici ve teknik topluluklar
yol                api
izin_durumu        api-acik
izin_aciklama      Belgelenmiş API ucu var; programatik erişim için tasarlanmış yol
guven              dogrulandi
dogrulama_izi      api:downloads
hizmet_ettigi_soru doygun-mu, lisans-modeli, odeme-istegi, rakip-kim, talep-var-mi
```

Okunuşu: *npm'den indirme sayısı alınır; yol açık API'dir, izin programatik
erişime uygundur, ve bu iddia indirilmiş yanıttaki `downloads` anahtarıyla
kanıtlanmıştır. Alan beş soruya hizmet eder.*

**Beyan ve gerekçesi — dosyanın çoğunluğu, aynı zamanda çekim listesi:**

```
ad                 Apple App Store
alan               yorum_sayisi
yol                fulltext
izin_durumu        robots-izinli
guven              beyan
neden_dogrulanmadi Elimizde anasayfa artefaktı var; alanı taşıyan iç sayfa çekilmedi
```

**İzin ayrımının görünür hâli:**

```
ad                 Apple Maps
alan               yorum_sayisi
izin_durumu        yasak
izin_aciklama      robots.txt bu kaynağı kapatıyor — denenmedi
neden_dogrulanmadi Kaynak robots.txt ile kapalı; hiçbir artefakt alınmadı
```

Apple Maps yerel hizmet araştırmasında değerli bir kaynaktır. Silinmedi,
işaretlendi — sistem bunu görüp izinli bir alternatife yönelebilir.

### Diğer dosyalar

| Dosya | Rolü |
|---|---|
| `build_source_fields.py` | Sözlüğü, izin sınıflarını ve doğrulamayı üretir |
| `test_build_source_fields.py` | 22 test |

Testler dört şeyi korur: alan adının sözlük dışına çıkamayacağını, `dogrulandi`
satırının iz taşıdığını, `beyan` satırının gerekçesiz kalamayacağını ve sitenin
kendi puanının ölçüm kanıtı sayılamayacağını.

## 4.8 Yeniden üretim

```bash
python3 build_source_fields.py
python3 -m unittest test_build_source_fields
```

Dosya defteri, artefakt dizinini, arama yüzeylerini ve görev 1–2'nin çıktılarını
okur. Yeni veri çekildiğinde sıra şudur:

```bash
python3 build_coverage_ledger.py results/bulk-site-access-*.json results/common-crawl-*.json
python3 build_artifact_index.py
python3 build_product_categories.py
python3 build_category_questions.py
python3 build_candidate_catalog.py
python3 build_source_fields.py
```

Yeni sayfalar çekildikçe doğrulanan satır sayısı kendiliğinden artar; alan
sözlüğü ve izin sınıfları değişmez.

---

# Görev 5 — Fikirden kaynak paketine

**İstenen:** Bir ürün fikri geldiğinde tüm 636 kaynağı çalıştırmak yerine, en
değerli ve bağımsız kaynak paketini deterministik seçebilmek.

## 5.1 Problem

İlk dört görev bir katalog üretti: hangi kaynak hangi ürün tipine hizmet eder,
hangi soruyu cevaplar, hangi alanı hangi izinli yoldan verir. Katalog kimseye
tek başına araştırma yaptırmaz.

Bir fikir geldiğinde — *"diyabet hastaları için mobil takip uygulaması"* — 636
kaynağın hepsini çalıştırmak üç şeyi israf eder: süre, site kotası ve dikkat.
Kaynakların çoğu o fikirle ilgisizdir; diyabet uygulaması araştırırken oyun
platformlarına ya da mevzuat sitelerine bakmanın karşılığı yoktur.

Bu adım kataloğu **kullanan** ilk parçadır.

## 5.2 Neden düz bir liste olmaz

İlk akla gelen çözüm "en yüksek puanlı 12 kaynağı seç"tir. Bu yaklaşım
denendiğinde çıkan paketin dokuzu uygulama mağazasıydı: APKMirror, App Store,
Aptoide, Google Play, Huawei AppGallery, Microsoft Store, Samsung, Uptodown,
Xiaomi.

Dokuzuna da bakıp *"dokuz kaynak da doğruladı"* demek yanıltıcıdır — dokuzu da
aynı şeyi aynı yöntemle ölçer: mağazadaki uygulama sayısı. Aynı bilgi dokuz kez
okunmuş olur. Görev 3'te aynı host'u paylaşan markalar için işaretlediğimiz
**sahte doğrulama** riski, burada aynı yöntemi paylaşan kaynaklarda tekrar
eder. Farklı host bağımsızlık için yeterli değildir.

Bu yüzden çıktı bir kaynak listesi değil, **soru başına kanıt yuvasıdır:**

```
soru: doygun-mu
  yuva 1 — Mobil uygulama mağazaları    Google Play Store → App Store → APKMirror
  yuva 2 — Dijital ürün pazar yerleri   ThemeForest → Envato Market → CodeCanyon
```

Her yuva **ayrı bir ölçme yöntemidir**. Yuva içindeki kaynaklar birbirinin
rakibi değil **yedeğidir**: Google Play bot koruması verirse App Store denenir.
Testler bir sorunun yuvalarının farklı gruplardan ve farklı host'lardan
geldiğini, yedeklerin ise birincil ile aynı gruptan olduğunu korur.

## 5.3 Fikirden kategoriye

Kategori tespiti sabit bir anahtar kelime tablosuyla yapılır. Modele
sorulmaz — görev *deterministik* şart koşuyor, aynı fikir her zaman aynı
kategoriye düşmelidir.

Hiçbir anahtar eşleşmezse script hata verir ve durur. Sessizce bir varsayılana
düşmek yanlış olur: yanlış kategori bütün seçimi yanlış yapar.

**Katman kuralı görev 1'den devralınır, yeniden icat edilmez.** *"Mobil bulmaca
oyunu"* hem `oyun` hem `mobil-uygulama` anahtarı taşır. Görev 1 bu durumu zaten
karara bağlamıştı: `katman_olabilir` işaretli kategoriler dağıtım ya da teknoloji
katmanıdır, başkasının üstüne biner. Ana kategori araştırmanın ayırt edici
sorusunu cevaplayandır, yani katman **olmayan** kategoridir. Script bu işareti
`URUN-KATEGORILERI.csv`'den okur.

```
"mobil bulmaca oyunu"        → kategori: oyun,          katman: mobil-uygulama
"yerel esnaf randevu uygulaması" → kategori: yerel-hizmet, katman: mobil-uygulama
"diyabet takip uygulaması"   → kategori: mobil-uygulama, katman: yok
```

## 5.4 Havuzun daralması

| Adım | Kalan kaynak |
|---|---:|
| Envanter | 636 |
| Kategori + katman + ek paket + ortak havuz (görev 1) | 320 |
| Ölçüm alanı ve izinli yolu olanlar (görev 4 süzgeci) | 214 |
| Soru başına bağımsız yuva (görev 5) | **11** |

Görev 4'ün süzgeci burada bir kapı görevi görür: ölçüm alanı vermeyen ya da
izinli yolu olmayan kaynak havuza **girmez**. Böylece robots.txt yasağı seçim
aşamasında yeniden kontrol edilmek zorunda kalmaz; zaten elenmiştir.

## 5.5 Yuva içindeki sıra

Yuva içinde hangi kaynağın birincil olacağı ölçülmüş değerlere dayanır:

1. Artefaktta doğrulanmış alan sayısı
2. İzin sınıfı — açık API, robots-izinliden önce gelir
3. **`tam_metin_bayt`** — o kaynaktan fiilen alınan metin miktarı
4. Ölçüm alanı sayısı
5. Eşitlikte kaynak adı

Üçüncü kriter belirleyicidir ve ölçülmüş bir değerdir:

| Kaynak | Alınan metin |
|---|---:|
| Google Play Store | 2.957.024 |
| Apple App Store | 1.403.708 |
| APKMirror | 766.236 |
| Aptoide | 404.084 |
| F-Droid | 13.156 |

Büyük kataloğu olan kaynak daha çok metin döndürür; bu, içerik zenginliğinin
dolaylı ama **ölçülmüş** göstergesidir. Hiç içerik döndürmemiş kaynak (0 bayt)
birincil seçilmez — API'si olsa bile elimizde ondan gelmiş tek satır yoktur.

**Bilinçli bir sınır:** elimizde pazar büyüklüğü verisi yoktur. Google Play'in
F-Droid'den büyük olduğunu söyleyen bir sütun yoktur. Seçim kapsama ve
bağımsızlık garantisi verir, pazar ağırlığı garantisi vermez; sıralama
ölçülebilir kriterlere dayanır, tahmini popülerliğe değil.

## 5.6 Sınır görünür kalır

Soru başına en fazla üç yuva açılır. Bu bir tercihtir, veriden türetilmiş bir
eşik değil — üç bağımsız ölçüm bir soruyu desteklemeye yeter, dördüncüsü
maliyeti getirisi olmadan artırır.

Tercih olduğu için **gizlenmez**. Görev 4'te konulan kural burada da geçerlidir:
yapılmayan şey için nedeni yazılır. Her satır kaç yuva olduğunu, kaçının
kullanıldığını ve hangi grupların elendiğini taşır:

```
soru_id            rakip-kim
mevcut_yuva        6
yuva_sayisi        3
kullanilmayan_yuva Mobil uygulama mağazaları, Haber basın ve sektör yayınları,
                   Dijital ürün ve şablon pazar yerleri
```

`--yuva` parametresi sınırı yükseltir; derinlik istendiğinde altı yuvanın
tamamı açılır. Sınırın az olduğu durumlar da işaretlenir: yalnız bir yuvası olan
soru çıktıda `tek_yuvali_soru` altında listelenir.

## 5.7 Üretilen dosya

### `SECIM-ORNEKLERI.csv` — 72 satır

Üç örnek fikir için üretilen paketler. Satır birimi **(fikir, soru, yuva)**.

```
fikir              diyabet hastaları için mobil takip uygulaması
kategori           mobil-uygulama
ekler              saglik
soru_id            doygun-mu
soru               Pazar doygun mu, boşluk var mı?
yuva               1
kaynak_grubu       Mobil uygulama mağazaları
kanit_turu         İlk 20'nin yorum sayısı dağılımı ve son güncelleme tarihleri
birincil_kaynak    Google Play Store
yedekler           Apple App Store, APKMirror
host               play.google.com
izin_durumu        robots-izinli
olcum_alani        fiyat, indirme_sayisi, puan, siralama, urun_sayisi, yorum_sayisi
kaynak_rolu        cekirdek
neden_secildi      1. kanıt yuvası (Mobil uygulama mağazaları); kategorinin çekirdek kaynağı
mevcut_yuva        2
yuva_sayisi        2
```

Okunuşu: *diyabet uygulaması araştırılırken "pazar doygun mu" sorusunun birinci
kanıt yuvası uygulama mağazalarıdır; oradan ilk 20'nin yorum dağılımına
bakılır. Google Play birincil kaynaktır çünkü kategorinin çekirdeğidir; o
çalışmazsa App Store ve APKMirror denenir. Bu soru için iki yuva mevcuttu,
ikisi de kullanıldı.*

### Üç örnek fikrin paketleri

| Fikir | Kategori | Katman | Ek | Soru | Yuva | Kaynak |
|---|---|---|---|---:|---:|---:|
| Diyabet takip uygulaması | `mobil-uygulama` | — | `saglik` | 10 | 23 | 11 |
| Muhasebeci fatura yazılımı | `b2b-web-yazilimi` | — | `fintech` | 8 | 24 | 13 |
| Esnaf randevu uygulaması | `yerel-hizmet` | `mobil-uygulama` | — | 11 | 25 | 11 |

Kategoriye özel yuvalardan gelen kaynaklar tamamen farklı çıkıyor:

| Fikir | Kategoriye özel kaynaklar |
|---|---|
| Diyabet uygulaması | Google Play Store, NICE |
| Fatura yazılımı | CloudPrice, Indeed, Investing.com, SoftwareSuggest |
| Esnaf randevu uygulaması | Google Play Store, Houzz |

Diyabet ile fatura paketleri arasında **hiç ortak kategori kaynağı yok**.
Diyabet ile randevu arasındaki tek ortak Google Play — ikisi de mobil uygulama
olduğu için doğru. Görev 1'in *"kategori yalnız etiket olmamalı"* şartının
çalışma anındaki karşılığı budur.

### Diğer dosyalar

| Dosya | Rolü |
|---|---|
| `select_sources.py` | Seçim fonksiyonu |
| `test_select_sources.py` | 20 test |

Testler dört şeyi korur: aynı fikrin her zaman aynı paketi vermesini, bir
sorunun yuvalarının farklı grup ve host'lardan gelmesini, seçilen her kaynağın
görev 4 süzgecinden geçmiş olmasını ve elenen yuvanın sessizce kaybolmamasını.

## 5.8 Yeniden üretim

```bash
python3 select_sources.py --fikir "diyabet hastaları için mobil takip uygulaması"
python3 select_sources.py --fikir "..." --yuva 6      # daha derin
python3 select_sources.py --fikir "..." --kategori oyun --ek saglik
python3 -m unittest test_select_sources
```

Script beş dosyayı birden okur: `KATEGORI-KAYNAK.csv` ve `URUN-KATEGORILERI.csv`
(görev 1), `KATEGORI-SORU.csv` (görev 2), `ADAY-KATALOG.csv` (görev 3),
`KAYNAK-ALAN.csv` ve `ARAMA-YUZEYLERI.csv` (görev 4). Önceki görevlerden
herhangi biri yeniden üretildiğinde seçim kendiliğinden güncellenir; seçim
mantığında değişiklik gerekmez.

---

# Görev 6 — Sorguları derlenebilir şablonlara çevirmek

**İstenen:** Sorguları genel kelime listesi olmaktan çıkarıp kaynak, niyet,
ürün dili ve pazar bağlamına göre derlenebilir şablonlara dönüştürmek.

## 6.1 Problem: tek kelime listesi dört şeyi göz ardı ediyor

Görev 1 her kaynak grubuna bir arama kalıbı yazmıştı:

```
kaynak_grubu   Sağlık ve biyoteknoloji dikeyi
hangi_arama    {urun}; {urun} clinical
```

620 kaynak için toplam **30 kalıp**. Kalıp dört şeyi görmüyor:

**Kaynak.** PubMed ile Google Play aynı sorgu sözdizimini kullanmaz. Birine
alan öneki, diğerine mağaza parametresi gider.

**Niyet.** *"Talep var mı"* ile *"şikâyet ne"* aynı kelimelerle aranamaz;
ikincisi sorunu anlatan kelimeleri gerektirir.

**Ürün dili.** Kurucunun cümlesi (*"diyabet hastaları için mobil takip
uygulaması"*) ile mağaza kullanıcısının yazdığı (*"kan şekeri takip"*) aynı
değildir.

**Pazar.** Türkiye ve ABD pazarı için dil, bölge parametresi ve terim farklıdır.

## 6.2 Şablon dört parçadan derlenir

```
[çekirdek terim] + [kaynak grubunun dili] + [niyet eki] + [pazar profili]
  fikirden otomatik    31 grup, sabit        14 soru       TR / US
```

Fikirden fikre değişen tek şey çekirdek terimdir ve o otomatik çıkarılır. Geri
kalan üç tablo **bir kez** yazılır; yeni bir ürün fikri geldiğinde elle terim
eklemek gerekmez.

**Çekirdek terim** iki temizlikle çıkarılır. Birincisi dolgu kelimeler
(*için, hastaları, bir*). İkincisi **dağıtım biçimi** (*mobil, bulut, web*) ve
**ürün tipi** (*uygulaması, yazılımı, kütüphanesi*): mağazaya soruyorsak ürün
zaten mobildir, sorguya `mobil` koymak sonucu daraltır — kaynak grubunun dili
kendi karşılığını (`app`) zaten ekler.

```
"diyabet hastaları için mobil takip uygulaması"  →  diyabet takip
"veteriner için randevu sistemi"                 →  veteriner randevu
"react için bir grafik kütüphanesi"              →  react grafik
```

**Kaynak grubunun dili** aynı konunun kaynağa göre hangi kelimeyle arandığını
tutar: mağazada `app`, geliştirici topluluğunda `library`, akademik yayında
`study`, yerel dizinde `appointment`.

**Niyet ekleri** görev 2'nin kanıt tanımından türetildi — kanıt ne arıyorsa
sorgu da onu aramalı:

| Soru | Ek |
|---|---|
| `talep-var-mi` | (sade terim) |
| `sikayet-ne` | `problem`, `issue`, `sorun` |
| `odeme-istegi` | `pricing`, `premium`, `subscription` |
| `rakip-kim` | `alternative`, `vs`, `competitors` |

## 6.3 Derleme yola göre değişir: uzak sorgu / yerel arama

Kaynakların yolu iki türlüdür ve çıktı buna göre değişir:

| Yol | Kaynak | Çıktı |
|---|---:|---|
| `fulltext` | 217 | **Yerel arama** — sayfa zaten indirilmiş |
| `local_index` | 183 | **Yerel arama** |
| `site_search` | 84 | Uzak URL |
| `opensearch` | 36 | Uzak URL |
| `api` | 13 | Uzak URL |

**400 kaynak yerel aramadır**: sayfaları görev 1–4 boyunca zaten indirildi.
Onlara URL üretmek yanıltıcı olurdu — çıktı, indirilmiş metinde aranacak terim
listesidir.

API uçları sorgu terimini farklı parametrede bekler (`q`, `search_for`, `text`);
parametre adları API dokümanından yazıldı, tahmin edilmedi. Serbest metin
araması kabul etmeyen uçlar (tarih/DOI ile çalışanlar) işaretlenir, zorlanmaz.

**OpenSearch şablonları uydurulmadı.** `ARAMA-YUZEYLERI.csv` bu kaynaklar için
yalnızca tanım dosyasının adresini tutuyordu. 36 kaynağın kendi tanım dosyası
bir kez çekildi, `{searchTerms}` şablonu ayıklandı ve
`OPENSEARCH-SABLONLARI.csv`'ye yazıldı: **28 şablon alındı**, alınamayan 8'i
(403, 404, bozuk XML) gerekçesiyle işaretli. Dosya repoda olduğu için derleyici
ağa çıkmaz.

Pazar parametresi yalnızca kabul eden uçlara eklenir; kabul etmeyene eklemek
sorguyu bozar.

## 6.4 Ürün dili: çeviri katmanı

Türkiye pazarı için hiçbir sözlüğe gidilmez — fikir Türkçe, sorgu Türkçe. Çeviri
yalnızca İngilizce pazar için sorgu üretilirken devreye girer ve dört katmanlıdır:

| Katman | Ne çözer |
|---|---|
| 1. `--terim` | Kullanıcı verdiyse hiçbir yere gidilmez |
| 2. Wikipedia, ifadenin tamamı | Çok kelimeli alan terimleri |
| 3. Wiktionary adayları + kategori dili | Tek kelimeler |
| 4. Wikipedia hakemliği | Kategori dilinin seçemediği kelimeler |

**Wiktionary bir sözlüktür**, kelimenin olabilecek karşılıklarını verir:
`randevu` için `date`, `rendezvous`, `appointment`. Üçü de doğru çeviridir;
hangisini kastettiğimizi sözlük bilemez.

**Kategori dili belirsizliği çözer.** Yerel hizmet araştırmasında `appointment`
geçerlidir, `date` değil — kategori dili bizim kendi tablomuzdur ve 6.2'deki
kaynak grubu dillerinden türetilir.

**Wikipedia hakemlik yapar.** Kategori dili karar veremediğinde aynı kelime
Wikipedia'ya sorulur; dönen İngilizce başlık Wiktionary adaylarından biriyse
**iki bağımsız kaynak aynı şeyi söylüyor** demektir ve seçim güvenlidir.
`fatura` böyle çözülür: Wiktionary `bill, invoice, note` verir, Wikipedia
`Invoice` der, ikisinin kesişimi seçilir.

**Wikipedia sonucu koruma altındadır.** Wikipedia araması ilgisiz makaleye
düşebilir (`randevu sistemi` → *Sağlık.NET*). Bu yüzden bulunan başlığın aranan
ifadenin kelimelerinin **tamamını** içermesi aranır. Yarım eşleşme kabul edilse
ifadenin bir parçası sessizce düşerdi: `diyabet takip` → *Diyabet* → `diabetes`
olur, `takip` kaybolurdu. Kısmi eşleşmeler bunun yerine bitişik ikili gruplara
bırakılır — `kan şekeri takip` ifadesinde `kan şekeri` Wikipedia'da tam
karşılığı olan bir terimdir, `takip` ayrıca çevrilir.

**Hiçbir katman çözemezse çeviri yapılmaz.** Orijinal kelime kalır, satırda
gerekçesi yazılır. Yanlış çeviri yapmak çevirmemekten kötüdür: `randevu` yerine
`dating` aramak bütün sonucu bozar.

Bütün kararlar `TERIM-ONBELLEGI.json`'da izleriyle saklanır ve dosya repoya
işlenir. Böylece görev 5'in determinizm şartı korunur ve aynı terim için iki kez
ağa çıkılmaz.

## 6.5 Sonuç

Üç örnek fikrin 72 kanıt yuvası için **33 uzak URL** ve **34 yerel arama**
üretildi; tek kalıp yerine **69 farklı sorgu metni** çıktı.

Kalan 5 satır derlenmedi ve nedeni yazılı: Lemmy için keşfedilen uç
`/api/v3/site`, örnek bilgisi döndüren bir uçtur — sonuna arama terimi eklemek
arama yapmaz. Keşfedilmiş her uç arama ucu değildir; olmayanı zorlamak yerine
işaretlenir ve o yuvanın yedekleri (Hacker News, YouTube) devreye girer.

Bir kaynağın sorgu ucu başka bir alan adında olabilir — Lemmy'nin defterdeki
adresi `join-lemmy.org` (proje sitesi) iken API'si `lemmy.ml` (örnek sunucu)
üzerindedir. Bu meşrudur ama `alan_notu` sütununda görünür kalır: bir kaynağın
sayfasından başkasının arama ucunu devralmak sessizce olmamalı.

**Aynı kaynak, farklı soru:**

```
Google Play / doygun-mu      q=diyabet+takip+app
Google Play / sikayet-ne     q=diyabet+takip+app+problem
Google Play / odeme-istegi   q=diyabet+takip+app+pricing
```

**Aynı soru, farklı kaynak:**

```
Stack Exchange / rakip-kim   api.stackexchange.com/2.3/questions?site=...&q=diyabet+takip+library+alternative
Dimensions / giris-engeli    (yerel arama) 'diyabet takip study regulation'
```

**Aynı sorgu, farklı pazar:**

| Pazar | Sorgu |
|---|---|
| TR | `q=diyabet+takip+app+problem&hl=tr&gl=TR` |
| US | `q=diabetes+takip+app+problem&hl=en&gl=US` |

Çeviri sonuçları: `fatura` → `invoice` (Wikipedia hakemliği), `randevu` →
`appointment` (kategori dili), `diyabet` → `diabetes` (Wiktionary tek aday).
`takip`, `esnaf`, `muhasebeciler` çevrilemedi ve satırlarında gerekçesi yazılı —
`takip` için Wiktionary'de karşılık yok, `esnaf` Türkçeye özgü bir kavram.

## 6.6 Üretilen dosyalar

### `DERLENMIS-SORGULAR.csv` — 72 satır

```
fikir              diyabet hastaları için mobil takip uygulaması
kategori           mobil-uygulama
soru_id            sikayet-ne
kaynak             Google Play Store
kaynak_grubu       Mobil uygulama mağazaları
pazar              TR
yol                opensearch
cekirdek_terim     diyabet takip
grup_dili          app
niyet_eki          problem
sorgu_metni        diyabet takip app problem
sorgu_turu         uzak-url
derlenmis_sorgu    https://play.google.com/store/search?q=diyabet+takip+app+problem&hl=tr&gl=TR
yedekler           Apple App Store, APKMirror
```

Okunuşu: *diyabet uygulaması için "şikâyet ne" sorusu Google Play'e sorulacak;
çekirdek terim `diyabet takip`, mağaza dili `app` ekliyor, niyet `problem`
ekliyor. Yol OpenSearch olduğu için çıktı bir URL. Google Play yanıt vermezse
App Store denenecek.*

Aynı satırın ABD pazarı karşılığı `DERLENMIS-SORGULAR-US.csv`'de, çeviri
sütunlarıyla:

```
orijinal_terim     diyabet takip
cekirdek_terim     diabetes takip
ceviri_guveni      orta
ceviri_katmani     wiktionary+kategori (kismi)
ceviri_uyarisi     1 kelime çevrilemedi
```

### Diğer dosyalar

| Dosya | Rolü |
|---|---|
| `query_templates.py` | Dört parçalı şablon: grup dili, niyet ekleri, pazar, çekirdek terim |
| `compile_queries.py` | Yol farkındalıklı derleyici |
| `terim_sozlugu.py` | Dört katmanlı çeviri ve önbellek |
| `fetch_opensearch_templates.py` | Tanım dosyalarını bir kez çeker |
| `OPENSEARCH-SABLONLARI.csv` | 36 kaynak, 28 şablon |
| `TERIM-ONBELLEGI.json` | Çeviri kararları ve izleri |
| `test_query_templates.py` | 27 test |
| `test_terim_sozlugu.py` | 20 test |

Testler dört şeyi korur: sorgunun kaynağa ve niyete göre gerçekten değiştiğini,
yerel yolların URL üretmediğini, alınamamış OpenSearch şablonu yerine URL
uydurulmadığını ve çeviri kararlarının izlenebilir olduğunu. Çeviri testleri ağa
çıkmaz; hepsi önbellek ve saf fonksiyonlar üzerinden kurulur.

## 6.7 Yeniden üretim

```bash
python3 compile_queries.py --pazar TR
python3 compile_queries.py --pazar US --out DERLENMIS-SORGULAR-US.csv
python3 compile_queries.py --fikir "..." --terim "veterinary appointment"
python3 -m unittest test_query_templates test_terim_sozlugu
```

Derleyici görev 5'in çıktısını, arama yüzeylerini, OpenSearch şablonlarını ve
terim önbelleğini okur. Dördü de repoda olduğu için çalıştırma ağa çıkmaz.
Önbellekte olmayan bir terim için ağa çıkmak `--cevrimici` ile açıkça istenir;
istenmezse terim çevrilmeden bırakılır ve satırda gerekçesi kalır.

Yeni tanım dosyası gerektiğinde:

```bash
python3 fetch_opensearch_templates.py --canli
```
