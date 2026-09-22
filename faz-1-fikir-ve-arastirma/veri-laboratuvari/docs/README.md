# Veri laboratuvarı belgeleri

- [Pilotlar](pilots/): DuckDuckGo ve Hacker News scriptlerinin kapsam, limit, çıktı ve kabul sözleşmeleri. Üretim connector'ı değildir.
- [Tarihsel erişim raporları](../../../trash/eski-raporlar/): önceki koşulara ait raporlar; güncel durum listesi değildir.
- [Laboratuvar kullanımı ve veri haritası](../README.md).
- [Güncel kayıt özeti](../../../ortak/raporlar/kaynak-verisi-durumu.md).

`results/` altındaki koşu/ham içerik kanıtları ve üst dizindeki CSV/JSON indeksleri yerinde korunur. `summarize_site_access.py` yeni çalıştırılırsa yerel `docs/reports/` altında yeni çıktı üretebilir; arşivlenen eski raporun silinmiş veya yeniden üretilmiş olduğu varsayılmaz.
