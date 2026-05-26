import { render, screen, fireEvent } from "@testing-library/react";
import ProviderCard from "../../../src/components/search/ProviderCard";
import { ProviderSearchHit } from "../../../src/lib/types";

const baseProvider: ProviderSearchHit = {
  npi: "1234567890",
  name: "Dr. Jane Smith",
  specialty_group: "Physician",
  primary_specialty: "Family Medicine",
  state: "CA",
  identity_confidence: 0.98,
  report_count: 0,
  exclusion_flag: false,
};

describe("ProviderCard", () => {
  it("renders provider name and NPI", () => {
    render(<ProviderCard provider={baseProvider} onRequestReport={jest.fn()} />);
    expect(screen.getByText("Dr. Jane Smith")).toBeInTheDocument();
    expect(screen.getByText(/NPI: 1234567890/)).toBeInTheDocument();
  });

  it("renders specialty and state", () => {
    render(<ProviderCard provider={baseProvider} onRequestReport={jest.fn()} />);
    expect(screen.getByText("Physician")).toBeInTheDocument();
    expect(screen.getByText("CA")).toBeInTheDocument();
  });

  it("shows exclusion badge when exclusion_flag=true", () => {
    render(
      <ProviderCard
        provider={{ ...baseProvider, exclusion_flag: true }}
        onRequestReport={jest.fn()}
      />,
    );
    expect(screen.getByText("Exclusion Flag")).toBeInTheDocument();
  });

  it("does not show exclusion badge when exclusion_flag=false", () => {
    render(<ProviderCard provider={baseProvider} onRequestReport={jest.fn()} />);
    expect(screen.queryByText("Exclusion Flag")).not.toBeInTheDocument();
  });

  it("calls onRequestReport with correct NPI on button click", () => {
    const onRequestReport = jest.fn();
    render(<ProviderCard provider={baseProvider} onRequestReport={onRequestReport} />);
    fireEvent.click(screen.getByRole("button", { name: /request report/i }));
    expect(onRequestReport).toHaveBeenCalledWith("1234567890");
  });

  it("disables button when isRequesting=true", () => {
    render(
      <ProviderCard
        provider={baseProvider}
        onRequestReport={jest.fn()}
        isRequesting={true}
      />,
    );
    expect(screen.getByRole("button")).toBeDisabled();
    expect(screen.getByText("Requesting...")).toBeInTheDocument();
  });

  it("shows confidence percentage", () => {
    render(<ProviderCard provider={baseProvider} onRequestReport={jest.fn()} />);
    expect(screen.getByText("98% confidence")).toBeInTheDocument();
  });
});
