# DemandRift — Claude çalışma girişi

`AGENTS.md` ve `ortak/gelistirme-plani.md` geçerlidir. Aktif kapsam üç fazdır; eski yedi faz belgeleri tarihçedir.

Doğrudan `main` üzerinde geliştir; yeni branch, worktree veya PR açma. Ana AI uygulamayı tamamlar, `code_pusher` subagent aynı checkout'ta yalnız commit/push yapar. Geliştirme sırasında test, lint/typecheck/build kontrolü, bağımsız review/verify/integration veya run graph oluşturma. Tüm işlevler bittikten sonra final test ve kontrol, hata düzeltme ve son regresyon yapılır. CI yalnız manuel final turunda başlatılır.

Eski `.orchestrator` kayıtlarını devam edilmesi zorunlu iş grafiği sayma. Ürün güvenlik, bütçe, kaynak ve kanıt kurallarını koru; mevcut değişiklikleri kaybetme. Çalıştırılmamış testleri geçti diye sunma.
