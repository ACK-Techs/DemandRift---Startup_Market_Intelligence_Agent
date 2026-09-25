# SourceFitMatrix — şema ve alan taslağı

**Sürüm 1.0.0** · Üreten: `source_fit_matrix.py` · Hazırlayan: Ayselin Aydoğdu

Bu belge `SOURCE-FIT-MATRIX.csv` dosyasının alan sözleşmesidir. Amaç: aynı
şemayı kullanan başka bir çalışmanın satırları aynı anlamda okuyabilmesi.

## Satırın anlamı

Bir satır şu cümledir: **"<kategori> kategorisinde <arama_niyeti> sorusuna,
<source_id> kaynağı cevap verebilir, ve bunun kanıtı <ornek_kayit>."**

Kanıtı olmayan cümle satır olmaz. Kanıtsız kalan (kategori, niyet) çifti
`KATEGORI-YETERLILIK.csv` içinde **gap** olarak, sebebiyle birlikte durur.

## Alanlar

| Alan | Tip | | Anlamı |
|---|---|---|---|
| `kategori` | `string` | zorunlu | URUN-KATEGORILERI.csv'deki ürün kategorisi |
| `arama_niyeti` | `enum(7)` | zorunlu | Faz2-Plan.md'nin yedi niyetinden biri. observed_market_pricing ve stated_wtp_weak_signal AYRI değerlerdir, birleştirilmez. |
| `source_id` | `string` | zorunlu | Kanonik kaynak kimliği (source_manifest.json) |
| `ornek_kayit` | `string` | zorunlu | document_id + kaynak URL. Bu satırın dayandığı, GERÇEKTEN AÇILMIŞ belge. Boş olamaz — dayanağı olmayan eşleşme satır olmaz. |
| `kanit_gerekcesi` | `string` | zorunlu | Bu belgenin neden o niyetin kanıtı sayıldığı (çıkarılan alan ya da yüzey türü) |
| `beklenen_benzersiz_katki` | `string` | zorunlu | Bu kaynağın aynı hücredeki diğerlerinin vermediği katkı |
| `alinabilen_alan` | `string[]` | opsiyonel | Belgeden gerçekten çıkarılmış alanlar. Çıkmadıysa '(ölçülebilir alan yok)' |
| `bagimsizlik_grubu` | `string` | zorunlu | Aynı kayıtlı alan adı ya da duplicate_of ilişkisi olan kaynaklar aynı gruptadır. Yeterlilik sayımı kaynak değil GRUP sayar. |
| `dil_pazar` | `string` | zorunlu | Belgelerden okunan dil + TR/global pazar işareti |
| `tazelik` | `string` | zorunlu | Sayfa yayın tarihi beyan ediyorsa o tarih; etmiyorsa 'yayın tarihi YOK' ve yalnızca toplama anı. Tarih TAHMİN EDİLMEZ. |
| `erisim_kisiti` | `string` | zorunlu | Arşiv/JS kabuğu/politika kısıtı + erişim anlığının tarihi. Erişim anlığı GÜNCEL İZİN GARANTİSİ DEĞİLDİR. |
| `fallback` | `string` | zorunlu | FARKLI bir bağımsızlık grubundan yedek kaynak. Aynı gruptaki kaynak yedek değil, kopyadır. |
| `aday_sorgu_yuzeyi` | `string` | zorunlu | ARAMA-YUZEYLERI.csv'den sorgu yolu. Arama SONUCU aday keşiftir, kanıt değildir. |
| `incelenen_belge_sayisi` | `int` | zorunlu | Bu eşleşmeyi destekleyen belge sayısı |

## Arama niyetleri

Faz2-Plan.md'nin yedi niyeti. Sıra sabittir.

| Niyet | Tanım |
|---|---|
| `problem_demand` | Kullanıcıların problemi veya ihtiyacı nasıl anlattığı |
| `existing_alternatives` | Bugün hangi ürün, yöntem veya workaround kullanıldığı |
| `dissatisfaction` | Mevcut çözümlerle ilgili şikâyet ve eksikler |
| `use_case` | Kullanım bağlamı ve gerçek iş akışı |
| `competitor_discovery` | Doğrudan ve dolaylı rakip adayları |
| `observed_market_pricing` | Satıcı sayfasında yayımlanan fiyat, paket ve ticari model |
| `stated_wtp_weak_signal` | Kullanıcının açık fiyat ifadesi. ZAYIF BEYAN SİNYALİDİR; gerçek ödeme davranışı sayılmaz (Faz2-Plan.md) |

### İki fiyat niyeti neden ayrı

`observed_market_pricing` satıcının kendi sayfasında **yazan** fiyattır:
gözlemlenebilir, doğrulanabilir bir ticari veridir.

`stated_wtp_weak_signal` kullanıcının "buna şu kadar öderim" demesidir.
Faz2-Plan.md bunu açıkça **zayıf beyan sinyali** sayar ve gerçek ödeme
davranışı kabul etmez. İkisi tek sütunda birleşirse, bir forum yorumu bir
fiyat listesiyle aynı ağırlığa gelir.

Bu veri kümesinde `stated_wtp_weak_signal` için **hiç kanıt yoktur** ve her
kategoride açık gap taşır. Sebebi ölçülmüştür: o sinyal sayfanın adresinden
değil metninden okunur, bu çalışmada metin taraması yapılmadı.

## Üç sayım kuralı

1. **Bağımsızlık kaynak değil grup sayar.** Aynı kayıtlı alan adına sahip ya da
   belgeleri `duplicate_of` ile bağlı kaynaklar tek gruptur. `421` grup,
   `489` kaynaktan türedi.
2. **Yeterlilik eşiği 2 bağımsız gruptur.** Altında kalan hücre `zayif`
   işaretlenir: kanıt var ama tek sahiplikten geliyor.
3. **Boş hücre pazar sonucu değildir.** Her gap bir sebep kodu taşır:
   `yontem-disi`, `yuzey-bulunamadi`, `js-kabugu`, `erisilemiyor`,
   `icerik-yok`, `kaynak-yok`. Hiçbiri "bu pazarda talep yok" demez.

## Bu sürümün durumu

| | Hücre |
|---|---:|
| Yeterli (2+ bağımsız grup) | 47 |
| Zayıf (tek grup) | 29 |
| Boş (gap) | 36 |
| **Toplam** | **112** |

## Bağlı dosyalar

| Dosya | Rol |
|---|---|
| `SOURCE-FIT-MATRIX.csv` | Eşleşmeler — bu şemanın uygulandığı yer |
| `KATEGORI-YETERLILIK.csv` | Hücre bazında yeterlilik ve gap sebebi |
| `PAKET-ONERILERI.csv` | Kategori başına Standard/Deep aday paketi |
| `NORMALIZE-BELGELER.csv` | `ornek_kayit`ın işaret ettiği belgeler |
| `KAYNAK-ALAN.csv` | Alan × izin matrisi (Görev 4) |
| `ARAMA-YUZEYLERI.csv` | `aday_sorgu_yuzeyi`nin kaynağı |
