# Koşu Artefact'ları

Bu dizin, kaynak erişim laboratuvarının koşu sonuçlarını ve içerik-adresli ham
artefact'larını taşır.

- `*.json` — koşu sonucu, yöntem sonucu, hata sınıfı ve provenance kayıtları.
- `raw/<sha256>.bin` — içerik hash'iyle adreslenmiş ham response gövdeleri.
- `ARTEFAKT-DIZINI.csv` (üst dizinde) — her artefact'ın kaynak, URL, yöntem,
  koşu, zaman, sonuç ve hash bağını kuran kanonik indekstir.

Bu dosyalar kanıttır; silinmez veya elle yeniden adlandırılmaz. Bir kayıt
`source_unavailable`, `blocked_by_policy` veya `no_results` ise bunlar ayrı
durumlardır ve başarıya dönüştürülmemelidir.
