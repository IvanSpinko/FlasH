import { useT, type Key } from "../i18n";
import type { Answered } from "./Quiz";

interface Props {
  log: Answered[];
  onHome: () => void;
  onPractiseMistakes: () => void;
  practiseError: string;
}

/** Score, a grade, and every mistake with the right answer. */
export function Results({ log, onHome, onPractiseMistakes, practiseError }: Props) {
  const t = useT();
  const right = log.filter((a) => a.correct).length;
  const total = log.length;
  const pct = total ? Math.round((100 * right) / total) : 0;
  const grade: Key = pct >= 90 ? "grade_5" : pct >= 75 ? "grade_4" : pct >= 60 ? "grade_3" : "grade_2";
  const tone = pct >= 75 ? "ok" : pct >= 60 ? "accent" : "bad";
  const mistakes = log.filter((a) => !a.correct);
  const ring = 2 * Math.PI * 52;

  return (
    <div className="stack">
      <section className="card result-head">
        <svg viewBox="0 0 120 120" className={`ring ${tone}`} role="img" aria-label={`${pct}%`}>
          <circle cx="60" cy="60" r="52" className="track" />
          <circle
            cx="60"
            cy="60"
            r="52"
            className="arc"
            strokeDasharray={`${(ring * pct) / 100} ${ring}`}
            transform="rotate(-90 60 60)"
          />
          <text x="60" y="68" textAnchor="middle">
            {pct}%
          </text>
        </svg>
        <div className="stack tight">
          <h1 className={`${tone}-text`}>{t(grade)}</h1>
          <p className="muted">{t("resultLine", { right, total })}</p>
          <div className="row wrap">
            <span className="pill ok">✔ {t("chipRight", { n: right })}</span>
            <span className="pill bad">✘ {t("chipWrong", { n: total - right })}</span>
          </div>
        </div>
      </section>

      <section className="card">
        <h2>{mistakes.length ? t("mistakesTitle", { n: mistakes.length }) : t("noMistakes")}</h2>
        <ol className="mistakes">
          {mistakes.map((m, i) => (
            <li key={i}>
              <p className="strong">{m.text}</p>
              <p className="bad-text">✘ {t("yourAnswer", { text: m.options[m.chosen] })}</p>
              <p className="ok-text">✔ {t("rightAnswer", { text: m.options[m.correctPosition] })}</p>
              {m.explanation && <p className="muted small">{m.explanation}</p>}
            </li>
          ))}
        </ol>
      </section>

      {practiseError && (
        <p className="error" role="alert">
          {practiseError}
        </p>
      )}
      <div className="row between wrap">
        <button className="ghost" onClick={onHome}>
          ⌂ {t("home")}
        </button>
        {mistakes.length > 0 && (
          <button className="primary" onClick={onPractiseMistakes}>
            ↻ {t("practiseMistakes")}
          </button>
        )}
      </div>
    </div>
  );
}
