import { render, screen } from "@testing-library/react";
import ReportViewer from "../../../src/components/report/ReportViewer";
import { ReportStatus } from "../../../src/lib/types";

const paidReport: ReportStatus = {
  report_id: "rpt-001",
  npi: "1234567890",
  status: "complete",
  payment_status: "paid",
  has_html: true,
  report_html: "<html><body><h1>Provider Report</h1></body></html>",
  is_partial: false,
  completed_at: "2026-05-26T12:00:00Z",
};

describe("ReportViewer", () => {
  it("renders iframe with srcDoc when report_html is present", () => {
    render(<ReportViewer report={paidReport} />);
    const iframe = screen.getByTestId("report-iframe");
    expect(iframe).toBeInTheDocument();
  });

  it("displays NPI in metadata", () => {
    render(<ReportViewer report={paidReport} />);
    expect(screen.getByText("1234567890")).toBeInTheDocument();
  });

  it("shows partial badge when is_partial=true", () => {
    render(<ReportViewer report={{ ...paidReport, is_partial: true }} />);
    expect(screen.getByText("Partial Report")).toBeInTheDocument();
  });

  it("does not show partial badge when is_partial=false", () => {
    render(<ReportViewer report={paidReport} />);
    expect(screen.queryByText("Partial Report")).not.toBeInTheDocument();
  });

  it("shows no-html message when has_html=false", () => {
    render(<ReportViewer report={{ ...paidReport, has_html: false, report_html: null }} />);
    expect(screen.getByText(/not available in HTML format/i)).toBeInTheDocument();
    expect(screen.queryByTestId("report-iframe")).not.toBeInTheDocument();
  });

  it("shows no-html message when report_html is null", () => {
    render(<ReportViewer report={{ ...paidReport, report_html: null }} />);
    expect(screen.getByText(/not available in HTML format/i)).toBeInTheDocument();
  });
});
