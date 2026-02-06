import { StrictMode, Component, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
// Note: Cesium CSS is imported only in AirspacesTab to avoid global style conflicts
import App from "./App";

class ErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 32, fontFamily: "monospace" }}>
          <h2>Erreur</h2>
          <pre style={{ whiteSpace: "pre-wrap", color: "red" }}>
            {this.state.error.message}
          </pre>
          <pre style={{ whiteSpace: "pre-wrap", color: "#666", fontSize: 12 }}>
            {this.state.error.stack}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
