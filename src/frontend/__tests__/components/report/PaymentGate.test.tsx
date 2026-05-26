/**
 * PaymentGate tests.
 *
 * createCheckout is mocked to avoid real fetch calls.
 * window.location.href is captured to verify Stripe redirect.
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import PaymentGate from "../../../src/components/report/PaymentGate";

// Mock the api module
jest.mock("../../../src/lib/api", () => ({
  createCheckout: jest.fn(),
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      message: string,
      public detail?: unknown,
    ) {
      super(message);
      this.name = "ApiError";
    }
  },
}));

import * as api from "../../../src/lib/api";

const mockCreateCheckout = api.createCheckout as jest.MockedFunction<typeof api.createCheckout>;

// Capture location.href changes
const originalLocation = window.location;
beforeAll(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...originalLocation, href: "" },
  });
});
afterAll(() => {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: originalLocation,
  });
});

describe("PaymentGate", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.location.href = "";
  });

  it("renders the payment gate with price", () => {
    render(<PaymentGate reportId="abc-123" npi="1234567890" priceUsd={15} />);
    expect(screen.getByText("Unlock This Report")).toBeInTheDocument();
    expect(screen.getByText("$15.00 one-time")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /pay.*view report/i })).toBeInTheDocument();
  });

  it("shows the Path B disclaimer", () => {
    render(<PaymentGate reportId="abc-123" npi="1234567890" />);
    expect(screen.getByText(/personal use only/i)).toBeInTheDocument();
    expect(screen.getByText(/path b certification/i)).toBeInTheDocument();
  });

  it("redirects to checkout_url on successful payment initiation", async () => {
    mockCreateCheckout.mockResolvedValueOnce({
      report_id: "abc-123",
      checkout_url: "https://checkout.stripe.com/c/pay/test_abc",
      session_id: "cs_test_abc",
      stripe_configured: true,
      price_usd: 15,
      npi: "1234567890",
    });

    render(<PaymentGate reportId="abc-123" npi="1234567890" />);
    fireEvent.click(screen.getByRole("button", { name: /pay/i }));

    await waitFor(() => {
      expect(window.location.href).toBe("https://checkout.stripe.com/c/pay/test_abc");
    });
  });

  it("calls createCheckout with certified_personal_use_only=true", async () => {
    mockCreateCheckout.mockResolvedValueOnce({
      report_id: "abc-123",
      checkout_url: "https://checkout.stripe.com/c/pay/x",
      session_id: "cs_test_x",
      stripe_configured: true,
      price_usd: 15,
      npi: "1234567890",
    });

    render(<PaymentGate reportId="abc-123" npi="1234567890" />);
    fireEvent.click(screen.getByRole("button", { name: /pay/i }));

    await waitFor(() => {
      expect(mockCreateCheckout).toHaveBeenCalledWith({
        report_id: "abc-123",
        npi: "1234567890",
        certified_personal_use_only: true,
      });
    });
  });

  it("shows error message when checkout fails", async () => {
    const { ApiError } = jest.requireActual("../../../src/lib/types");
    mockCreateCheckout.mockRejectedValueOnce(
      new Error("Payment setup failed. Please try again."),
    );

    render(<PaymentGate reportId="abc-123" npi="1234567890" />);
    fireEvent.click(screen.getByRole("button", { name: /pay/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("disables button while loading", async () => {
    let resolveCheckout!: (v: unknown) => void;
    mockCreateCheckout.mockImplementationOnce(
      () => new Promise((res) => { resolveCheckout = res; }),
    );

    render(<PaymentGate reportId="abc-123" npi="1234567890" />);
    const btn = screen.getByRole("button", { name: /pay/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/redirecting/i)).toBeInTheDocument();
      expect(btn).toBeDisabled();
    });
  });
});
