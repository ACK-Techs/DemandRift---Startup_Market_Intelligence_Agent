# F03 canlı kaynak çalıştırma sözleşmesi

Üretim geçişi: bu eski public endpoint geçerli istekte `410 preview_unavailable`
döndürür. Hesap ve ortak bütçe kaydı olmadan canlı çağrı başlatamaz. Aşağıdaki
sınırlı dönüşüm davranışı ağsız harness ve mock testlerinde korunur; yeni
kimlikli collector bu eski endpoint üzerinden çalıştırılmaz. Geçersiz senaryo
ve kaynak seçimi giriş sözleşmesinde `422` olarak reddedilir.

`POST /api/v1/research/source-runs/f03`, BT-02'nin F03 denemesi için yalnız
manifestteki izinli üç API kaynağını çağırır: GitHub, Stack Overflow ve Hacker
News. İstek gövdesi yalnız senaryo ve bu üç kaynaktan bir alt küme içerebilir;
istemci URL, sorgu metni, HTTP başlığı, token veya secret veremez.

Her kaynak isteği en fazla beş kayıt, on saniye zaman aşımı ve redirect kapalı
olarak çalışır. Yanıt kaynak başına `success`, `no_results`, `rate_limited`,
`source_unavailable` veya `invalid_output` durumunu döndürür. `rate_limited`
ve `source_unavailable`, sıfır sonuç olarak yorumlanmaz.

Kaynak alanlarının beklenen türe dönüştürülememesi `invalid_output` üretir.
Bu yanıtta bozuk gövde veya doğrulama istisnası paylaşılmaz ve sıradaki izinli
kaynak çalışmaya devam eder. Bozuk dönüşüm başarılı ham artefakt olarak
saklanmaz; `body` metni ve yorum bağlantısı yalnız geçerli yanıtta korunur.

Endpoint başarılı veya boş API yanıtının ham JSON gövdesini, yalnız DemandRift
Compose projesine ait `demandrift_api_artifacts` named volume'unda tutar.
Container içinde tek yazılabilir yol `/data/artifacts`tır; dönen `raw_artifact`
referansı SHA-256 ve byte sayısını içerir. Yanıt boyutu 1 MiB ile sınırlıdır.

Bu kalıcılık kaynaklı iddia veya karar üretmez. `success`, insan etiketi
olmaktan ve `run-records/validate` ile denetlenmekten muaf değildir.

`previews` kaynakta bulunan belge gövdesini `body` alanında taşır. Hacker News
için `source_url`, bağlı haber URL'si değil, her zaman `objectID` ile kurulan
kanonik `news.ycombinator.com/item?id=...` yorum/permalink adresidir.

GitHub issue aramasında `surum` alanı uygulanamaz olarak işaretlenir: issue
kaydı bir release/tag'a zorunlu olarak bağlı değildir. Release sürümü ayrı bir
araştırma sinyali gerektiğinde ayrı kaynak planı ve endpoint ile toplanır.
