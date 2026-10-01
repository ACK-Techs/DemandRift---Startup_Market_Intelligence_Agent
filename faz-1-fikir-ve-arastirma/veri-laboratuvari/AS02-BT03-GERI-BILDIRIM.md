# BT-03 bildirimine yanıt — AS-02 yeniden üretim + AS-03 deneme kaydı

**Tarih:** 2026-10-01 · **Sorgu:** `API breaking changes backward compatibility`
**Üreten:** `bt03_alan_analizi.py`, `yeniden_uret.py`
**Veri:** `BT03-ALAN-ANALIZI.csv`, `AS03-BT03-DENEMELERI.csv`, `AS02-YENIDEN-URETIM.csv`

## Kısa cevap

Bildirdiğin dört eksikten **üçü API'de aslında var**, biri gerçekten yok.
Yani çoğu durumda kaynak sınırlı değil, alanı okuyan taraf okumuyor.

| Kaynak | Bildirdiğin | Ölçtüğümüz | Düzeltme nerede |
|---|---|---|---|
| GitHub | `govde` eksik | `body` var, **5/5 kayıtta dolu** (2105 ve 577 karakter) | çıkarımda |
| GitHub | `surum` eksik | `/search/issues` ucunda sürüm alanı **yok** | beklenti listesinde |
| Stack Overflow | tam | tam — dört alan 5/5 | — |
| Hacker News | `govde` eksik | `comment_text` var, **5/5 kayıtta dolu** | çıkarımda |
| Hacker News | konu uygunluğu zayıf | **haklısın**, bizim otomatik test gevşekti | testte (düzeltildi) |

## 1. GitHub `surum`: alan gerçekten yok

Beş kaydın hiçbirinde `version` ya da `tag_name` benzeri bir anahtar yok. Bu
bir hata değil, tasarım: **issue bir sürüme değil depoya bağlı bir kayıt.**

İki yakın ihtimali de denedik, ikisi de çözüm değil:

- `milestone.title` bazı kayıtlarda sürüm gibi görünüyor (`v5.0.0`) ama
  5 kaydın yalnız 2'sinde var ve ikinci örnek `v0.1 Foundation`, yani sürüm
  bile değil. **Vekil olarak kullanılamaz.**
- `/repos/{owner}/{repo}/releases` ucu beş alanı da veriyor (`tag_name`,
  `body`, `html_url`, `published_at` dolu döndü) **ama serbest sorgu kabul
  etmiyor, depo başına çalışıyor.**

Sonuç: tek uçtan hem issue gövdesi hem sürüm gelmiyor. Ya `surum`'u
`source-0017`'nin beklenen alan listesinden çıkarırız, ya da releases ucunu
**ayrı bir kaynak** olarak tanımlarız. Bence ikincisi daha doğru çünkü
sürüm/changelog zaten farklı bir sinyal.

## 2. Senin raporunda görünmeyen bir şey: HN `kaynak_url` yanlış belgeyi gösteriyor

`story_url` **bağlanan yazının** adresi, yorumun kendi adresi değil. Üstelik
5 kaydın birinde boş (metin gönderisine gelen yorum). `objectID` ise 5/5 dolu
ve `news.ycombinator.com/item?id=<objectID>` yorumun kanonik adresi.

Yani alan "eksik" değil, **yanlış** — ki bu daha kötüsü, çünkü eksik alan
fark edilir, yanlış alan sessizce rapora girer. `kaynak_url` objectID'den
türetilmeli.

## 3. Konu uygunluğu: haklısın, testimiz gevşekti

HN için otomatik testimiz beş kaydın beşini de "ilgili" saymıştı. Sebebi:
4 ayırt edici kelimeden 2 eşleşme yetiyordu ve uzun teknik gövdelerde
"breaking"/"compatibility" alakasız bağlamlarda da geçiyor.

Testi düzelttim, üç şey değişti:

1. **Başlık kanıtı isteniyor.** Gövdede geçmesi yetmez.
2. **Başlık kayıt başına ölçülüyor.** Önce hepsini birleştiriyordum, tek
   başlığın eşleşmesi tüm yanıtı "ilgili" yapıyordu.
3. **Üçüncü bir sonuç var: `uncertain`.** "İlgisiz" demek için de kanıt
   gerekir; emin olmadığında makine karar vermiyor, insan etiketine bırakıyor.

Düzeltme sonrası:

| Kaynak | Başlık eşleşmesi | Sonuç |
|---|---|---|
| GitHub | 5/5 | `relevant` |
| Stack Overflow | 1/5 | `uncertain` |
| Hacker News | 0/5 | `uncertain` |

Sıralama senin gözlemiyle aynı yönde: HN en zayıf. `uncertain` kayıtlar
AS-04 insan etiketi kuyruğuna giriyor.

## 4. AS-02 makinesi bu alanları ölçemiyor — ve artık bunu söylüyor

`beklenen_alanlar` kolonunu senin `expected_fields` listenle doldurdum ve
makine üçünü de `alan-cikarimi` verdi. **Bu yanlıştı.** Senin "tam" dediğin
Stack Overflow için bile "baslik çıkarılamadı" diyordu.

Sebebi şu: bizim çıkarıcımızın sözlüğü **pazar sinyali** sözlüğü
(`fiyat`, `lisans`, `engagement_yildiz`, `paket_adi`...), seninki **belge
kaydı** sözlüğü (`baslik`, `govde`, `yazar`...). Ortak tek isim `surum` ve o
bile aynı şeyi anlatmıyor — bizimki metnin içinde geçen herhangi bir sürüm
dizgisi, seninki belgenin sürümü.

Makineye aramadığı bir alanı sorup "bulamadı" demesi ölçüm hatası olurdu.
Yeni bir sınıf ekledim: **`sozlesme-disi`** — "bu alan benim sözlüğümde yok,
ölçemem, yargı vermiyorum". Belge-kaydı alanları artık API yanıtından
doğrudan sınanıyor (`bt03_alan_analizi.py`).

## AS-03 deneme kaydı

İstediğin gibi eksik/uygunsuz alanların hepsi deneme olarak kayıtlı —
"çalıştı" demek yetmiyor, hangi alan neden gelmedi yazıyor.
`AS03-BT03-DENEMELERI.csv`: 9 deneme, **4 başarılı / 2 kısmi / 3 başarısız**.

Başarısız olanlar: GitHub `surum` (uçta yok), milestone vekili (reddedildi),
HN konu uygunluğu (testimiz gevşekti). Kısmi olanlar: releases ucu (alan var,
sorgulanamıyor), HN `kaynak_url` (dolu ama yanlış belge).

## Kanıt dosyaları

Rapordaki her sayı diskteki bir yanıt dosyasına geri izlenebilir. API canlı
olduğu için yanıt her koşuda değişir; aşağıdaki özetler **bu rapordaki
sayıların çıktığı** koşuya aittir.

| Kaynak | sha256 | Dosya |
|---|---|---|
| GitHub | `96e70f0ddc01…` | [results/raw/96e70f0ddc019d8bad582aac83b3d102f1fc9ac5a0adcf9ce742b2dfe27f94e7.bin](results/raw/96e70f0ddc019d8bad582aac83b3d102f1fc9ac5a0adcf9ce742b2dfe27f94e7.bin) |
| Stack Overflow | `8141c7f3caa8…` | [results/raw/8141c7f3caa8b51ea74bcbab0e82c32d2c3c4affad9f8cda1df60a25aa35bab8.bin](results/raw/8141c7f3caa8b51ea74bcbab0e82c32d2c3c4affad9f8cda1df60a25aa35bab8.bin) |
| Hacker News | `97c8f89dbcbd…` | [results/raw/97c8f89dbcbd8f97efa525e1c1e2e5d4fc29435404a7523696dbf0693f031ef7.bin](results/raw/97c8f89dbcbd8f97efa525e1c1e2e5d4fc29435404a7523696dbf0693f031ef7.bin) |

Yeniden üretmek için:

```bash
cd faz-1-fikir-ve-arastirma/veri-laboratuvari
python3 bt03_alan_analizi.py --canli --yaz   # BT03-ALAN-ANALIZI.csv
python3 yeniden_uret.py --asama once --yaz   # AS02-YENIDEN-URETIM.csv
python3 cozum_gunlugu.py --yaz               # COZUM-GUNLUGU.csv/.md
```

Bu turun bulguları çözüm günlüğünde `CG-21`–`CG-24` olarak kayıtlı.

## Senden ricam

1. `source-0017` için `surum`: listeden çıkarmak mı, releases'i ayrı kaynak
   yapmak mı? Seçimi sen yap, ben ona göre güncellerim.
2. HN `kaynak_url`'ü `objectID`'den türetmek `SourceItemPreview`'de bir
   değişiklik gerektiriyor mu?
3. `SourceItemPreview`'de `govde` ve `surum` alanı yok — `_returned_fields()`
   yalnız `baslik, kaynak_url, yayin_tarihi, etiket, yazar` üretebiliyor.
   `govde` sözleşmede beklenirken modelde yoksa, API verse de rapora hiç
   giremez. Bu AS-06 uyum notunda da yazdığım iki uyumsuzluktan biri.
