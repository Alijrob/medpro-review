/**
 * Proxy route: GET /api/reports/[id]/pdf -> report service /v1/reports/{id}/pdf
 *
 * Phase 2-N: streams PDF bytes from the report service to the browser.
 * Requires an active Auth0 session and a paid, completed report.
 *
 * On success: returns application/pdf with Content-Disposition: attachment.
 * On upstream error: proxies the JSON error body and status code.
 */

import { getSession } from "@auth0/nextjs-auth0";
import { NextRequest, NextResponse } from "next/server";

const REPORT_SERVICE_URL =
  process.env.REPORT_SERVICE_URL ?? "http://localhost:8004";

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = params;

  try {
    const res = await fetch(`${REPORT_SERVICE_URL}/v1/reports/${id}/pdf`, {
      // PDF rendering can take several seconds -- allow up to 30s
      signal: AbortSignal.timeout(30_000),
    });

    if (!res.ok) {
      // Proxy the error body from the report service (JSON detail)
      const data = await res
        .json()
        .catch(() => ({ error: "PDF unavailable" }));
      return NextResponse.json(data, { status: res.status });
    }

    const pdfBytes = await res.arrayBuffer();
    const disposition =
      res.headers.get("Content-Disposition") ??
      `attachment; filename="medpro-report-${id}.pdf"`;

    return new NextResponse(pdfBytes, {
      status: 200,
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": disposition,
      },
    });
  } catch (err) {
    console.error("[pdf-proxy] upstream error:", err);
    return NextResponse.json(
      { error: "Report service unavailable" },
      { status: 502 },
    );
  }
}
