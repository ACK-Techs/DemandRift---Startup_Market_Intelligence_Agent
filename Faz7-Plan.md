# Faz 7 — Karar Motoru ve Yön Önerisi

> Ortak Citation Service, karar sürümleme, feedback, evaluation ve tenant kuralları için `Platform-Temeli.md`; fazlar arası entegrasyon ve Faz 8'e çıkış sınırı için `Ust-Yonetim-Ana-Mimari-Plani.md` bağlayıcıdır.

## Amaç

Faz 6'nın kaynaklı Evidence Dossier'ini; kanıt yeterliliği, pazar sinyalleri, karşıt kanıt, farklılaşma ve kullanıcının uygulama koşulları üzerinden değerlendirmek ve kullanıcıya gerekçeli bir yön önerisi sunmak.

Bu faz, tek bir fikir skoru veya AI'ın kişisel yorumu değildir. Kanıt yeterliliğini önce kontrol eden; pazar ve uygulama koşullarını ayrı değerlendiren; karşıt kanıtı, belirsizliği ve karar stabilitesini görünür tutan bir gated decision-support system olacaktır.

> Faz 7, startup başarısını tahmin etmez. Mevcut kanıtlarla hangi yönün daha mantıklı olduğunu ve hangi belirsizliğin kararı değiştirebileceğini gösterir.

## Faz sınırı

### Girdi

- Faz 1 Idea Brief ve kullanıcı onayları
- Faz 2 Research Plan
- Faz 3/4 araştırma veri seti ve provenance bilgisi
- Faz 5 Deep Research çıktıları, varsa
- Faz 6 Evidence Dossier:
  - Problem Evidence Map
  - Voice of Customer Map
  - Competitor Matrix
  - Pricing Evidence Map
  - Opportunity Hypotheses
  - Counter-Evidence Map
  - Research Limitations
  - Evidence Confidence Profiles
- Kullanıcının bütçe, teknik kapasite, zaman ve platform tercihleri

### Çıktı

- Build, Modify, Kill veya Investigate More yön önerisi
- Evidence Sufficiency sonucu
- Karar gerekçesi
- Dayanak ve karşıt claim'ler
- Kritik bilinmeyenler
- Karar stabilitesi
- Varsayımlar
- Value of Information / en değerli sonraki doğrulama adımları
- Investigate More alt türü: `investigate_secondary` veya `validate_primary`
- Primary validation status ve henüz doğrulanmamış davranışlar
- Kararın dayandığı sürümlenmiş Decision Dossier

### Faz 7'nin yapmadığı işler

- Nihai PRD, MVP scope, teknik mimari veya prompt paketi üretmek
- Yeni kaynak/crawler araştırması başlatmak
- Kaynağa dayanmayan iddia veya yatırım tavsiyesi vermek
- Kullanıcı adına ürün fikrini zorla değiştirmek
- Startup'ın başarı olasılığına dair kesin yüzde üretmek

## Seçilen mimari

Akış:

Faz 6 Evidence Dossier
→ Evidence Sufficiency Gate
→ Decision Pillar Evaluation
→ Decision Policy Engine
→ Gate Counterfactual ve kalibre edilmiş Stability Analysis
→ AI Decision Synthesis
→ Decision Validator
→ Build, Modify, Kill veya Investigate More

### Bileşen sorumlulukları

| Bileşen | Sorumluluk |
| --- | --- |
| Evidence Sufficiency Gate | Kritik kanıt ve araştırma kapsama eşiğini kontrol eder. |
| Decision Pillar Engine | Pazar ve uygulama boyutlarındaki kanıt profillerini oluşturur. |
| Decision Policy Engine | Hard gate'ler, outcome eligibility ve sürümlenmiş karar kurallarını uygular. |
| Stability Analyzer | Kararı değiştirecek gate, claim ve varsayımları counterfactual olarak test eder; yalnızca kalibre edilmişse ağırlık duyarlılığı çalıştırır. |
| Value of Information Engine | Kararı en çok değiştirebilecek sonraki doğrulama bilgisini önceliklendirir. |
| AI Decision Synthesizer | Kaynaklı kararı, karşıt kanıtı ve sonraki adımı anlaşılır biçimde yazar. |
| Decision Validator | AI çıktısındaki citation, claim, outcome ve politika uyumunu doğrular. |

AI, kararın tek sahibi değildir. Hard gate'ler, hesaplamalar, outcome uygunluğu ve kaynak doğrulama deterministik katmanda uygulanır.

## Pazar kararı ve uygulama koşulunun ayrımı

Pazar fırsatı ile kullanıcının mevcut koşullarını tek puanda karıştırmak yasaktır.

### Pazar sinyali

- Problem doğrulaması
- Kullanıcı/buyer sinyali
- Rekabet ve farklılaşma
- Fırsat hipotezi
- Ödeme/fiyat sinyali

### Uygulama koşulu

- Bütçe
- Teknik kapasite
- Zaman
- Platform tercihi
- Lean MVP ile doğrulama yapılabilirliği

Güçlü pazar fırsatı, kullanıcı için mevcut haliyle pahalı/zor olabilir. Bu durum çoğunlukla Kill değil, Modify sonucuna veya daha küçük MVP kapsamına işaret eder.

## 1. Evidence Sufficiency Gate

Bu ilk kapı geçilmeden sistem kesin Build veya Kill önerisi vermemelidir.

Kontrol edilecekler:

- Kritik araştırma niyetleri kapsandı mı?
- Bağımsız kaynak çeşitliliği yeterli mi?
- Kanıtların çoğu duplicate/repost mu?
- Karşıt kanıt araştırıldı mı?
- Veriler yeterince güncel mi?
- Kaynak erişim engelleri sonucu bozuyor mu?
- Problem, rakip, fiyat veya ödeme verisinde kritik boşluk var mı?
- Dil ve coğrafya kapsamı hedef pazar için yeterli mi?
- Pazar olgunluğu profiline uygun kanıt beklentisi kullanıldı mı?
- Araştırma sınırlılıkları mevcut tezi doğrudan etkiliyor mu?

Kapı geçilmezse varsayılan sonuç Investigate More'dur.

Bu sonuç fikrin kötü olduğu anlamına gelmez. Güvenilir karar için kanıtın yetersiz veya çelişkili olduğu anlamına gelir.

## 2. Karar sütunları

Kesin ağırlıklar ve eşikler, gerçek kullanım verisi görüldükten sonra kalibre edilir. İlk sürümde çerçeve aşağıdaki sütunlardan oluşur:

| Sütun | Ölçtüğü şey |
| --- | --- |
| Problem doğrulaması | Problem gerçek, tekrar eden ve yeterince güçlü mü? |
| Kullanıcı/buyer sinyali | İnsanlar çözüm arıyor, workaround kullanıyor veya doğrulanmış davranış gösteriyor mu? Beyan edilen ödeme isteği yalnızca zayıf sinyaldir. |
| Rekabet ve farklılaşma | Mevcut alternatifler güçlü mü, kullanıcılar nerede memnun değil? |
| Fırsat hipotezi | Hedef segment, problem ve çözüm yaklaşımında savunulabilir alan var mı? |
| Uygulanabilirlik | Kullanıcının koşullarında lean bir MVP mümkün mü? |
| Kanıt kalitesi | Sonuç yeterli, bağımsız ve güncel araştırmaya dayanıyor mu? |

Her sütun tek sayı yerine şu profili taşır:

- status: strong, mixed, weak veya insufficient
- supporting_evidence
- challenging_evidence
- unknowns
- confidence_profile

## 3. Karar sonuçları

### Build

Build için birlikte aranacak koşullar:

- Evidence Sufficiency Gate geçilmiş olmalı
- Problem sinyali güçlü olmalı
- Karşıt kanıt kararı çökertmemeli
- En az bir gerçek farklılaşma/fırsat hipotezi bulunmalı
- Kullanıcının koşullarında lean bir MVP mümkün olmalı

İç sistem kodunda bu sonuç `build_to_validate` olarak tutulur. Kullanıcı arayüzünde **Build** gösterilir; anlamı tam ürünü inşa etme garantisi değil, en kritik varsayımları test edecek MVP'yi geliştirmektir. Gerçek ödeme davranışı veya kullanıcı görüşmesi yoksa bu eksik açıkça görünür ve Build sonucunun altında zorunlu primary validation planı bulunur.

Build, başarı garantisi değildir.

Anlamı: Mevcut kanıtlarla, dar bir MVP ile doğrulamaya devam etmek mantıklıdır.

### Modify

Modify şu durumlarda kullanılır:

- Problem gerçek görünür
- Ancak mevcut hedef segment, konumlandırma, çözüm yaklaşımı veya kapsam zayıftır
- Fırsat vardır fakat kullanıcının bütçe/teknik koşulları için MVP yaklaşımı değişmelidir
- Ödeme veya farklılaşma yalnızca daha dar bir segmentte görünmektedir

Modify çıktısında mutlaka şu alanlar bulunur:

- korunacak sinyal
- değiştirilecek varsayım
- önerilen yeni niş/segment veya çözüm sınırı
- yapılmaması gerekenler
- kararı yeniden değerlendirecek kanıt

### Kill

Kill sonucu kullanıcı arayüzünde mümkünse şu dilde sunulur:

Do not build this thesis now.

Kill ancak şu koşullarda önerilir:

- Araştırma kapsamı yeterlidir
- Problem sinyali sürekli zayıf veya güçlü biçimde çelişkilidir
- Mevcut alternatiflerin ihtiyacı yeterince çözdüğüne dair pozitif kullanıcı veya davranış kanıtı vardır
- Savunulabilir farklılaşma bulunamamış ve bu durum yeterli rakip/alternatif kanıtıyla desteklenmiştir
- Karşıt kanıt güçlüdür
- Bu sonuç kaynak bulunamadığı için değil, yeterli araştırma yapıldığı için oluşmuştur

Şikâyet bulunmaması memnuniyet kanıtı değildir. Sessizlik, düşük paylaşım kültürü veya erişilemeyen kaynak Kill'i besleyemez. Kill için yalnızca kanıt yokluğu değil, mevcut teze karşı pozitif ve bağımsız karşıt kanıt gerekir. `new`, `emerging` veya `unknown` pazar profillerinde düşük kanıt varsayılan olarak Kill değil primary validation gerektirir.

Kill, kullanıcının girişimcilik potansiyeli veya başka fikirleri hakkında hüküm vermez. Yalnızca mevcut tez için şimdi geliştirme önerilmediğini belirtir.

### Investigate More

Investigate More şu durumlarda kullanılır:

- Kritik veri eksik veya çelişkilidir
- Tek platforma/kaynak ailesine aşırı bağımlılık vardır
- Fiyat/ödeme isteği net değildir
- Araştırma sınırlılıkları sonucu değiştirebilir
- Küçük bir ek araştırma, Build/Modify/Kill sonucunu değiştirme potansiyeline sahiptir

Bu sonuç boş olmamalıdır. Value of Information Engine en değerli sonraki doğrulama adımını sunar.

Investigate More iki deterministik alt türe ayrılır:

#### `investigate_secondary`

Sistemin kendi araştırma döngüsüyle kapatabileceği boşluklar içindir: erişilemeyen kaynak, eksik dil/coğrafya, güncellik, tek platform yanlılığı, rakip changelog'u veya karşıt kanıt eksikliği. Faz 6 `ResearchGapRequest` üretir; Faz 5 politikası üzerinden Faz 3–4–6 döngüsü yeniden çalışır.

#### `validate_primary`

İnternet araştırmasının kapatamayacağı boşluklar içindir: gerçek ödeme isteği/fiyat toleransı, problem şiddeti, segment uyumu, çözümün işe yararlığı ve satın alma süreci. Çıktı en az bir somut yöntem içerir:

```text
interview | landing_test | preorder | concierge | pilot
target_segment
sample_or_traffic_target
script_or_offer
success_threshold
failure_threshold
evidence_to_capture
reassessment_trigger
```

Problem varlığı bir kez yeterince desteklendikten sonra, aynı konuda daha fazla ikincil araştırmanın azalan getirisi Value of Information hesabında görünür bir ceza alır; karar değiştirecek davranış verisi önceliklendirilir.

## 4. Gated MCDA yaklaşımı

Sadece ağırlıklı toplam skor kullanılmaz. Güçlü problem sinyali; eksik araştırma, sıfır farklılaşma veya kritik uygulama engelini maskeleyemez.

Yaklaşım:

1. Hard gate'ler
2. Çok kriterli değerlendirme
3. Belirsizlik ve hassasiyet analizi
4. Kaynaklı karar anlatımı

Karar politikası, her sütun için ağırlıkları ve minimum koşulları sürümlenmiş biçimde saklar. Eşikler ilk sürümde basit ve açıklanabilir olur; gerçek kullanım, kullanıcı geri bildirimi ve gerçekleşen sonuçlarla kalibre edilir.

## 5. Gate Counterfactual ve Stability Analysis

Birincil yöntem **gate counterfactual** analizidir. Sistem şu soruları test eder:

- Hangi zorunlu gate yalnızca bir bağımsız kaynak veya tek bir kritik claim farkıyla geçmiştir?
- Hangi claim geçersiz/stale olursa outcome değişir?
- Hangi açık varsayım tersine dönerse Build, Modify, Kill veya Investigate More değişir?
- Hangi yeni kanıtın sonucu değiştirmesi mümkün değildir?

Kalibre edilmemiş ağırlıklarla Monte Carlo veya hassasiyet çalıştırılıp bilimsel kesinlik görüntüsü verilmez. Ağırlık duyarlılığı ancak gerçek outcome/feedback verisiyle kalibre edilen policy sürümlerinde ikincil analiz olarak kullanılır.

Karar motorunun ikincil olarak test edebileceği sorular:

- Problem doğrulaması biraz daha düşük kabul edilirse sonuç değişiyor mu?
- Farklılaşma ağırlığı artarsa sonuç değişiyor mu?
- Kullanıcının bütçesi veya zamanı düşerse MVP yaklaşımı değişiyor mu?
- Fiyat/ödeme sinyali belirsizse Build hâlâ mantıklı mı?
- Araştırma sınırlılıkları giderilirse eligible outcome değişiyor mu?

Çıktı:

- stable: makul varsayım değişikliklerinde sonuç aynı kalır
- sensitive: bir veya iki kritik belirsizlik sonucu değiştirebilir
- fragile: küçük veri/ağırlık değişimleri sonucu tersine çevirebilir

Decision stability, startup başarı olasılığı veya AI self-confidence değildir. Kararın mevcut varsayım, gate ve kritik claim'lere ne kadar dayandığını ifade eder.

## 6. Value of Information Engine

Investigate More sonucunda sistem yalnızca daha çok araştır dememelidir.

Value of Information Engine şu soruya cevap verir:

Hangi yeni bilgi, kararı en çok değiştirebilir?

Önceliklendirme girdileri:

- belirsizliğin karar sütunu üzerindeki etkisi
- outcome flip potansiyeli
- ek bilgiyi elde etme maliyeti
- süre
- mevcut araştırma sınırlılığı
- hedef kullanıcıyla doğrulanabilirlik

Örnek bilgi türleri:

- hedef kullanıcıyla ücretli pilot veya ön satış görüşmesi
- belirli segmentte ödeme isteği doğrulaması
- rakibin yeni sürümünde şikâyetin çözülüp çözülmediği
- dar hedef kullanıcı grubunda kullanım sıklığı
- regülasyon veya teknik uygulanabilirlik doğrulaması

## 7. AI'ın görevi

AI yalnızca şu işlerde kullanılır:

- yapılandırılmış Evidence Dossier'i okumak
- karar gerekçesini kaynaklı ve anlaşılır yazmak
- çelişen kanıtları açıklamak
- Modify için kaynaklı yön değişikliği önerileri üretmek
- Investigate More için yüksek değerli doğrulama aksiyonlarını ifade etmek
- karara ters düşen güçlü kanıtları görünür kılmak

AI şu işlerde kullanılmaz:

- kendi başına karar sütunu puanlamak
- hard gate'leri geçersiz kılmak
- kaynak veya claim uydurmak
- kaynakta olmayan pazar büyüklüğü/başarı tahmini vermek
- counter-evidence'ı tek bir metrikte yok saymak
- kullanıcı adına ürün fikri seçmek
- AI self-confidence yüzdesini startup başarı olasılığı olarak sunmak

## Deterministik sistemin görevi

- Evidence Sufficiency Gate
- Karar sütunu profillerini hesaplama
- Hard gate'leri uygulama
- Outcome eligibility kontrolü
- Sensitivity ve Stability Analysis
- Value of Information önceliklendirme
- Secondary research ile primary validation ayrımını uygulama
- Citation/claim doğrulama
- AI'ın desteklenmeyen iddiasını reddetme
- Politika, ağırlık, eşik ve sürüm kaydı

Başlangıçta tek bir şemalı AI Decision Synthesizer ve deterministik validator yeterlidir. Multi-agent karar sistemi kullanılmaz.

## Decision Dossier

Her karar için saklanacak veri:

- decision_id
- idea_brief_version
- research_plan_version
- evidence_set_version
- decision_policy_version
- user_constraints_snapshot
- evidence_sufficiency_result
- pillar_profiles
- eligible_outcomes
- selected_outcome
- supporting_claim_ids
- challenging_claim_ids
- critical_unknowns
- assumptions
- decision_stability
- value_of_information_actions
- model_version
- prompt_version
- created_at

Bu kayıt, kararın daha sonra aynı veri ve politika sürümüyle tekrar üretilebilmesini sağlar.

## Kullanıcıya gösterilecek karar yapısı

- Karar: Build, Modify, Kill veya Investigate More
- Karar kararlılığı: stable, sensitive veya fragile
- Nedenler: kaynaklı en güçlü dayanaklar
- Karşıt kanıt: sonucu sınırlayan veya tersine çeviren sinyaller
- Eksik/kritik bilinmeyenler
- Eğer Modify ise: korunacak sinyal, değiştirilecek varsayım ve önerilen odak
- Eğer Investigate More ise: en yüksek değerli sonraki doğrulama
- Kaç ikincil kaynağa ve kaç gerçek kullanıcı/ödeme davranışı gözlemine dayanıldığı; sıfırsa açıkça `0` olarak
- Dayanak kaynaklara ve alıntılara erişim

## Hata, güven ve izlenebilirlik

- Karar, kaynak veya claim ID olmadan gerekçelendirilemez.
- Kanıt yetersizse Build veya Kill önerilemez.
- AI self-confidence yüzdesi kullanılmaz.
- Karar stabilitesi ile başarı ihtimali birbirine karıştırılmaz.
- Karşıt kanıt karar özetinde görünür olmalıdır.
- Kullanıcının bütçesi/teknik seviyesi pazar fırsatını yok sayma sebebi değildir.
- Kaynağa erişilememesi negatif pazar kararı anlamına gelmez.
- Şikâyet yokluğu memnuniyet kanıtı değildir; Kill için pozitif karşıt kanıt zorunludur.
- `stated_wtp_weak_signal` Build'i pozitif ağırlıkla besleyemez; gerçek ödeme doğrulaması ayrı gösterilir.
- Karar politikası, ağırlıklar, eşikler, input sürümleri ve AI sürümleri kayıt altında tutulur.
- Kullanıcı kararın dayandığı kanıtları inceleyebilmelidir.
- Kullanıcı yeni bilgi/tercih girdisinde bulunduğunda yeni Decision Dossier sürümü oluşur.

## Bilinçli olarak kapsam dışı bırakılanlar

- Nihai PRD, MVP scope, teknik plan veya kodlama promptu üretmek
- Yeni dış kaynak araştırması başlatmak
- Kullanıcı adına yatırım, ödeme veya dış aksiyon almak
- Startup başarı yüzdesi veya kesin pazar büyüklüğü tahmini
- Tek sayıdan oluşan fikir skoru
- Kanıt yetersizken Kill veya Build sonucu
- LLM'in kontrolsüz biçimde tüm kararı vermesi
- Multi-agent karar mimarisi
- Kullanıcıyı fikrini değiştirmeye zorlamak

## Ölçümler

- Evidence Sufficiency Gate geçiş oranı
- Outcome dağılımı: Build, Modify, Kill, Investigate More
- Karar stabilitesi dağılımı
- Karar başına kaynak/claim/provenance tamlık oranı
- Counter-evidence görünürlük oranı
- Investigate More aksiyonlarının karar değişimine katkısı
- Kullanıcının karardan sonra fikri/segmenti değiştirme oranı
- Karar yeniden üretilebilirlik oranı
- Kullanıcının sonraki doğrulama aksiyonunu tamamlama oranı
- Model/prompt doğrulama hatası
- Sonraki gerçek kullanıcı geri bildirimiyle karar kalibrasyonu

## Faz 7 kabul kriterleri

- Her karar gerekçesi kaynaklı claim'lere ve provenance verisine bağlanmalıdır.
- Evidence Sufficiency Gate geçmeden Build veya Kill çıkmamalıdır.
- Pazar fırsatı ve kullanıcının uygulama koşulları ayrı değerlendirilmelidir.
- Her önemli karar karşıt kanıt ve kritik bilinmeyenleri göstermelidir.
- Modify sonucu somut değiştirilecek varsayım ve korunacak sinyal içermelidir.
- Kill sonucu mevcut teze sınırlı, kanıta dayalı ve yeterli araştırma şartına bağlı olmalıdır.
- Investigate More sonucu en değerli sonraki doğrulama aksiyonunu içermelidir.
- Decision stability öncelikle gate counterfactual ile üretilmelidir; ağırlık sensitivity yalnızca kalibre edilmiş policy'de ikincil analizdir.
- Gate counterfactual ile kararı tersine çevirecek kritik claim, gate ve varsayımlar gösterilmelidir; kalibre edilmemiş ağırlık analizi kesinlik gibi sunulmamalıdır.
- Investigate More alt türü deterministik seçilmeli; primary validation boşluğu yeniden web araştırmasına gönderilmemelidir.
- Yeni/emerging pazar kanıt kıtlığı nedeniyle otomatik Kill almamalıdır.
- AI çıktısı deterministik policy ve citation validator tarafından onaylanmadan kullanıcıya gösterilmemelidir.
- Faz 7, planlama/PRD/teknik mimari çıktısı üretmemelidir.

## Faz 7 çıkışı

Faz 8'e aktarılmaya hazır; kaynakları, karşıt kanıtı, belirsizlikleri, stabilitesi ve sonraki doğrulama aksiyonları görünür olan sürümlenmiş bir yön önerisi ve Decision Dossier.
