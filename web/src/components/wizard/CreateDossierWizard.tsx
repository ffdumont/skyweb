/** Main wizard container: step indicator + current step component. */

import { useDossierStore } from "../../stores/dossierStore";
import StepUpload from "./StepUpload";
import StepReviewRoute from "./StepReviewRoute";
import StepDossierInfo from "./StepDossierInfo";

const STEPS = [
  { num: 1, label: "Import" },
  { num: 2, label: "Route" },
  { num: 3, label: "Dossier" },
] as const;

export default function CreateDossierWizard() {
  const step = useDossierStore((s) => s.wizard.step);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#f5f6fa" }}>
      {/* Step indicator */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: 0,
          padding: "16px 0 0",
          background: "#fff",
          borderBottom: "1px solid #e0e0e0",
          flexShrink: 0,
        }}
      >
        {STEPS.map((s, i) => {
          const isActive = step === s.num;
          const isDone = step > s.num;
          return (
            <div key={s.num} style={{ display: "flex", alignItems: "center" }}>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 4,
                  padding: "0 24px 12px",
                  borderBottom: isActive ? "2px solid #1a1a2e" : "2px solid transparent",
                }}
              >
                <div
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: "50%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 12,
                    fontWeight: 600,
                    background: isActive ? "#1a1a2e" : isDone ? "#2e7d32" : "#e0e0e0",
                    color: isActive || isDone ? "#fff" : "#888",
                  }}
                >
                  {isDone ? "\u2713" : s.num}
                </div>
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: isActive ? 600 : 400,
                    color: isActive ? "#1a1a2e" : "#888",
                  }}
                >
                  {s.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div
                  style={{
                    width: 40,
                    height: 1,
                    background: isDone ? "#2e7d32" : "#e0e0e0",
                    marginBottom: 14,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Step content */}
      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        {step === 1 && <StepUpload />}
        {step === 2 && <StepReviewRoute />}
        {step === 3 && <StepDossierInfo />}
      </div>
    </div>
  );
}
