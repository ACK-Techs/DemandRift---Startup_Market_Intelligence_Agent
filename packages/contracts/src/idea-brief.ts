import { z } from "zod";

/**
 * Faz 1'in çıktısı. Faz 2 bu paketi alıp araştırma planı üretir.
 * Kaynak: Faz1-Plan.md - "Idea Brief veri modeli" (16 alan)
 */
export const IdeaBriefSchema = z.object({
  original_idea: z.string().min(1),
  normalized_idea: z.string().min(1),

  product_type: z.enum(["agent", "mobile_app", "web_saas", "extension", "other"]),

  target_user: z.enum(["known", "inferred", "missing"]),
  problem_or_job: z.enum(["known", "inferred", "missing"]),
  context_or_niche: z.enum(["known", "inferred", "missing"]),

  clarity_status: z.enum(["ready", "needs_clarification", "broad_but_continue"]),

  // Opsiyonel: kullanıcı belirtmemiş olabilir.
  constraints: z
    .object({
      budget: z.string().min(1).optional(),
      technical_level: z.string().min(1).optional(),
      platform_preference: z.string().min(1).optional(),
    })
    .optional(),

  // Eksik veya belirsiz alanların adları. Boş dizi = eksik yok.
  missing_fields: z.array(z.string().min(1)),

  // Plan en fazla üç soru diyor; sınır şemada zorunlu.
  clarifying_questions: z.array(z.string().min(1)).max(3),

  suggested_niches: z.array(z.string().min(1)).optional(),

  // AI'ın kendi değerlendirmesine güveni: 0 ile 1 arası.
  confidence: z.number().min(0).max(1),

  user_confirmed_fields: z.array(z.string().min(1)),

  // Her alan adı -> o alandaki bilginin kökeni.
  // Kritik kural: ai_hypothesis onaylanmadan araştırmayı besleyemez.
  field_origins: z.record(
    z.string().min(1),
    z.enum(["user_stated", "user_confirmed", "ai_inferred", "ai_hypothesis"]),
  ),

  // Araştırma boyunca taşınacak açık varsayım kimlikleri.
  assumption_ids: z.array(z.string().min(1)),

  // Değiştirilemez sürüm numarası; her onayda artar.
  brief_version: z.number().int().positive(),
});
