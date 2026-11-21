// The whole app with a fake API: navigation between screens and the language switch.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import { App } from "./App";
import { ErrorBoundary } from "./ErrorBoundary";
import { deck } from "./test/render";

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  api: { listDecks: vi.fn(), startTest: vi.fn(), answer: vi.fn(), uploadDeck: vi.fn(), deleteDeck: vi.fn() },
}));
const mocked = vi.mocked(api);

beforeEach(() => {
  mocked.listDecks.mockResolvedValue([deck({ questions: 3 })]);
});

describe("App", () => {
  it("switches language and remembers it", async () => {
    const user = userEvent.setup();
    localStorage.setItem("flash.lang", "uk");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Мої тести" })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("uk");

    await user.click(screen.getByRole("button", { name: "EN" }));
    expect(screen.getByRole("heading", { name: "My tests" })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("en");
    expect(localStorage.getItem("flash.lang")).toBe("en");
  });

  it("goes from the library to setup and starts a test with the chosen options", async () => {
    const user = userEvent.setup();
    localStorage.setItem("flash.lang", "en");
    mocked.startTest.mockResolvedValue({
      test_id: "t1",
      deck_id: "d1",
      total: 3,
      answered: 0,
      score: 0,
      finished: false,
      question: { number: 1, text: "First?", options: ["a", "b", "c"] },
    });
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /Start test/ }));
    expect(screen.getByText("Test setup")).toBeInTheDocument();
    await user.click(screen.getByLabelText("In order"));
    await user.click(screen.getByLabelText("Shuffle answer options"));
    await user.click(screen.getByRole("button", { name: /Start test/ }));

    expect(mocked.startTest).toHaveBeenCalledWith("d1", { mode: "ordered", count: null, shuffle_options: false });
    expect(await screen.findByText("First?")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /FlasH/ }));
    expect(await screen.findByRole("heading", { name: "My tests" })).toBeInTheDocument();
  });
});

describe("ErrorBoundary", () => {
  it("shows a reload message instead of a blank page", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const Broken = () => {
      throw new Error("bug");
    };
    render(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong");
    expect(screen.getByRole("button", { name: /Reload/ })).toBeInTheDocument();
  });
});
