# Üç faz için kanonik API sözleşmesi v1

Tek kaynak `apps/api/app/contracts.py` içindeki Pydantic modelleridir. `apps/api/scripts/generate_contracts.py`, serialization şemasından `packages/contracts/schema/wire.schema.json` ve `packages/contracts/src/generated.ts` üretir. Paket index'i yalnız bu tipleri dışa aktarır; confidence ve eski faz varsayımları taşıyan Zod kopyası kaldırılmıştır. Pydantic 2.13.5 ve TypeScript 6.0.3 sabitlenmiştir.

Repo kökünde API dependencies kurulu sanal ortamla:

```sh
python apps/api/scripts/generate_contracts.py
python apps/api/scripts/generate_contracts.py --check
npm ci --ignore-scripts --prefix packages/contracts
npm run typecheck --prefix packages/contracts
PYTHONPATH=apps/api python -m pytest -q apps/api/tests
```

CI Python 3.13 test imajıyla ağsız pytest ve üretilmiş dosya drift kontrolünü, ardından TypeScript kontrolünü çalıştırır. Local Python 3.14 sonucu hedef imaj kontrolünün yerine geçmez.

`GET /api/v1/contracts` aynı katalog ve `schema_version=1.0.0` döndürür. OpenAPI içinde aynı şemalar `Wire_` önekiyle bulunur; `$defs` referansları `components/schemas/Wire_` referansına çevrilir. Bu ayrım eski preview `SourceHealth/AccessMethod` değerlerini üretim yeterliliği olarak yorumlamayı önler. `/health` yalnız süreç canlılığıdır.

Faz kayıtları server kaynaklı user/project/research UUID'leri, timezone içeren created_at, schema_version ve ilgili versions taşır. Brief/plan/document/bundle/report/gap kimlik ve pozitif sürümleri ayrıdır. Persistence ve immutable sürüm oluşturma BE-02/07/14 işidir; DTO doğrulaması kaydın kalıcı veya yetkili olduğunu kanıtlamaz.

Unknown `value=null, state=missing, origin=null, confirmed=false` olur. State known/inferred/missing/conflicting; AI kökenli alan assumption_id taşır. Çelişen adaylar conflicting_values, eski köken prior_origins içinde korunur. continue_with_unknowns kullanıcı tercihidir. original_idea boşluk ve satır sonlarıyla korunur. Kullanıcı ifadesi/onayı ve AI çıkarımı/hypothesis ayrıdır. Unmatched kategori null kalır. Onaylı plan çözümlenmemiş clarification, onaysız kategori/hypothesis veya planlanmamış kaynağa bağlı sorgu içeremez. Onay zamanı ve status uyuşur. Fingerprint idempotency değildir.

Run lifecycle, source sonucu, citation validation ve evidence sufficiency ayrı enumlardır. completed yeterlilik iddiası değildir. Discovery/snippet/sitemap kaydı fetched_content değildir. Başarılı içerik body_ref, hash ve pozitif byte sayısı gerektirir; arşiv archive_copy kökeni taşır.

Bütçede request/byte/page/record/duration/token/concurrency açık sınırlardır. USD cost altı ondalıklı string'dir; NaN/Infinity, boolean sayaç ve kayan noktalı para reddedilir. Soft cost hard cost'u aşamaz. Gerçek atomik reservation ve provider uzlaştırması BE-05'te uygulanır; Usage gerçekleşen ve rezerv maliyetini ayırır.

Tam normalized text ile segment owner/project/research/document/normalizer ve metin dilimi eşleşir. Offset Unicode code point indeksidir, UTF-8 byte değildir. Citation quote, document sürümü, artifact/document/segment, segment/full hash, normalizer, URL/capture zamanı taşır; validated timestamp veya rejected reason gerektirir. EvidenceBundle validated claim/citation, çift yönlü bağ ve aynı owner/project/research ister. Tam kaynak/hash doğruluğu BE-11'de kalıcı artifact/document üzerinden doğrulanır; salt shape kontrolü bu doğruluğu iddia etmez. Kaynak, belge ve bağımsız örnek sayıları ayrıdır.

Dört outcome positive_findings/modify/kill/investigate_more; management_review_required=true. Build/MVP/confidence yoktur. Insufficient kesin outcome üretmez; eligible outcome kümesi deterministik policy'den gelir. Gerçek 3/2+nitel hesaplama BE-13'tedir. Gap investigate_secondary veya validate_primary olur; primary web dispatch etmez, secondary en fazla üç cycle ile sınırlandırılır.

ApiError güvenli mesaj/code/request kimliği, retry/usage/remaining work tanımlar. Runtime hata eşlemesi BE-03/15, frontend tüketimi FE-02 işidir. Eski `/api/v1/research/plans` stateless preview geriye uyumlu kalır; persist edilmiş run değildir. Bu teslim auth/DB/worker/model/kaynak veya tam ürün kabulünü kapatmaz.

Üreteç gerçek Pydantic örneklerini packages/contracts/tests/producer-consumer.ts dosyasına da yazar. Dolu constraints/connector/prompt/raw-field/qualitative-check eşlemeleri TypeScript tarafından kabul edilir; yanlış map value/durumlar derleme kontrolünde reddedilir. patternProperties ve enum-keyed dictionary değer tipleri korunur.
