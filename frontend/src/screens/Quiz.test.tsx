// The quiz screen with the API mocked: answers come back instantly from the test.
import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, type AnswerResult, type TestState } from "../api";
import { renderIn } from "../test/render";
import { Quiz } from "./Quiz";

vi.mock("../api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api")>()),
  api: { answer: vi.fn() },
}));
const answer = vi.mocked(api.answer);

const QUESTIONS = [
  { text: "Which organ pumps blood?", options: ["Liver", "Heart", "Lungs"], right: 1, explanation: "" },
  { text: "Symbol of sodium?", options: ["K", "Na", "S"], right: 1, explanation: "From natrium." },
];

function stateAt(index: number, score: number): TestState {
  const q = QUESTIONS[index];
  return {
    test_id: "t1",
    deck_id: "d1",
    total: QUESTIONS.length,
    answered: index,
    score,
    finished: !q,
    question: q ? { number: index + 1, text: q.text, options: q.options } : null,
  };
}

let score = 0;
beforeEach(() => {
  score = 0;
  answer.mockImplementation(async (_testId, position) => {
    const index = QUESTIONS.findIndex((q) => screen.queryByText(q.text));
    const q = QUESTIONS[index];
    const correct = position === q.right;
    if (correct) score += 1;
    return {
      correct,
      correct_position: q.right,
      explanation: q.explanation,
      state: stateAt(index + 1, score),
    } satisfies AnswerResult;
  });
});

describe("Quiz", () => {
  it("shows feedback, moves on, and reports every answer at the end", async () => {
    const user = userEvent.setup();
    const onFinish = vi.fn();
    renderIn(<Quiz test={stateAt(0, 0)} onFinish={onFinish} />);

    expect(screen.getByText("Question 1 of 2")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Heart/ }));
    expect(answer).toHaveBeenCalledWith("t1", 1);
    expect(await screen.findByRole("status")).toHaveTextContent("Correct!");
    expect(screen.getByRole("button", { name: /Heart/ })).toHaveClass("correct");
    expect(screen.getByRole("button", { name: /Liver/ })).toBeDisabled();

    await user.click(screen.getByRole("button", { name: "Next ➜" }));
    expect(screen.getByText("Symbol of sodium?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^3/ }));
    expect(await screen.findByRole("status")).toHaveTextContent("Wrong. Correct answer: Na");
    expect(screen.getByText("Explanation: From natrium.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^3/ })).toHaveClass("wrong");

    await user.click(screen.getByRole("button", { name: "Results ➜" }));
    expect(onFinish).toHaveBeenCalledOnce();
    const log = onFinish.mock.calls[0][0];
    expect(log.map((a: { correct: boolean }) => a.correct)).toEqual([true, false]);
    expect(log[1]).toMatchObject({ chosen: 2, correctPosition: 1, explanation: "From natrium." });
  });

  it("can be answered with the keyboard", async () => {
    renderIn(<Quiz test={stateAt(0, 0)} onFinish={vi.fn()} />);
    fireEvent.keyDown(window, { key: "2" });
    expect(await screen.findByRole("status")).toHaveTextContent("Correct!");
    fireEvent.keyDown(window, { key: "Enter" });
    expect(screen.getByText("Symbol of sodium?")).toBeInTheDocument();
  });

  it("ignores a second answer to the same question", async () => {
    const user = userEvent.setup();
    renderIn(<Quiz test={stateAt(0, 0)} onFinish={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Heart/ }));
    await screen.findByRole("status");
    fireEvent.keyDown(window, { key: "1" });
    expect(answer).toHaveBeenCalledOnce();
  });

  it("shows an error and lets the user try again", async () => {
    const user = userEvent.setup();
    answer.mockRejectedValueOnce(new TypeError("offline"));
    renderIn(<Quiz test={stateAt(0, 0)} onFinish={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /Heart/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");
    await user.click(screen.getByRole("button", { name: /Heart/ }));
    expect(await screen.findByRole("status")).toHaveTextContent("Correct!");
  });

  it("finishing early hands over what was answered", async () => {
    const user = userEvent.setup();
    const onFinish = vi.fn();
    renderIn(<Quiz test={stateAt(0, 0)} onFinish={onFinish} />);
    await user.click(screen.getByRole("button", { name: /Finish/ }));
    expect(onFinish).toHaveBeenCalledWith([]);
  });
});
