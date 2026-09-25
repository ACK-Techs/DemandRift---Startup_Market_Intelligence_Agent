# AS-04 — Hata incelemesi ve etiketli referans

**Sürüm 1.0.0** · Ölçüm: 2026-09-25 · Üreten: `hata_incelemesi.py`
Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan

AS-04 Faz 2'ye ait ve BT-06 hata bildirimine bağlı; bildirim gelmedi. Kartın
istediği dört hata sınıfını **kendi verimizde** aradım, bulduklarımı düzelttim
ve etiketli referans kümesini kurdum. Batuhan bildirim gönderdiğinde aynı
yöntem onun örneklerine uygulanacak.

## 1. Dört hata sınıfı — arandı, ne çıktı

### Dedup yanlış birleşmesi — bulunamadı

77 çapraz-kaynak birleşme incelendi,
**hiçbiri yanlış değil.** Hepsi aynı alan adının farklı katalog kayıtları —
örneğin Facebook, Facebook Marketplace ve Facebook Pages tek `robots.txt`
dosyasını paylaşıyor. Birleşme doğru.

"Aranmış ve bulunamamış" ile "hiç bakılmamış" aynı şey değil; bu satır
birincisini kaydeder.

### Yanlış/eksik alan — bulundu ve düzeltildi

Fiyat yüzeyi olarak çekilmiş **48 sayfada fiyat çıkmıyordu**. 25'inin gövdesinde
apaçık fiyat vardı: Kagi `$5/$10/$25`, Sistrix `€119/€239/€419`, Exploding
Topics `$39/$99/$249`.

Kök sebep: alan çıkarımı **kaynağın ailesine** bakıyordu, sayfanın kendisine
değil. Ailesi eşlenmemiş kaynaklar `genel` sınıfına düşüyordu ve o sınıfın hiç
deseni yoktu — yani `/pricing` sayfasından bile fiyat aranmıyordu.

Düzeltme: sayfanın kendi türü de hangi desenlerin aranacağını belirliyor.

| | Önce | Sonra |
|---|---:|---:|
| Çıkarılan alan | 212 | **273** |
| Alan çıkan belge | 164 | **213** |
| Fiyat | 56 | **108** |
| Fiyat sayfası olup fiyat çıkmayan | 48 | **16** |

Kalan 13 sayfada gövdede fiyat ifadesi yok — sayfa fiyat yayımlamıyor.

### Filtrede kaybolan kanıt — 10 gerçek kayıp

"Ölçüm kanıtı üretmez" diye elenen belgelerin 76'sinde fiyat çıktı.
Bağlamlarına tek tek bakınca **10'u gerçek kanıt**, 66'sı gürültü:

| Kaynak | Bulgu | Neden kayıp |
|---|---|---|
| Airbnb | `₺4,733 · r sign up Popular homes in Istanbul 0 of 0 items ` | ilan/puan işaretinin yanında gerçek fiyat |
| AppSumo | `$39 · p Manifest V3 Chrome extensions from a plain-English` | ilan/puan işaretinin yanında gerçek fiyat |
| AppSumo | `$79 · rs, covers, and KDP-ready exports from one AI worksp` | ilan/puan işaretinin yanında gerçek fiyat |
| Infracost | `$51 · What is Infracost? github.com/acme/infra Last scanne` | ilan/puan işaretinin yanında gerçek fiyat |
| Lyft | `$23 · ng on XL, Extra Comfort, Black, and Black SUV rides.` | ilan/puan işaretinin yanında gerçek fiyat |
| Remote OK | `$ 0 · lent on demand, pre-screened and thoroughly vetted. ` | ilan/puan işaretinin yanında gerçek fiyat |

Gürültü örnekleri fiyat gibi görünüp fiyat olmayanlar: "$2.3 **billion** in AUM"
(fon büyüklüğü), "$1,000,000 total **prize pool**" (yarışma ödülü), "$2.1
billion NASA cost estimate" (haber başlığı).

Ayrım kuralı: fiyatın yanında **ilan işareti** (puan, yorum sayısı, `/month`,
`for 2 nights`) varsa kanıt; **büyüklük ifadesi** (milyar, fon, ödül) varsa
değil.

### Desteksiz claim — bulunamadı

Alan çıkmamış belgeye dayanan 200 matris satırı incelendi.
**Hiçbiri desteksiz değil**: her biri zaten `alinabilen_alan = "(ölçülebilir
alan yok)"` diyor ve `kanit_gerekcesi` alanında "yüzey olarak çekildi"
yazıyor. Satırlar ne olduklarını dürüstçe beyan ediyor.

## 2. Etiketli referans kümesi

Otomatik etiket insan etiketinin yerine geçmez. Faz 2 rehberi açıkça *"örnek
sonuçları **insan etiketlesin**"* diyor. Aşağıdaki 15 örneği elle açtım,
bağlamını okudum, sebebiyle etiketledim.

| # | Örnek | Etiket | Sebep | Karşıt bulgu |
|---|---|---|---|---|
| ET-01 | 500 Global ana sayfası · fiyat=$2.3 | **irrelevant** | bağlam 'VC firm with $2.3 billion in AUM' — fon büyüklüğü, ürün fiyatı | — |
| ET-02 | Alibaba ana sayfası · fiyat=$1,000,000 | **irrelevant** | 'total prize pool' — yarışma ödülü, üstelik JSON bloğu içinde | — |
| ET-03 | Ars Technica ana sayfası · fiyat=$2.1 | **irrelevant** | 'NASA's cost estimate ... $2.1 billion' — haber başlığı | — |
| ET-04 | Axios ana sayfası · fiyat=$1 | **irrelevant** | '$1 Trump coins' — haber başlığı | — |
| ET-05 | Airbnb ana sayfası · fiyat=₺4,733 | **relevant** | '₺4,733 for 2 nights · 4.78 out of 5' — gerçek ilan fiyatı, puanıyla b | — |
| ET-06 | AppSumo ana sayfası · fiyat=$39 | **relevant** | '3 reviews $39 / lifetime $129' — gerçek ürün listesi | — |
| ET-07 | SourceForge · 'salon scheduling software' ar | **irrelevant** | HTTP 200 ve 19 bin karakter geldi ama içerik Kubernetes orkestrasyon v | — |
| ET-08 | Kagi /pricing · $5 $10 $25 | **relevant** | plan fiyatları; çıkarıcı kaçırıyordu, sayfa doğru | — |
| ET-09 | Google Play · Sleep Cycle uygulama sayfası | **uncertain** | HTTP 200 geldi ama gövde boş; sayfa doğru olabilir, biz göremiyoruz —  | — |
| ET-10 | G2 arşiv kopyası (2025-02-12) | **uncertain** | G2'nin ana sayfası, yorum sayfası değil; 596 gün eski. İçerik gerçek a | — |
| ET-11 | Booksy Biz App Store yorumu · 'charged for a | **relevant** | F09'un tam konusu: işletmenin no-show sorunu, gerçek kullanıcı ifadesi | — |
| ET-12 | Fresha /pricing · TRY 240.95 per month | **relevant** | satıcının ilan ettiği plan fiyatı, TR pazarına yerelleşmiş | — |
| ET-13 | Filestage 'alternatives' sayfası | **uncertain** | rakip listesi var ama satıcının kendi pazarlama sayfası; bağımsız kanı | — |
| ET-14 | Booksy Biz · 4.5 puan, 14.888 yorum | **relevant** | yüksek puan, F09'un 'bu alanda çözüm yok' varsayımına KARŞIT sinyal —  | **EVET** |
| ET-15 | Fresha · ücretsiz katman + düşük abonelik | **relevant** | F09'un 'ödeme isteği var' varsayımına KARŞIT: pazarda ücretsiz alterna | **EVET** |

### Precision — ve recall neden yok

```
incelenen örnek : 15
relevant        : 7
irrelevant      : 5
uncertain       : 3
precision       : 0.467
recall          : YOK
```

**Recall hesaplanmadı ve hesaplanamaz.** Recall için açık web'deki tüm ilgili
içeriğin bilinmesi gerekir; bilinmiyor. Kart da bunu yasaklıyor: *"Etiketli
referans olmadan web recall oranı üretme."* Faz 2 rehberi aynı şeyi diyor:
*"referans yoksa recall yok"*.

Precision düşük görünüyor (0.467) ama bu bir kalite ölçüsü değil:
örnekler **kasten zor vakalardan** seçildi — filtrenin elediği, çıkarıcının
kaçırdığı, arşivden gelen. Temsili bir örneklem değil, sınır vakası kümesi.

### Doğrudan karşıt bulgular

2 örnek doğrudan karşıt bulgu olarak işaretlendi — yani mevcut fikrin
varsayımını **çürüten** yönde:

- **Booksy Biz · 4.5 puan, 14.888 yorum** — yüksek puan, F09'un 'bu alanda çözüm yok' varsayımına KARŞIT sinyal — mevcut çözüm var ve memnuniyet yüksek
- **Fresha · ücretsiz katman + düşük abonelik** — F09'un 'ödeme isteği var' varsayımına KARŞIT: pazarda ücretsiz alternatif mevcut

Kanıt politikası karşıt bulgunun ayrı sayılmasını istiyor; destekleyen ve
karşıt örnekler aynı kefeye konmuyor.

## 3. Bu belge ne söylemez

- Precision bu kümeye aittir, veri kümesinin tamamına değil.
- **Recall yok.** Hiçbir yerde web recall oranı üretilmedi.
- 3 örnek `uncertain` kaldı; zorlama etiket konmadı.
- Hiçbir satır kabul edilmiş değil; Batuhan kontrolü bekliyor.

## 4. Yeniden üretim

```bash
python3 hata_incelemesi.py --yaz
python3 -m unittest test_hata_incelemesi
```
