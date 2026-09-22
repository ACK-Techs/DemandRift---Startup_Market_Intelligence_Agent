# Kaynak verisinin mevcut kaydı

İnceleme: 22 Eylül 2026. Sayılar yerel CSV kayıtlarından sayıldı; bugün tüm sitelere canlı erişim tekrar denenmedi.

| Durum | Kaynak |
|---|---:|
| En az bir içerik yüzeyi çekilmiş | 534 |
| Kısmi; kullanılabilir içerik alınamamış | 44 |
| Adres var, erişim yok | 54 |
| Adres yok | 4 |
| Toplam | 636 |

534 başarılı kaydın 104'ü yalnız Common Crawl yüzeyine dayanır; 430'u başka içerik yüzeyleri de içerir. “Çekildi”, ilgili yorumların/fiyatların tamamının veya belirli araştırma sorusunun cevabının elde edildiği anlamına gelmez. Ana sayfa, sitemap, API, RSS ve arşiv ayrı değerlendirilir.

## Kanonik veriler

[Faz 1 veri laboratuvarı](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/README.md) altında:

- [KAYNAK-DEFTERI.csv](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/KAYNAK-DEFTERI.csv): kaynak bazlı erişim gözlemi.
- [source_manifest.json](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/source_manifest.json): adres/erişim manifesti.
- [SITE-LISTESI.md](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/SITE-LISTESI.md): kaynak grupları; mevcut bir test bu dosyayı okur.
- [ARTEFAKT-DIZINI.csv](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/ARTEFAKT-DIZINI.csv): 1984 indeks satırı; ham dosya/run/hash bağları.
- [ARAMA-YUZEYLERI.csv](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/ARAMA-YUZEYLERI.csv): 578 yüzey kaydı; 533'ü katalogda arama yolu taşıyor. Canlı çalışabilirlik garantisi değil.
- `veriler-ornek/`: 252 kaynak klasöründen seçilmiş içerikler.
- `results/`: mevcut koşu ve ham içerik kayıtları.
- `test_*.py`: mevcut araç testleri. Yeni 30 fikir girdisiyle aynı test seti değildir.

## Kanıt sınırı

Bu checkout tam corpus değildir. İndekste kayıt bulunması, ilgili ham gövdenin bu makinede bulunduğu anlamına gelmez. Veri kalite çalışmasında referansın varlığı, hash'i, MIME/alan yapısı ve araştırmaya uygunluğu ayrı doğrulanmalı. Eksik dosya veya yalnız sitemap, kullanılabilir kullanıcı yorumu gibi sayılmamalı.

Eski 2 Eylül erişim raporu, 10 Ağustos koşusundaki 37 tamam ve 546 çözülememiş kaynak durumunu anlatır. Bu eski snapshot bugünkü defter yerine kullanılmamalı. Eski raporlar [trash/eski-raporlar](../../trash/eski-raporlar/) altında tarihsel olarak tutuldu.

Bu düzenleme yeni veri indirmedi, eksik arşivi tamamlamadı ve araştırma backend'i oluşturmadı. Var olan veriler, scriptler ve testler birlikte taşındı.
