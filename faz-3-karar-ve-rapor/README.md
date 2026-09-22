# Faz 3 — Karar ve rapor

**Kapsam kararı — Çağlar:** Build kararı, MVP/PRD önerisi, geliştirilecek ürünün özellikleri ve geliştirme yol haritası mevcut üç fazın hiçbirine dahil değildir. Bunlar projenin sonraki aşamasıdır; yönetici Çağlar tarafından daha sonra değerlendirilip planlanacaktır. Bu aşama kanıtları, araştırma değerlendirmesini ve eksikleri raporlar. Olumlu bulgu otomatik geliştirme kararı üretmez.

**Durum: uygulanacak backend/AI planı.** Faz 2'nin kaynaklı `EvidenceBundle` çıktısı, kanıt yeterliliği ve doğrulama kurallarından geçirilerek `DecisionReport` üretir.

Çıktı kaynaklı araştırma değerlendirmesidir. Modify/Kill/Investigate More araştırma sonuçları olarak korunur; olumlu bulgular raporlanır ve Çağlar’ın değerlendirmesine bırakılır. Olumlu sonuç etiketi: **Olumlu bulgular — yönetici değerlendirmesi bekliyor**.


- [Hazırlık süreci](docs/hazirlik-sureci.md)
- [Entegrasyon planı](docs/entegrasyon-plani.md)
- [Teknolojiler ve kararlar](docs/teknolojiler-ve-kararlar.md)
- [Test planı](docs/test-plani.md)
- [Veri sözleşmeleri](docs/veri-sozlesmeleri.md)
- [Görev ve teslim planı](docs/gorev-ve-teslim-plani.md)
- [Test senaryoları](tests/README.md)

## Kapsam

Karar, gerekçe, hedef müşteri/problem, rakip/fırsat bulguları, karşıt kanıtlar, belirsizlikler ve somut sonraki doğrulama adımları döndürülür. AI anlatımı backend şema, citation ve politika doğrulamasından geçer. Yeni internet çağrısı kararı doğrudan model tarafından yürütülmez.

Ürün geliştirme veya MVP/pilot tasarımı önerilmez. Birincil doğrulama eksikleri raporlanır; bu eksikler için ürün/deney planlamasını daha sonra Çağlar yapar. DemandRift rapor ekranı Ayşenur tarafından backend geldikçe bağlanır.

## Önceki belgeler

Eski Faz 6'nın karar girdileri ve Faz 7'nin yeterlilik, karşıt kanıt, pazar/uygulama ayrımı ve karar kuralları bu yapıda korunur. Eski [Faz 7 planı](../trash/eski-planlar/Faz7-Plan.md) tarihsel kayıttır; ayrı bir yedinci faz yürütülmez. Ortak açık teknoloji/ortam kararları [ortak klasördedir](../ortak/README.md).

## Güncel ekip ve kabul rehberi

[Kontrol ve kabul rehberi](docs/kontrol-ve-kabul-rehberi.md), [kişi görevleri](../ortak/ekip-ve-teslim.md), [model ve kapsam kuralları](../ortak/RULES.md). Ayşenur her fazın backend teslimi geldikçe ilgili ekranları bağlar; frontend entegrasyonu üç fazın tamamlanmasını beklemez.
