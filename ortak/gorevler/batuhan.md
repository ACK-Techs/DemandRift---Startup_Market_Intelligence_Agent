# Batuhan — proje yürütücüsü ve backend

Calendar kullanıcı adı: **batuhanevleksiz**. [İçe aktarılacak görev dosyası](../calendar-import/demandrift-batuhanevleksiz.json).

Tüm işler **planlandı**; bu dosya tamamlanma raporu değildir. Kabul eden ve düzeltmeleri yeniden kontrol eden: **Batuhan**. [Ortak takip/geri bildirim kuralları](../ekip-ve-teslim.md).

| ID | Faz | Görev | Bağımlılık | Teslim / kabul koşulu | Durum | Kanıt / FB / son güncelleme |
|---|---|---|---|---|---|---|
| BT-01 | 1 | Kategori/sorgu kuralları, sürümlü ResearchPlan ve Gemini sohbet akışı | Ortak teknoloji/API kararları; F1 senaryoları | Şema kontrollü akış; model araçsız; eksik bilgi korunur | planlandı | — |
| BT-02 | 1 | Kategori → kaynak → script → alan eşlemesi ve ilk gerçek sorgu denemeleri | BT-01; kaynak profilleri; test erişimi | 30 fikir sonucu ve seçili kaynaklarda ham kanıtlı denemeler | çalışılıyor | [AS-01 ön kabul / kaynak kullanım sınırları](geri-bildirim/BT02-AS01-KONTROL-2026-09-26.md) · 2026-09-26 |
| BT-03 | 1 | Başarısız denemeleri Ayselin’e bildir; düzeltmeleri yeniden kontrol et | Başlangıç: BT-02; yeniden kontrol: AS-02/03 teslimi | Her bulgu beklenen/gerçek/düzeltme/kabul koşullu; geri kontrol kaydı | planlandı | — |
| BT-04 | 1 | Ayşenur’a fikir/plan API ve hata örnekleri ver; bağlı ekranı kabul et | Başlangıç: BT-01; son kabul: AY-03 teslimi | Gerçek plan kimliği ve ekran durumları kontrol edilmiş | planlandı | — |
| BT-05 | 2 | Script adaptörü, kayıt, limit/retry/iptal ve veri hazırlama hattı | Faz 1 kabulü; mimari seçimleri | Ham→normalize→claim/citation→SourceReport→EvidenceBundle izlenebilir | planlandı | — |
| BT-06 | 2 | Filtre/alıntı/kapsam sorunlarını Ayselin’e; ekran/API sorunlarını ilgili kişiye yönlendir | Başlangıç: BT-05; yeniden kontrol: AS-04 ve AY-04 teslimi | 24 senaryo + etiketli veri sonucu; her düzeltme yeniden kontrol edilmiş | planlandı | — |
| BT-07 | 3 | 3/2 ve nitel gate kuralları, araçsız Gemini sentezi, rapor validator | Faz 2 paketi; policy v1 | Olumlu/karşıt/eksik çıktı; Build/MVP engeli; sürümlü rapor | planlandı | — |
| BT-08 | 3 | Ayselin rapor/kanıt değerlendirmesini ve Ayşenur rapor ekranını kontrol et | Başlangıç: BT-07; son kabul: AS-05 ve AY-05 teslimi | Kanıt bağlantıları, sınır senaryoları ve gerçek ekran aynı sonucu gösterir | planlandı | — |
| BT-09 | Tümü | Ekip takibi, API teslim sırası, engel ve nihai kapanış raporu | Her teslim | Sahipsiz hata yok; kapsam/teknoloji soruları Çağlar’a; test yapılmadıysa açık | planlandı | — |

Batuhan yalnız iş dağıtmaz: Ayselin’in her düzeltmesini aynı sorgu/veriyle, Ayşenur’un her bağlantısını gerçek backend çıktısıyla yeniden kontrol eder. “Yapılması gerekiyor/düzeltilmesi gerekiyor” bildirimini somut kabul koşuluna bağlar. Kendi backend hatasını kendisi çözer. Kaynak çözülemiyorsa yalan başarı yerine engel/kapsam açığı kaydeder.

## Açık geri bildirimler

Henüz gerçek bulgu kaydı açılmadı. [Şablon](geri-bildirim-sablonu.md) kullan; görev ID ve kanıt bağlantısını üst tabloya ekle.

## Bağımlılıkların anlamı

Başlatma girdisi ile son kabul ayrı adımlardır. Batuhan önce API/örnek veya hata bildirimini teslim eder; karşı taraf bu girdiye dayanarak çalışır. Batuhan’ın kabul alt adımı karşı tarafın tesliminden sonra yürür. API/hata bildirimi hazır olduğunda Batuhan’ın bütün görevinin kapanması beklenmez.

## Ortam ve teslim sınırı

Backend teslim hedefi Hetzner’de FastAPI + Celery/Redis + PostgreSQL. API/OpenAPI, ortamdan ayar okuma, sağlık/durum ve erişim kontrollerini hazırla; Çağlar’ın sağlayacağı API adresiyle Ayşenur’a sürümlü örnek ver. Hetzner erişimi, runner kurulumu ve deployment branch yapılandırması Çağlar ile sonraki ayrı çalışmanın işidir.
