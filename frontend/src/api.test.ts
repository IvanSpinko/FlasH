// The API client, with fetch replaced by a mock: no server is needed.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./api";

const fetchMock = vi.fn<typeof fetch>();

function reply(status: number, body?: unknown) {
  const text = body === undefined ? null : typeof body === "string" ? body : JSON.stringify(body);
  return new Response(text, { status, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

describe("api", () => {
  it("prefixes every address with /api", async () => {
    fetchMock.mockResolvedValue(reply(200, []));
    await expect(api.listDecks()).resolves.toEqual([]);
    expect(fetchMock).toHaveBeenCalledWith("/api/decks", undefined);
  });

  it("sends JSON bodies and escapes ids", async () => {
    fetchMock.mockResolvedValue(reply(201, { test_id: "t" }));
    await api.startTest("a/b", { mode: "smart", count: 10, shuffle_options: false });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/decks/a%2Fb/tests");
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(init?.body as string)).toEqual({ mode: "smart", count: 10, shuffle_options: false });
  });

  it("uploads the file as a form and says whether to use notes", async () => {
    fetchMock.mockResolvedValue(reply(201, { id: "d1" }));
    const file = new File(["text"], "notes.md");
    await api.uploadDeck(file, false);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/decks?generate=none");
    expect((init?.body as FormData).get("file")).toBeInstanceOf(File);
  });

  it("returns nothing for 204 No Content", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(api.deleteDeck("d1")).resolves.toBeUndefined();
  });

  it("turns the API's error message into an ApiError", async () => {
    fetchMock.mockResolvedValue(reply(404, { detail: "Deck not found" }));
    await expect(api.listDecks()).rejects.toEqual(new ApiError(404, "Deck not found"));
  });

  it("keeps field errors readable", async () => {
    fetchMock.mockResolvedValue(reply(422, { detail: [{ loc: ["body", "position"], msg: "too small" }] }));
    const err = await api.answer("t", -1).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.message).toContain("too small");
  });

  it("uses the status text when the error isn't JSON (e.g. from nginx)", async () => {
    fetchMock.mockResolvedValue(new Response("<html>Too Large</html>", { status: 413, statusText: "Too Large" }));
    await expect(api.listDecks()).rejects.toEqual(new ApiError(413, "Too Large"));
  });

  it("reports status 0 when the server can't be reached", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(api.listDecks()).rejects.toEqual(new ApiError(0, "unreachable"));
  });
});
