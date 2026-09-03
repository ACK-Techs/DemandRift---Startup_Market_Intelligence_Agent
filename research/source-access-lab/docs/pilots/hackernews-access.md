# Hacker News Çok-Process Erişim Pilotu Sözleşmesi

## 1. Amaç ve sınır

Bu pilot, Hacker News üzerinde anahtarsız resmî public API ile izinli API-dışı yüzeyleri küçük ve denetlenebilir bir koşuda karşılaştırır. Toplu site testi, genel web crawler, ücretli servis, key/OAuth/login, belgelenmemiş dahili endpoint, CAPTCHA aşma ve kimlik/header rotasyonu kapsam dışıdır.

Pilot Faz 3 acquisition sınırında kalır: ham artefact, aday kayıt ve provenance üretir; yorum analizi, pazar çıkarımı veya Build/Modify/Kill kararı üretmez. Arama/listeden görülen aday, ayrıca fetch edilmiş kanıtla eşit sayılmaz.

## 2. Yöntem taksonomisi

Parametre, header, encoding veya query varyasyonu yeni yöntem sayılmaz. Her kayıt aşağıdaki kategorilerden tam birini taşır.

| Kategori | Pilot öğeleri | Anlamı |
|---|---|---|
| Acquisition surface | `hn_html`, `hn_rss`, `hn_official_keyless_api` | Verinin sunulduğu gerçekten farklı erişim yüzeyi |
| Tactic | `frontpage_discovery`, `pagination`, `list_then_item` | Bir surface üzerinde aday kapsamını artırma stratejisi |
| Pipeline stage | `discover`, `resolve_native_id`, `fetch_item`, `persist_provenance`, `deduplicate` | Adayı immutable ham artefact'a götüren aşama |
| Extractor | `html_story_rows`, `html_item_fields`, `rss_xml_items`, `api_list_ids`, `api_item_json` | Aynı alınmış response'u ayrıştıran kod; yeni ağ yöntemi değildir |

Pilotun raporlayacağı sabit `method_id` değerleri:

| `method_id` | Surface | Rol |
|---|---|---|
| `html_frontpage` | `hn_html` | Ön sayfadan aday story URL/native ID keşfi |
| `html_pagination` | `hn_html` | Tek kontrollü sonraki sayfadan yeni aday ölçümü |
| `html_item_page` | `hn_html` | Seçilmiş native item sayfasını ayrıca fetch etme |
| `rss_frontpage` | `hn_rss` | Resmî RSS response ve item adayları |
| `official_api_topstories` | `hn_official_keyless_api` | Anahtarsız resmî listeden native ID keşfi |
| `official_api_item` | `hn_official_keyless_api` | Seçilmiş native ID'nin JSON kaydını ayrıca fetch etme |

Extractor tekrar çalıştırma veya aynı URL'yi farklı header ile çağırma `method_id` sayısını artırmaz. RSS aynı web origin'ini kullansa da farklı representation surface'idir; concurrency hesabında yine aynı origin kuyruğundadır.

## 3. Site sonucu ile global yöntem kataloğu ayrımı

Her yöntem sonucu iki ayrı alan taşır:

```text
site_id = hackernews
site_outcome = ...
global_catalog_disposition = retained
```

`site_outcome=failed`, `source_unavailable`, `blocked_by_policy` veya `not_applicable`, yalnız Hacker News + pilot sürümü + koşu zamanı için bir uygulanabilirlik gözlemidir. Bu sonuç:

- yöntemi global katalogdan silmez veya devre dışı bırakmaz,
- başka sitelerdeki başarı puanını düşürmez,
- “yöntem genel olarak çalışmıyor” sonucuna dönüşmez,
- başka surface veya connector'lara otomatik fallback yetkisi vermez.

Global katalog durumu yalnız çok-site evaluation, sürümlü policy kararı ve bağımsız kabul sonrasında ayrı bir iş öğesiyle değişebilir. Pilot her durumda `global_catalog_disposition=retained` yazar.

## 4. Sabit source allowlist

Yalnız aşağıdaki HTTPS origin'leri izinlidir:

```text
https://news.ycombinator.com
https://hacker-news.firebaseio.com
```

Kurallar:

- Scheme yalnız `https`, port yalnız `443` olabilir.
- IP literal, credential içeren URL, farklı hostname ve subdomain türetme reddedilir.
- DNS sonucundaki bütün adresler public/global olmalı; bağlantı doğrulanan IP'ye pinlenmeli ve özgün hostname ile TLS SNI/sertifika doğrulaması korunmalıdır.
- Her redirect hop'u yeniden doğrulanır. Redirect hedefi allowlist dışında kalırsa fetch yapılmadan `blocked_by_policy` döner.
- HTML/RSS origin'i için robots preflight zorunludur; robots alınamaz veya path'e izin vermezse ilgili iş `blocked_by_policy` olur.
- Firebase origin'inde yalnız belgelenmiş public API yolları kabul edilir: `/v0/topstories.json` ve planın listeden seçtiği sayısal ID için `/v0/item/<id>.json`. Başka Firebase path'i fail-closed reddedilir.
- Secret, cookie, kullanıcı hesabı veya kişisel veri fixture/result içine yazılmaz.

## 5. Process-worker yürütme modeli

Parent process, sabit iki origin için tam iki uzun ömürlü worker process başlatır:

```text
parent/coordinator
├── worker_web   -> news.ycombinator.com queue
└── worker_api   -> hacker-news.firebaseio.com queue
```

- Her worker yalnız atanmış tek origin'e ağ erişimi yapabilir.
- Aynı origin içindeki işler FIFO ve `concurrency=1` ile kesinlikle seridir.
- İki origin semantik bağımlılık yokken farklı process'lerde paralel ilerleyebilir.
- Thread pool, her iş için yeni process veya aynı origin için birden fazla worker kullanılmaz.
- Parent, work item'ları çalıştırmadan önce sabit origin bütçe lease'lerini verir. Lease toplamları global hard cap'i aşamaz; worker kullanılmayan lease'i başka origin'e kendiliğinden aktaramaz.
- Sonuç envelope'u `worker_pid`, `origin`, `sequence_no`, `started_at`, `completed_at`, `method_id` ve transaction sayaçlarını taşır. Fixture kabulünde en az iki farklı worker PID görülmelidir.
- Worker çökmesi diğer origin'in sonucunu yok etmez; koşu `partial` olabilir. Yeni worker ile otomatik retry bu pilotta yoktur.
- Parent cancellation iki worker'a yayılır; yeni çağrı rezervasyonu durur ve tamamlanan provenance korunur.

## 6. Hard kaynak sınırları

Bu değerler pilot sabitidir; CLI ile yükseltilemez.

| Sınır | Değer |
|---|---:|
| Global gerçek network transaction | 16 |
| `news.ycombinator.com` transaction lease | 8 |
| `hacker-news.firebaseio.com` transaction lease | 8 |
| Aynı origin concurrency | 1 |
| Farklı origin worker sayısı | 2 |
| Aynı origin minimum istek aralığı | 1.5 saniye |
| Connect timeout | 5 saniye |
| Response/read timeout | 10 saniye |
| Worker wall-clock timeout | 45 saniye |
| Redirect | En fazla 2 hop/istek |
| HTML veya RSS response | En fazla 512 KiB decoded |
| JSON response | En fazla 256 KiB decoded |
| Koşu toplam decoded byte | En fazla 4 MiB |
| Retry | 0 |

Robots, redirect hop'u ve hata response'u gerçek transport işlemi ise budget'tan düşer. Policy tarafından ağ öncesinde reddedilen deneme transaction sayılmaz; ayrı `policy_attempt_count` alanına yazılır. Budget rezervasyonu çağrıdan önce atomiktir; lease veya global cap yoksa transport çağrılmaz.

İlk `202`, `401`, `403` veya `429` ilgili origin circuit'ini açar. Aynı origin'de üç ardışık network/5xx hata da circuit'i açar. Açık circuit, kalan aynı-origin işleri `source_unavailable` veya `rate_limited` olarak sonlandırır; kimlik değiştirerek tekrar denenmez.

## 7. MIME, encoding ve response doğrulaması

İzinli response eşleşmeleri:

| Surface/path | İzinli MIME |
|---|---|
| HTML/item sayfası | `text/html`, `application/xhtml+xml` |
| RSS | `application/rss+xml`, `application/xml`, `text/xml` |
| Resmî API | `application/json`, `text/json` |
| `robots.txt` | `text/plain` |

Boş/identity, gzip ve deflate encoding desteklenebilir; çoklu veya desteklenmeyen encoding fail-closed reddedilir. Decoded byte sınırı sıkıştırma sonrasında uygulanır. Declared MIME ile içerik sniff sonucu tutarsızsa `invalid_output` üretilir. HTML yerine challenge/CAPTCHA gövdesi gelirse HTTP 200 olsa bile `challenge`dır. JSON parse ve beklenen liste/item shape doğrulaması başarısızsa `invalid_output` olur.

## 8. Sonuç ve provenance sözleşmesi

Site outcome taksonomisi:

```text
succeeded
no_results
challenge
source_unavailable
rate_limited
blocked_by_policy
invalid_output
partial
failed
not_applicable
cancelled
```

Anlam ayrımları bağlayıcıdır:

- `no_results`: İzinli surface başarıyla okundu ve geçerli biçimde ayrıştırıldı, fakat ilgili aday yok.
- `source_unavailable`: Kaynak teknik olarak alınamadı; “HN'de veri yok” anlamına gelmez.
- `blocked_by_policy`: allowlist, robots, path, redirect veya bütçe politikası çağrıyı engelledi.
- `challenge`: challenge/CAPTCHA veya challenge statüsü; `source_unavailable` içine gizlenmez.
- `not_applicable`: Yöntem bu site/surface için anlamlı değil; global katalog değerini değiştirmez.

Her method sonucu en az şu alanları taşır:

```text
schema_version
pilot_run_id
site_id
method_id
method_category
surface_id
tactic_ids
pipeline_stage_ids
extractor_ids
site_outcome
stop_reason
global_catalog_disposition = retained
worker_pid
origin
sequence_no
started_at
completed_at
network_transaction_count
policy_attempt_count
candidate_count
fetched_artifact_count
```

Her network transaction ayrıca requested/final/canonical URL, redirect chain, status, MIME, content encoding, decoded bytes, truncation, SHA-256, resolved/peer IP, robots kararı ve error class taşır. API list ID'si veya HTML/RSS linki `search_candidate`/`discovery_candidate`; yalnız ayrıca alınmış item/page response'u `fetched_artifact`tır. Aday lineage'ı `method_id`, native ID, source transaction ID ve parent list/page ile korunur.

Ham response immutable artefact olarak ayrı tutulur; extractor çıktısı ham içeriği değiştirmez. Duplicate native ID veya canonical URL tek bağımsız kanıt sayılmaz.

## 9. Minimum pilot sırası ve stop davranışı

Her worker kendi origin sırasını izler:

```text
worker_web: robots -> html_frontpage -> rss_frontpage -> html_pagination -> html_item_page
worker_api: official_api_topstories -> official_api_item
```

Item fetch yalnız aynı worker'ın/list surface'in ürettiği geçerli native ID veya allowlist URL'den türetilebilir. Liste boşsa item yolu `not_applicable/no_seed` olur; keyfi ID üretilmez. Hard budget, circuit, cancellation, timeout veya policy block sonrasında o origin için yeni çağrı başlatılmaz.

## 10. Uygulama ve fixture kabul kriterleri

- Script varsayılan çalışmada ağ açmaz; canlı erişim ayrı ve açık `--live` bayrağı ister.
- Fixture testleri iki farklı process PID'sini, aynı-origin seri sıra numaralarını ve originler arası örtüşebilen zaman aralığını kanıtlar.
- Sadece iki allowlist origin'ine gidilebildiği ve redirect kaçışının engellendiği test edilir.
- Global/origin bütçe, timeout, byte, redirect ve MIME cap'leri aşım testleriyle fail-closed doğrulanır.
- Altı sabit `method_id`, kategori ayrımları ve `global_catalog_disposition=retained` fixture çıktısında görülür.
- `no_results`, `source_unavailable`, `challenge`, `rate_limited`, `blocked_by_policy`, `invalid_output` ve `not_applicable` birbirine dönüşmeden test edilir.
- Discovery candidate ile fetched artifact ayrı tutulur ve provenance tamlığı doğrulanır.

Bu doküman yalnız pilot sözleşmesidir; production connector veya global yöntem kataloğu için kendiliğinden onay oluşturmaz.
