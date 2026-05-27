#!/usr/bin/env python3
"""
Generate 1000+ design prompts for a 3D cinematic landing page / web app
(React + Framer Motion + 21st.dev) using a local Ollama model.

Coverage: 88 subjects across 6 categories (sections, full pages, components,
backgrounds/effects, micro-interactions, layout patterns) × 16 visual styles ×
10 topics × 10 animation recipes. Round-robin distribution ensures every
subject is represented evenly in the final set.

Streams to output/prompts.jsonl (resumable: re-running appends only missing IDs).
After generation, compiles output/prompts.json for the website.

Usage:
    python3 generate.py --model phi4:14b --target 1000
"""

import argparse
import itertools
import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import urllib.request
import urllib.error


# ---------- Variation axes ----------

SUBJECTS = {
    "page_section": [
        "hero", "feature_bento", "scroll_storytelling", "interactive_demo",
        "testimonials_marquee", "pricing_table", "faq_accordion", "stats_counter",
        "integrations_orbit", "team_grid", "case_study_split", "cta_finale",
        "footer_gradient", "logo_cloud", "comparison_table", "timeline_journey",
        "product_gallery_3d", "live_dashboard_preview", "kinetic_typography_intro",
        "feature_carousel", "newsletter_signup", "blog_masonry", "video_hero",
        "before_after_slider", "tabbed_features", "command_palette_demo",
        "social_proof_wall", "metric_hero", "scroll_zoom_reveal", "sticky_sidebar_story",
    ],
    "full_page": [
        "landing_page", "product_detail_page", "about_page", "pricing_page",
        "contact_page", "login_signup", "dashboard_app", "blog_index",
        "blog_post", "404_error_page", "coming_soon", "changelog_page",
    ],
    "component": [
        "animated_navbar", "mega_menu", "magnetic_cta_button", "glow_card",
        "3d_tilt_card", "floating_dock", "command_palette", "modal_dialog",
        "toast_notification", "skeleton_loader", "animated_form", "search_overlay",
        "sidebar_drawer", "breadcrumb_trail", "pagination", "tooltip_rich",
        "avatar_stack", "progress_indicator", "tag_chip", "code_snippet_block",
    ],
    "background_effect": [
        "animated_gradient_mesh", "particle_field", "aurora_borealis",
        "noise_grain_overlay", "cursor_spotlight", "scroll_progress_bar",
        "cinematic_loader_screen", "grid_pattern_bg", "star_field_parallax",
        "liquid_blob_morph",
    ],
    "micro_interaction": [
        "hover_3d_tilt", "magnetic_cursor", "ripple_click", "text_scramble",
        "typewriter_reveal", "sticker_peel_hover", "drag_to_reorder",
        "pull_to_refresh", "sound_reactive_visual", "gesture_swipe_card",
    ],
    "layout_pattern": [
        "split_screen_scroll", "sticky_aside", "masonry_responsive",
        "bento_asymmetric", "stacked_card_deck", "horizontal_scroll_section",
        "pinned_section_chapters", "revealed_on_scroll_lock",
    ],
}

ELEMENT_LABEL = {
    "page_section": "page section",
    "full_page": "full-page layout",
    "component": "reusable UI component",
    "background_effect": "decorative background or full-screen effect",
    "micro_interaction": "micro-interaction pattern",
    "layout_pattern": "layout / structural pattern",
}

VISUAL_STYLES = [
    "cosmic_dark_with_aurora", "liquid_chrome_holography",
    "neo_brutalist_typography_meets_glass", "vaporwave_retrofuturist",
    "editorial_swiss_minimal", "biomorphic_organic_blobs",
    "y2k_cybercore", "warm_analog_film_grain", "glassmorphism_with_depth_blur",
    "neon_synthwave_grid", "paper_collage_3d", "industrial_blueprint",
    "soft_serif_luxe", "obsidian_monochrome_with_red_accent",
    "iridescent_pearl", "ascii_terminal_3d",
]

TOPICS = [
    "Neura — an AI productivity assistant",
    "Orbit — async collaboration tool for distributed teams",
    "Halo — a privacy-first password manager",
    "Lumen — AI-powered video editor",
    "Forge — design system platform",
    "Pulse — developer analytics dashboard",
    "Drift — async voice notes for product teams",
    "Quill — AI writing studio",
    "Nimbus — cloud infrastructure observability",
    "Atlas — AI knowledge base",
]

ANIMATION_RECIPES = [
    "scroll-driven (useScroll + useTransform) parallax with 3 depth layers",
    "shared layout transitions (layoutId) between cards",
    "stagger reveal of children with spring physics on viewport enter",
    "mouse-driven 3D tilt with damped spring on the hero artwork",
    "AnimatePresence morph between two states triggered by hover",
    "scrub-controlled camera dolly using scrollYProgress",
    "magnetic cursor attraction on CTAs with motion values",
    "kinetic looping marquee with infinite-scroll seam blending",
    "orchestrated timeline using useAnimate + sequence()",
    "scroll-snap sections with camera-FOV change on each snap",
]


# ---------- Meta-prompt template ----------

META_PROMPT = """You are a senior creative director writing detailed design prompts for an AI code generator (Cursor / v0 / Claude). Target stack: React + TypeScript + Tailwind + Framer Motion, with components sourced from 21st.dev.

Write ONE self-contained design prompt for the following element. The prompt must be directly actionable by a code-gen AI — 3 to 6 sentences of confident, present-tense imperative prose.

PARAMETERS
- Element type: {element_label}
- Subject: {subject}
- Visual style: {style}
- Product / topic: {topic}
- Animation recipe: {animation}

YOUR PROMPT MUST INCLUDE
1. What is being built and its purpose (one short phrase weaving in the subject name).
2. The cinematic / 3D visual concept (camera move, depth layering, lighting, particles, materials).
3. Specific Framer Motion APIs to use (e.g. useScroll, useTransform, AnimatePresence, layoutId, useSpring, useMotionValue, useAnimate, stagger, variants, useInView).
4. At least one concrete 21st.dev component category to drop in (e.g. animated buttons, bento grids, marquees, gradient cards, magnetic CTAs, hover-borders, glow-cards, scroll-areas, animated navbars, command-menu, sparkles, beam-borders).
5. Typography and colour direction in one short clause.
6. The interaction that triggers the animation (scroll, hover, viewport-enter, drag, mouse-position, focus, click).

CONSTRAINTS
- Output the prompt ONLY — no preamble, no closing remark, no markdown headings, no bullets.
- Plain prose, 3 to 6 sentences, max ~150 words.
- Written in English, present-tense, direct imperative voice ("Build…", "Animate…", "Render…").
- Do NOT include code blocks or backticks around API names.
- Do NOT repeat the parameter list verbatim — weave the constraints into the prose.
"""


def post_ollama(host: str, model: str, prompt: str, temperature: float, num_predict: int):
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": num_predict,
            "top_p": 0.95,
        },
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.loads(resp.read())
    return data.get("response", "").strip()


def load_existing(path: Path):
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            ids.add(json.loads(line)["id"])
        except Exception:
            continue
    return ids


def build_combos(target: int, seed: int = 42):
    """
    Round-robin across all (category, subject) pairs to guarantee even coverage.
    Each round picks one (style, topic, animation) per subject. After ceil(target/N)
    rounds, every subject has the same number (±1) of prompts.
    """
    rng = random.Random(seed)
    pairs = [(cat, sub) for cat, subs in SUBJECTS.items() for sub in subs]
    rng.shuffle(pairs)

    combos = []
    rounds_needed = (target + len(pairs) - 1) // len(pairs)
    for r in range(rounds_needed):
        # Rotate subject order each round so the first subjects aren't always first.
        order = pairs.copy()
        rng.shuffle(order)
        for (cat, sub) in order:
            style = rng.choice(VISUAL_STYLES)
            topic = rng.choice(TOPICS)
            animation = rng.choice(ANIMATION_RECIPES)
            combos.append((cat, sub, style, topic, animation))
    return combos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="phi4:14b")
    ap.add_argument("--target", type=int, default=1000)
    ap.add_argument("--host", default="http://localhost:11434")
    ap.add_argument("--temperature", type=float, default=0.9)
    ap.add_argument("--num-predict", type=int, default=380)
    ap.add_argument("--out-dir", default=str(Path(__file__).parent / "output"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / "prompts.jsonl"
    final_json = out_dir / "prompts.json"

    done_ids = load_existing(jsonl)
    print(f"[init] model={args.model} target={args.target} already_done={len(done_ids)}", flush=True)

    combos = build_combos(args.target, seed=args.seed)
    print(f"[init] built {len(combos)} combos across {sum(len(v) for v in SUBJECTS.values())} subjects", flush=True)

    fh = jsonl.open("a", buffering=1)
    written = len(done_ids)
    started = time.time()
    last_log = started

    for i, (category, subject, style, topic, animation) in enumerate(combos):
        if written >= args.target:
            break
        pid = f"{i:05d}"
        if pid in done_ids:
            continue

        meta = META_PROMPT.format(
            element_label=ELEMENT_LABEL[category],
            subject=subject,
            style=style,
            topic=topic,
            animation=animation,
        )

        try:
            text = post_ollama(args.host, args.model, meta, args.temperature, args.num_predict)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"[err]  {pid} {category}/{subject}: {e} — retrying in 5s", flush=True)
            time.sleep(5)
            try:
                text = post_ollama(args.host, args.model, meta, args.temperature, args.num_predict)
            except Exception as e2:
                print(f"[skip] {pid}: {e2}", flush=True)
                continue

        if not text or len(text) < 60:
            print(f"[thin] {pid} produced {len(text)} chars — skipping", flush=True)
            continue

        record = {
            "id": pid,
            "category": category,
            "subject": subject,
            "style": style,
            "topic": topic,
            "animation": animation,
            "prompt": text,
            "model": args.model,
            "generated_at": datetime.now().astimezone().isoformat(),
        }
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        written += 1

        now = time.time()
        if now - last_log > 3 or written % 10 == 0:
            elapsed = now - started
            new_count = written - len(done_ids)
            rate = new_count / max(elapsed, 0.001)
            eta = (args.target - written) / max(rate, 0.001)
            print(f"[gen]  {written}/{args.target}  rate={rate:.2f}/s  eta={eta/60:.1f}m  last={category}/{subject}", flush=True)
            last_log = now

    fh.close()

    # Compile final JSON array for the website.
    all_records = []
    for line in jsonl.read_text().splitlines():
        if line.strip():
            try:
                all_records.append(json.loads(line))
            except Exception:
                pass
    final_json.write_text(json.dumps(all_records, ensure_ascii=False, indent=2))

    # Coverage report
    from collections import Counter
    cat_counter = Counter(r["category"] for r in all_records)
    sub_counter = Counter(r["subject"] for r in all_records)
    print(f"[done] {len(all_records)} prompts -> {final_json}")
    print(f"[done] categories: {dict(cat_counter)}")
    print(f"[done] subjects covered: {len(sub_counter)} / {sum(len(v) for v in SUBJECTS.values())}")
    print(f"[done] subject min/max: {min(sub_counter.values())} / {max(sub_counter.values())}")


if __name__ == "__main__":
    main()
