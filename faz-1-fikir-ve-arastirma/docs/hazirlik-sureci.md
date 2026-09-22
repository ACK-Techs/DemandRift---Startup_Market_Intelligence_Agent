# Hazırlık süreci

## Amaç ve sınır

Fikrin ne olduğu, kime hizmet ettiği, hangi problemi çözdüğü ve nasıl araştırılacağı belirlenir. Çıktı, Faz 2'nin çalıştırabileceği doğrulanmış araştırma planıdır. Bu aşamada pazar sonucu, uydurma rakip veya nihai karar üretilmez. Mevcut veriler üzerinde kaynak yeterliliği incelemesi ise bu fazın hazırlık işidir.

## Hazırlanacak tasarım girdileri

1. **Kategori taksonomisi:** Tanım, dahil/hariç örnekleri, ana kategori/ek kategori ayrımı ve eşleşmeme davranışı.
2. **Kanıt gereksinimi matrisi:** Kategori → araştırma sorusu → gerekli alanlar → kabul edilen kanıt → yanıltıcı göstergeler → öncelik.
3. **Kaynak profilleri:** Gerçek alınabilir alanlar, sorgu yüzeyi, tarih/dil/coğrafya, erişim yöntemi, kısıtlar, kota, maliyet, saklama koşulları ve bağımsızlık grubu.
4. **Kaynak uygunluk matrisi:** Kategori × araştırma amacı × kaynak; benzersiz katkı, kullanılacak alanlar, yedek kaynak ve bilinen eksikler.
5. **Sorgu kuralları:** Ürün, müşteri, problem, şikâyet, alternatif, rakip, teknik terim, dil/pazar ve negatif terim bileşenleri. Kaynak desteklemiyorsa parametre veya arama URL'si uydurulmaz.
6. **Araştırma derinliği profilleri:** Kaynak, sorgu, kayıt/sayfa, süre, token ve maliyet sınırları; erken durdurma ve yedek kaynak kuralları. Sayısal varsayılanlar pilotlarla belirlenecek.

## İlk kategori seti

| Kimlik | Tanım ve sınır |
|---|---|
| `mobil-uygulama` | Telefonda kullanılan ürün; mobil oyunlarda oyun ana, mobil ek kategoridir. |
| `b2b-web-yazilimi` | İşletmeye iş akışı sağlayan web/SaaS ürünü. Berber müşterisi olması tek başına yerel hizmet kategorisi değildir. |
| `gelistirici-araci` | CLI, API, kütüphane ve geliştirici iş akışı araçları. |
| `eklenti-entegrasyon` | Shopify gibi bir ana platformu genişleten ürün. |
| `yapay-zeka-urunu` | AI yeteneğinin ürünün esas satın alınan hizmeti olduğu ürün. Her AI özelliği bu etiketi zorunlu kılmaz. |
| `oyun` | Temel kullanım amacı oyun olan ürün; dağıtım platformu ayrıca tutulur. |
| `yerel-hizmet` | Coğrafi hizmet bulma, eşleştirme veya rezervasyon platformu. |

Sağlık, eğitim, finans, Türkiye pazarı, self-host ve iki taraflı pazar gibi bağlamlar `modifiers` veya brief alanlarında taşınır; gerektiğinde ek kanıt paketi açar. Listeye uymayan fikir zorla eşleştirilmez: `unmatched` durumu ve gerekçesi üretilir. Yeni kategoriler kaynak/kanıt ihtiyacını gerçekten değiştiriyorsa sürümlü olarak eklenir.

## Fikrin netleştirilmesi

Orijinal metin aynen korunur. Ürün, hedef müşteri, problem ve pazar bilgisi `user_stated`, `user_confirmed`, `ai_inferred` veya `ai_hypothesis` kökeniyle saklanır. Eksik bilgiler kesinleştirilmez. Araştırmayı anlamlı biçimde etkileyen boşluklarda 1–3 kısa soru sorulur; eski tasarımdaki en fazla iki tur sınırı başlangıç önerisidir. Kullanıcı soruları atlayıp bilinmeyenleri koruyarak devam edebilir. Kullanıcı seçmedikçe AI'ın önerdiği yeni niş araştırmanın kesin kapsamı olmaz.

## Mevcut verilerle kaynak hazırlığı

[Laboratuvar](../veri-laboratuvari) yolu bu belgenin konumuna göre `../veri-laboratuvari/`dir. Önce defter ve artefakt indeksi, sonra ilgili `_kaynak.json` ve örnek içerik birlikte incelenir. Alan gerçekten var mı, tarih güncel mi, kaynak ilgili mi, bot/boş sayfa mı, yalnız URL keşfi mi soruları cevaplanır. Sitemap, snippet ve kök sayfa araştırma sorusunu destekleyen içerik olmadığı sürece karar kanıtı sayılmaz.

Kaynak ailesi başına önce küçük etiketli örnek kümesi hazırlanır. Beklenen alanlar, doğru/yanlış çıkarım, tekrar, dil, tarih, ilgililik ve başarısız erişim örnekleri etiketlenir. Bu teslimler yeni ürün testlerinin girdisidir; mevcut laboratuvar testlerinin yerini almaz.

## Tarihsel belgelerden alınacaklar

[Ayselin kılavuzu](../../ortak/arastirmalar/ayselin/KILAVUZ.md) ve [görev tanımı](../../ortak/arastirmalar/ayselin/GOREV-TANIMI.md) kategori, soru, kanıt, kaynak ve sorgu tasarımının referansıdır. Kılavuzda adı geçen her CSV/script bu checkout'ta teslim edilmiş kabul edilmez; mevcut dosyalarla doğrulanıp eksikler görev listesine yazılır. Eski deterministik kategori seçimi ve çevrimiçi sözlük çevirisi, yeni LLM + doğrulama kararının yerine geçmez.
