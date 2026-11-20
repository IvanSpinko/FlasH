import { useEffect, useRef, useState } from "react";
import { api, type Deck } from "../api";
import { errorText } from "../errors";
import { useT } from "../i18n";

interface Props {
  onStart: (deck: Deck) => void;
}

/** The list of decks, with a button to add a new file. */
export function Library({ onStart }: Props) {
  const t = useT();
  const [decks, setDecks] = useState<Deck[] | null>(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [fromNotes, setFromNotes] = useState(true);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = () =>
    api
      .listDecks()
      .then((list) => {
        setDecks(list);
        setError("");
      })
      .catch((err) => setError(errorText(t, err, "other")));

  useEffect(() => {
    load();
  }, []); // load once when the screen opens

  const upload = async (file: File) => {
    setUploading(true);
    setError("");
    try {
      await api.uploadDeck(file, fromNotes);
      await load();
    } catch (err) {
      setError(errorText(t, err, "upload"));
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  return (
    <div className="stack">
      <div className="row between">
        <h1>{t("decks")}</h1>
        <button className="primary" onClick={() => fileInput.current?.click()} disabled={uploading}>
          {uploading ? t("reading") : "＋ " + t("addFile")}
        </button>
        <input
          id="file"
          ref={fileInput}
          type="file"
          accept=".pdf,.txt,.md"
          hidden
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
        />
      </div>
      <label className="check">
        <input id="from-notes" type="checkbox" checked={fromNotes} onChange={(e) => setFromNotes(e.target.checked)} />
        {t("fromNotes")}
      </label>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {decks === null && !error && <p className="muted">{t("loading")}</p>}

      {decks?.length === 0 && (
        <div className="card empty">
          <div className="empty-icon" aria-hidden="true">
            📚
          </div>
          <h2>{t("emptyTitle")}</h2>
          <p className="muted">{t("emptyBody")}</p>
        </div>
      )}

      {decks?.map((deck) => <DeckCard key={deck.id} deck={deck} onStart={() => onStart(deck)} onDeleted={load} />)}
    </div>
  );
}

function DeckCard({ deck, onStart, onDeleted }: { deck: Deck; onStart: () => void; onDeleted: () => void }) {
  const t = useT();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const p = deck.progress;
  const pct = p.total ? Math.round((100 * p.learned) / p.total) : 0;

  const remove = async () => {
    try {
      await api.deleteDeck(deck.id);
      onDeleted();
    } catch (err) {
      setError(errorText(t, err, "other"));
    }
  };

  return (
    <article className="card deck">
      <div className="row wrap">
        <h2 className="deck-name">{deck.name}</h2>
        <span className="badge">{t(`kind_${deck.kind}`)}</span>
      </div>
      <p className="muted small">
        {t("stats", { total: p.total, seen: p.seen, learned: p.learned })}
        {p.weak > 0 && " · " + t("weak", { n: p.weak })}
      </p>
      <div className="row">
        <div className="bar" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className={pct >= 80 ? "fill ok" : "fill"} style={{ width: `${pct}%` }} />
        </div>
        <span className="muted small nowrap">{t("learnedPct", { pct })}</span>
      </div>

      {confirming ? (
        <div className="confirm">
          <p>{t("confirmDelete", { name: deck.name })}</p>
          <div className="row">
            <button className="danger" onClick={remove}>
              {t("delete")}
            </button>
            <button onClick={() => setConfirming(false)}>{t("cancel")}</button>
          </div>
        </div>
      ) : (
        <div className="row">
          <button className="primary" onClick={onStart}>
            ▶ {t("start")}
          </button>
          <button className="ghost" onClick={() => setConfirming(true)}>
            {t("delete")}
          </button>
        </div>
      )}
      {error && <p className="error">{error}</p>}
    </article>
  );
}
