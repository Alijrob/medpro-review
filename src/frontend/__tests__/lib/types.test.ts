/**
 * Unit tests for Zod schemas in src/lib/types.ts.
 * Tests parse valid data, reject invalid data, and apply defaults.
 */

import { z } from "zod";
import {
  ProviderSearchHitSchema,
  SearchResponseSchema,
  ReportStatusSchema,
  CheckoutResponseSchema,
  ReportRequestResponseSchema,
  certificationPayloadSchema,
  ApiError,
} from "../../src/lib/types";

// ---------------------------------------------------------------------------
// ProviderSearchHitSchema
// ---------------------------------------------------------------------------

describe("ProviderSearchHitSchema", () => {
  const valid = {
    npi: "1234567890",
    name: "Dr. Jane Smith",
    specialty_group: "Physician",
    primary_specialty: "Family Medicine",
    state: "CA",
    identity_confidence: 0.98,
    report_count: 2,
    exclusion_flag: false,
  };

  it("parses a complete valid hit", () => {
    const result = ProviderSearchHitSchema.parse(valid);
    expect(result.npi).toBe("1234567890");
    expect(result.name).toBe("Dr. Jane Smith");
    expect(result.identity_confidence).toBe(0.98);
  });

  it("applies default identity_confidence=0 when missing", () => {
    const result = ProviderSearchHitSchema.parse({ npi: "1234567890", name: "X" });
    expect(result.identity_confidence).toBe(0);
    expect(result.report_count).toBe(0);
    expect(result.exclusion_flag).toBe(false);
  });

  it("accepts null specialty fields", () => {
    const result = ProviderSearchHitSchema.parse({
      npi: "1234567890",
      name: "X",
      specialty_group: null,
      state: null,
    });
    expect(result.specialty_group).toBeNull();
    expect(result.state).toBeNull();
  });

  it("rejects missing required npi", () => {
    expect(() => ProviderSearchHitSchema.parse({ name: "X" })).toThrow(z.ZodError);
  });

  it("rejects missing required name", () => {
    expect(() => ProviderSearchHitSchema.parse({ npi: "1234567890" })).toThrow(z.ZodError);
  });
});

// ---------------------------------------------------------------------------
// SearchResponseSchema
// ---------------------------------------------------------------------------

describe("SearchResponseSchema", () => {
  it("parses a response with hits", () => {
    const result = SearchResponseSchema.parse({
      total: 1,
      hits: [{ npi: "1234567890", name: "Dr. X" }],
      took_ms: 45,
    });
    expect(result.total).toBe(1);
    expect(result.hits).toHaveLength(1);
    expect(result.took_ms).toBe(45);
  });

  it("parses empty results", () => {
    const result = SearchResponseSchema.parse({ total: 0, hits: [] });
    expect(result.total).toBe(0);
    expect(result.hits).toHaveLength(0);
  });

  it("rejects if hits is not an array", () => {
    expect(() => SearchResponseSchema.parse({ total: 0, hits: "bad" })).toThrow(z.ZodError);
  });
});

// ---------------------------------------------------------------------------
// ReportStatusSchema
// ---------------------------------------------------------------------------

describe("ReportStatusSchema", () => {
  const base = {
    report_id: "abc-123",
    npi: "1234567890",
    status: "queued",
  };

  it("parses a queued report with defaults", () => {
    const result = ReportStatusSchema.parse(base);
    expect(result.status).toBe("queued");
    expect(result.payment_status).toBe("unpaid");
    expect(result.has_html).toBe(false);
    expect(result.is_partial).toBe(false);
  });

  it("parses a complete paid report", () => {
    const result = ReportStatusSchema.parse({
      ...base,
      status: "complete",
      payment_status: "paid",
      has_html: true,
      report_html: "<html>...</html>",
    });
    expect(result.status).toBe("complete");
    expect(result.payment_status).toBe("paid");
    expect(result.has_html).toBe(true);
    expect(result.report_html).toBe("<html>...</html>");
  });

  it("rejects invalid status", () => {
    expect(() =>
      ReportStatusSchema.parse({ ...base, status: "pending" }),
    ).toThrow(z.ZodError);
  });

  it("rejects invalid payment_status", () => {
    expect(() =>
      ReportStatusSchema.parse({ ...base, payment_status: "processing" }),
    ).toThrow(z.ZodError);
  });

  it("accepts null/undefined optional fields", () => {
    const result = ReportStatusSchema.parse({
      ...base,
      report_html: null,
      error_message: null,
      completed_at: null,
    });
    expect(result.report_html).toBeNull();
    expect(result.error_message).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// CheckoutResponseSchema
// ---------------------------------------------------------------------------

describe("CheckoutResponseSchema", () => {
  const valid = {
    report_id: "abc-123",
    checkout_url: "https://checkout.stripe.com/c/pay/test",
    session_id: "cs_test_abc",
    stripe_configured: true,
    price_usd: 15.0,
    npi: "1234567890",
  };

  it("parses valid checkout response", () => {
    const result = CheckoutResponseSchema.parse(valid);
    expect(result.checkout_url).toBe("https://checkout.stripe.com/c/pay/test");
    expect(result.stripe_configured).toBe(true);
    expect(result.price_usd).toBe(15.0);
  });

  it("parses unconfigured Stripe response", () => {
    const result = CheckoutResponseSchema.parse({
      ...valid,
      checkout_url: "https://example.com/mock",
      stripe_configured: false,
    });
    expect(result.stripe_configured).toBe(false);
  });

  it("rejects missing checkout_url", () => {
    const { checkout_url: _, ...rest } = valid;
    expect(() => CheckoutResponseSchema.parse(rest)).toThrow(z.ZodError);
  });
});

// ---------------------------------------------------------------------------
// ReportRequestResponseSchema
// ---------------------------------------------------------------------------

describe("ReportRequestResponseSchema", () => {
  it("parses a successful report request", () => {
    const result = ReportRequestResponseSchema.parse({
      report_id: "uuid-1234",
      status: "queued",
      npi: "1234567890",
      db_persisted: true,
      temporal_queued: true,
      message: "Report queued successfully",
    });
    expect(result.report_id).toBe("uuid-1234");
    expect(result.db_persisted).toBe(true);
  });

  it("parses a response where services are unavailable", () => {
    const result = ReportRequestResponseSchema.parse({
      report_id: "uuid-5678",
      status: "queued",
      npi: "9876543210",
      db_persisted: false,
      temporal_queued: false,
      message: "DB not configured",
    });
    expect(result.db_persisted).toBe(false);
    expect(result.temporal_queued).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// certificationPayloadSchema
// ---------------------------------------------------------------------------

describe("certificationPayloadSchema", () => {
  it("parses a valid certification payload", () => {
    const result = certificationPayloadSchema.parse({
      certified_at: "2026-05-26T10:00:00Z",
      version: "path-b-v1",
    });
    expect(result.certified_at).toBe("2026-05-26T10:00:00Z");
    expect(result.version).toBe("path-b-v1");
  });
});

// ---------------------------------------------------------------------------
// ApiError
// ---------------------------------------------------------------------------

describe("ApiError", () => {
  it("constructs with status and message", () => {
    const err = new ApiError(404, "Not found");
    expect(err.status).toBe(404);
    expect(err.message).toBe("Not found");
    expect(err.name).toBe("ApiError");
    expect(err instanceof Error).toBe(true);
  });

  it("stores detail payload", () => {
    const detail = { error: "provider not found" };
    const err = new ApiError(404, "Not found", detail);
    expect(err.detail).toEqual(detail);
  });
});
