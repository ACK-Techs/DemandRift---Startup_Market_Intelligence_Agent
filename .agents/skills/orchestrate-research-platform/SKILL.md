---
name: orchestrate-research-platform
description: DemandRift üç faz geliştirmesini main üzerinde kısa planla tamamla; code pusher Git işlemlerini yürütür, test ve kontrol yalnız proje sonunda yapılır.
---

# DemandRift geliştirme

3 Ekim 2026 kullanıcı kararı eski çok rollü run graph sürecini kaldırdı. `AGENTS.md`, `ortak/gelistirme-plani.md` ve işin ilgili gerçek kodunu oku. Ürün anlamları için ilgili ortak sözleşme/faz belgesini kullan; eski Faz1–7/Platform belgeleri zorunlu okuma değildir.

## Uygulama

1. Mevcut `main` checkout'unda çalış. Branch, worktree, PR veya ayrı checkout açma.
2. Plandaki kalan işlevleri bağımlılık sırasıyla uygula; yalnız kısa ilerleme listesini güncelle.
3. Ara test, lint/typecheck/build kontrolü, review/verify/integration ve acceptance kapısı oluşturma. Her küçük değişiklik için test yazma. Mevcut test/fixture'ları koru; gerekli ek testleri finalde hazırla.
4. `.orchestrator` CLI, run/result/event/schema/hash checkpoint akışı aktif geliştirmede kullanılmaz. Eski sonuçlar tarihçedir; başarısız düğümleri kapatmak için yeni revision zinciri açma.
5. Git işleri için aynı checkout'ta `code_pusher` subagent kullan. Ana AI dosya listesini ve değişikliğin amacını verir; pusher yetki dahilinde anlamlı commit ve normal `main` push yapar. Test sonucu ara commit/push ön koşulu değildir.
6. Üç fazın tüm işlevleri bitince final test ve kontrol turunu çalıştır; hataları düzelt, etkilenen testleri ve en sonda tam paketi tekrar çalıştır.

## Ürün sınırları

Kullanıcı/proje izolasyonu, kaynak erişim izinleri, ortak bütçe, onaylı hipotez, doğrulanabilir alıntı ve kanıt yeterliliği runtime özellikleridir; süreç sadeleşmesi bunları kaldırmaz. Model kaynakları kendi araçlarıyla taramaz; yalnız backend'in sağladığı veriyi kullanır. Veri yokluğu Kill gerekçesi değildir. Araştırılan fikre Build/MVP/PRD veya sonraki ürün planı önerilmez.

## Teslim

Plan ilerlemesi, commit/push sonucu, finalde çalıştırılan testlerin kısa özeti ve gerçek engeller yeterlidir. Ara işler için ayrı JSON kanıtı/bağımsız onay üretme. Secret veya ham özel veri paylaşma. Kullanıcı değişikliklerini kaybetme; force push/reset --hard/git clean kullanma.
