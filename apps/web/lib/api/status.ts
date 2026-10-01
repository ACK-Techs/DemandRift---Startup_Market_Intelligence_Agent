import type { Outcome, Phase, RunStatus, SourceStatus } from "../../../../packages/contracts/src/generated";

export type StatePresentation = { label: string; tone: "neutral" | "active" | "success" | "warning" | "danger"; terminal: boolean };
export const phaseLabels: Record<Phase, string> = {
  planning: "Fikir ve araştırma planı", evidence: "Kaynak ve kanıt analizi", decision: "Karar ve gerekçe",
};
export const outcomeLabels: Record<Outcome, string> = {
  positive_findings: "Olumlu bulgular", modify: "Değiştir", kill: "Durdur", investigate_more: "Daha fazla araştır",
};
export const runStates: Record<RunStatus, StatePresentation> = {
  draft: { label: "Taslak", tone: "neutral", terminal: false },
  awaiting_user: { label: "Onay bekliyor", tone: "warning", terminal: false },
  planned: { label: "Planlandı", tone: "neutral", terminal: false },
  queued: { label: "Sırada", tone: "neutral", terminal: false },
  acquiring: { label: "Kaynaklar toplanıyor", tone: "active", terminal: false },
  normalizing: { label: "Belgeler hazırlanıyor", tone: "active", terminal: false },
  analyzing: { label: "Kanıtlar analiz ediliyor", tone: "active", terminal: false },
  deciding: { label: "Karar hazırlanıyor", tone: "active", terminal: false },
  completed: { label: "İşlem tamamlandı", tone: "success", terminal: true },
  partial: { label: "Kısmi sonuç", tone: "warning", terminal: true },
  cancelled: { label: "İptal edildi", tone: "neutral", terminal: true },
  failed: { label: "İşlem başarısız", tone: "danger", terminal: true },
};
export const sourceStates: Record<SourceStatus, StatePresentation> = {
  queued: { label: "Sırada", tone: "neutral", terminal: false },
  running: { label: "Çalışıyor", tone: "active", terminal: false },
  succeeded: { label: "Kaynak işlemi tamamlandı", tone: "success", terminal: true },
  no_results: { label: "Sonuç bulunamadı", tone: "neutral", terminal: true },
  source_unavailable: { label: "Kaynağa erişilemiyor", tone: "warning", terminal: true },
  rate_limited: { label: "Kaynak hız sınırı", tone: "warning", terminal: true },
  blocked_by_policy: { label: "Kaynak politikası izin vermiyor", tone: "warning", terminal: true },
  challenge: { label: "Kaynak doğrulama istiyor", tone: "warning", terminal: true },
  invalid_output: { label: "Kaynak çıktısı geçersiz", tone: "danger", terminal: true },
  partial: { label: "Kısmi kaynak çıktısı", tone: "warning", terminal: true },
  cancelled: { label: "İptal edildi", tone: "neutral", terminal: true },
  failed: { label: "Kaynak işlemi başarısız", tone: "danger", terminal: true },
};
export function presentState(kind: "run" | "source", status: string): StatePresentation {
  const states = kind === "run" ? runStates : sourceStates;
  return Object.hasOwn(states, status) ? states[status as keyof typeof states] :
    { label: "Bilinmeyen durum", tone: "warning", terminal: false };
}

export type FailureCategory = "authentication" | "permission" | "not_found" | "conflict" | "validation" |
  "rate_limit" | "budget" | "policy" | "unavailable" | "contract" | "timeout" | "cancelled" | "network" | "server";
export const failureMessages: Record<FailureCategory, string> = {
  authentication: "Oturum açmanız gerekiyor.", permission: "Bu kayıt için erişim izniniz yok.",
  not_found: "Kayıt bulunamadı.", conflict: "Kayıt değişti; güncel durumu yeniden okuyun.",
  validation: "Gönderilen bilgileri kontrol edin.", rate_limit: "İstek sınırına ulaşıldı; belirtilen süreyi bekleyin.",
  budget: "Araştırma bütçe sınırına ulaştı.", policy: "Bu işlem kaynak politikası nedeniyle durduruldu.",
  unavailable: "Backend şu anda kullanılamıyor.", contract: "Yanıt beklenen veri sözleşmesiyle eşleşmiyor.",
  timeout: "Yanıt süresi doldu.", cancelled: "İstek iptal edildi.", network: "Backend bağlantısı kurulamadı.",
  server: "İşlem sırasında bir hata oluştu.",
};
export function failureCategory(status: number, code?: string): FailureCategory {
  if (status === 401) return "authentication";
  if (code === "budget_exceeded" || code === "budget_exhausted") return "budget";
  if (code === "blocked_by_policy") return "policy";
  if (status === 403) return "permission";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 422 || status === 400) return "validation";
  if (status === 429) return "rate_limit";
  if (status === 502 || status === 503 || status === 504) return "unavailable";
  return "server";
}
