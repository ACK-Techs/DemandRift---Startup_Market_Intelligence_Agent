# F03 canlı kaynak çalıştırma sözleşmesi

`POST /api/v1/research/source-runs/f03`, BT-02'nin F03 denemesi için yalnız
manifestteki izinli üç API kaynağını çağırır: GitHub, Stack Overflow ve Hacker
News. İstek gövdesi yalnız senaryo ve bu üç kaynaktan bir alt küme içerebilir;
istemci URL, sorgu metni, HTTP başlığı, token veya secret veremez.

Her kaynak isteği en fazla beş kayıt, on saniye zaman aşımı ve redirect kapalı
olarak çalışır. Yanıt kaynak başına `success`, `no_results`, `rate_limited`,
`source_unavailable` veya `invalid_output` durumunu döndürür. `rate_limited`
ve `source_unavailable`, sıfır sonuç olarak yorumlanmaz.

Endpoint başarılı veya boş API yanıtının ham JSON gövdesini, yalnız DemandRift
Compose projesine ait `demandrift_api_artifacts` named volume'unda tutar.
Container içinde tek yazılabilir yol `/data/artifacts`tır; dönen `raw_artifact`
referansı SHA-256 ve byte sayısını içerir. Yanıt boyutu 1 MiB ile sınırlıdır.

Bu kalıcılık kaynaklı iddia veya karar üretmez. `success`, insan etiketi
olmaktan ve `run-records/validate` ile denetlenmekten muaf değildir.
