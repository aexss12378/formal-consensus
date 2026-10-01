"""所有提示詞與工具資料規格集中於此。"""

from __future__ import annotations

import json
from typing import Any, Iterable, Sequence

from ..core.schemas import Problem, public_pool_entry


GENERATION_SYSTEM_PROMPT = """You are one member of a three-model formal proof team.
Your task is to produce complete Lean 4 proof bodies for one fixed theorem.

The theorem header is fixed by the system. You may not rewrite, weaken, or replace it.
Use lean_check privately: it runs anything from an incomplete probe to a finished
proof against the fixed goal and never saves what you send. Use lean_submit only to
put a proof into the shared pool. When you
have no further candidate, call stop. Do not answer with prose instead of a tool call.

Inter-agent communication is Lean-only. The shared pool contains complete verified
proofs from earlier rounds. Do not include natural-language solution explanations,
plans, critiques, or comments in proof_body. Metadata fields required by the protocol
are allowed. The primary_technique label is shared with peers alongside each
verified proof in later rounds.

Every submitted candidate must completely prove the fixed theorem. Do not submit
fragments, helper lemmas, sorry, admit, axioms, opaque declarations, or modified
theorem statements.
"""


def format_shared_pool(shared_pool: Sequence[dict[str, Any]]) -> str:
    if not shared_pool:
        return "(empty: this is the independent first round)"
    blocks: list[str] = []
    for candidate in shared_pool:
        public = public_pool_entry(candidate)
        blocks.append(
            "\n".join(
                [
                    f"CANDIDATE {public['candidate_id']}",
                    f"round: {public['round']}",
                    f"method: {public['primary_technique']}",
                    "derived_from: "
                    + json.dumps(public["derived_from"], ensure_ascii=False),
                    "proof_body:",
                    "```lean",
                    public["proof_body"],
                    "```",
                ]
            )
        )
    return "\n\n".join(blocks)


def generation_user_prompt(
    problem: Problem,
    shared_pool: Sequence[dict[str, Any]],
    round_number: int,
    primary_techniques: Iterable[str],
    max_candidates: int,
) -> str:
    labels = "\n".join(f"- {label}" for label in primary_techniques)
    pool_text = format_shared_pool(shared_pool)
    return f"""ROUND
{round_number}

PROBLEM
{problem.problem_text}

FIXED LEAN IMPORTS
{chr(10).join(problem.lean_imports)}

FIXED THEOREM HEADER
```lean
{problem.lean_theorem_header}
```

SHARED VERIFIED PROOFS FROM EARLIER ROUNDS
{pool_text}

PRIMARY TECHNIQUE LABELS
Choose exactly one label for each submitted proof. The backend stores the label and
shares it with peers alongside the verified proof in later rounds.
{labels}

PROTOCOL
- Call exactly one tool in each response. Wait for its result before choosing the next
  tool.
- Use lean_check and lean_submit as needed.
- lean_check accepts an incomplete probe using exact?, apply?, simp?, rw?, aesop?, or
  library_search, and equally accepts a complete proof you want to test. Its result
  tells you whether the goal closes. Nothing sent to lean_check is ever saved.
- lean_submit must contain one complete proof and its candidate metadata. A successful
  verification automatically saves that candidate for this round.
- Save at most {max_candidates} candidates.
- action=new requires derived_from=[].
- action=derived requires one or more candidate IDs visible in the shared pool.
- Before calling lean_submit, compare your proof against every proof in the pool.
  Read what those proofs actually do; the method label its author assigned is not
  evidence that a proof differs from yours. Verify yours only when it reaches the
  goal by a route none of them takes. If yours does the same thing as one already
  in the pool -- even under a different name -- or if the one already there does it
  better, do not verify it.
- Saving nothing this round is a correct and expected outcome. You are not expected
  to contribute in every round. A round where the pool already covers everything you
  can prove should end with stop and no saved candidate.
- Aim for a small number of genuinely different methods, not an exhaustive search of
  Mathlib. After you have saved at least one candidate, call stop once about five
  further searches have failed to yield a new verified proof.
- Call stop when you have no further contribution from the current shared-pool
  snapshot, even when no candidate was saved. If this round adds a verified proof, the
  system may call you again with the changed pool in a later round.
"""


def generation_tools(
    primary_techniques: Sequence[str], max_candidates: int
) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "lean_check",
                "description": (
                    "Privately check any tactic body against the fixed theorem goal. "
                    "It may be an incomplete probe using Mathlib search or suggestion "
                    "tactics, or a complete proof you want to test before deciding "
                    "whether to submit it. The result tells you whether it closes the "
                    "goal. Nothing sent here is ever saved or shared."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "proof_body": {
                            "type": "string",
                            "description": (
                                "A Lean tactic body starting with by, such as "
                                "by\\n  exact?."
                            ),
                        }
                    },
                    "required": ["proof_body"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "lean_submit",
                "description": (
                    "Submit one proof to the shared pool. This is the submission "
                    "step, not the checking step: use lean_check to check a proof "
                    "first. Anything that passes here is saved to the pool "
                    "immediately and cannot be withdrawn. "
                    f"At most {max_candidates} verified candidates may be saved."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["new", "derived"],
                        },
                        "derived_from": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "primary_technique": {
                            "type": "string",
                            "enum": list(primary_techniques),
                        },
                        "proof_body": {
                            "type": "string",
                            "description": "A complete Lean proof term starting with by.",
                        },
                    },
                    "required": [
                        "action",
                        "derived_from",
                        "primary_technique",
                        "proof_body",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "stop",
                "description": (
                    "Finish this round after all intended candidates have been verified."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        },
    ]


METHOD_REVIEW_SYSTEM_PROMPT = """You are reviewing the claimed primary mathematical
technique of one already Lean-verified proof. Do not vote on mathematical truth; Lean
has already checked the fixed theorem. You must call review_method exactly once.

The primary technique is the one that determines the overall shape of the proof:
replace it and the proof has to be rewritten from the start. Algebraic manipulation
performed to simplify an expression -- factoring, cancelling, clearing denominators,
expanding -- is not the primary technique, however laborious that step is. A
technique that merely appears somewhere in the proof is not primary either.
"""


def method_review_prompt(
    problem: Problem, candidate: dict[str, Any]
) -> str:
    return f"""PROBLEM
{problem.problem_text}

FIXED THEOREM HEADER
```lean
{problem.lean_theorem_header}
```

CLAIMED PRIMARY TECHNIQUE
{candidate['primary_technique_claim']}

VERIFIED PROOF BODY
```lean
{candidate['proof_body']}
```

Choose pass when the claimed technique determines the overall shape of this proof,
questionable when it is present but a different technique determines the shape, and
fail when the label is inconsistent with the proof or forced.
"""


METHOD_REVIEW_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "review_method",
        "description": "Submit one blind method-label review.",
        "parameters": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["pass", "questionable", "fail"],
                },
                "reason": {"type": "string"},
            },
            "required": ["verdict", "reason"],
            "additionalProperties": False,
        },
    },
}


SELECTION_SYSTEM_PROMPT = """You are selecting one representative among multiple
Lean-verified proofs that have the same confirmed primary technique. Mathematical truth
is not under vote. Prefer the proof that most clearly represents the technique, is least
needlessly complex, and uses suitable dependencies. You must call select_representative
exactly once.
"""


def representative_selection_prompt(
    problem: Problem,
    technique: str,
    candidates: Sequence[dict[str, Any]],
) -> str:
    blocks = []
    for candidate in candidates:
        blocks.append(
            "\n".join(
                [
                    f"CANDIDATE {candidate['candidate_id']}",
                    "```lean",
                    candidate["proof_body"],
                    "```",
                ]
            )
        )
    return f"""PROBLEM
{problem.problem_text}

FIXED THEOREM HEADER
```lean
{problem.lean_theorem_header}
```

CONFIRMED PRIMARY TECHNIQUE
{technique}

CANDIDATES
{chr(10).join(blocks)}
"""


def representative_selection_tool(
    candidate_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "select_representative",
            "description": "Select exactly one representative candidate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_id": {
                        "type": "string",
                        "enum": list(candidate_ids),
                    },
                    "reason": {"type": "string"},
                },
                "required": ["candidate_id", "reason"],
                "additionalProperties": False,
            },
        },
    }


TRANSLATION_SYSTEM_PROMPT = """You turn one verified formal proof into the solution a
calculus teacher would write on the board for students. Write in English, in ordinary
mathematical language and notation, as numbered steps a student could reproduce on an
exam answer sheet. Never mention Lean, Mathlib, tactics, lemma names, or formal proof.
Follow the same mathematical argument as the given proof, using the given primary
technique; do not switch to a different method. You must call submit_solution exactly
once.
"""


def translation_prompt(problem: Problem, technique: str, proof_body: str) -> str:
    return f"""PROBLEM
{problem.problem_text}

PRIMARY TECHNIQUE
{technique}

VERIFIED PROOF (for your reference only; students never see it)
```lean
{problem.lean_theorem_header}
{proof_body}
```
"""


TRANSLATION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "submit_solution",
        "description": "Submit the step-by-step solution for students.",
        "parameters": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "One entry per numbered step, without the number.",
                },
            },
            "required": ["steps"],
            "additionalProperties": False,
        },
    },
}


FORMALIZATION_SYSTEM_PROMPT = """You write the Lean 4 + Mathlib theorem statement for one
calculus problem written by a teacher. A person will check your statement against the
problem before anyone tries to prove it, so faithfulness matters more than anything else.

Rules:
- Output only the theorem header: it starts with `theorem`, ends with `:=`, and has no
  proof. `import Mathlib` is already provided; do not add imports, definitions, or
  other declarations.
- State exactly what the problem asks to prove. Do not weaken, strengthen, or add
  hypotheses. Keep every quantifier, domain, and condition of the problem.
- Use real numbers (ℝ) unless the problem says otherwise.
- Remember Lean's conventions differ from textbook math: x / 0 = 0 and Real.sqrt of a
  negative number is 0. Write the statement so these conventions cannot change its
  meaning.

You must call submit_statement exactly once. If Lean rejects the statement, you will
see the error and may submit a corrected one.
"""


def formalization_prompt(problem_id: str, problem_text: str) -> str:
    return f"""PROBLEM ID
{problem_id}

PROBLEM
{problem_text}
"""


FORMALIZATION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "submit_statement",
        "description": "Submit the Lean theorem header for this problem.",
        "parameters": {
            "type": "object",
            "properties": {"lean_theorem_header": {"type": "string"}},
            "required": ["lean_theorem_header"],
            "additionalProperties": False,
        },
    },
}


BACK_TRANSLATION_SYSTEM_PROMPT = """You explain one Lean 4 + Mathlib theorem statement to a
calculus teacher who cannot read Lean. The teacher will compare your explanation with
the problem they wrote, so be literal: say exactly what this statement asserts, not what
it was probably meant to assert. Mention every variable and its type, every quantifier,
and every hypothesis. If Lean's conventions (for example x / 0 = 0, or Real.sqrt of a
negative number being 0) affect what the statement means, say so. Write in English,
without Lean syntax. You must call explain_statement exactly once.
"""


def back_translation_prompt(lean_theorem_header: str) -> str:
    return f"""LEAN STATEMENT
```lean
{lean_theorem_header}
```
"""


BACK_TRANSLATION_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "explain_statement",
        "description": "Explain in plain English what the Lean statement asserts.",
        "parameters": {
            "type": "object",
            "properties": {"explanation": {"type": "string"}},
            "required": ["explanation"],
            "additionalProperties": False,
        },
    },
}
