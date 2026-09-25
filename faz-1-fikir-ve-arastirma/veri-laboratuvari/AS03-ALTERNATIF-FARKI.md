# AS-03 — Alternatifin farkı, limitleri ve kalan eksikleri

**Sürüm 1.0.0** · Ölçüm: 2026-09-25 · Üreten: `alternatif_fark.py`
Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan

AS-01 kapalı kaynaklara alternatif aradı ve buldu. Bu belge **farkı** ölçer:
bir alternatifin çalışması, kapananın yerini tuttuğu anlamına gelmez.

## 1. Arşiv güncel veri değildir — ve dizinimiz bunu göstermiyordu

Bir arşiv kopyasının **iki tarihi** vardır ve ikisi karıştırılırsa eski bir
sayfa bu ayın verisi görünür:

| | Ne demek |
|---|---|
| `arsiv_icerik_tarihi` | Common Crawl'ın sayfayı çektiği an — **içeriğin yaşı** |
| `bizim_cekme_tarihimiz` | O kopyayı bizim indirdiğimiz an |

`ARTEFAKT-DIZINI.csv` yalnız ikincisini tutuyordu. Arşivin kendi zaman
damgası koşu JSON'unda duruyordu ve hiçbir tabloya taşınmamıştı.

Ölçülen sonuç — **104 arşiv kopyasının yaşı**:

| Yaş | Kaynak |
|---|---:|
| 0-90 gün | 9 |
| 90-180 gün | 1 |
| 180-365 gün | 1 |
| **365+ gün** | **93** |

**94 kopya 180 günlük uyarı eşiğini aşıyor.** En eskiler:

| Kaynak | Arşiv içerik tarihi | Bizim çekme tarihimiz | Yaş (gün) |
|---|---|---|---:|
| Indiegogo | 2025-02-06 | 2026-09-03 | 596 |
| Bureau of Labor Statistics | 2025-02-06 | 2026-09-03 | 596 |
| Regulations.gov | 2025-02-06 | 2026-09-03 | 596 |
| U.S. Securities and Exchan | 2025-02-06 | 2026-09-03 | 596 |
| Brave Search | 2025-02-07 | 2026-09-03 | 595 |
| CodeProject | 2025-02-07 | 2026-09-03 | 595 |
| Monster | 2025-02-07 | 2026-09-03 | 595 |
| ResearchGate | 2025-02-07 | 2026-09-03 | 595 |
| SearXNG | 2025-02-08 | 2026-09-03 | 594 |
| TrustRadius | 2025-02-08 | 2026-09-03 | 594 |

Hepsi dizinde `2026-09-03` görünüyordu. Ayrıntı:
[`AS03-ARSIV-YASI.csv`](AS03-ARSIV-YASI.csv) — her satır `guncel_veri_mi = hayır`.

## 2. Alternatifin farkı

8 eşleşme incelendi. **4'i satıcının kendi sitesi**, yani
fiyat verir şikâyet vermez.

| Kapanan | Alternatif | Verdiği | Fark | Kalan eksik |
|---|---|---|---|---|
| G2 | Filestage | fiyat | SATICI SİTESİ — fiyat/ürün verir, kullanıcı şikâyeti V | kullanıcı şikâyeti ve problem ifadesi |
| G2 | Ziflow | fiyat | SATICI SİTESİ — fiyat/ürün verir, kullanıcı şikâyeti V | kullanıcı şikâyeti ve problem ifadesi |
| Capterra | Filestage | fiyat | SATICI SİTESİ — fiyat/ürün verir, kullanıcı şikâyeti V | kullanıcı şikâyeti ve problem ifadesi |
| Capterra | Ziflow | fiyat | SATICI SİTESİ — fiyat/ürün verir, kullanıcı şikâyeti V | kullanıcı şikâyeti ve problem ifadesi |
| Reddit | Apple App Store — Booksy Biz | fiyat, puan, yazar, kullanıcı yorumu | üçüncü taraf — kullanıcı yorumu taşıyor | — |
| Trustpilot | (bulunamadı) |  | alternatif yok — bu kaynağın verdiği hiçbir alan başka | tüketici yorumu ve puanı — kaynağı yok |
| Google Play Store | Apple App Store | puan, yazar, kullanıcı yorumu | üçüncü taraf — kullanıcı yorumu taşıyor | — |
| Capterra Education | (bulunamadı) |  | alternatif yok — bu kaynağın verdiği hiçbir alan başka | eğitim yazılımı yorumu ve fiyatı — kaynağı yok |

### G2 ve Capterra'nın yerini hiçbir şey tutmuyor

İkisi de **kullanıcı yorumu** veriyordu. Bulunan alternatifler (Filestage,
Ziflow) satıcının kendi siteleri: fiyat ve ürün iddiası verirler, kendileri
hakkındaki şikâyeti yayımlamazlar. Kanıt politikası da aynı yere varıyor —
*"aynı kurumun pazarlama kopyaları bir köken"*.

G2 için arşiv kopyası var ama işe yaramıyor: elimizdeki kopya G2'nin **ana
sayfası**, yorum sayfası değil; 9.965 karakter ve sıfır çıkarılabilir alan.
Üstelik **590 gün eski.**

### Alternatifi bulunamayanlar

2 kaynak için alternatif **arandı ve bulunamadı**:

- **Trustpilot** (F07) — tüketici yorumu ve puanı — kaynağı yok
- **Capterra Education** (F10) — eğitim yazılımı yorumu ve fiyatı — kaynağı yok

Bu bir eksiklik kaydı değil **sınır** kaydıdır: aranmış, bulunamamış.

## 3. Çözülemeyenler için sonraki seçenekler

| Engel türü | Sonraki seçenek |
|---|---|
| **Politika** (Reddit, Trustpilot) | Kaynağın resmî araştırma programına başvuru — hesap ve şartname onayı gerekir, **karar Çağlar'da** |
| **Bot koruması** (G2, Capterra) | Üçüncü taraf kaynak · arşiv (yaşıyla) · resmî API varsa registry'ye ekleme |
| **JS kabuğu** (Google Play) | Aynı ürünün başka platformdaki sayfası — App Store'da çalıştı |

Hiçbiri **zorlama** içermiyor: bot koruması aşılmıyor, robots yasağına
uyuluyor.

## 4. Bu belge ne söylemez

- Bir alternatifin bulunması kanıt yeterliliği sağlamaz; 3/2 eşiği Faz 3'e ait.
- **Arşiv sonucu tam ya da güncel veri gibi sunulamaz.** Her arşiv satırı
  kendi tarihini ve yaşını taşır.
- Alternatif bulunamaması o pazarda talep olmadığını göstermez.
- Ölçüm 2026-09-25 tarihlidir.

## 5. Yeniden üretim

```bash
python3 alternatif_fark.py --yaz
python3 -m unittest test_alternatif_fark
```
