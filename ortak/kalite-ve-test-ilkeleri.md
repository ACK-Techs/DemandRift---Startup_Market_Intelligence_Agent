# Ortak kalite ve test ilkeleri

Bu belge **ne test edileceğini** ve nasıl kanıtlanacağını tanımlar. Ekibin hangi makine/sunucuda test çalıştıracağı açık karardır. Ücretli/live kaynak veya LLM çağrısı bu dokümantasyon işiyle başlatılmaz.

## Testlerin üç ayrı durumu

1. **Mevcut araç testleri:** Faz 1 veri laboratuvarındaki `test_*.py` dosyaları. Bunlar kaynak araçlarının offline davranışlarını kontrol eder.
2. **Yeni planlı değerlendirme girdileri:** Faz `tests/` dizinlerindeki senaryo JSON'ları. Beklenen davranışları tanımlar; backend/test runner henüz yoksa geçen test değildir.
3. **Sonradan oluşacak koşu kanıtı:** Gerçek komut, tarih, sürüm, veri seti, model/prompt, sonuç ve hatalar. Plan metniyle karıştırılmaz.

## Her faz için ortak test katmanları

| Katman | Sınanacak şey |
|---|---|
| Birim | Kategori/şema/sorgu kontrolleri, limitler, temizleme, durum ve karar kuralları |
| Sözleşme | Fazlar arası girdi/çıktı, Python adaptörü ve consumer uyumu |
| Recorded fixture | Önceden alınmış içerikte parser, alan, hata ve kaynak bağı |
| AI değerlendirmesi | İnsan etiketli fikir/bulgu örneğinde anlam doğruluğu ve kaynak desteği |
| Entegrasyon | Kayıt, tekrar çalışma, timeout, iptal, kısmi sonuç ve sürüm ilişkisi |
| Uçtan uca | Aynı fikrin brief → sorgu → veri → bulgu → karar zinciri |

Canlı testler, offline testlerin geçtiği iddiasından türetilemez. Model kalitesi de yalnız JSON şemasının geçmesiyle kanıtlanmaz.

## Ortak kabul kuralları

- Kabul edilen her çıktı şemaya uyar; geçersiz çıktı ilerlemez.
- Desteksiz iddia, uydurma alıntı, izinsiz kaynak, kullanıcı kapsamını değiştirme ve veri sızıntısı kritik hata sayılır.
- Hata ile gerçek boş sonuç ayrı kalır; kısmi veri tam araştırma diye sunulmaz.
- Girdi, beklenen davranış, fiili çıktı, fark, değerlendiren kişi ve sürüm kaydedilir.
- Aynı veriyle model/prompt değişimini karşılaştır; farklı model çıktısının birebir kelime eşleşmesini zorunlu tutma.
- Sorguların anlam/niyet/kaynak uyumunu ölç; tek bir sabit anahtar kelime dizisini doğru kabul etme.
- İnsan etiketleri ve belirsiz örnekler LLM çıktısı görülmeden mümkün olduğunca hazırlanır. Tartışmalı örnek tek kesin etiketle gizlenmez.
- Ölçümler yanında hata örnekleri, örneklem büyüklüğü, kategori/dil dağılımı ve veri sürümü gösterilir.
- Önerilen yüzde/eşikler “hedef” olarak etiketlenir; ölçülmüş başarı gibi sunulmaz. Kesin eşikler ilk etiketli koşu ve ekip kabulüyle sabitlenir.

## Faz 1 veri testlerinin özel önemi

[Veri laboratuvarı](../faz-1-fikir-ve-arastirma/veri-laboratuvari/README.md) çekilmiş örnekleri, kaynak/artefact/arama indekslerini, scriptleri ve mevcut testleri bir arada tutar. Testler script import ve dosya yolları korunması için laboratuvar kökünde bırakılmıştır; fazın `tests/README.md` belgesi buraya yönlendirir.

Kontrol: doğru site/alan mı, gerçekten içerik mi yoksa sitemap/challenge mı, hash ve URL bağı var mı, tarih doğru mu, arşiv/canlı ayrılmış mı, gerekli alan eksik mi, tekrar/boilerplate oranı nedir? Her kaynak için aynı sayfa tipinin aynı araştırma sorusuna cevap verdiği varsayılmaz.

Mevcut arşiv tam olmayabilir. Eksik ham dosya doğrulama başarısı değil `missing_artifact` olarak raporlanır; örnek dosyanın varlığı tüm corpus'un tamamlığını kanıtlamaz.

## Senaryo sonuç kaydı önerisi

```text
case_id, fixture_version, run_id, timestamp,
code_revision, model_version, prompt_version, schema_version,
expected, actual, result(pass/fail/not_run/not_verified),
evidence_paths, evaluator, failure_reason, follow_up
```

Test planı ile test sonucu farklı dosyalardır. Sonuçlar eski beklenenleri sessizce değiştirmez. Regresyon düzeltmesinin ardından ilgili başarısız örnek kalıcı sete eklenir. Bir fazın kabulü sonraki fazın geçtiği anlamına gelmez.

## Onaylı başlangıç kararları

Üç fazın AI modeli Gemini 3.1 Flash Lite, ağ/araç yetkisi yok; [RULES](RULES.md) geçerlidir. [Kanıt policy v1](kanit-yeterliligi-ve-karar-kurallari.md) 3 bağımsız örnek/2 kaynak tabanını nitel kontrollerle uygular. Bu sayı kategori doğruluğu veya site erişim başarısının kabul eşiği değildir. Test sahibi/nihai yeniden kontrol Batuhan; veri düzeltmesi Ayselin, ekran düzeltmesi Ayşenur.
