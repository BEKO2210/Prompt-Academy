#!/usr/bin/env bash
set -euo pipefail

PROMPT='You are a senior creative director. Write EXACTLY 5 detailed design prompts for sections of a 3D cinematic landing page built with React, Framer Motion, and 21st.dev UI components. Topic: "Neura" — an AI productivity assistant.

Each prompt MUST:
- Describe ONE section (e.g. hero, feature grid, testimonials, pricing, footer, scroll-driven story)
- Specify the 3D / cinematic visual concept (camera move, depth-of-field, lighting, particles, parallax layers)
- Name specific Framer Motion APIs to use (useScroll, useTransform, layoutId, AnimatePresence, stagger, spring)
- Reference 21st.dev component categories (animated buttons, bento grids, marquees, cards, navbars, gradient backgrounds)
- Be 3-5 sentences, written as a direct instruction to an AI code generator (Cursor / v0 / Claude)
- Be in English

Output format: ONLY the 5 prompts, each prefixed with the section name in brackets like [HERO], then the prompt text. No preamble, no closing remark.'

OUT_DIR="$(dirname "$0")/results"
mkdir -p "$OUT_DIR"

for MODEL in qwen2.5:14b phi4:14b mistral-small3.2:latest mistral-nemo:12b; do
  SAFE="${MODEL//[:\/]/_}"
  echo "=== $MODEL ===" | tee "$OUT_DIR/$SAFE.txt"
  /usr/bin/time -f "elapsed=%e s" ollama run "$MODEL" "$PROMPT" 2>>"$OUT_DIR/$SAFE.timing" | tee -a "$OUT_DIR/$SAFE.txt"
  echo | tee -a "$OUT_DIR/$SAFE.txt"
done

echo "Done. Results in $OUT_DIR"
