// The deck list with the API mocked.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "../api";
import { deck, renderIn } from "../test/render";
import { Library } from "./Library";

vi.mock("../api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api")>()),
  api: { listDecks: vi.fn(), uploadDeck: vi.fn(), deleteDeck: vi.fn() },
}));
const mocked = vi.mocked(api);

beforeEach(() => {
  mocked.listDecks.mockResolvedValue([]);
});

describe("Library", () => {
  it("invites the user to add a first file", async () => {
    renderIn(<Library onStart={vi.fn()} />);
    expect(await screen.findByText("Add your first file")).toBeInTheDocument();
  });

  it("lists decks with their progress and starts one", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();
    const krok = deck();
    mocked.listDecks.mockResolvedValue([krok]);
    renderIn(<Library onStart={onStart} />);

    const card = (await screen.findByText("Krok 2024")).closest("article")!;
    expect(within(card).getByText("Test bank")).toBeInTheDocument();
    expect(within(card).getByText(/40 questions · 10 attempted · 4 learned · mistakes: 2/)).toBeInTheDocument();
    expect(within(card).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "10");

    await user.click(within(card).getByRole("button", { name: /Start test/ }));
    expect(onStart).toHaveBeenCalledWith(krok);
  });

  it("uploads a file and refreshes the list", async () => {
    const user = userEvent.setup();
    renderIn(<Library onStart={vi.fn()} />);
    await screen.findByText("Add your first file");

    mocked.uploadDeck.mockResolvedValue(deck({ name: "biology" }));
    mocked.listDecks.mockResolvedValue([deck({ name: "biology" })]);
    await user.click(screen.getByLabelText(/make questions offline/));
    const file = new File(["notes"], "biology.md", { type: "text/markdown" });
    await user.upload(document.getElementById("file") as HTMLInputElement, file);

    expect(mocked.uploadDeck).toHaveBeenCalledWith(file, false);
    expect(await screen.findByText("biology")).toBeInTheDocument();
  });

  it("explains why an upload failed", async () => {
    const user = userEvent.setup();
    mocked.uploadDeck.mockRejectedValue(new ApiError(415, "Unsupported file type"));
    renderIn(<Library onStart={vi.fn()} />);
    await user.upload(document.getElementById("file") as HTMLInputElement, new File(["x"], "a.txt"));
    expect(await screen.findByRole("alert")).toHaveTextContent("This file type isn't supported");
  });

  it("asks before deleting", async () => {
    const user = userEvent.setup();
    mocked.listDecks.mockResolvedValue([deck()]);
    mocked.deleteDeck.mockResolvedValue(undefined);
    renderIn(<Library onStart={vi.fn()} />);
    await screen.findByText("Krok 2024");

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(screen.getByText(/Delete “Krok 2024”\?/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mocked.deleteDeck).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Delete" }));
    mocked.listDecks.mockResolvedValue([]);
    await user.click(screen.getAllByRole("button", { name: "Delete" })[0]);
    await waitFor(() => expect(mocked.deleteDeck).toHaveBeenCalledWith("d1"));
    expect(await screen.findByText("Add your first file")).toBeInTheDocument();
  });

  it("says so when the server is down", async () => {
    mocked.listDecks.mockRejectedValue(new ApiError(0, "unreachable"));
    renderIn(<Library onStart={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Can't reach the FlasH server");
  });
});
