# Devir Notu — alan ve sözleşme

**Sürüm 1.0.0** · Hazırlayan: Ayselin Aydoğdu · Alıcı: Ayşe Sena

Bu not, beş günlük veri çalışmasının çıktılarını devralmak için gereken
bilgiyi tek yerde toplar. Alan alan sözleşme [`SOURCEFIT-SEMA.md`](SOURCEFIT-SEMA.md)
içinde; bu belge **nasıl kullanılacağını** ve **neye güvenilmeyeceğini** anlatır.

## Paket içeriği ve bağlantı anahtarları

Bütün çıktılar `source_id` ve artefakt/kayıt kimlikleriyle birbirine bağlanır.

| Dosya | Rol | Bağlantı anahtarı |
|---|---|---|
| [`KATEGORI-SOZLUGU.md`](KATEGORI-SOZLUGU.md) | Kategori sözlüğü — etiketlerin tanımı | — |
| [`PILOT-KAYITLAR.csv`](PILOT-KAYITLAR.csv) | Sözlüğün 97 açılmış örnek üzerindeki uygulaması | source_id |
| [`NORMALIZE-BELGELER.csv`](NORMALIZE-BELGELER.csv) | Kategorize veri seti — teknik normalizasyon | document_id, artifact_hash, source_id |
| [`SINIFLANDIRMA.csv`](SINIFLANDIRMA.csv) | Kategorize veri seti — yorumlayıcı sınıflandırma | document_id, source_id |
| [`BELGE-ILISKILERI.csv`](BELGE-ILISKILERI.csv) | Tekrar ilişkileri | document_id |
| [`KATEGORI-ALANLARI.csv`](KATEGORI-ALANLARI.csv) | Çıkarılan alanlar | document_id, source_id |
| [`SOURCE-FIT-MATRIX.csv`](SOURCE-FIT-MATRIX.csv) | Kaynak eşleme tablosu | source_id, document_id |
| [`KATEGORI-YETERLILIK.csv`](KATEGORI-YETERLILIK.csv) | Hücre bazında yeterlilik ve gap sebebi | — |
| [`PAKET-ONERILERI.csv`](PAKET-ONERILERI.csv) | Standard/Deep aday paketleri | source_id |
| [`KALITE-RAPORU.md`](KALITE-RAPORU.md) | Bu denetimin raporu | — |
| [`KALITE-METRIKLERI.csv`](KALITE-METRIKLERI.csv) | Kategori bazında sayılar | — |
| [`DENETIM-BULGULARI.csv`](DENETIM-BULGULARI.csv) | Açık bulgular ve gerekçeleri | document_id, source_id |
| [`DENETIM-ORNEKLERI.csv`](DENETIM-ORNEKLERI.csv) | İncelenen örnek kayıtlar | document_id, source_id |
| [`VERI-PAKETI-ORNEKLERI.csv`](VERI-PAKETI-ORNEKLERI.csv) | Hangi soru hangi kayıtla cevaplanıyor | document_id, artifact_hash |
| [`KALAN-IS.csv`](KALAN-IS.csv) | Önceliklendirilmiş kalan iş | — |
| [`SOURCEFIT-SEMA.md`](SOURCEFIT-SEMA.md) | Alan sözleşmesi | — |
| [`DEVIR-NOTU.md`](DEVIR-NOTU.md) | Ayşe Sena için devir notu | — |

### Bir kaydı uçtan uca izlemek

```text
SOURCE-FIT-MATRIX.csv  ornek_kayit = "doc-xxxx · https://..."
        ↓ document_id
NORMALIZE-BELGELER.csv artifact_hash, body_original_ref
        ↓ body_original_ref
results/raw/<sha256>.bin    ← diskteki ham dosya, hiç değiştirilmedi
```

`artifact_hash` dosyanın SHA-256'sıdır; yeniden hesaplanarak doğrulanabilir.

## Etiketleme tekrar uygulanabilir

Hiçbir etiket CSV'ye elle yazılmadı. Sıra:

```bash
python3 kategori_sozlugu.py      # sözlük + pilot
python3 veri_envanteri.py        # envanter
python3 normalize_belgeler.py --yaz
python3 source_fit_matrix.py --yaz
python3 denetim.py --yaz
python3 -m unittest discover -s . -p 'test_*.py'
```

Aynı girdi aynı çıktıyı verir: sıralamalar sabit, eşitlikler `source_id` ile
bozulur, örneklem deterministik seçilir.

## Neye güvenilmemeli

- **`engagement_indirme_sayisi` → talep var** olarak okunamaz. İndirme sayısı ilgi gösterir, ödeme davranışı göstermez. Ücretsiz bir uygulamanın 5M indirmesi bir ödeme kanıtı değildir.
- **`engagement_yorum_sayisi` → memnuniyetsizlik düzeyi** olarak okunamaz. Yorum SAYISI şikâyetin miktarını değil, ürünün kullanım hacmini gösterir. Şikâyet kanıtı yorum METNİNDEDİR ve bu veri kümesinde taranmadı.
- **`engagement_yildiz` → ürün kalitesi** olarak okunamaz. Yıldız ortalaması kaynağın kendi ölçüm yöntemine bağlıdır ve kaynaklar arasında karşılaştırılamaz.
- **`fiyat` → ödeme isteği** olarak okunamaz. Satıcının ilan ettiği fiyat, kullanıcının o fiyatı ödediğini göstermez. stated_wtp_weak_signal ayrı bir niyettir ve kanıtı yoktur.
- **`belge_sayisi` → pazar büyüklüğü** olarak okunamaz. Bir kategoride çok belge olması pazarın büyük olduğunu değil, o kaynakların bize açık olduğunu gösterir.
- **`icerik_yoklugu` → talep yokluğu** olarak okunamaz. Veri bulunamaması toplama yönteminin sınırıdır; pazarda sinyal olmadığı anlamına GELMEZ.

## Bilinen sınırlar

- **`stated_wtp_weak_signal` için hiç kanıt yok.** 16 kategorinin hepsinde açık
  gap. Sebebi ölçülmüş: o sinyal sayfanın adresinden değil metninden okunur.
- **Tarih çoğu belgede yok.** `published_at` boşsa `unknown_date` bayrağı var;
  `collected_at` yayın tarihi yerine kullanılamaz.
- **Erişim anlığı izin garantisi değil.** Matristeki her satır bunu yazar;
  kullanımdan önce robots yeniden kontrol edilmeli.
- **Kategoriler örtüşür.** Bir kaynak birden çok kategoriye bağlı olabilir;
  kategori sütunları toplanmaz.

## Devralan ne yapabilir

**Hemen kullanılabilir:** 329 ölçüm kanıtı üreten kayıt,
`SOURCE-FIT-MATRIX.csv`'nin 47 yeterli hücresi.

**Kısa sürede genişletilebilir:** [`KALAN-IS.csv`](KALAN-IS.csv)'nin ilk dört
satırı — toplam 797 kayıt, hepsi çözülebilir işaretli.

**Bu yöntemle çözülemez:** bot koruması, robots yasağı ve tamamen istemci
tarafında üretilen uygulama mağazası sayfaları.
