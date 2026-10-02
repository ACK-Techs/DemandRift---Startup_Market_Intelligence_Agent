# Final güvenlik ve veri kontrolü

3 Ekim 2026 kullanıcı kararı: `AGENTS.md` ve `ortak/gelistirme-plani.md` geçerlidir.

Runtime tenant/kaynak/bütçe/alıntı kuralları geliştirmede uygulanır; ayrı uzman onayı veya test kapısı kurulmaz. Tüm işlevler bittikten sonra bu davranışlar final kontrol paketinde sınanır.

Yeni branch/worktree, her iş için bağımsız onay ve run graph yoktur. Test yapılmadıysa yapılmış gibi yazılmaz; mevcut kullanıcı değişiklikleri ve ürün kuralları korunur.
