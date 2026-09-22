# Git eşitleme — 22 Eylül 2026

- Kullanıcı iki projedeki yerel dosyaların anlamlı commitler halinde push edilmesini istedi.
- `origin/batuhan/frontend-ui` (`7980bef`) zaten uzak `main`in atasıydı. Frontend için ikinci bir merge veya kod üzerine yazma yapılmadı.
- Mevcut yerel `e869848` planlama commit’i değiştirilmedi. Uzak main’deki ekip veri çalışmaları ve Docker workflow’u normal merge ile bu commit’le birleştirildi; force push/rebase yok.
-80 dosyanın eski `research/source-access-lab` ile yeni `faz-1-fikir-ve-arastirma/veri-laboratuvari` arasındaki yer çakışması yeni faz klasörü lehine çözüldü.789 kod/veri dosyası uzak main ile byte düzeyinde aynı; tarihsel raporlar trash içinde korundu.
- Bağımsız kontrol:frontend atalık kontrolü geçti;çözülmemiş index kaydı0;70 offline sorgu/kaynak/bütçe testi geçti. CSV satır sonları özgün veri olarak değiştirilmedi.
- Build workflow ve sunucu script’i yeni laboratuvar yolunu zaten destekliyor. Frontend Vercel root’u apps/web olarak kalır.
- API anahtarları ve yerel cache/bağımlılıklar Git kapsamı dışında tutulur; Gemini anahtarı yalnız sunucudaki root-only runtime dosyasındadır.
