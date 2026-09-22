# Faz 2 test dosyaları

[planlanan-senaryolar.json](planlanan-senaryolar.json), makine tarafından okunabilir **planlanmış senaryo ve beklenti** listesidir. `status: planned` kayıtları otomatik testlerin uygulanmış veya çalıştırılmış olduğu anlamına gelmez. Test runner ve runtime fixture bağlayıcıları henüz bu teslimde yazılmadı.

Her senaryo için Ayselin etiketli veri/kanıt örneğini tamamlar, Batuhan runner ve assertion'ları uygular. Girdiler sentetik, küçük ve açıklayıcıdır; gerçek kaynak kayıtlarının yerini almaz. Kaydedilmiş site verisiyle test gerektiğinde [Faz 1 veri laboratuvarındaki](../../faz-1-fikir-ve-arastirma/veri-laboratuvari/) artefact/hash referansı eklenir; ham dosya çoğaltılmaz.

Çalıştırma yeri, API sağlayıcısı/anahtar yöntemi ve ücretli canlı test düzeni açık karardır. Bu klasör offline/fixture test planını tanımlar; herhangi bir canlı dış çağrı veya ücretli koşu yapılmamıştır.

Kabul ve değerlendirme ayrıntıları: [test planı](../docs/test-plani.md).
