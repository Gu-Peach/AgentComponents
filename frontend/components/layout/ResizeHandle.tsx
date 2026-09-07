"use client";

import { useState } from "react";

interface ResizeHandleProps {
  axis: "x" | "y";
  onDrag: (event: PointerEvent) => void;
  ariaLabel: string;
}

export function ResizeHandle({ axis, onDrag, ariaLabel }: ResizeHandleProps) {
  const [active, setActive] = useState(false);

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    event.preventDefault();
    setActive(true);

    const handlePointerMove = (moveEvent: PointerEvent) => {
      onDrag(moveEvent);
    };

    const handlePointerUp = () => {
      setActive(false);
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
  }

  return (
    <div
      aria-label={ariaLabel}
      className={`${axis === "x" ? "resize-handle-x" : "resize-handle-y"} ${active ? "resize-handle-active" : ""}`}
      role="separator"
      tabIndex={0}
      onPointerDown={handlePointerDown}
    />
  );
}
