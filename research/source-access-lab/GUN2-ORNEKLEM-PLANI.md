# Gün 2 Örneklem Planı

Gün 1 envanteri 636 kanonik kaynağı kapsadı. Gün 2'de açılacak
aday havuzu: **açılabilir dosyası olan ama henüz incelenmemiş 370 kaynak.**

## Öncelik sırası ve gerekçesi

| Sıra | İçerik durumu | Aday | Neden bu sırada |
|---|---|---:|---|
| 1 | `api-yaniti` | 3 | Yapılandırılmış alan taşır; doğrulama maliyeti en düşük |
| 2 | `gercek-icerik` | 230 | Görünür metin var; belge türü ve alan çıkarımı mümkün |
| 3 | `besleme` | 7 | Tarih ve başlık kesin; gövde için bağlantıya gitmek gerekir |
| 4 | `arsiv` | 63 | İçerik var ama güncel değil; tazelik ayrıca işaretlenmeli |
| 5 | `js-kabugu` | 34 | Düz çekimle metin alınamıyor; örneklem yerine **kayıt** konusu |
| 7 | `aday-kesif` | 21 | Kanıt değil; yalnız hangi iç sayfaların çekileceğini gösterir |
| 8 | `politika` | 12 | Araştırma malzemesi değil |

## Örneklem kuralı

1. **Kaynak ailesi başına en az üç örnek**, aile tükenene kadar.
2. Aile üç örnek veremiyorsa **eksik kaydı yazılır**, doldurulmaz.
3. Her **yüzey türünden** en az bir örnek ayrıca açılır; aile örneklemi
   en bilgilendirici dosyayı seçtiği için az sayıda ama değerli yüzeyler
   (API yanıtları) dışarıda kalır.
4. `js-kabugu` ve `aday-kesif` kaynakları örnekleme **girmez**; onlar
   içerik üretmediği için ayrı bir iş kaleminin konusudur.

## Gün 2'de açılmayacaklar ve nedeni

| Grup | Kaynak | Neden |
|---|---:|---|
| Açılabilir dosyası yok | 171 | Elde dosya yok; incelenmiş gösterilemez |
| Zaten incelendi (DR-L02) | 95 | Artefakt hash'iyle kayıtlı |
| `js-kabugu` | 34 | Düz çekimle metin alınamıyor |

## Beklenen çıktı

Gün 2 sonunda her açılan kaynak için belge türü, çıkarılabilen alanlar ve
sınıflandırma gerekçesi; açılamayan her kaynak için eksik kaydı.

