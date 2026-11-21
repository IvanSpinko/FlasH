import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  failed: boolean;
}

/**
 * Shows a "reload" message instead of a blank page if a screen crashes.
 * The text is in both languages because the crash may have happened before the language was known.
 */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("FlasH crashed:", error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="page">
        <div className="card empty" role="alert">
          <h2>Щось пішло не так · Something went wrong</h2>
          <p className="muted">Оновіть сторінку · Please reload the page</p>
          <button className="primary" onClick={() => window.location.reload()}>
            ↻ Reload
          </button>
        </div>
      </main>
    );
  }
}
