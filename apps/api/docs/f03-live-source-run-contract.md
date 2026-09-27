# F03 canlı kaynak çalıştırma sözleşmesi

`POST /api/v1/research/source-runs/f03`, BT-02'nin F03 denemesi için yalnız
manifestteki izinli üç API kaynağını çağırır: GitHub, Stack Overflow ve Hacker
News. İstek gövdesi yalnız senaryo ve bu üç kaynaktan bir alt küme içerebilir;
istemci URL, sorgu metni, HTTP başlığı, token veya secret veremez.

Her kaynak isteği en fazla beş kayıt, on saniye zaman aşımı ve redirect kapalı
olarak çalışır. Yanıt kaynak başına `success`, `no_results`, `rate_limited`,
`source_unavailable` veya `invalid_output` durumunu döndürür. `rate_limited`
ve `source_unavailable`, sıfır sonuç olarak yorumlanmaz.

Endpoint yalnız geçici özet kayıtlar döndürür. Ham artefakt depolamaz, kaynaklı
iddia üretmez ve karar vermez. Bu nedenle endpointten dönen `success`, tek
başına `run-records/validate` için yeterli değildir: kalıcı ham artefakt
referansı ve insan etiketi ayrıca üretilmelidir.
