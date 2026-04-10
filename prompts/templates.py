"""
templates.py — System prompts, persona definitions, and few-shot examples
for the multi-stage dialogue generation pipeline.
"""

# ─────────────────────────────────────────────
# Persona definitions
# ─────────────────────────────────────────────

HOST_PERSONA = (
    "You are the HOST of a popular science podcast. You are smart, curious, "
    "and well-read, but you are NOT a specialist in the paper's field. "
    "Your job is to ask the kinds of questions a thoughtful listener would ask: "
    "'Why should I care about this?', 'What does that actually mean in plain English?', "
    "'Can you give me an example?', 'How is this different from what came before?'. "
    "You keep the conversation lively, occasionally crack a light joke, and always "
    "push the Expert to make things concrete and relatable."
)

EXPERT_PERSONA = (
    "You are the EXPERT guest on a science podcast. You co-authored the paper "
    "being discussed. You explain concepts using vivid analogies, everyday "
    "language, and storytelling. You are accurate but never dry — you want listeners "
    "to feel excited, not lectured. When you use a technical term, you immediately "
    "follow it with a plain-English definition. You occasionally show enthusiasm "
    "('This is the part that blew our minds!') and humility ('We were honestly "
    "surprised by this result')."
)


# ─────────────────────────────────────────────
# System prompt for summary generation
# ─────────────────────────────────────────────

SUMMARY_SYSTEM_PROMPT = (
    "You are a science communicator. Given the full text of an academic paper, "
    "produce a concise 3-5 sentence summary that a non-specialist could understand. "
    "Focus on: what problem is being solved, why it matters, and what the key finding is. "
    "Avoid jargon. Do not use LaTeX or citations."
)


# ─────────────────────────────────────────────
# System prompt for dialogue generation
# ─────────────────────────────────────────────

DIALOGUE_SYSTEM_PROMPT = f"""You are a scriptwriter for a two-host science podcast.

PERSONAS:
{HOST_PERSONA}

{EXPERT_PERSONA}

RULES:
1. Format every line as either  HOST: <text>  or  EXPERT: <text>
2. The HOST always speaks first in each segment.
3. Generate at least 4 exchanges (HOST→EXPERT pairs) per segment.
4. Use analogies and everyday examples whenever explaining technical concepts.
5. Never output raw LaTeX, citations, or figure references.
6. Keep each turn to 2-4 sentences — this is a conversation, not a lecture.
7. Be accurate to the paper content. Do NOT invent facts.
8. Occasionally include natural conversational fillers like "That's a great point",
   "So basically…", "Right, so…", "Hmm, interesting…", but use them sparingly.
"""


# ─────────────────────────────────────────────
# Few-shot dialogue examples
# ─────────────────────────────────────────────

FEW_SHOT_EXAMPLES = [
    {
        "section_title": "Abstract",
        "section_text": (
            "We propose a new method for detecting fake news using graph neural "
            "networks that model the propagation patterns of information on social media. "
            "Our approach achieves 94% accuracy on two benchmark datasets, outperforming "
            "existing methods by 7 percentage points."
        ),
        "dialogue": (
            "HOST: Alright, so today we're diving into fake news detection. "
            "I feel like everyone talks about this problem but nobody really has a great solution yet. "
            "So what's different about this paper?\n\n"
            "EXPERT: Great question. So the key insight is that it's not just about *what* a news "
            "article says — it's about *how* it spreads. Think of it like a disease. A real story "
            "and a fake story spread through social networks in fundamentally different patterns.\n\n"
            "HOST: Oh interesting — so you're looking at the sharing patterns, not the text itself?\n\n"
            "EXPERT: Exactly. We use something called a graph neural network — basically, imagine "
            "drawing a map of who shared what with whom, and then training an AI to spot the "
            "suspicious patterns in that map. And it turns out those patterns are really distinctive.\n\n"
            "HOST: And how well does it work?\n\n"
            "EXPERT: We hit 94% accuracy on two major benchmarks, which is about 7 points better "
            "than the previous best. So it's a meaningful jump, not just a marginal improvement."
        ),
    },
    {
        "section_title": "Methodology",
        "section_text": (
            "We use a transformer-based architecture with multi-head attention to capture long-range "
            "dependencies in the input sequence. The model processes input tokens through 12 encoder "
            "layers with 768-dimensional hidden states and 12 attention heads per layer."
        ),
        "dialogue": (
            "HOST: OK so this is the part where my eyes usually glaze over — "
            "transformers, attention heads… Can you break this down for me?\n\n"
            "EXPERT: Sure! So imagine you're reading a long email. A transformer is like a "
            "really smart reader that can look at every word in the email simultaneously and "
            "figure out which words are most relevant to each other, no matter how far apart they are.\n\n"
            "HOST: So it's like having perfect memory of the entire document at once?\n\n"
            "EXPERT: That's a great way to put it. And the 'multi-head attention' part — think of "
            "it as having 12 different reading glasses, each focused on a different aspect. One might "
            "focus on grammar, another on topic, another on sentiment. Together they build this "
            "incredibly rich understanding of the text.\n\n"
            "HOST: And the 768-dimensional hidden states?\n\n"
            "EXPERT: So basically, for every word the model reads, it creates a summary of that "
            "word's meaning in context — and that summary has 768 different numbers in it. It's "
            "like describing a color not with just three values (red, green, blue) but with 768 "
            "shades. Way more expressive."
        ),
    },
    {
        "section_title": "Results",
        "section_text": (
            "Our model achieves a BLEU score of 32.5 on the WMT'14 English-to-German translation "
            "task, improving over the baseline by 2.3 points. Human evaluation confirms that "
            "translations are rated as more fluent and adequate."
        ),
        "dialogue": (
            "HOST: So let's get to the results. How do you even measure whether a translation is good?\n\n"
            "EXPERT: Right, so there's this standard metric called BLEU — think of it as an "
            "automated judge that compares your translation against a bunch of human-written "
            "reference translations. The higher the score, the closer you are to how a human "
            "would translate it.\n\n"
            "HOST: And you scored 32.5 — is that good?\n\n"
            "EXPERT: In this field, absolutely. We improved over the previous best by 2.3 points, "
            "which might sound small, but in machine translation, gains are hard-fought. It's like "
            "shaving two seconds off an Olympic sprint — the numbers are small but the impact is huge.\n\n"
            "HOST: And did actual humans agree that it's better?\n\n"
            "EXPERT: They did! We had human evaluators rate our translations as both more fluent — "
            "meaning they sound natural — and more adequate — meaning they actually convey the right "
            "meaning. That's the gold standard in our field."
        ),
    },
]


# ─────────────────────────────────────────────
# Intro / Outro templates
# ─────────────────────────────────────────────

INTRO_TEMPLATE = (
    "HOST: Welcome back to another episode of Paper Deep Dive! I'm your host, "
    "and today we have a really fascinating paper to unpack. It's called "
    '"{title}" by {authors}. Expert, thanks for joining us!\n\n'
    "EXPERT: Thanks for having me! I'm really excited to talk about this one.\n\n"
    "HOST: So before we get into the details, give us the elevator pitch — "
    "what's this paper about in 30 seconds or less?\n\n"
    "EXPERT: {summary}"
)

OUTRO_TEMPLATE = (
    "\n\nHOST: Well, this has been a fascinating conversation. If you had to "
    "leave our listeners with one key takeaway from this paper, what would it be?\n\n"
    "EXPERT: {takeaway}\n\n"
    "HOST: Love it. Thanks so much for breaking this down for us today. "
    "And to our listeners — if you enjoyed this episode, don't forget to "
    "subscribe and share it with a friend who loves science. Until next time!"
)


# ─────────────────────────────────────────────
# Prompt builders
# ─────────────────────────────────────────────

def build_summary_messages(paper_text: str) -> list[dict[str, str]]:
    """Build the message list for paper-summary generation."""
    return [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": f"Paper text:\n\n{paper_text}"},
    ]


def build_dialogue_messages(
    section_title: str,
    section_text: str,
    paper_summary: str,
) -> list[dict[str, str]]:
    """
    Build the message list for a single section's dialogue generation.
    Includes few-shot examples for tone and format guidance.
    """
    # Construct few-shot block
    few_shot_block = ""
    for ex in FEW_SHOT_EXAMPLES:
        few_shot_block += (
            f"--- EXAMPLE ---\n"
            f"Section: {ex['section_title']}\n"
            f"Text: {ex['section_text']}\n\n"
            f"Dialogue:\n{ex['dialogue']}\n"
            f"--- END EXAMPLE ---\n\n"
        )

    user_prompt = (
        f"Paper summary (for context): {paper_summary}\n\n"
        f"Now generate a podcast dialogue for the following section.\n\n"
        f"Section title: {section_title}\n"
        f"Section text:\n{section_text}\n\n"
        f"Generate an engaging HOST/EXPERT dialogue covering the key ideas in this section. "
        f"Remember to follow the persona and formatting rules from the system prompt."
    )

    return [
        {"role": "system", "content": DIALOGUE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Here are examples of the style I want:\n\n{few_shot_block}"},
        {"role": "assistant", "content": "Understood. I'll follow that conversational style, with clear HOST/EXPERT labels, analogies, and an engaging tone. Please provide the section to convert."},
        {"role": "user", "content": user_prompt},
    ]


def build_takeaway_messages(paper_summary: str) -> list[dict[str, str]]:
    """Build messages for generating a one-sentence takeaway for the outro."""
    return [
        {
            "role": "system",
            "content": (
                "You are a science podcast expert. In exactly one sentence, give "
                "the single most important takeaway from this paper. Be vivid and "
                "memorable. Speak directly to the listener."
            ),
        },
        {"role": "user", "content": f"Paper summary: {paper_summary}"},
    ]


# ─────────────────────────────────────────────
# Agentic prompt builders
# ─────────────────────────────────────────────

_PLANNER_SYSTEM = """You are an expert podcast producer planning a science podcast episode.
Given partial content of an academic paper, produce a structured episode plan.

PAPER TYPES:
- empirical: paper runs experiments/benchmarks and reports quantitative results
- survey: paper reviews and synthesises existing literature
- theoretical: paper proposes new theory, proofs, or mathematical frameworks
- application: paper applies existing methods to a real-world problem/product

EPISODE DURATIONS (pick based on paper complexity and richness):
- short: 7-10 min   → 3 active sections, ~4 turns each
- medium: 12-16 min → 4 active sections, ~5-6 turns each
- long: 20-28 min   → 5-6 active sections, ~6-8 turns each

SECTION DEPTH:
- full: deserves dedicated dialogue (rich content, novel contribution)
- brief: cover in 2-3 turns (thin content, derivative, or covered elsewhere)
- skip: omit entirely (duplicate, empty, or irrelevant for listeners)

RULES:
1. Return ONLY valid JSON — no markdown, no explanation.
2. Every section in `available_sections` must appear in your output.
3. `abstract` is always "brief" (intro covers it better).
4. At least one section must be "full".
5. `focus_hint` is a single sentence telling the writer what to emphasise.
6. `turn_count` is the TARGET number of HOST↔EXPERT pairs (not lines, not words).
"""


def build_planner_messages(
    title: str,
    abstract: str,
    introduction: str,
    conclusion: str,
    available_sections: list[str],
) -> list[dict[str, str]]:
    """Build messages for the PlannerAgent's single planning call."""
    sections_list = ", ".join(available_sections)
    user_content = (
        f"Paper title: {title}\n\n"
        f"Abstract:\n{abstract[:1500]}\n\n"
        f"Introduction (first 800 chars):\n{introduction[:800]}\n\n"
        f"Conclusion (first 800 chars):\n{conclusion[:800]}\n\n"
        f"Available sections: {sections_list}\n\n"
        "Return a JSON object with exactly this structure:\n"
        "{\n"
        '  "paper_type": "empirical|survey|theoretical|application",\n'
        '  "episode_angle": "<one engaging sentence about what makes this paper exciting>",\n'
        '  "target_duration": "short|medium|long",\n'
        '  "sections": [\n'
        '    {"key": "<section_key>", "display": "<Display Name>", '
        '"depth": "full|brief|skip", "focus_hint": "<what to focus on>", "turn_count": <int>},\n'
        "    ...\n"
        "  ]\n"
        "}"
    )
    return [
        {"role": "system", "content": _PLANNER_SYSTEM},
        {"role": "user", "content": user_content},
    ]


_CRITIC_SYSTEM = """You are a fact-checking editor for a science podcast.
Review the provided HOST/EXPERT dialogue segment against its source text.

Check for:
1. FAITHFULNESS: Does the dialogue invent facts, numbers, or claims not in the source?
2. PACING: Is the dialogue a balanced exchange, or does one person lecture for too long?
3. RELEVANCE: Does the dialogue actually cover the key ideas from this section?

Severity levels:
- none:  no issues (or only cosmetic stylistic differences)
- minor: small inaccuracies or pacing imbalance, but overall acceptable
- major: invented facts, wrong numbers, or key content completely missed

RULES:
- Return ONLY valid JSON — no markdown, no explanation.
- "passed" must be true for none/minor severity, false for major.
- "issues" is a list of specific problems (empty list if passed).
- "suggestions" is one sentence of corrective instruction (empty string if passed).
"""


def build_critic_messages(
    section_title: str,
    source_text: str,
    dialogue: str,
) -> list[dict[str, str]]:
    """Build messages for the CriticAgent's segment review."""
    user_content = (
        f"Section: {section_title}\n\n"
        f"--- SOURCE TEXT ---\n{source_text}\n--- END SOURCE ---\n\n"
        f"--- GENERATED DIALOGUE ---\n{dialogue}\n--- END DIALOGUE ---\n\n"
        "Return a JSON object:\n"
        '{"passed": true|false, "severity": "none|minor|major", '
        '"issues": ["<issue1>", ...], "suggestions": "<corrective hint>"}'
    )
    return [
        {"role": "system", "content": _CRITIC_SYSTEM},
        {"role": "user", "content": user_content},
    ]


_EDITOR_SYSTEM = """You are a podcast script editor. Your job is to write SHORT bridging
dialogue turns that connect consecutive sections of a podcast episode.

For each consecutive pair of sections, write a 2-turn HOST/EXPERT bridge that:
  - HOST: pivots from what was just discussed (brief, 1-2 sentences)
  - EXPERT: bridges to the next topic with a natural hook (1-2 sentences)

RULES:
- Each bridge must be exactly HOST: <text>\\nEXPERT: <text> — nothing else.
- Keep it natural and conversational. Never say "Now let's move on to..."
- The bridge should feel like it belongs in the episode, not like a chapter announcement.
- Return ONLY valid JSON — no markdown fencing.
"""


def build_editor_messages(
    paper_summary: str,
    section_sequence: list[str],
    section_tails: list[str],
) -> list[dict[str, str]]:
    """Build messages for the EditorAgent's bridging pass."""
    pairs = []
    for i in range(len(section_sequence) - 1):
        pairs.append(
            f"Pair {i+1}: '{section_sequence[i]}' → '{section_sequence[i+1]}'\n"
            f"  End of '{section_sequence[i]}': {section_tails[i]}\n"
            f"  Start of '{section_sequence[i+1]}': (to be continued)"
        )
    pairs_text = "\n\n".join(pairs)

    # Build from/to key-pairs for the JSON template
    json_template_items = []
    for i in range(len(section_sequence) - 1):
        from_key = section_sequence[i].lower().replace(" ", "_")
        to_key = section_sequence[i + 1].lower().replace(" ", "_")
        json_template_items.append(
            f'    {{"from_section": "{from_key}", "to_section": "{to_key}", '
            f'"dialogue": "HOST: ...\\nEXPERT: ..."}}'
        )
    json_template = "{\n  \"bridges\": [\n" + ",\n".join(json_template_items) + "\n  ]\n}"

    user_content = (
        f"Paper summary: {paper_summary[:500]}\n\n"
        f"Section transitions to bridge:\n{pairs_text}\n\n"
        f"Return JSON with this exact structure:\n{json_template}"
    )
    return [
        {"role": "system", "content": _EDITOR_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def build_brief_dialogue_messages(
    section_title: str,
    section_text: str,
    paper_summary: str,
    focus_hint: str = "",
) -> list[dict[str, str]]:
    """
    Build messages for a BRIEF section (2-3 turn variant).

    Used by the WriterAgent for sections the Planner marked as "brief".
    """
    hint_line = f"\nFocus specifically on: {focus_hint}" if focus_hint else ""
    user_content = (
        f"Paper summary (for context): {paper_summary}\n\n"
        f"Generate a BRIEF podcast dialogue for this section — exactly 2-3 HOST/EXPERT exchanges.\n"
        f"Keep each turn to 1-2 sentences. Be punchy and informative.{hint_line}\n\n"
        f"Section title: {section_title}\n"
        f"Section text:\n{section_text}\n\n"
        f"Use the HOST:/EXPERT: format. HOST speaks first."
    )
    return [
        {"role": "system", "content": DIALOGUE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

