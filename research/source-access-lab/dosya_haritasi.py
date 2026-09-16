"""Hangi dosya hangi goreve ait - README'deki haritayi uretir.

GitHub klasoru alfabetik listeler. Mentor `ADAY-KATALOG.csv` satirini
gorunce bunun hangi gorevin ciktisi oldugunu bilemez. Bu modul o eslemeyi
**veri olarak** tutar, README bolumunu ondan uretir ve bir test her izlenen
dosyanin sahiplenildigini dogrular - boylece yeni dosya eklendiginde harita
sessizce eskimez.

Kural: ``test_X.py`` dosyalari ``X.py``'yi korur, ayri satir almazlar.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent

# gorev anahtari -> (baslik, kilavuz bagi)
GOREVLER: dict[str, tuple[str, str]] = {
    "ORTAK": ("Ortak", "önce bunlar"),
    "A": ("Erişim laboratuvarı", "636 kaynağa erişim denemesi ve defteri"),
    "G1": ("Görev 1", "Ürün kategorilerini belirlemek"),
    "G2": ("Görev 2", "Soruları ve kanıtlarını tanımlamak"),
    "G3": ("Görev 3", "Defteri aday kataloğa dönüştürmek"),
    "G4": ("Görev 4", "Hangi alan, hangi izinli yol"),
    "G5": ("Görev 5", "Fikirden kaynak paketine"),
    "G6": ("Görev 6", "Sorguları derlenebilir şablonlara çevirmek"),
    "G7": ("Görev 7", "Aynı tasarımı iki bütçe seviyesinde"),
    "G8": ("Görev 8", "Tasarımı kontrollü bir deneyle sınamak"),
    "G9": ("Görev 9", "Kategori sözlüğü (veri çalışması Gün 2)"),
    "G10": ("Görev 10", "Veri envanteri (veri çalışması Gün 1)"),
    "G11": ("Görev 11", "Normalize veri kümesi (veri çalışması Gün 3)"),
}

# dosya -> (gorev, rol, bir cumlelik aciklama)
# rol: cikti | kod | girdi | belge
HARITA: dict[str, tuple[str, str, str]] = {
    # --- Ortak ---
    "README.md": ("ORTAK", "belge", "Bu dosya — klasörün haritası"),
    "KILAVUZ.md": ("ORTAK", "belge", "**Başlangıç noktası.** On bir görevin tamamını sırayla anlatır"),
    ".gitignore": ("ORTAK", "girdi", "İndirilen 721 MB ham artefaktı depo dışında tutar"),
    "source_manifest.json": ("ORTAK", "girdi", "636 kaynağın kanonik kimlik ve adres listesi"),
    "dosya_haritasi.py": ("ORTAK", "kod", "README'deki bu haritayı üretir"),

    # --- A. Erişim laboratuvarı ---
    "SITE-LISTESI.md": ("A", "girdi", "Başlangıç site listesi — her şeyin kaynağı"),
    "KAYNAK-DEFTERI.csv": ("A", "cikti", "636 kaynağın erişim defteri (çekildi / kısmi / erişim yok)"),
    "KAYNAK-DEFTERI.md": ("A", "belge", "Defterin okunabilir özeti"),
    "ARTEFAKT-DIZINI.csv": ("A", "cikti", "Hangi kaynak hangi dosyaya karşılık geliyor — izlenebilirliğin temeli"),
    "ARAMA-YUZEYLERI.csv": ("A", "cikti", "Her kaynağın izinli arama yüzeyleri"),
    "OPENSEARCH-SABLONLARI.csv": ("A", "cikti", "Sitelerin kendi ilan ettiği arama şablonları"),
    "manifest-arsiv-retry.json": ("A", "girdi", "Arşivden yeniden denenecek kaynaklar"),
    "manifest-arsiv-retry-kalan.json": ("A", "girdi", "Yeniden denemeden sonra kalanlar"),
    "bulk_site_access_lab.py": ("A", "kod", "Toplu erişim denemesi"),
    "probe_site_access.py": ("A", "kod", "Tek kaynak erişim yoklaması"),
    "probe_hackernews_access.py": ("A", "kod", "Hacker News özel erişim yolu"),
    "build_artifact_index.py": ("A", "kod", "Artefakt dizinini üretir"),
    "build_search_surfaces.py": ("A", "kod", "Arama yüzeylerini üretir"),
    "build_coverage_ledger.py": ("A", "kod", "Erişim defterini üretir"),
    "fetch_opensearch_templates.py": ("A", "kod", "OpenSearch şablonlarını toplar"),
    "common_crawl_pass.py": ("A", "kod", "Common Crawl arşiv geçişi"),
    "survey_common_crawl.py": ("A", "kod", "Arşivde ne var diye tarar"),
    "secondary_index_pass.py": ("A", "kod", "İkincil dizin geçişi"),
    "adaptive_domain_pass.py": ("A", "kod", "Alan adı çözümleme geçişi"),
    "resolve_missing_domains.py": ("A", "kod", "Bulunamayan adresleri çözer"),
    "merge_resolved_domains.py": ("A", "kod", "Çözülen adresleri deftere işler"),
    "keyword_search_pass.py": ("A", "kod", "Anahtar kelime arama geçişi"),
    "summarize_site_access.py": ("A", "kod", "Erişim sonuçlarını özetler"),
    "export_by_source.py": ("A", "kod", "Kaynak bazında dışa aktarım"),

    # --- Görev 1 ---
    "URUN-KATEGORILERI.csv": ("G1", "cikti", "15 ürün kategorisi ve katmanlanma kuralları"),
    "URUN-KATEGORILERI.md": ("G1", "belge", "Kategorilerin neden böyle ayrıldığı"),
    "KATEGORI-KAYNAK.csv": ("G1", "cikti", "658 satır: hangi kategori hangi kaynak ailesine bağlı"),
    "build_product_categories.py": ("G1", "kod", "İki CSV'yi envanterden üretir"),

    # --- Görev 2 ---
    "KATEGORI-SORU.csv": ("G2", "cikti", "198 satır: her kategori için araştırma sorusu ve gereken kanıt"),
    "build_category_questions.py": ("G2", "kod", "Soru–kanıt eşlemesini üretir"),

    # --- Görev 3 ---
    "ADAY-KATALOG.csv": ("G3", "cikti", "636 kaynağın aday kataloğu — erişim defterinden türer"),
    "build_candidate_catalog.py": ("G3", "kod", "Defteri kataloğa çevirir"),

    # --- Görev 4 ---
    "KAYNAK-ALAN.csv": ("G4", "cikti", "3218 satır: hangi kaynaktan hangi alan, hangi izinli yolla alınır"),
    "build_source_fields.py": ("G4", "kod", "Alan–izin matrisini üretir"),

    # --- Görev 5 ---
    "SECIM-ORNEKLERI.csv": ("G5", "cikti", "73 satır: örnek ürün fikirlerinden seçilen kaynak paketleri"),
    "select_sources.py": ("G5", "kod", "Fikirden kaynak paketi seçer (deterministik)"),
    "terim_sozlugu.py": ("G5", "kod", "Türkçe terimleri hedef pazarın diline çevirir"),
    "TERIM-ONBELLEGI.json": ("G5", "girdi", "Çeviri önbelleği — depoya işlenir, aynı sonuç tekrarlanır"),

    # --- Görev 6 ---
    "DERLENMIS-SORGULAR.csv": ("G6", "cikti", "73 derlenmiş sorgu (TR pazarı)"),
    "DERLENMIS-SORGULAR-US.csv": ("G6", "cikti", "Aynı tasarımın US pazarı karşılığı"),
    "compile_queries.py": ("G6", "kod", "Şablonları çalıştırılabilir sorgulara derler"),
    "query_templates.py": ("G6", "kod", "Sorgu şablonlarının tanımı"),

    # --- Görev 7 ---
    "BUTCE-KARSILASTIRMA.csv": ("G7", "cikti", "Ücretsiz ve premium profillerin farkı — 6 satır"),
    "butce_profilleri.py": ("G7", "kod", "İki bütçe profilini tanımlar ve karşılaştırır"),

    # --- Görev 8 ---
    "DENEY-KAYNAK.csv": ("G8", "cikti", "Deneyde seçilen 64 kaynak"),
    "DENEY-VERI.csv": ("G8", "cikti", "Deneyde gerçekten çekilen 14 veri satırı"),
    "deney.py": ("G8", "kod", "Ön kayıtlı ölçütlerle kontrollü deney"),

    # --- Görev 9 (veri çalışması Gün 2) ---
    "KATEGORI-SOZLUGU.md": ("G9", "belge", "Dört eksenli kategori sözlüğü — etiketlerin tanımı"),
    "INCELEME-GUNLUGU.md": ("G9", "belge", "Hangi dosya açıldı, ne görüldü"),
    "PILOT-KAYITLAR.csv": ("G9", "cikti", "97 açılmış artefaktın etiketleri"),
    "PILOT-EKSIKLER.csv": ("G9", "cikti", "Sözlüğün karar veremediği 3 kayıt"),
    "kategori_sozlugu.py": ("G9", "kod", "Sözlüğü ve pilot çıktıları üretir"),

    # --- Görev 10 (veri çalışması Gün 1) ---
    "VERI-ENVANTERI.csv": ("G10", "cikti", "636 kaynak: erişim durumu **ve** içerik durumu ayrı sütunlarda"),
    "KAPSAMA-RAPORU.md": ("G10", "belge", "Erişim × içerik çapraz tablosu"),
    "ENVANTER-ISLENEMEYEN.csv": ("G10", "cikti", "754 işlenemeyen artefakt kaydı ve sebebi"),
    "GUN2-ORNEKLEM-PLANI.md": ("G10", "belge", "Gün 2'de ne açılacak, ne neden açılmayacak"),
    "veri_envanteri.py": ("G10", "kod", "Envanteri ve raporları üretir"),

    # --- Görev 11 (veri çalışması Gün 3) ---
    "NORMALIZE-BELGELER.csv": ("G11", "cikti", "591 belge — teknik normalizasyon (Faz 4 şeması)"),
    "SINIFLANDIRMA.csv": ("G11", "cikti", "591 satır — yorumlayıcı sınıflandırma, teknikten **ayrı** tutulur"),
    "BELGE-ILISKILERI.csv": ("G11", "cikti", "98 tekrar ilişkisi — tekrarlar silinmez, ilişkilendirilir"),
    "KATEGORI-ALANLARI.csv": ("G11", "cikti", "139 çıkarılan alan; `olcum` / `etiket` ayrımıyla"),
    "ISLENEMEYEN-BELGELER.csv": ("G11", "cikti", "754 işlenemeyen kayıt ve sebebi"),
    "VERI-SOZLUGU.md": ("G11", "belge", "Her sütunun anlamı + bu verinin **cevaplayamadığı** sorular"),
    "DONUSUM-KURALLARI.md": ("G11", "belge", "Dönüşümün on adımı, ölçülmüş sayılarıyla"),
    "normalize_belgeler.py": ("G11", "kod", "Ham artefaktları normalize veri kümesine çevirir"),
}

ROL_SIRASI = {"belge": 0, "cikti": 1, "kod": 2, "girdi": 3}
ROL_ADI = {"belge": "belge", "cikti": "çıktı", "kod": "kod", "girdi": "girdi"}


def izlenen_dosyalar() -> list[str]:
    """Bu klasorde git'in izledigi kok seviye dosyalar."""
    cikti = subprocess.run(
        ["git", "ls-files", "."], cwd=HERE, capture_output=True, text=True, check=True)
    return sorted(a for a in cikti.stdout.split("\n") if a and "/" not in a)


def sahipsiz_dosyalar() -> list[str]:
    """Haritada yeri olmayan izlenen dosyalar. Testin koruduğu sey budur."""
    return [a for a in izlenen_dosyalar()
            if a not in HARITA and not a.startswith("test_")]


def yetim_test_dosyalari() -> list[str]:
    """Korudugu modul haritada olmayan test dosyalari."""
    izlenen = set(izlenen_dosyalar())
    return [a for a in izlenen
            if a.startswith("test_") and a[len("test_"):] not in HARITA]


def alfabetik_tablo() -> str:
    """GitHub'in gosterdigi sirayla: dosyadan goreve."""
    satirlar = ["| Dosya | Görev | Ne olduğu |", "|---|---|---|"]
    for ad in izlenen_dosyalar():
        if ad.startswith("test_"):
            continue
        gorev, _rol, aciklama = HARITA[ad]
        basligi = GOREVLER[gorev][0]
        satirlar.append(f"| [`{ad}`]({ad}) | {basligi} | {aciklama} |")
    return "\n".join(satirlar)


def gorev_tablosu() -> str:
    """Gorevden dosyaya: her gorev tek blokta."""
    parcalar: list[str] = []
    for anahtar, (baslik, alt) in GOREVLER.items():
        ait = [(a, HARITA[a]) for a in izlenen_dosyalar()
               if not a.startswith("test_") and HARITA[a][0] == anahtar]
        if not ait:
            continue
        ait.sort(key=lambda t: (ROL_SIRASI[t[1][1]], t[0]))
        parcalar.append(f"### {baslik} — {alt}\n")
        parcalar.append("| Dosya | Rol | Ne olduğu |")
        parcalar.append("|---|---|---|")
        for ad, (_g, rol, aciklama) in ait:
            parcalar.append(f"| [`{ad}`]({ad}) | {ROL_ADI[rol]} | {aciklama} |")
        parcalar.append("")
    return "\n".join(parcalar)





BASLANGIC = "<!-- HARITA:BASLANGIC -->"
BITIS = "<!-- HARITA:BITIS -->"


def readme_bolumu() -> str:
    return f"""{BASLANGIC}
## Hangi dosya hangi görev

Klasörde {len(izlenen_dosyalar())} dosya var ve GitHub bunları alfabetik sıralıyor.
Aşağıdaki tablo her dosyanın hangi görevin parçası olduğunu söyler.

**Kural:** `test_X.py` dosyası `X.py`'yi korur, ayrı satırı yoktur.

{gorev_tablosu()}
<details>
<summary><b>Alfabetik dizin</b> — GitHub'ın gösterdiği sırayla, dosyadan göreve</summary>

{alfabetik_tablo()}

</details>
{BITIS}"""


def readme_guncelle() -> bool:
    yol = HERE / "README.md"
    metin = yol.read_text(encoding="utf-8")
    bas, bit = metin.find(BASLANGIC), metin.find(BITIS)
    if bas == -1 or bit == -1:
        raise SystemExit("README'de HARITA isaretleri yok")
    yeni = metin[:bas] + readme_bolumu() + metin[bit + len(BITIS):]
    if yeni == metin:
        return False
    yol.write_text(yeni, encoding="utf-8")
    return True


if __name__ == "__main__":
    for ad in sahipsiz_dosyalar():
        print(f"UYARI sahipsiz dosya: {ad}")
    print("README güncellendi" if readme_guncelle() else "README zaten güncel")
