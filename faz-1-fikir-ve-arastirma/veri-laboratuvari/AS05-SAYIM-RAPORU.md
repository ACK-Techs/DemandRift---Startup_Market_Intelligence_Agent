# AS-05 — Kanıt sayımı, bağımsızlık ve alıntı kontrolü

**Sürüm 1.0.0** · Politika: `kanit-yeterliligi-v1` · Ölçüm: 2026-09-27
Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan

AS-05 BT-07'ye bağlı ve o bildirim gelmedi. Faz 3 rehberi sayım incelemesini
bana veriyor ("3/2 sınırını Batuhan uygular; **Ayselin sayımı inceler**"), bu
yüzden eşiği **kendi verimize** uyguladım ve nerede geçip nerede geçmediğini
ölçtüm.

## 1. En önemli bulgu: bağımsızlığı yanlış seviyede ölçüyoruz

Politika **kişi/kurum** bağımsızlığı istiyor: *"en az 3 bağımsız kullanıcı veya
kurum gözlemi"*. Bizim veri kümemiz **belge ve kaynak** seviyesinde. İkisi aynı
şey değil:

| Durum | Kaç bağımsız gözlem |
|---|---|
| Üç farklı satıcının ilan ettiği fiyat | 3 kurum gözlemi |
| Bir sayfadan çıkan üç fiyat | 1 kurum, 1 gözlem |
| Bir forumdaki üç yorum, yazarı bilinmiyor | **0** — bilinmeyen bağımsızlık |

`KATEGORI-ALANLARI.csv`'de kullanıcı kimliği alanı **yok**. Yani aynı kişinin
tekrarı ile farklı kişiler ayırt edilemiyor.

Politika bu durumda ne yapılacağını söylüyor: *"Kimliği/bağımsızlığı belirsiz
örnek alt eşiğe eklenmez; bilinen/unknown ayrı raporlanır."* Uyguladım.

## 2. 3/2 eşiği uygulandığında

77 hücre sayıldı. Sonuç:

| | Hücre |
|---|---:|
| Nicel eşiği **geçen** | **14** |
| Tüm örneklerin bağımsızlığı bilinmediği için düşen | **50** |
| Bağımsız gözlem var ama 3'ün altında | 13 |

Geçen hücreler:

| Kategori | Niyet | Bağımsız gözlem | Ayrı kaynak | Bilinmeyen |
|---|---|---:|---:|---:|
| b2b-web-yazilimi | competitor_discovery | 5 | 17 | 12 |
| b2b-web-yazilimi | observed_market_pricing | 17 | 19 | 2 |
| eklenti-entegrasyon | competitor_discovery | 5 | 13 | 8 |
| eklenti-entegrasyon | observed_market_pricing | 9 | 9 | 0 |
| fintech | competitor_discovery | 5 | 6 | 1 |
| gayrimenkul | observed_market_pricing | 3 | 3 | 0 |
| gelistirici-araci | competitor_discovery | 4 | 5 | 1 |
| mobil-uygulama | competitor_discovery | 3 | 4 | 1 |
| ortak | competitor_discovery | 12 | 50 | 38 |
| ortak | existing_alternatives | 4 | 16 | 12 |
| ortak | observed_market_pricing | 38 | 45 | 7 |
| oyun | observed_market_pricing | 4 | 4 | 0 |
| yapay-zeka-urunu | observed_market_pricing | 5 | 5 | 0 |
| yerel-hizmet | observed_market_pricing | 6 | 8 | 0 |

Hepsi `observed_market_pricing`, `competitor_discovery` ve
`existing_alternatives` — yani **kurum gözlemi** sayılabilen niyetler. Bir
satıcının kendi sayfasında ilan ettiği fiyat o kurumun beyanıdır ve
sayılabilir.

Kişi gözlemi gerektiren niyetlerde (`problem_demand`, `dissatisfaction`,
`stated_wtp_weak_signal`, `use_case`) **hiçbir hücre geçmiyor**, çünkü kim
söylemiş bilmiyoruz.

## 3. Karşıt bulgular ayrı sayıldı

2 örnek doğrudan karşıt bulgu olarak işaretli. Politika bunların ayrı
raporlanmasını istiyor; destekleyen ve karşıt örnekler aynı kefeye konmadı.

## 4. Alıntı bağı — metin, hash, sürüm

307 çıkarılan değerin tamamı kontrol edildi:

| | Adet |
|---|---:|
| Geçerli alıntı | **307** |
| Kopuk | 0 |
| Hash doğrulandı | 307 |

Metin bağının nerede çözüldüğü:

- gövde sütununda: 205
- ham artefaktta (gövde sütunu kırpılmış): 102

**Dikkat edilmesi gereken:** `body_normalized` sütunu 4000 karakterde
kırpılıyor. 102 değer yalnız ham artefaktta doğrulanabiliyor.
Alıntı doğrulaması CSV sütunu üzerinden değil **artefakt üzerinden** yapılmalı.

Sürüm bağı her satırda var (`normalization_version`).

## 5. Claim düzeyinde bildirim

| # | İddia | Durum | Gerekçe |
|---|---|---|---|
| CL-01 | Kategori × niyet hücreleri 3/2 kanıt eşiğini sağlıyor | **DESTEKLENMIYOR** | 58 hücrede örneklerin bağımsızlığı kişi/kurum düzeyinde bilinmiyor. Politika b |
| CL-02 | problem_demand / dissatisfaction / stated_wtp bulgular | **DESTEKLENMIYOR** | 38 hücre kişi gözlemi gerektiriyor ama veri kümesinde kullanıcı kimliği alanı  |
| CL-03 | 14 hücre nicel eşiği geçtiği için bulgu üretilebilir | **KISMEN** | Nicel taban sağlandı ama politika 'sayılar tek başına yeterli değildir' diyor: |
| CL-04 | Çıkarılan her değer alıntı olarak taşınabilir | **DESTEKLENIYOR** | 307 değerin 307'i artefaktında bulundu ve hash'i doğrulandı; kopuk alıntı yok |

Hiçbiri kapatılmış değil; Batuhan kontrolü bekliyor.

## 6. Bu sayım ne söylemez

- **Eşiği geçmemek "pazar kötü" demek değildir.** Politika açık: *"erişim
  engeli, bütçe bitmesi veya no_results ile Kill üretilmez."* Geçmemek
  "bu veriyle sonuca varılamaz" demektir.
- **Nicel eşik tek başına yetmez.** Politika *"sayılar tek başına yeterli
  değildir"* diyor; hedef müşteri, güncellik, karşıt kanıt araması ve alıntı
  doğrulanabilirliği ayrıca geçmelidir. Bu sayım onların yerine geçmez.
- **Fiyat beyanı gerçek ödeme değildir.** Geçen hücrelerin hepsi ilan edilmiş
  fiyata dayanıyor; kimsenin o fiyatı ödediği gösterilmiş değil.
- Uydurma başarı ya da güven yüzdesi üretilmedi.

## 7. Yeniden üretim

```bash
python3 kanit_sayimi.py --yaz
python3 -m unittest test_kanit_sayimi
```
