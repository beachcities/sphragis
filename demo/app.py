"""Sphragis policy simulator.

Interactive demo of the deterministic evaluation in ``sphragis.policy``:
change the document's declared governance and the requested operation,
and watch how the verdict is reached *before* any model is involved.

Run:
    pip install -r demo/requirements.txt
    streamlit run demo/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Allow running from a source checkout without installing the package.
_SRC = Path(__file__).resolve().parents[1] / "src"
if _SRC.exists():
    sys.path.insert(0, str(_SRC))

from sphragis import Governance, Operation, Verdict, evaluate, parse_governance  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"

PRESETS = {
    "Open Minimal": EXAMPLES / "open_minimal.dclg.xml",
    "Restricted Case": EXAMPLES / "restricted_case.dclg.xml",
    "Custom": None,
}

_TRISTATE = {"(not declared)": None, "true": "true", "false": "false"}

VERDICT_STYLE = {
    Verdict.ALLOW: ("✅ ALLOW", "green"),
    Verdict.ALLOW_WITH_OBLIGATIONS: ("✅ ALLOW — with obligations", "orange"),
    Verdict.DENY: ("⛔ DENY", "red"),
    Verdict.UNSPECIFIED: ("❔ UNSPECIFIED", "gray"),
}


def _tristate(label: str, key: str) -> str | None:
    return _TRISTATE[st.sidebar.radio(label, list(_TRISTATE), key=key, horizontal=True)]


def build_custom_governance() -> Governance:
    st.sidebar.caption("Each element below is a *declaration* in the document's <head>.")
    elements: dict[str, object] = {}
    fields = {
        "extraction_permitted": "extraction_permitted",
        "pii_extraction_allowed": "pii_extraction_allowed",
        "rag_permitted": "rag_permitted",
        "rag_indexing_allowed": "rag_indexing_allowed",
        "rag_pii_exposure_allowed": "rag_pii_exposure_allowed",
        "training_permitted": "training_permitted",
        "downstream_sharing_permitted": "downstream_sharing_permitted",
        "extraction_audit_required": "extraction_audit_required",
        "human_in_the_loop_required": "human_in_the_loop_required",
    }
    for name, key in fields.items():
        value = _tristate(name, key)
        if value is not None:
            elements[name] = value
    scope = st.sidebar.text_input("extraction_scope (optional)", value="")
    if scope.strip():
        elements["extraction_scope"] = scope.strip()
    return Governance(elements=elements)


def main() -> None:
    st.set_page_config(page_title="Sphragis policy simulator", page_icon="🔏")
    st.title("🔏 Sphragis policy simulator")
    st.caption(
        "DocLang governance metadata is a **declaration**. Sphragis turns it into a "
        "**deterministic decision** before any probabilistic processing happens. "
        "Change the declaration and the requested operation; watch the verdict."
    )

    st.sidebar.header("Document declaration")
    preset = st.sidebar.selectbox("Governance preset", list(PRESETS))
    if PRESETS[preset] is not None:
        gov = parse_governance(PRESETS[preset])
        with st.sidebar.expander("Declared elements", expanded=False):
            st.json(gov.elements)
    else:
        gov = build_custom_governance()

    st.sidebar.header("Requested operation")
    op = Operation(st.sidebar.selectbox("Operation", [o.value for o in Operation]))
    involves_pii = st.sidebar.toggle("Request touches personal data (involves_pii)", value=False)
    strict = st.sidebar.toggle("Strict posture (deny what is not explicitly permitted)", value=True)

    decision = evaluate(gov, op, strict=strict, involves_pii=involves_pii)
    label, color = VERDICT_STYLE[decision.verdict]

    st.subheader("Verdict")
    st.markdown(f"### :{color}[{label}]")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Reasons**")
        for r in decision.reasons or ["—"]:
            st.markdown(f"- {r}")
    with col2:
        st.markdown("**Obligations**")
        for o in decision.obligations or ["—"]:
            st.markdown(f"- {o}")

    st.divider()
    with st.expander("What this demonstrates", expanded=False):
        st.markdown(
            """
**1. Mechanical blocking beats contextual guessing.**
Set the operation to `extract` and turn *involves_pii* on. Even when
`extraction_permitted` is true, the request is denied unless
`pii_extraction_allowed` is explicitly true (or merely undeclared in
permissive posture). There is no room left for a model to decide,
probabilistically, that extraction "looks fine in context".

**2. Strict posture removes implicit permission.**
Request an operation the document does not declare, then flip the strict
toggle. Most leaks happen because something *was not forbidden*. In strict
posture, anything not explicitly permitted is denied — default-secure,
provable at the code level.

**3. Obligations are a controller, not a switch.**
Run a non-PII `extract` against the *Restricted Case* preset. The verdict is
`allow_with_obligations`, carrying constraints such as
`extraction_scope=tables_only` and `human_in_the_loop_required`. The decision
hands the downstream pipeline a *safe path*, not just a yes/no.
            """
        )

    st.caption(
        "The verdict is computed from the declaration alone — deterministic, "
        "auditable, and reproducible. A prompt is a request; this is a rule."
    )


if __name__ == "__main__":
    main()
