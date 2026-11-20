// Talks to the FlasH web API (flash/api). Every address starts with /api:
// nginx (in the container) or Vite (in development) forwards it to the API.

export type Mode = "smart" | "random" | "ordered" | "mistakes" | "unseen";
export const MODES: Mode[] = ["smart", "random", "ordered", "mistakes", "unseen"];

export interface Progress {
  total: number;
  seen: number;
  learned: number;
  weak: number;
}

export interface Deck {
  id: string;
  name: string;
  kind: "bank" | "generated" | "ai";
  created: string;
  questions: number;
  progress: Progress;
}

export interface OpenQuestion {
  number: number;
  text: string;
  options: string[];
}

export interface TestState {
  test_id: string;
  deck_id: string;
  total: number;
  answered: number;
  score: number;
  finished: boolean;
  question: OpenQuestion | null;
}

export interface AnswerResult {
  correct: boolean;
  correct_position: number;
  explanation: string;
  state: TestState;
}

export interface TestOptions {
  mode: Mode;
  count: number | null;
  shuffle_options: boolean;
}

/** An error from the API: the HTTP status and the API's own message. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError(0, "unreachable");
  }
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // not JSON: keep the status text
    }
    throw new ApiError(res.status, message);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  listDecks: () => request<Deck[]>("/decks"),

  uploadDeck: (file: File, generateFromNotes: boolean) => {
    const form = new FormData();
    form.append("file", file);
    const generate = generateFromNotes ? "offline" : "none";
    return request<Deck>(`/decks?generate=${generate}`, { method: "POST", body: form });
  },

  deleteDeck: (deckId: string) => request<void>(`/decks/${encodeURIComponent(deckId)}`, { method: "DELETE" }),

  startTest: (deckId: string, options: TestOptions) =>
    request<TestState>(`/decks/${encodeURIComponent(deckId)}/tests`, json(options)),

  answer: (testId: string, position: number) =>
    request<AnswerResult>(`/tests/${encodeURIComponent(testId)}/answer`, json({ position })),
};
