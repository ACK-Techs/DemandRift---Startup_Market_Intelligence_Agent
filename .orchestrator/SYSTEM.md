# DemandRift çalışma sistemi — 3 Ekim 2026

Kullanıcı geliştirme sırasında çok rollü kontrol, test ve kabul akışını kaldırdı. Aktif kaynak `AGENTS.md` ve `ortak/gelistirme-plani.md` dosyalarıdır.

Ana AI bütün üç fazı main üzerinde uygular. Code pusher subagent aynı checkout'ta yalnız Git commit/push yapar. Yeni branch/worktree yoktur. Geliştirme sırasında review, verify, integration, PM acceptance, run graph veya result/event/checkpoint JSON'u oluşturulmaz. Eski run/failed/revision kayıtları tarihçedir; yeniden kabul edilmeleri gerekmez.

Test, kod kontrolü, model değerlendirmesi, browser/E2E ve işletim kontrolleri ürünün tüm işlevleri tamamlandıktan sonra tek final aşamasında yapılır. Bulunan hatalar düzeltilir; etkilenen testler ve son tam paket yeniden çalıştırılır. CI geliştirme push'larında otomatik çalışmaz; finalde manuel başlatılır.

`.orchestrator/bin`, `src`, eski şemalar ve arşivler silinmedi; güncel geliştirme için kullanılması zorunlu değildir. `config.json` içindeki eski zorunlu gate listeleri boşaltıldı ve worktree tercihi kapatıldı. Ürün runtime güvenlik/tenant/bütçe/kaynak/kanıt kuralları bundan etkilenmez.

Git bütünlüğü, çatışma çözümü ve kullanıcı çalışmalarını korumak için ref/diff incelemesi ürün testi değildir. Force push veya kullanıcı değişikliklerini silmek yasaktır.
