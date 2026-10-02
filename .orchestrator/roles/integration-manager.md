# Birleştirme

3 Ekim 2026 kullanıcı kararı: `AGENTS.md` ve `ortak/gelistirme-plani.md` geçerlidir.

Ana AI backend/frontend ve fazları uygulama sırasında doğrudan bağlar; ayrı accepted review/verify/integration zinciri beklenmez. Git dallarını mevcut main üzerinde code_pusher normal merge ile birleştirir. İşlevsel entegrasyon finalde kontrol edilir.

Yeni branch/worktree, her iş için bağımsız onay ve run graph yoktur. Test yapılmadıysa yapılmış gibi yazılmaz; mevcut kullanıcı değişiklikleri ve ürün kuralları korunur.
