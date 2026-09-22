# Frontend entegrasyonu ve eksikler — Ayşenur

Bu belge mevcut `apps/web` kodunun okunmasıyla hazırlanan iş planıdır. Frontend kodu bu çalışma sırasında değiştirilmedi; uygulama açılıp görsel doğrulama veya çalışma zamanı testi yapılmadı. Aşağıdaki görevler tamamlanmış değildir.

**Sahip:** Ayşenur. **Entegrasyon bağımlılığı ve kabul sorumlusu:** Batuhan. **Kaynak/veri sorunlarının çözüm desteği:** Ayselin. Ayşenur, backend parçaları kullanılabilir oldukça ilgili ekranı bağlar; üç fazın tamamlanmasını beklemez.

## Kapsam ve değişmez kurallar

- Mevcut ürün kapsamı fikir hazırlığı, kaynak verisinin işlenmesi ve kanıta dayalı araştırma raporudur. Build kararı, MVP/PRD, ürün özellikleri ve geliştirme önerileri rapora veya ekran akışına eklenmez. Projenin sonraki ürün geliştirme sürecini yönetici Çağlar daha sonra değerlendirip planlar.
- Başlangıç modeli üç faz için **Gemini 3.1 Flash Lite**. Model yalnız kendisine verilen girdide sohbet, netleştirme, kategori/sorgu hazırlığı, analiz ve raporlama yapar. Sitelerde arama, gezinme, veri çekme veya bağımsız araştırma yapmaz. Bunları backend kaynak scriptleri gerçekleştirir. Ekran metinleri bu ayrımı doğru anlatır.
- Frontend sağlayıcı anahtarını taşımaz veya modele doğrudan veri çekme yetkisi vermez. Anahtarın ekipçe kullanım biçimi, hosting ve test ortamı ayrıca kararlaştırılacaktır.
- API yolu, taşıma yöntemi, kimlik doğrulama altyapısı ve istemci veri kütüphanesi bu belgede seçilmez. Batuhan ile kabul edilen sürümlü sözleşmeye göre bağlanır.
- Mock tasarım ve sözleşme hazırlığında kullanılabilir; gerçek backend yanıtı ve ilgili kabul kanıtı olmadan görev **entegrasyon tamamlandı** sayılmaz. Başarı mesajı yalnız backend işlemi doğruladığında gösterilir.

## Kodda görülen somut eksikler

Kaynak bağlantıları inceleme anındaki dosyalardır. Bunlar düzeltilmesi planlanan kod bulgularıdır; ekranın görsel görünümüne ilişkin doğrulanmış bir denetim sonucu değildir.

| Alan | Mevcut durum ve kaynak | Ayşenur'un yapacağı iş |
|---|---|---|
| Fikir formu | [new-validation-form.tsx](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/components/workspace/new-validation-form.tsx>) yalnız adım ve `started` state tutuyor. Alanlar ortak taslakta tutulmuyor; koşullu adımlar arasında geri dönünce içerik kaybolabilir. Başlat düğmesi yalnız `setStarted(true)` çalıştırıyor. | Form verisini ve seçilen kapsamı koru; alan doğrulama, backend netleştirme soruları, kategori/sorgu planı inceleme ve gerçek başlatma sonucunu bağla. Sabit “4 selected” ve “2–4 hours” gibi dayanaksız değerleri kaldır veya gerçek veriye bağla. |
| Araştırma ilerlemesi | [research-run.tsx](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/components/workspace/research-run.tsx>) ilerlemeyi 68, taranan kaynağı 318 ve maliyeti sabit gösteriyor. Pause/Resume yalnız yerel state değiştiriyor; aşamalar eski sabit liste. | Faz ve kaynak işlerinin gerçek durumunu göster. Desteklenmeyen durdur/devam et işlemini çalışır gibi sunma. Gerçek ilerleme ölçümü yoksa uydurma yüzde yerine durum göster. |
| Projeler ve özet | [dashboard mock](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/lib/mock-data/dashboard.ts>), [workspace mock](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/lib/mock-data/workspace.ts>) ve [projects-board.tsx](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/components/workspace/projects-board.tsx>) sabit projeleri, sayıları ve kararları gösteriyor. | Proje/araştırma kimliklerini kullan; liste, seçili araştırma ve özetlerin aynı backend kaydını göstermesini sağla. Başka proje veya eski çalışmanın verisi seçili rapora karışmasın. |
| Kanıt | [evidence-library.tsx](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/components/workspace/evidence-library.tsx>) mock alıntıları yerelde filtreliyor. Kaynak aç düğmesi işlevsiz; mock kayıtlarda artifact/citation bağı ve URL yok. | Gerçek kanıt kimliği, URL, alıntı, tarih ve bağlamı göster; kaynak bağını aç. “Verified” gibi etiketleri backend doğrulama sonucu olmadan kullanma. |
| Rakipler ve sorunlar | [competitor-table.tsx](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/components/workspace/competitor-table.tsx>) sabit satırları, [pain-points-board.tsx](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/components/workspace/pain-points-board.tsx>) mock sayıları kullanıyor. Karşılaştırma/kanıt inceleme düğmeleri bağlı değil. | Kaynaklı rakip ve sorun verilerini bağla. Sayıların neyi saydığını ve kapsamını belirt; her bulgudan ilgili kanıta geçiş sağla. |
| Rapor ve kapsam | [decision-report.tsx](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/components/workspace/decision-report.tsx>) sabit “BUILD · 82% CONFIDENCE”, 100 üzerinden puanlar, ürün planına ekle eylemi ve işlevsiz dışa aktarma içeriyor. [dashboard tipleri](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/lib/types/dashboard.ts>) `BUILD` ve sayısal `confidence` bekliyor; [confidence-badge.tsx](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/components/ui/confidence-badge.tsx>) bunları yüzdeye çeviriyor. | Build/MVP/ürün planı akışını ve dayanaksız başarı/güven yüzdelerini kaldırma görevini uygula. Faz 3'ün güncel rapor sözleşmesini kullan; olumlu bulguyu otomatik geliştirme kararı gibi sunma. |
| Kaydetme ve genel eylemler | [settings-panel.tsx](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/components/workspace/settings-panel.tsx>) yalnız `setSaved(true)` ile kayıt bildiriyor. [workspace-screen.tsx](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/components/workspace/workspace-screen.tsx>) başlık düğmelerinin, [top-bar.tsx](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/components/layout/top-bar.tsx>) yeni araştırma/bildirim/tarih düğmelerinin işlem bağlantısı yok. | Kapsamdaki eylemleri gerçek route/işleme bağla; henüz desteklenmeyen işlevi devre dışı ve anlaşılır göster veya gizle. Backend onayı gelmeden “kaydedildi” yazma. Profil/ayar backend kapsamı ayrıca Batuhan ile netleştirilsin; yeni hesap ürünü tasarlamak bu görevin varsayımı değildir. |
| Yardım ve açıklamalar | [help-center.tsx](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/components/workspace/help-center.tsx>) güveni talep/şiddet/kalite birleşimi gibi tanımlıyor; [workspace metinleri](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/apps/web/lib/mock-data/workspace.ts>) “AI research” ve karar odaklı eski açıklamalar içeriyor. | Üç fazın gerçek kapsamına, modelin yetki sınırına ve kanıt yeterliliği anlamına göre düzelt. Tanımlanmamış skor metodunu kullanıcıya mevcut özellik gibi anlatma. |

## Fazlara göre backend teslimi ve ekran bağlantısı

Aşağıdakiler gerekli yetenek ve veri bağımlılıklarıdır; seçilmiş endpoint adları veya uygulanmış servisler değildir. Ayrıntılı alanlar [ortak sözleşme](</Users/caglarkc/Desktop/ACK TECHS/DemandRift---Startup_Market_Intelligence_Agent/ortak/veri-sozlesmeleri.md>) ve ilgili faz sözleşmesinden alınır.

| Faz | Batuhan'dan beklenen sözleşme/işlev | Ayşenur'un bağlayacağı alan ve kabul örneği |
|---|---|---|
| 1 | Fikir oluşturma/güncelleme, netleştirme turu, kategori ve sorgu planı; `project_id`, `research_id`, plan sürümü, `status`, `unknowns`, doğrulama hataları | Fikir formu ve plan inceleme. Kullanıcı onayı ile AI çıkarımı ayrı görünür; yanlış kategoriyi düzeltme yeni plan sürümüne yansır. Eksik bilgide sahte “hazır” yerine netleştirme beklenir. |
| 1 → 2 | Onaylı planı yürütme, çalışma kimliği/durumu, başlatma sonucunun tekrar okunması | Başlatma ve araştırma ekranına geçiş. Çift tıklama veya ağ kesintisinden sonra birden fazla iş başlatılmaz; mevcut işlem durumu kontrol edilir. |
| 2 | Kaynak işi durumları, toplama kapsamı ve limitler, `SourceReport`, kanıt/alıntı kayıtları, `EvidenceBundle` ve sürümü | Araştırma, kanıt, rakip ve sorun ekranları. Hangi sitenin çekildiği, hangisine erişilemediği ve sonuçların kapsamı görünür. Kaynak sayısı ile bağımsız örnek sayısı birbirine karıştırılmaz. |
| 3 | `DecisionReport`, `evidence_sufficiency`, bulgu/karşıt kanıt/eksikler, kaynak referansları, yönetici incelemesi ve gerçek rapor durumu | Araştırma raporu ekranı. Yeterlilik eşiği tek başına başarı puanı olmaz. Eksik/çelişkili kanıt görünür; kaynak bağı açılabilir; Build/MVP/ürün planı sunulmaz. |
| Ortak | Proje/araştırma listeleme ve detay, sürümlü hata zarfı, mevcut erişim bağlamı; kapsamda kararlaştırılan kayıt/dışa aktarma işlevleri | Dashboard ve proje seçimi, yenileme, doğru kayda dönüş, güvenli hata mesajı. Dosya dışa aktarma ancak kararlaştırılmış kapsam ve gerçek çıktı ile tamamlandı sayılır. |

Backend hazır olmayan alana Ayşenur sahte kesin veri eklemek yerine ihtiyaç kaydı açar: ekran/görev, gerekli alan, örnek payload, kullanım nedeni ve eksikliğin kullanıcı akışına etkisi. Batuhan şemayı kabul eder veya gerekçeli alternatif verir.

## Her bağlı ekranda durum kabul tablosu

| Durum | Beklenen davranış |
|---|---|
| İlk yükleme / işlem sürüyor | İşlem durumu anlaşılır; çift gönderim engellenir. Uydurma ilerleme yüzdesi veya tamamlanmış rapor gösterilmez. |
| Doğrulama / netleştirme bekliyor | Hata ilgili alana bağlanır; kullanıcının girdisi korunur. Eksik kategori/bağlam sessizce tamamlanmış sayılmaz. |
| Boş liste / uygun sonuç yok | Henüz araştırma yapılmadı, filtre eşleşmedi ve kaynak başarıyla aranıp sonuç bulunamadı ayrı anlatılır. |
| Kısmi sonuç | Gelen veri görünür; başarısız/eksik kaynaklar, kapsam ve rapora etkisi saklanmaz. |
| Erişim engeli / kota / doğrulama engeli | `source_unavailable`, `rate_limited`, `blocked_by_policy`, `challenge` boş pazar sonucu sayılmaz. Kaynak erişim sorunu ile kullanıcının kayda erişim yetkisi farklıdır. |
| API / model / ağ hatası | Güvenli açıklama, işlem kimliği ve izinli tekrar deneme yolu gösterilir. Form verisi korunur; mevcut işin sonucu bilinmiyorsa yeni iş otomatik yaratılmaz. |
| Kullanıcının kayda erişimi yok | Kaynak/rapor içeriği sızdırılmaz; başka projeden eski veri ekranda kalmaz. Kimlik doğrulama teknolojisi bu belgeyle seçilmiş değildir. |
| Yenileme / geri dönüş | Seçili proje, araştırma ve rapor backend kimliğiyle yeniden yüklenir. Son bilinen veri ile güncel veri ayrılır; bitmemiş iş sırf sayfa yenilendi diye tamamlanmaz. |
| Yeniden analiz / yeni sürüm | Önceki rapor ve güncel çalışma karıştırılmaz; gösterilen sürüm ve güncellenme tarihi bellidir. Eski citation yeni rapora yanlış bağlanmaz. |
| Tamamlandı / yetersiz kanıt | Teknik tamamlanma ile kanıt yeterliliği ayrılır. Tamamlanmış `Investigate More` raporu yeterli kanıt bulunduğu anlamına gelmez. |

## AY görevleri ve teslim sırası

Başlangıç durumu bütün satırlarda **planlandı**. Görev kimlikleri Ayşenur'un kişisel takip dosyasında aynı kalır; tamamlanma ve geri bildirim o dosyada izlenir.

| Kimlik | Görev ve bağımlılık | Teslim çıktısı | Batuhan'ın kabul kontrolü |
|---|---|---|---|
| AY-01 | Ekran envanteri, yukarıdaki kapsam kalıntıları ve tasarım düzeltmeleri. Backend beklemeyen hazırlıkla başla. | Ekran → faz → bileşen → ihtiyaç → açık sorun eşlemesi; Build/yüzde/ürün planı ve işlevsiz eylem düzeltmeleri | Aktif arayüzde kapsam dışı ürün önerisi veya gerçekmiş gibi mock iddia kalmadığını kontrol et; eksikleri dosya/ekran bazında geri bildir. |
| AY-02 | Batuhan ile sürümlü veri sözleşmesini ve durumları eşleştir. Her faz başlamadan ilgili kısmını tamamla. | İstek/yanıt/hata örnekleri, eksik alan listesi, alan kökeni ve durum eşlemesi | Gerçek backend payload'ının ekranda kayıpsız temsilini ve bilinmeyen alanların uydurulmamasını kontrol et. |
| AY-03 | Faz 1 fikir, netleştirme, kategori ve plan ekranlarını bağla. Faz 1 backend dilimine bağlı. | Girdiyi koruyan form; kategori/sorgu planı görünümü; onay ve gerçek başlatma bağlantısı | Açık/eksik/yanlış etiketli fikir örneklerinde girdinin korunmasını, doğru plan sürümünü ve hata davranışını doğrula. |
| AY-04 | Faz 2 kaynak durumu, kanıt, rakip ve sorun ekranlarını bağla. Kaynak işi/kanıt sözleşmelerine bağlı. | Gerçek kaynak bazlı ilerleme, alıntı-bağlam geçişi, filtreler ve kısmi/erişim hatası durumları | Gösterilen değerleri backend çıktısıyla karşılaştır; veri yanlışı varsa Ayselin'e, görüntüleme/eşleme yanlışı varsa Ayşenur'a kanıtlı düzeltme ver. |
| AY-05 | Faz 3 raporu bağla. Doğrulanmış rapor ve yeterlilik alanlarına bağlı. | Kaynaklı bulgu, karşıt bulgu, bilinmeyenler, yeterlilik ve yönetici değerlendirmesi görünümü | En az 3 bağımsız örnek/2 kaynak eşiğinin nitel kontrollerden ayrı görünmesini, yetersiz kanıtın saklanmamasını ve Build/MVP/uydurma güven yüzdesi olmamasını kontrol et. |
| AY-06 | Ortak gezinme, proje/araştırma seçimi, yenileme ve kapsamdaki kayıt eylemlerini tamamla. İlgili backend yeteneğine bağlı. | Doğru kimliğe yönlenen ekranlar, gerçek kayıt geri bildirimi, yenilemeden sonra tutarlı durum | Projeler arası veri karışmasını, çift işlem başlatmayı, yenilemede kaybı ve işlevsiz başarı mesajlarını kontrol et. |
| AY-07 | Her backend dilimi sonunda tasarım ve entegrasyon kabul kanıtlarını topla; son dilimde bütün akışı kapat. | Gerçek çalışma kimliği, girdi/çıktı, kontrol edilen ekranlar, durum senaryoları, açık hatalar ve düzeltme sonrası yeniden kontrol kaydı | Önceki geri bildirimlerin kapandığını ve mock ile gerçek entegrasyon sonuçlarının ayrıldığını kontrol et; kabul/red gerekçesini yaz. |

## Tasarım ve kullanılabilirlik kontrol listesi

Ayşenur her ilgili ekran değişikliğinde aşağıdakileri kontrol eder; henüz test edildiği varsayılmaz:

- Dar/geniş ekranlarda uzun fikir, kaynak URL'si, kategori, alıntı ve hata metni okunabilir; tablo ve paneller önemli alanı kırpmaz.
- Aydınlık/karanlık temada metin, hata, seçili durum ve butonlar ayırt edilebilir; durum yalnız renkle anlatılmaz.
- Form etiketleri, klavye odağı, düğme isimleri ve hata duyuruları anlaşılır. Tıklanabilir tablo satırına klavyeyle de erişilebilir.
- Yüklenme, boş ve hata görünümü tasarımın parçasıdır. Bütün ekranı boş bırakmak veya eski mock değerleri geri getirmek hata çözümü değildir.
- Kanıt, AI yorumu, varsayım ve bilinmeyen bilgi görsel/metinsel olarak ayrılır. Kritik sınırlamalar yalnız küçük bir tooltip'e saklanmaz.
- Seçilen dil, tarih/saat, sayı ve durum adları tutarlı kullanılır. Gerçek kayıt yokken sabit “Updated today” veya kaynak sayısı gösterilmez.

## Geri bildirim ve kapanış

Ayşenur tesliminde görev kimliği, ilgili ekran, backend/sözleşme sürümü, gerçek `research_id`, örnek girdi/çıktı, beklenen/gerçekleşen davranış ve çalıştırılmayan kontrolleri bildirir. Yerel test/ortak entegrasyon düzeni onaylandı; uzak build ve erişim ayrıntıları ortak kararda netleştirilecek.

Batuhan teslimi inceler; **“şu alan yanlış eşleniyor / şu durum eksik / şu davranışın düzeltilmesi gerekiyor”** şeklinde somut geri bildirim verir. Her kayıt sahip, öncelik, tekrar üretim adımı ve kabul beklentisi taşır. Ayşenur düzeltme kanıtını ekler; Batuhan tekrar kontrol etmeden görev kapatılmaz. Kaynak çıktısının doğruluğu sorununda Batuhan Ayselin'e çözüm görevi açar; arayüz hatası gibi kapatılmaz.

## Yayın hedefi ve sonraki kurulum

Frontend **Vercel**, backend **Hetzner**. Çağlar test API erişimini/adresini sağlayacak. Ayşenur API adresini ortamdan alan entegrasyonu ve durum ekranlarını hazırlayacak; Gemini anahtarı tarayıcıya taşınmayacak. Vercel proje/repo bağlantısı, API HTTPS adresi, origin/oturum ayarları ve deploy işlemlerini Çağlar ile sonraki ayrı kurulum çalışmasında yapacağız. Mevcut planlama görevi bunları yayınlamaz. [Ortam planı](dagitim-ve-ortam-plani.md).
