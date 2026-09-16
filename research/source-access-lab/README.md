# Kaynak Erişim Laboratuvarı

**Sahip:** Ayselin Aydoğdu · **Görev:** [`tasks/ayselin-task/`](../../tasks/ayselin-task/)

Bu klasör iki ayrı çalışmayı barındırıyor. İkisi de aynı 636 kaynaklı envanteri
kullanıyor ama farklı soruları cevaplıyorlar.

| | Soru | Anlatı |
|---|---|---|
| **A. Erişim laboratuvarı** | Bu kaynaklara ulaşabiliyor muyuz, ne indi? | Bu dosyanın alt bölümleri |
| **B. Araştırma tasarımı** | Bir ürün fikri geldiğinde hangi kaynağa ne sorulur? | [`KILAVUZ.md`](KILAVUZ.md) |

**Başlangıç noktası [`KILAVUZ.md`](KILAVUZ.md)** — dokuz görevi sırayla anlatır,
her bölümde problem, izlenen yol, sonuç ve gerçek CSV satır örnekleri vardır.

> **Uyarı:** Aşağıdaki "Faz A" bölümlerinde geçen *Görev 1/2/3* ile kılavuzdaki
> *Görev 1–9* **aynı şeyler değildir.** İlki erişim çalışmasının adımları,
> ikincisi araştırma tasarımının görevleridir.

---

## B. Araştırma tasarımı — dokuz görev ve çıktıları

| # | Görev | Çıktı |
|---|---|---|
| 1 | Ürün kategorileri | [`URUN-KATEGORILERI.csv`](URUN-KATEGORILERI.csv) (15) · [`KATEGORI-KAYNAK.csv`](KATEGORI-KAYNAK.csv) (658) |
| 2 | Sorular ve kanıt gereksinimleri | [`KATEGORI-SORU.csv`](KATEGORI-SORU.csv) (198) |
| 3 | Aday katalog | [`ADAY-KATALOG.csv`](ADAY-KATALOG.csv) (636) |
| 4 | Kaynak yeteneği ve veri alanları | [`KAYNAK-ALAN.csv`](KAYNAK-ALAN.csv) (3218) |
| 5 | Fikirden kaynak paketine | [`SECIM-ORNEKLERI.csv`](SECIM-ORNEKLERI.csv) (73) |
| 6 | Sorgu şablonları | [`DERLENMIS-SORGULAR.csv`](DERLENMIS-SORGULAR.csv) (73) · [`-US`](DERLENMIS-SORGULAR-US.csv) · [`OPENSEARCH-SABLONLARI.csv`](OPENSEARCH-SABLONLARI.csv) |
| 7 | İki bütçe seviyesi | [`BUTCE-KARSILASTIRMA.csv`](BUTCE-KARSILASTIRMA.csv) (6) |
| 8 | Kontrollü pilot deney | [`DENEY-KAYNAK.csv`](DENEY-KAYNAK.csv) (64) · [`DENEY-VERI.csv`](DENEY-VERI.csv) (14) |
| 9 | Kategori sözlüğü | [`KATEGORI-SOZLUGU.md`](KATEGORI-SOZLUGU.md) · [`INCELEME-GUNLUGU.md`](INCELEME-GUNLUGU.md) · [`PILOT-KAYITLAR.csv`](PILOT-KAYITLAR.csv) (97) · [`PILOT-EKSIKLER.csv`](PILOT-EKSIKLER.csv) (3) |

Her çıktı bir script tarafından üretilir; elle yazılmış sayı yoktur. Üretici
dosyalar `build_*.py`, `select_sources.py`, `compile_queries.py`,
`butce_profilleri.py`, `deney.py` ve `kategori_sozlugu.py`.

### Zincir

```text
ürün fikri → kategori → araştırma sorusu → gerekli kanıt → kaynak ailesi
          → kaynak yeteneği → veri alanı → sorgu şablonu → bütçe/fallback
```

---

## A. Erişim laboratuvarı — 636 kaynağa erişim

`çekildi` etiketi, en az bir içerik yüzeyinin başarıyla alındığını gösteren bir
**erişim snapshot**'ıdır; tek başına araştırma sorusuna uygun, güncel veya
alıntılanabilir karar kanıtı anlamına gelmez.

| | Kaynak |
|---|---:|
| Verisi çekildi | **534** |
| Kısmi | 44 |
| Adresi var, veri alınamadı | 54 |
| Adresi bulunamadı | 4 |
| **Toplam** | **636** |

Defter: [`KAYNAK-DEFTERI.csv`](KAYNAK-DEFTERI.csv) ·
Artefakt dizini: [`ARTEFAKT-DIZINI.csv`](ARTEFAKT-DIZINI.csv) ·
Arama yüzeyleri: [`ARAMA-YUZEYLERI.csv`](ARAMA-YUZEYLERI.csv)

Raporlar [`docs/reports/`](docs/reports/), pilot çalışmalar
[`docs/pilots/`](docs/pilots/) altında.

### İndirilen içerik

`results/raw/` altında 2323 artefakt (721 MB) var ve `.gitignore` ile depo
dışında tutulur. Her artefakt sha256 ile adlandırılmıştır;
`ARTEFAKT-DIZINI.csv` hangi kaynağın hangi dosyaya karşılık geldiğini gösterir,
böylece her sayı izlenebilir kalır. Ayrıntı: [`results/README.md`](results/README.md).

---

## Testler

```bash
cd research/source-access-lab
python3 -m unittest discover -s . -p 'test_*.py'
```

404 test. Testler yalnız kodu değil, **kuralları** korur: robots yasaklı kaynağın
hiçbir profilde seçilmemesi, aday keşfin ölçüm kanıtı sayılmaması, zayıf bir
işaretin içerik etiketi üretmemesi ve üretilen sorguda doldurulmamış yer tutucu
kalmaması gibi.

## Politika

Bu çalışma boyunca değişmeyen kurallar:

- **Bot koruması aşılmaz.** Tarayıcı taklidi, User-Agent rotasyonu ve CAPTCHA
  çözme yoktur. Site bizi bot olarak tanıyıp reddediyorsa bu bir karardır.
- **robots.txt bağlayıcıdır.** Her origin için ön kontrol yapılır; RFC 9309
  uyarınca 404/410 kısıt yok, 401/403 tam yasak sayılır.
- **Arşiv canlı veriyle karıştırılmaz.** Common Crawl'dan gelen içerik
  `common_crawl_warc` olarak işaretlenir.
- **Erişim, kanıt demek değildir.** Sitemap ve arama sonucu aday keşiftir;
  içerik bulunmayan yerde yorum ya da fiyat verisi varsayılmaz.
