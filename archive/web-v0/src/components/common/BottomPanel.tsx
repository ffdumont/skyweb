import { useState, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  title?: string;
  defaultOpen?: boolean;
}

const COLLAPSED_H = 32;
const EXPANDED_H = 220;

export default function BottomPanel({
  children,
  title = "Profile",
  defaultOpen = true,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        right: 0,
        height: open ? EXPANDED_H : COLLAPSED_H,
        background: "rgba(255,255,255,0.97)",
        borderTop: "1px solid #ccc",
        zIndex: 20,
        transition: "height 0.2s ease",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          height: COLLAPSED_H,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 12px",
          cursor: "pointer",
          userSelect: "none",
          borderBottom: open ? "1px solid #eee" : "none",
          flexShrink: 0,
        }}
        onClick={() => setOpen((o) => !o)}
      >
        <span style={{ fontSize: 12, fontWeight: 600, color: "#444" }}>
          {title}
        </span>
        <span style={{ fontSize: 11, color: "#999" }}>
          {open ? "\u25BC" : "\u25B2"}
        </span>
      </div>

      {open && (
        <div
          style={{
            flex: 1,
            overflow: "hidden",
            padding: "4px 0",
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
}
