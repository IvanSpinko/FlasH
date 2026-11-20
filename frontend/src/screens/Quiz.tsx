import { useCallback, useEffect, useState } from "react";
import { api, type AnswerResult, type TestState } from "../api";
import { errorText } from "../errors";
import { useT } from "../i18n";

/** One answered question, kept for the results screen. */
export interface Answered {
  text: string;
  options: string[];
  chosen: number;
  correctPosition: number;
  correct: boolean;
  explanation: string;
}

interface Props {
  test: TestState;
  onFinish: (log: Answered[]) => void;
}

/** One question at a time, with feedback right after each answer. */
export function Quiz({ test, onFinish }: Props) {
  const t = useT();
  const [state, setState] = useState(test);
  const [feedback, setFeedback] = useState<{ chosen: number; result: AnswerResult } | null>(null);
  const [log, setLog] = useState<Answered[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const question = state.question;

  const choose = useCallback(
    async (pos: number) => {
      if (!question || feedback || busy) return;
      setBusy(true);
      setError("");
      try {
        const result = await api.answer(state.test_id, pos);
        setFeedback({ chosen: pos, result });
        setLog((prev) => [
          ...prev,
          {
            text: question.text,
            options: question.options,
            chosen: pos,
            correctPosition: result.correct_position,
            correct: result.correct,
            explanation: result.explanation,
          },
        ]);
      } catch (err) {
        setError(errorText(t, err, "other"));
      } finally {
        setBusy(false);
      }
    },
    [question, feedback, busy, state.test_id, t],
  );

  const next = useCallback(() => {
    if (!feedback) return;
    if (feedback.result.state.finished) {
      onFinish(log);
    } else {
      setState(feedback.result.state);
      setFeedback(null);
      window.scrollTo({ top: 0 });
    }
  }, [feedback, log, onFinish]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // A focused button handles Enter/Space itself; don't do it twice.
      if (e.target instanceof HTMLButtonElement && (e.key === "Enter" || e.key === " ")) return;
      if (e.key === "Enter" || e.key === " ") {
        if (feedback) {
          e.preventDefault();
          next();
        }
      } else if (/^[1-9]$/.test(e.key)) {
        choose(Number(e.key) - 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [choose, next, feedback]);

  if (!question) return null;

  const shown = feedback ? feedback.result.state : state;
  const wrongSoFar = shown.answered - shown.score;
  const finished = feedback?.result.state.finished;

  const optionClass = (i: number) => {
    if (!feedback) return "option";
    if (i === feedback.result.correct_position) return "option correct";
    if (i === feedback.chosen) return "option wrong";
    return "option dim";
  };

  return (
    <div className="stack">
      <div className="row between">
        <button className="ghost" onClick={() => onFinish(log)}>
          ✕ {t("finish")}
        </button>
        <span className="muted strong">{t("question", { i: question.number, n: state.total })}</span>
        <span className="score">
          <span className="ok-text">✔ {shown.score}</span> <span className="bad-text">✘ {wrongSoFar}</span>
        </span>
      </div>
      <div className="bar">
        <div className="fill" style={{ width: `${(100 * shown.answered) / Math.max(state.total, 1)}%` }} />
      </div>

      <section className="card quiz">
        <h2 className="question">{question.text}</h2>
        <div className="options">
          {question.options.map((option, i) => (
            <button key={i} className={optionClass(i)} onClick={() => choose(i)} disabled={!!feedback || busy}>
              <span className="num">{i + 1}</span>
              <span>{option}</span>
            </button>
          ))}
        </div>

        {feedback && (
          <div className={feedback.result.correct ? "feedback ok" : "feedback bad"} role="status">
            <strong>
              {feedback.result.correct
                ? "✔ " + t("correct")
                : "✘ " + t("wrong", { answer: question.options[feedback.result.correct_position] })}
            </strong>
            {feedback.result.explanation && <p>{t("explanation", { text: feedback.result.explanation })}</p>}
          </div>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
      </section>

      <div className="row between">
        <span className="muted small hint">{t("keysHint", { n: question.options.length })}</span>
        {feedback && (
          <button className="primary big push-right" onClick={next} autoFocus>
            {finished ? t("results") : t("next")}
          </button>
        )}
      </div>
    </div>
  );
}
