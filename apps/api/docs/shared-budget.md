# Ortak dış istek bütçesi

BE-05 iç kaynak sözleşmesi `app/budget_contract.py` içindedir. Mevcut 1.0.0
`BudgetLimits` ve `Usage` wire sözleşmeleri korunur; bu teslim yeni HTTP
uç noktası, PostgreSQL ledger veya dış çağrı açmaz. Kalıcı reservation,
Gemini adaptörü ve gerçek anahtar/model kabulü ayrı zorunlu teslimlerdir.

Her model veya kaynak denemesi en az bir `request` rezervasyonu ister.
Request, byte, sayfa, edinilen kayıt, model token ve maliyet boyutları aynı
kapasite hesabında birlikte kontrol edilir. Kaynak kayıt sayısı edinilen ham
öğeleri kapsar; modelin ürettiği iddia sayısı edinilen kaynak kaydı değildir.
Harcanan + tutulmuş + yeni rezervasyon herhangi bir tavanı aşarsa veya aktif
rezervasyon eşzamanlılık sınırına ulaşmışsa yeni deneme kabul edilmez.
Bozuk toplamlar sessizce küçültülmez; negatif, bool, float, taşan veya eksik
sayaç girdileri reddedilir.

Maliyet içerde 12 ondalık USD hassasiyetinde pozitif `BIGINT` birimiyle
hesaplanır (`cost_picousd`, 1 USD = 10^12 birim). `Decimal` dışındaki veya
bilinmeyen/nonfinite maliyet girdisi sıfıra çevrilmez. Daha küçük kesirler
yukarı yuvarlanır; çağıranın Decimal precision/rounding/trap ayarları hesabı
değiştiremez. Örneğin dört ayrı $0.00000025 token maliyeti toplandığında
$0.000001 eder. Wire'ın altı ondalıklı tutarı, toplamdan sonra yukarı
yuvarlanır; token başına altı ondalığa yuvarlanıp fazladan ücret yazılmaz.
Soft maliyet tavanı hard tavanı aşamaz. Wire limitleri yeniden doğrulanır ve
immutable iç değerlere kopyalanır; sonraki DTO değişikliği bütçeyi büyütemez.

Kalıcı ledger tesliminin değişmez kuralları: ortak suite ve owner/research
hesapları tek PostgreSQL transaction içinde sabit kilit sırasıyla tutulur;
retry ve secondary gap aynı orijinal bütçeyi tüketir. Faz 1 plan üretimi de
server tarafından yaratılmış research hesabına bağlıdır. Onaylanan planın
scope/fingerprint/version ilişkisi araştırma başladığında ayrıca bağlanır;
bu işlem geçmiş harcamayı sıfırlamaz. Global suite toplamı tenant RLS ile
filtrelenmiş kayıtların SUM sonucundan hesaplanmaz.

Dış gönderimden önce `dispatched` durumu kalıcılaştırılır. Sonucu bilinmeyen
gönderim yeniden harcama veya süreye bağlı otomatik iade oluşturamaz; tutar
ve eşzamanlılık uzlaştırmaya kadar tutulur. Bilinen gerçekleşen kullanım
rezervasyondan fazla çıkarsa gerçek harcama kaybolmadan hesap kapanır ve
incident kaydı gerekir. Henüz gönderilmeyen rezervasyon iptal edilebilir.
Bu davranışlar ledger'ın gerçek PostgreSQL kabul testleriyle kanıtlanacaktır.

Canlı kabul suite'i için kullanıcının ortak sınırı: $5, 300 dış istek,
50.000.000 byte, 150 sayfa, 1000 kayıt, 300.000 token, 1800 saniye ve
eşzamanlılık 2. Süre ilk gerçek gönderimde bir kez başlar; geliştirme
fixture'ları ayrı sentetik suite'ler kullanır. Backend/worker runtime secret
repo dışında kalır. Bu sözleşmenin offline kabulü, canlı model erişimi veya
87 senaryonun final kabulü anlamına gelmez.
