/**
 * Shared TypeScript types and Zod runtime schemas for the medpro-review frontend.
 *
 * Zod parses API responses at the boundary so TypeScript types match reality.
 * All types are inferred from schemas -- no manual interface duplication.
 */

import { z } from "zod";

// ---------------------------------------------------------------------------
// Provider search (proxied from search service :8003)
// ---------------------------------------------------------------------------

export const ProviderSearchHitSchema = z.object({
  npi: z.string(),
  name: z.string(),
  specialty_group: z.string().nullable().optional(),
  primary_specialty: z.string().nullable().optional(),
  state: z.string().nullable().optional(),
  identity_confidence: z.number().default(0),
  report_count: z.number().default(0),
  exclusion_flag: z.boolean().default(false),
});
export type ProviderSearchHit = z.infer<typeof ProviderSearchHitSchema>;

export const SearchResponseSchema = z.object({
  total: z.number(),
  hits: z.array(ProviderSearchHitSchema),
  took_ms: z.number().optional(),
  query: z.string().optional(),
});
export type SearchResponse = z.infer<typeof SearchResponseSchema>;

// ---------------------------------------------------------------------------
// Report status (proxied from report service :8004)
// ---------------------------------------------------------------------------

export const ReportStatusSchema = z.object({
  report_id: z.string(),
  npi: z.string(),
  status: z.enum(["queued", "started", "complete", "failed"]),
  payment_status: z.enum(["unpaid", "pending", "paid", "refunded"]).default("unpaid"),
  has_html: z.boolean().default(false),
  report_html: z.string().nullable().optional(),
  is_partial: z.boolean().default(false),
  created_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  error_message: z.string().nullable().optional(),
  workflow_id: z.string().nullable().optional(),
});
export type ReportStatus = z.infer<typeof ReportStatusSchema>;

export const ReportRequestResponseSchema = z.object({
  report_id: z.string(),
  status: z.string(),
  npi: z.string(),
  db_persisted: z.boolean(),
  temporal_queued: z.boolean(),
  message: z.string(),
});
export type ReportRequestResponse = z.infer<typeof ReportRequestResponseSchema>;

// ---------------------------------------------------------------------------
// Payment / Stripe Checkout (proxied from payment service :8005)
// ---------------------------------------------------------------------------

export const CheckoutResponseSchema = z.object({
  report_id: z.string(),
  checkout_url: z.string(),
  session_id: z.string(),
  stripe_configured: z.boolean(),
  price_usd: z.number(),
  npi: z.string(),
});
export type CheckoutResponse = z.infer<typeof CheckoutResponseSchema>;

// ---------------------------------------------------------------------------
// Path B certification (client-side session cookie only -- DB record at payment)
// ---------------------------------------------------------------------------

export const CERTIFICATION_COOKIE = "medpro_path_b_certified";

export const certificationPayloadSchema = z.object({
  certified_at: z.string(),
  version: z.string(),
});
export type CertificationPayload = z.infer<typeof certificationPayloadSchema>;

// ---------------------------------------------------------------------------
// API error shape
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
