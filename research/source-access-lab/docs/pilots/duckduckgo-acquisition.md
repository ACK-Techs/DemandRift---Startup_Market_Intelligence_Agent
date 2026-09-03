# DuckDuckGo Non-API Acquisition Pilotu

Bu pilot “510 yöntem” iddiasını üretmez. User-Agent, header, dil ve encoding değişiklikleri ayrı yöntem değildir. Sabit kimlikle, sıralı ve küçük bir bütçeyle araştırma faydasını ölçer.

## Taksonomi

| Tür | Bu pilottaki öğeler | Ne sayılır? |
|---|---|---|
| Acquisition surface | `ddg_html`, `ddg_lite` | Gerçekten ayrı iki DDG HTML yüzeyi |
| Taktik | Eşit bütçeli query comparison, pagination | Bir yüzeyde keşif stratejisi; yeni yüzey değildir |
| Pipeline aşaması | Yerel `uddg` çözme, destination fetch | Aday URL’yi gerçek artefact’a götüren işlem |
| Extractor | HTML meta, JSON-LD, embedded JSON | Aynı fetch yanıtından alan çıkarır; yeni HTTP yöntemi değildir |

Pagination, pilotun sıkı DDG bütçesinde ancak kullanılabilir bütçe kaldığında anlamlıdır; parametre varyasyonu olarak yöntem sayısını artırmaz. Browser rendering izole worker olmadığı için `not_applicable/tooling_missing_isolated_worker` olarak raporlanır. Mevcut archive yolu API kullandığından `cached_archive` bu non-API pilotta `not_applicable`dır.

## Hard güvenlik ve istek sözleşmesi

- En fazla 24 toplam ağ işlemi ve 10 DDG-owned işlem vardır. Destination tarafı en fazla 6 işlem ve her destination origin için en fazla 2 işlemle (robots + sayfa) sınırlıdır; DDG’nin iki kontrollü yüzeyi ayrıca 10 işlemlik aggregate source cap ile korunur.
- İşlemler sıralıdır; aynı origin için iki işlem arasında en az 1,5 saniye vardır.
- Retry, User-Agent/Referer/cookie rotasyonu ve CAPTCHA/challenge bypass yoktur.
- İlk `202`, `401`, `403` veya `429` origin circuit’ini açar. Üç ardışık network/5xx hatası da circuit’i açar.
- Yalnız `http`/`https`, yalnız 80/443; credential içeren URL, IP literal, internal/single-label hostname ve global olmayan DNS sonuçları reddedilir. Transport, DNS doğrulamasında seçilen IP’ye doğrudan bağlanır; HTTP `Host` ile TLS SNI/sertifika hostname kontrolü özgün hostname’i kullanır ve peer IP ayrıca karşılaştırılır.
- Redirect otomatik izlenmez. Her hop yeniden çözülür/doğrulanır ve yeni doğrulanmış IP’ye pinlenir; en fazla 3 redirect vardır ve HTTPS→HTTP düşüşü yasaktır. Cached robots parser, same-origin dahil her redirect hedef path’i için yeniden `can_fetch` çalıştırır.
- Her origin için `robots.txt` preflight yapılır. DDG HTML/Lite ve destination sayfaları açıkça tanımlı source-policy kapsamındadır; robots alınamazsa veya izin vermezse fetch `blocked_by_policy` olur.
- Destination erişimi fail-closed `fitness-app-lab-v1` fixture’ıdır: yalnız `play.google.com`, `apps.apple.com`, `reddit.com` ve `www.reddit.com`. Her kayıt access, terms, license, retention ve PII kararını taşır; bilinmeyen origin ağ çağrısından önce engellenir.
- İzinli MIME’lar HTML/XHTML/XML’dir; `text/plain` yalnız robots içindir. Boş/identity, gzip ve deflate dışındaki veya birden fazla content-encoding (`br`, `gzip, br` gibi) engellenir. Declared MIME ile basit body sniff uyuşmazlığı reddedilir. Decode edilmiş yanıt üst sınırı 1 MiB’dir.

## Veri ve başarı anlamı

`search_candidate`, arama sonucundan keşfedilen URL/title/snippet kaydıdır. Snippet hiçbir zaman fetch edilmiş kanıt sayılmaz. `fetched_artifact`, robots/egress izinlerinden sonra destination sayfasının ayrıca alınmış gövdesidir. Meta, JSON-LD ve embedded JSON aynı response üzerinden çıkarılır; extractor için refetch yapılmaz.

Her gerçek ağ işlemi timestamp, requested/final/canonical URL, redirect chain, status, MIME, byte sayısı, truncation, SHA-256, result kind, error class/stop reason, robots kararı, doğrulanan IP, peer IP ve source-policy kararını taşır. Sayaç yalnız gerçek transport işlemlerini ve budget transaction delta’sını sayar; policy nedeniyle yapılmayan denemeler ayrı `policy_attempts`/`policy_events` alanındadır.

Durumlar ayrıdır: `succeeded`, `no_results`, `challenge`, `source_unavailable`, `rate_limited`, `blocked_by_policy`, `invalid_output`, `partial`, `failed`. Uygulanmayan yetenekler `not_applicable` ile açıkça raporlanır.

Bir aday ilk `query` ve `arm` alanlarının yanında birleştirme sonrasında tüm `queries`, `arms`, `surfaces` ve `discovery_transaction_ids` lineage’ını korur.

Query decomposition iki sorguluk broad baseline ile iki sorguluk focused arm arasında değerlendirilir. Başarı için URL sayısı veya keyword coverage bakımından **strict** iyileşme gerekir; eşit sonuç başarı değildir.

Çıktı her raporlama aşamasından sonra geçici dosyaya yazılıp `os.replace` ile atomik checkpoint edilir.

## Çalıştırma

```bash
python3 probe_site_access.py --site duckduckgo --topic fitness_app
```

Bu komut kontrollü dış HTTP üretir. Unit testler canlı ağ kullanmaz:

```bash
python3 -m unittest -v test_probe_site_access.py
```
