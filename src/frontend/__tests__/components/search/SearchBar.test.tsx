import { render, screen, fireEvent } from "@testing-library/react";
import SearchBar from "../../../src/components/search/SearchBar";

describe("SearchBar", () => {
  it("renders input and search button", () => {
    render(<SearchBar onSearch={jest.fn()} />);
    expect(screen.getByRole("searchbox", { name: /search providers/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /submit search/i })).toBeInTheDocument();
  });

  it("calls onSearch with trimmed input on form submit", () => {
    const onSearch = jest.fn();
    render(<SearchBar onSearch={onSearch} />);
    const input = screen.getByRole("searchbox");
    fireEvent.change(input, { target: { value: "  Smith  " } });
    fireEvent.submit(input.closest("form")!);
    expect(onSearch).toHaveBeenCalledWith("Smith");
  });

  it("does not call onSearch for empty input", () => {
    const onSearch = jest.fn();
    render(<SearchBar onSearch={onSearch} />);
    const form = screen.getByRole("search");
    fireEvent.submit(form);
    expect(onSearch).not.toHaveBeenCalled();
  });

  it("search button is disabled when input is empty", () => {
    render(<SearchBar onSearch={jest.fn()} />);
    expect(screen.getByRole("button", { name: /submit search/i })).toBeDisabled();
  });

  it("shows loading state when isLoading=true", () => {
    render(<SearchBar onSearch={jest.fn()} isLoading={true} />);
    expect(screen.getByText("Searching...")).toBeInTheDocument();
    expect(screen.getByRole("searchbox")).toBeDisabled();
  });

  it("enables button once input is non-empty", () => {
    render(<SearchBar onSearch={jest.fn()} />);
    const input = screen.getByRole("searchbox");
    fireEvent.change(input, { target: { value: "1234567890" } });
    expect(screen.getByRole("button", { name: /submit search/i })).not.toBeDisabled();
  });
});
