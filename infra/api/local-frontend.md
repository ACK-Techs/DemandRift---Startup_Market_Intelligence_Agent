# Local frontend → Hetzner API

## Production domain

For a Vercel frontend at `https://demandrift.ack-techs.com`, set its server-only
`DEMANDRIFT_BACKEND_ORIGIN` to the exact `https://demandrift-api.ack-techs.com`
origin and deploy the configuration. The existing `/api/backend/:path*` rewrite
keeps browser requests and session cookies on the frontend origin; this value
is not a `NEXT_PUBLIC_` variable. Arbitrary proxy destinations remain rejected.

The backend's `CORS_ALLOWED_ORIGINS` must explicitly include
`https://demandrift.ack-techs.com` for Origin and CSRF validation. Keep the
host-only `Secure`, `HttpOnly`, `SameSite=Lax` session cookie policy. DNS, TLS,
deployment routing and real cookie/header forwarding must be verified during
the production rollout; this configuration does not prove those live checks.
Git automatic deployments remain disabled until separately authorized.

## Local tunnel

Bu tünel akışında frontend yerelde çalışır. Hetzner'deki DemandRift API yalnız
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
87 senaryonun geçtiği iddiası değildir. Local tünel akışı frontend yayını
yapmaz; production yayını ayrı rollout kapsamındadır.
