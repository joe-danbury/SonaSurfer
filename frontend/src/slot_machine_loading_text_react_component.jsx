import React, { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

/**
 * SlotMachineLoader
 * - Shows ONLY one phrase at a time (no scrolling list in the DOM)
 * - Slot-machine style roll: current text exits up, next text enters from below
 * - Letters themselves animate in a left-to-right wave using Spotify green
 * - Container party lights: DISCRETE colour jumps (no gradients)
 */
export default function SlotMachineLoader() {
  const phrases = useMemo(
    () => [
      "Exploring the vibes",
      "Hunting down tracks",
      "Finding the beat",
      "Crafting the playlist",
    ],
    []
  );

  // How long each phrase stays on screen
  const intervalMs = 2200;

  // Party light cadence (discrete jumps)
  const partyIntervalMs = 360;
  const partyColours = useMemo(
    () => [
      "rgba(255, 0, 0, 0.70)", // red
      "rgba(0, 255, 0, 0.70)", // green
      "rgba(0, 140, 255, 0.70)", // blue
      "rgba(255, 0, 200, 0.70)", // pink
      "rgba(255, 140, 0, 0.70)", // orange
      "rgba(0, 255, 0, 0.70)", // green
      "rgba(255, 0, 200, 0.70)", // pink
    ],
    []
  );

  const [index, setIndex] = useState(0);
  const [partyIdx, setPartyIdx] = useState(0);

  // Measure the tallest/widest phrase once so the slot window is fixed.
  const measureRef = useRef(null);
  const [rowH, setRowH] = useState(40);
  const [textW, setTextW] = useState(220); // px, updated after mount

  // Horizontal padding inside the slot viewport (Tailwind px-4 = 16px left + 16px right)
  const slotPadX = 16 * 2;
  const slotExtraW = 12; // extra breathing room so widest text never feels tight

  useEffect(() => {
    const measure = () => {
      if (!measureRef.current) return;
      const rect = measureRef.current.getBoundingClientRect();
      const h = rect.height;
      const w = rect.width;
      if (h && Math.abs(h - rowH) > 1) setRowH(h);
      if (w && Math.abs(w - textW) > 1) setTextW(w);
    };

    measure();

    let ro = null;
    if (typeof ResizeObserver !== "undefined" && measureRef.current) {
      ro = new ResizeObserver(measure);
      ro.observe(measureRef.current);
    }

    window.addEventListener("resize", measure);
    return () => {
      if (ro) ro.disconnect();
      window.removeEventListener("resize", measure);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cycle phrases
  useEffect(() => {
    const id = window.setInterval(() => {
      setIndex((i) => (i + 1) % phrases.length);
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [phrases.length]);

  // Party light colour jumps (no interpolation)
  useEffect(() => {
    const id = window.setInterval(() => {
      setPartyIdx((i) => (i + 1) % partyColours.length);
    }, partyIntervalMs);
    return () => window.clearInterval(id);
  }, [partyColours.length]);

  const text = phrases[index];
  const fixedWidth = Math.ceil(textW + slotPadX + slotExtraW);

  const partyColour = partyColours[partyIdx];
  const borderColour = partyColour.replace(", 0.70)", ", 0.55)");
  const glowColour = partyColour.replace(", 0.70)", ", 0.12)");
  const washColour = partyColour.replace(", 0.70)", ", 0.18)");

  return (
    <div className="w-full flex items-center justify-center p-6">
      <div className="relative">
        <div
          className="relative rounded-2xl border bg-white shadow-sm px-4 py-3"
          style={{
            borderColor: borderColour,
            boxShadow: `0 10px 25px ${glowColour}`,
          }}
        >
          {/* Discrete party wash overlay (solid colour, jumps) */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 rounded-2xl"
            style={{
              backgroundColor: washColour,
              opacity: 0.45,
              transition: "background-color 0ms", // ensure no smoothing
            }}
          />

          {/* Gloss highlight */}
          <div className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-b from-white/70 via-white/10 to-transparent" />

          {/* Slot window */}
          <div
            className="relative overflow-hidden rounded-xl bg-zinc-50 border border-zinc-200"
            style={{ width: fixedWidth }}
          >
            <div className="pointer-events-none absolute inset-x-0 top-0 h-6 bg-gradient-to-b from-zinc-50 to-transparent" />
            <div className="pointer-events-none absolute inset-x-0 bottom-0 h-6 bg-gradient-to-t from-zinc-50 to-transparent" />

            {/* Slot viewport: exactly one line tall */}
            <div
              className="relative flex items-center justify-center px-4"
              style={{ height: rowH }}
            >
              {/* Hidden measurer: measures the longest phrase so width/height stay fixed. */}
              <span
                ref={measureRef}
                className="absolute -z-10 opacity-0 pointer-events-none text-sm sm:text-base font-medium tracking-tight whitespace-nowrap"
              >
                {getLongest(phrases)}
              </span>

              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={text}
                  className="w-full flex items-center justify-center"
                  initial={{ y: rowH * 0.9, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: -rowH * 0.9, opacity: 0 }}
                  transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                >
                  <LetterWaveText text={text} cycleMs={intervalMs} rollMs={600} />
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          {/* Tiny loading dots */}
          <div className="mt-2 flex items-center justify-center gap-1">
            <Dot delay={0} />
            <Dot delay={0.15} />
            <Dot delay={0.3} />
          </div>
        </div>
      </div>
    </div>
  );
}

function getLongest(items) {
  if (!items.length) return "";
  return items.reduce((a, b) => (a.length > b.length ? a : b), items[0]);
}

function LetterWaveText({ text, cycleMs, rollMs }) {
  // Per-letter wave: near-black -> Spotify green -> near-black
  // We run ONE sweep per phrase (no infinite repeat), and remount on phrase change.
  // Timing is computed so the sweep completes before the slot roll begins.
  const letters = text.split("");
  const base = "#18181b"; // zinc-900-ish
  const spotifyGreen = "#1DB954";

  const n = Math.max(1, letters.length);

  // Leave a little buffer so the sweep finishes before the phrase starts rolling out.
  const bufferMs = 180;
  const availableMs = Math.max(700, cycleMs - rollMs - bufferMs);

  // Stagger determines how fast the green travels across letters.
  // Pulse duration is how long each letter stays in its colour cycle.
  const staggerSec = Math.max(0.02, (availableMs * 0.55) / Math.max(1, n - 1) / 1000);
  const pulseSec = Math.max(0.22, (availableMs * 0.45) / 1000);

  return (
    <span className="inline-flex text-sm sm:text-base font-medium tracking-tight whitespace-nowrap">
      {letters.map((char, i) => (
        <motion.span
          key={`${i}-${char}`}
          className="text-zinc-900"
          animate={{
            color: [base, spotifyGreen, base],
          }}
          transition={{
            duration: pulseSec,
            ease: "easeInOut",
            delay: i * staggerSec,
            times: [0, 0.5, 1],
          }}
        >
          {char === " " ? " " : char}
        </motion.span>
      ))}
    </span>
  );
}

function Dot({ delay }) {
  return (
    <motion.span
      className="inline-block h-1.5 w-1.5 rounded-full bg-zinc-400"
      animate={{ opacity: [0.25, 1, 0.25], scale: [0.9, 1.05, 0.9] }}
      transition={{ duration: 0.8, repeat: Infinity, delay, ease: "easeInOut" }}
    />
  );
}

/**
 * Lightweight "test hooks" (no-op in production) to make automated tests easy.
 */
export const __TEST__ = {
  defaultPhrases: [
    "Exploring the vibes",
    "Hunting down tracks",
    "Finding the beat",
    "Crafting the playlist",
  ],
  intervalMs: 2200,
  // rollMs is fixed inside the component (600)
  partyIntervalMs: 360,
  partyColours: [
    "rgba(255, 0, 0, 0.70)",
    "rgba(0, 255, 0, 0.70)",
    "rgba(0, 140, 255, 0.70)",
    "rgba(255, 0, 200, 0.70)",
    "rgba(255, 140, 0, 0.70)",
    "rgba(0, 255, 0, 0.70)",
    "rgba(255, 0, 200, 0.70)",
  ],
};

/**
 * Example tests (Vitest + React Testing Library)
 *
 * import { describe, it, expect, vi } from "vitest";
 * import { render, screen } from "@testing-library/react";
 * import SlotMachineLoader, { __TEST__ } from "./SlotMachineLoader";
 *
 * describe("SlotMachineLoader", () => {
 *   it("renders the first phrase initially", () => {
 *     render(<SlotMachineLoader />);
 *     expect(screen.getByText(__TEST__.defaultPhrases[0])).toBeTruthy();
 *   });
 *
 *   it("advances the phrase on the interval", () => {
 *     vi.useFakeTimers();
 *     render(<SlotMachineLoader />);
 *     vi.advanceTimersByTime(__TEST__.intervalMs);
 *     expect(screen.getByText(__TEST__.defaultPhrases[1])).toBeTruthy();
 *     vi.useRealTimers();
 *   });
 *
 *   it("keeps exactly one phrase visible at a time", () => {
 *     vi.useFakeTimers();
 *     render(<SlotMachineLoader />);
 *     expect(screen.getByText(__TEST__.defaultPhrases[0])).toBeTruthy();
 *     expect(screen.queryByText(__TEST__.defaultPhrases[2])).toBeNull();
 *     vi.useRealTimers();
 *   });
 *
 *   it("cycles party colours discretely", () => {
 *     vi.useFakeTimers();
 *     const { container } = render(<SlotMachineLoader />);
 *     const shell = container.querySelector(".rounded-2xl");
 *     expect(shell).toBeTruthy();
 *     const first = (shell as HTMLElement).style.borderColor;
 *     vi.advanceTimersByTime(__TEST__.partyIntervalMs);
 *     const second = (shell as HTMLElement).style.borderColor;
 *     expect(first).not.toEqual(second);
 *     vi.useRealTimers();
 *   });
 * });
 */
