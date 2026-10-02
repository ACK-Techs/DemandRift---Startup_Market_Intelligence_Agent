# Local frontend → Hetzner API

Frontend yalnız yerelde çalışır. Hetzner'deki DemandRift API yalnız
`127.0.0.1:18082` üzerinde dinler. Next.js sunucusu sabit SSH tüneli hedefine
`/api/backend/:path*` isteklerini yönlendirir; tarayıcı aynı origin üzerinde
kalır. `DEMANDRIFT_BACKEND_ORIGIN` sunucu ayarıdır; `NEXT_PUBLIC_` değildir ve
Gemini anahtarı içermez. Başka proxy hedefine veya kimlik bilgili URL'ye izin yoktur.

Bilinen sunucu anahtarıyla, mevcut SSH erişimini kullanarak:

```sh
ssh -N -o BatchMode=yes -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes \
  -L 127.0.0.1:18082:127.0.0.1:18082 root@167.235.158.118
```

Repo kökünde ikinci terminal:

```sh
DEMANDRIFT_BACKEND_ORIGIN=http://127.0.0.1:18082 \
  npm run dev --prefix apps/web -- --hostname 127.0.0.1 --port 3100
```

Frontend adresi `http://127.0.0.1:3100`. Backend'in açık origin listesi bu
adresi birebir içermelidir; cookie `Secure`, `HttpOnly` ve CSRF kontrolü
korunur. Gerçek tarayıcıdaki loopback cookie davranışı kabul testinde
doğrulanır. `/health` yalnız süreç canlılığı ve revision bilgisidir;
DB rolü/migration, kayıt/giriş, tenant izolasyonu ve ürün akışlarının kabulü
yerine geçmez.

Tünel kesilirse UI erişim hatası göstermelidir. POST otomatik tekrar edilmez;
belirsiz mutasyon yalnız aynı işlem kimliğiyle kullanıcı tarafından
uzlaştırılır. Tüneli yeniden açmak backend işlerini veya kalıcı veriyi sıfırlamaz.

Bu dosya bağlantı yapılandırmasını açıklar; çalışan Hetzner ürünü veya
87 senaryonun geçtiği iddiası değildir. Vercel veya başka frontend yayını
bu çalışma kapsamında yapılmaz.
