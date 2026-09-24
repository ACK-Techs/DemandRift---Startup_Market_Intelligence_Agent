# AS-01 eki — kapalı kaynaklara izinli alternatif

**Sürüm 1.0.0** · Ölçüm tarihi: 2026-09-24 · Üreten: `alternatif_kaynak.py`
Hazırlayan: Ayselin Aydoğdu · Kontrol eden: Batuhan

AS-01 ölçümü F02 ve F09'un **hiçbir kaynağının** bugün içerik vermediğini
gösterdi: G2 ve Capterra bot koruması, Reddit robots yasağı. Bu ek o iki
fikre izinli alternatif arar.

## Sonuç

| | |
|---|---|
| Denenen aday | 10 |
| Kullanılabilir bulunan | **5** |
| Bunlardan katalogda olmayan | 2 |

### F02 — ajans müşteri onayı ve revizyon

**Çözüldü — ama registry'ye ekleme gerekiyor.**

| Aday | source_id | Erişim | İlgililik | Fiyat | Kullanılabilir | Neden olmaz |
|---|---|---|---|---|---|---|
| Filestage | (katalogda yok) | ok | relevant | $ 0 | evet | — |
| Ziflow | (katalogda yok) | ok | relevant | $ 0 | evet | — |
| SourceForge Reviews | source-0141 | ok | uncertain | — | hayir | ilgililik belirsiz; insan etiketi gerekir |
| GetApp | source-0136 | challenge | sinanamadi | — | hayir | erişim hatası: challenge |
### F09 — berber/salon randevu ve gelmeme

**Çözüldü — katalogdaki kaynaklarla.**

| Aday | source_id | Erişim | İlgililik | Fiyat | Kullanılabilir | Neden olmaz |
|---|---|---|---|---|---|---|
| Fresha | source-0317 | ok | relevant | TRY 240.95 | evet | — |
| Booksy | source-0318 | ok | relevant | — | evet | — |
| SourceForge Reviews | source-0141 | ok | uncertain | — | hayir | ilgililik belirsiz; insan etiketi gerekir |
| SoftwareSuggest | source-0146 | challenge | sinanamadi | — | hayir | erişim hatası: challenge |
| Apple App Store — Booksy Biz | source-0096 | ok | relevant | $15.6 | evet | — |
| Apple App Store — Fresha | source-0096 | rate_limited | sinanamadi | — | hayir | erişim hatası: rate_limited |

## HTTP 200 ilgili içerik demek değildir

2 aday sayfa döndürdü ama nişle ilgisi belirsiz ya da yoktu.
En net örnek **SourceForge**: `salon scheduling software` aramasına HTTP 200
ve 19 bin karakter döndürdü. İçeriği Kubernetes orkestrasyon aracı ve kripto
fiyatlama yazılımıydı — SourceForge açık kaynak proje dizini, salon SaaS'ı
yok.

Bu yüzden her aday üç ayrı testten geçti:

1. **Erişim** — robots izin veriyor mu, HTTP yanıtı geldi mi
2. **İçerik** — gövdede görünür metin var mı (JS kabuğu değil mi)
3. **İlgililik** — nişin kendi kelimeleri gövdede geçiyor mu

Üçü de geçmeyen aday `kullanilabilir_mi = hayir` işaretlidir. İlgililik
etiketi otomatik ön elemedir; rehberin istediği insan etiketinin
(`relevant`/`irrelevant`/`uncertain` + neden) yerine geçmez, onu hazırlar.

## Registry'ye önerilenler

Aşağıdaki adaylar katalogda **yok**. Uydurma `source_id` verilmedi; kayıt kararı Batuhan'ın:

- **Filestage** — `https://filestage.io/pricing/` · F02 · kanıt `99a6a0440daf`
- **Ziflow** — `https://www.ziflow.com/pricing` · F02 · kanıt `eb96718a9701`

## Bu ek ne söylemez

- Bir alternatifin çalışması **kanıt yeterliliği** sağlamaz. 3 bağımsız örnek
  / 2 ayrı kaynak eşiği Faz 3'e aittir.
- Fiyat alanları satıcının ilan ettiği fiyattır; ödeme davranışı değildir.
- Kapalı kaynaklar **zorlanmadı**: bot koruması aşılmadı, robots yasağına
  uyuldu. G2, Capterra ve Reddit hâlâ kapalı ve öyle raporlanıyor.
- Ölçüm 2026-09-24 tarihlidir.

## Yeniden üretim

```bash
python3 alternatif_kaynak.py --yaz --canli
python3 -m unittest test_alternatif_kaynak
```
