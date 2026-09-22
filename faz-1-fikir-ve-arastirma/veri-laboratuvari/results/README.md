# Paylaşılan araştırma çıktıları

Ekip erişimi için 22 Eylül 2026'da Git kapsamına alındı. Önceden .gitignore nedeniyle yalnız yerel diskte bulunuyordu.

- raw/:134 alınmış kaynak yanıtı/artefakt (.bin).
- Kök dizin:7 tarihsel araştırma/arama/erişim koşusu JSON çıktısı.
- .bulk-progress-*/:3 mevcut koşu checkpoint kaydı.
- Toplam144 mevcut çıktı paylaşıldı; bugün siteler yeniden sorgulanmış sayılmaz.

Beş YouTube/Google Play HTML kaydındaki API anahtarı biçimli kaynak-site yapılandırmaları paylaşılan kopyadan temizlendi. Özgün beş dosya yalnız yerelde, Git dışında local-originals/ altında korunur. Diğer139 dosya değişmeden paylaşıldı. Hiçbir proje Gemini/SSH anahtarı bu dosyalara eklenmedi.

shared-redactions.json hangi dosyanın değiştiğini, özgün ve paylaşılan SHA256 değerlerini kaydeder. raw/ dosya adları özgün artefakt kimliğini korur; temizlenen beş dosyanın adı içerik hash'i olarak doğrulanmamalı, shared_sha256 kullanılmalıdır. Önceki alıntı/hash/offset kayıtları özgün baytlara aittir; temizlenmiş kopyayı özgün kanıtın birebir eşiti kabul etmeyin.

veriler-ornek/ altındaki548 dosya zaten Git kapsamındaydı. Güncel main çekildiğinde ekip bu çıktılara da erişebilir. API anahtarları ve sunucu runtime ortam dosyaları Git'e eklenmez. Backend build büyük ham artefaktları Docker imajına dahil etmez.
