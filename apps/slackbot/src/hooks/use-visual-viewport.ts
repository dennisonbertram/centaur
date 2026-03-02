"use client";

import { useEffect, useState } from "react";

export function useKeyboardHeight(): number {
  const [keyboardHeight, setKeyboardHeight] = useState(0);

  useEffect(() => {
    if (typeof window === "undefined" || !window.visualViewport) return;
    const vv = window.visualViewport;

    const update = () => {
      const viewportHeight = vv.height + vv.offsetTop;
      const keyboard = Math.max(0, window.innerHeight - viewportHeight);
      // Ignore small viewport shifts from browser chrome changes.
      setKeyboardHeight(keyboard > 100 ? keyboard : 0);
    };

    update();
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    return () => {
      vv.removeEventListener("resize", update);
      vv.removeEventListener("scroll", update);
    };
  }, []);

  return keyboardHeight;
}
