# Uygulama

3 Ekim 2026 kullanıcı kararı: `AGENTS.md` ve `ortak/gelistirme-plani.md` geçerlidir.

Ana AI main üzerinde bütün kapsamı uygular. Mevcut testler korunur, test/lint/typecheck/build kontrolü ve yeni regresyon testleri final aşamasına bırakılır. Git commit/push code_pusher sorumluluğundadır.

Yeni branch/worktree, her iş için bağımsız onay ve run graph yoktur. Test yapılmadıysa yapılmış gibi yazılmaz; mevcut kullanıcı değişiklikleri ve ürün kuralları korunur.
