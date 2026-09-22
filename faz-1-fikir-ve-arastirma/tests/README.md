# Faz 1 test girdileri

[fikir-senaryolari.json](fikir-senaryolari.json) onaylanan 10 fikrin üç anlatımını içerir: 30 **planlanmış** test vakası. Bu bir değerlendirme fixture'ıdır; çalıştırılabilir test runner, gerçek LLM çıktısı veya başarı raporu değildir.

Her vaka yalnız `input` alanını modele verir. `expected` değerlendirme için saklanır; modele verilerek cevabın ezberletilmesi önlenir. Eksik senaryolarda ana kategori null olabilir; `acceptable_primary_categories` olası makul seçenekleri, `clarify` sorulacak eksikleri gösterir. Net senaryonun ayrıntıları eksik senaryoya gizlice taşınmaz.

Sorgu örnekleri birebir metin karşılaştırması için değildir; kullanıcı/problem, niyet, kaynak türü ve pazar doğruluğu için anlam referansıdır. `forbidden_behaviors` kritik hata örneklerini gösterir. Her vaka başlangıçta `not_run` durumundadır.

Kabul eşikleri ve tüm hata/entegrasyon senaryoları [test planında](../docs/test-plani.md). **Mevcut sitelerden veri çekme ve arama scriptlerinin testleri** bu dizinde değil, [veri laboratuvarında](../veri-laboratuvari/) korunur. Ham örnekler `veri-laboratuvari/veriler-ornek/`, provenance ve sonuç indeksleri aynı laboratuvar içindedir.

İleride eklenecek runner bu fixture'ı okumalı, prompt/model/taksonomi/registry sürümünü kaydetmeli ve test sonucu üretmelidir. Anahtar, ücretli çağrı ve test ortamı konusunda bu dosya yeni karar vermez.
