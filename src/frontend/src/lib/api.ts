/**
 * Browser-side API helpers -- all calls go to /api/* proxy routes.
 * No direct browser-to-backend service calls.
 */

import {
  ApiError,
  CheckoutResponseSchema,
  CheckoutResponse,
  ReportRequestResponse,
  ReportRequestResponseSchema,
  ReportStatus,
  ReportStatusSchema,
  SearchResponse,
  SearchResponseSchema,
} from "./types";

async function handleResponse<T>(
  res: Response,
  parse: (data: unknown) => T,
): Promise<T> {
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, `HTTP ${res.status}: ${res.statusText}`, detail);
  }
  const raw = await res.json();
  return parse(raw);
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

export interface SearchParams {
  q?: string;
  npi?: string;
  state?: string;
  specialty?: string;
  limit?: number;
}

export async function searchProviders(params: SearchParams): Promise<SearchResponse> {
  const url = new URL("/api/search", window.location.origin);
  if (params.q) url.searchParams.set("q", params.q);
  if (params.npi) url.searchParams.set("npi", params.npi);
  if (params.state) url.searchParams.set("state", params.state);
  if (params.specialty) url.searchParams.set("specialty", params.specialty);
  if (params.limit != null) url.searchParams.set("limit", String(params.limit));

  const res = await fetch(url.toString());
  return handleResponse(res, (d) => SearchResponseSchema.parse(d));
}

// ---------------------------------------------------------------------------
// Reports
// ---------------------------------------------------------------------------

export async function requestReport(npi: string): Promise<ReportRequestResponse> {
  const res = await fetch("/api/reports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ npi }),
  });
  return handleResponse(res, (d) => ReportRequestResponseSchema.parse(d));
}

export async function getReport(reportId: string): Promise<ReportStatus> {
  const res = await fetch(`/api/reports/${reportId}`);
  return handleResponse(res, (d) => ReportStatusSchema.parse(d));
}

// ---------------------------------------------------------------------------
// Payments
// ---------------------------------------------------------------------------

export interface CheckoutParams {
  report_id: string;
  npi: string;
  certified_personal_use_only: boolean;
}

export async function createCheckout(params: CheckoutParams): Promise<CheckoutResponse> {
  const res = await fetch("/api/payments/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return handleResponse(res, (d) => CheckoutResponseSchema.parse(d));
}
