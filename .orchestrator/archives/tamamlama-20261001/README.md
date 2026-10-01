# Tamamlama run arşivi — 2026-10-01

Bu arşiv kullanıcı isteğiyle verilen durma checkpoint'idir. Ürün veya 87 zorunlu final senaryosu tamamlanmış değildir. Kapsam ve sonraki adımlar `ortak/raporlar/devam-notu-2026-10-01.md` içindedir.

- `state.json`: orijinal `run.json`, `events.jsonl`, progress ve başlangıç kullanıcı dosyalarının hashleri; sonuçlar, gelen sonuçlar (reddedilen girişler dahil), checkpoint ve yayın makbuzları, tasarım kayıtları. Her kaydın orijinal relatif yolu ve SHA256'sı saklanır. UTF-8 olmayan küçük tasarım kayıtları base64 olarak taşınır.
- `evidence.jsonl`: her satır bir orijinal evidence dosyasının relatif yolu, SHA256'sı ve UTF-8 metnidir. JSON, metin, Markdown, log ve diff kanıtları taşınır; olumlu ve başarısız geçmiş birlikte tutulur. Provider credential içermez.
- `manifest.json`: tam yerel evidence ağacındaki bütün dosyaların boyut/hash ve arşivlenme durumları. Source snapshot, tool download, binary ve cache dosyaları taşınmaz; bunlar yerel tam run'da kalır. Kod yayın SHA'ları ve source hash manifestleri taşınır.

Tam yerel run `.orchestrator/runs/tamamlama-20261001/` içinde korunur ve Git'ten ignore edilir. Bu arşivin state snapshot revision'u `state.json` içindeki run'dan okunur. Arşivin kendi review/push kayıtları daha sonra canlı run'a eklenebilir; bu nedenle ikisinin revision'larının aynı olması beklenmez.

## Kontrol ve gerekirse geri yükleme

Önce mevcut canlı run'a bakın; daha yeni revision varsa üzerine yazmayın. Arşivi boş ayrı bir dizine çıkarın, SHA'ları doğrulayın, mevcut run ile karşılaştırın. Aşağıdaki komut yalnız `/tmp` altında **yeni** bir dizin oluşturur; repo veya mevcut run'a yazmaz. Proje repo root'unda çalıştırın. Veriler kod olarak çalıştırılmaz.

```sh
python3 - <<'PY'
from pathlib import Path
import base64, hashlib, json, tempfile
archive = Path('.orchestrator/archives/tamamlama-20261001')
out = Path(tempfile.mkdtemp(prefix='demandrift-resume-', dir='/tmp'))
entries = json.loads((archive / 'state.json').read_text())['files']
for line in (archive / 'evidence.jsonl').read_text().splitlines():
    entry = json.loads(line)
    if entry['path'] in entries:
        raise ValueError('Duplicate archive path')
    entries[entry['path']] = entry
for relative, entry in entries.items():
    target = out / relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Unsafe archive path')
    encoding = entry.get('encoding', 'utf-8')
    if encoding not in ('utf-8', 'base64'):
        raise ValueError('Unknown archive encoding')
    body = (base64.b64decode(entry['data'], validate=True)
            if encoding == 'base64' else entry['text'].encode('utf-8'))
    if hashlib.sha256(body).hexdigest() != entry['sha256']:
        raise ValueError('Archive hash mismatch')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
print(out)
PY
```

Bundan sonra mevcut run'a uygulanması ayrı ve kontrollü adımdır. Başlangıçtaki üç kullanıcı raporu arşivde içerik olarak bulunmaz; yerelde değiştirilmeden korunur. Runtime secret dışarıda bırakılır. Source snapshots/binary/tool caches ve geçici PostgreSQL cluster'ları arşivden kurulmaz. Çalışma ortamını doküman ve pinlenmiş repo bağımlılıklarıyla yeniden hazırlayın.
