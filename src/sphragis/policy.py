"""Deterministic policy evaluation over DocLang governance metadata.

DocLang governance metadata is a machine-readable *declaration* of policy.
It is not, by itself, an enforcement mechanism. This module is the missing
half: given a parsed declaration and an intended operation, it returns a
deterministic decision *before* any probabilistic (LLM) processing happens.

Two postures are supported:

* ``strict`` (default): anything the document does not explicitly permit
  is denied. This is the recommended posture for sensitive deployments.
* ``permissive``: anything the document does not explicitly forbid is
  allowed, with obligations surfaced when declared.
"""

from __future__ import annotations

from .model import Decision, Governance, Operation, Verdict

# For each operation: the gate elements (all must not be False; in strict
# mode all must be explicitly True) and the condition elements surfaced when
# present. Conditions split by meaning: `*_required` booleans are duties
# (obligations), `*_allowed` / `*_permitted` booleans declared false are
# prohibitions (constraints), and valued elements are scoped constraints.
_RULES: dict[Operation, dict[str, tuple[str, ...]]] = {
    Operation.EXTRACT: {
        "gates": ("extraction_permitted",),
        "obligations": (
            "extraction_scope",
            "extraction_purpose",
            "extraction_granularity",
            "extraction_transformation_required",
            "extraction_output_constraints",
            "extraction_audit_required",
            "extraction_audit_retention",
            "human_in_the_loop_required",
        ),
        "pii_gates": ("pii_extraction_allowed", "sensitive_data_extraction_allowed"),
    },
    Operation.RAG_INDEX: {
        "gates": ("rag_permitted", "rag_indexing_allowed"),
        "obligations": (
            "rag_embedding_scope",
            "rag_chunking_constraints",
            "rag_caching_allowed",
            "rag_cache_retention",
            "rag_audit_required",
            "rag_audit_retention",
            "rag_model_scope",
        ),
        "pii_gates": (),
    },
    Operation.RAG_RETRIEVE: {
        "gates": ("rag_permitted",),
        "obligations": (
            "rag_query_restrictions",
            "rag_output_attribution_required",
            "rag_output_transformation_required",
            "rag_audit_required",
        ),
        "pii_gates": ("rag_pii_exposure_allowed", "rag_sensitive_data_exposure_allowed"),
    },
    Operation.TRAIN: {
        "gates": ("training_permitted",),
        "obligations": (
            "training_scope",
            "training_purpose",
            "training_model_type",
            "training_data_retention",
            "training_transformation_required",
            "training_provenance_required",
            "training_audit_required",
            "training_audit_retention",
            "model_output_usage_constraints",
            "right_to_be_forgotten_applicability",
        ),
        "pii_gates": (),
    },
    Operation.SHARE_DOWNSTREAM: {
        "gates": ("downstream_sharing_permitted",),
        "obligations": ("downstream_usage_restrictions",),
        "pii_gates": (),
    },
}


def evaluate(
    gov: Governance,
    operation: Operation,
    *,
    strict: bool = True,
    involves_pii: bool = False,
) -> Decision:
    """Evaluate one operation against one document's declared governance.

    ``involves_pii`` should be True when the caller knows the concrete
    request would touch personal data (e.g. the requested fields include
    PII columns). When the document declares ``pii_status`` as present and
    the caller cannot rule PII out, pass True.
    """
    rules = _RULES[operation]
    reasons: list[str] = []
    obligations: list[str] = []
    constraints: list[str] = []

    # --- gates -----------------------------------------------------------
    explicit_allow = False
    undeclared_gates: list[str] = []
    for gate in rules["gates"]:
        value = gov.get_bool(gate)
        if value is False:
            return Decision(
                operation,
                Verdict.DENY,
                reasons=[f"{gate} is declared false"],
            )
        if value is True:
            explicit_allow = True
            reasons.append(f"{gate} is declared true")
        else:
            undeclared_gates.append(gate)
            reasons.append(f"{gate} is not declared")

    # --- PII gates -------------------------------------------------------
    if involves_pii:
        for gate in rules["pii_gates"]:
            value = gov.get_bool(gate)
            if value is False:
                return Decision(
                    operation,
                    Verdict.DENY,
                    reasons=[f"operation involves PII and {gate} is declared false"],
                )
            if value is None and strict:
                return Decision(
                    operation,
                    Verdict.DENY,
                    reasons=[
                        f"operation involves PII and {gate} is not declared (strict posture)"
                    ],
                )

    # --- unspecified handling ---------------------------------------------
    # In strict posture EVERY gate must be explicitly true: a partially
    # declared gate set (e.g. rag_permitted=true without rag_indexing_allowed)
    # must not slip through on the strength of one gate alone.
    if strict and undeclared_gates:
        if not explicit_allow:
            extra = "no explicit permission found (strict posture)"
        else:
            extra = (
                "gate(s) not explicitly permitted (strict posture): "
                + ", ".join(undeclared_gates)
            )
        return Decision(operation, Verdict.DENY, reasons=reasons + [extra])
    if not explicit_allow:
        return Decision(operation, Verdict.UNSPECIFIED, reasons=reasons)

    # --- conditions: obligations vs constraints ----------------------------
    for name in rules["obligations"]:
        declared = gov.get(name)
        if declared is None:
            continue
        as_bool = gov.get_bool(name)
        if name.endswith("_required"):
            # A duty to perform. False means "not required" and imposes
            # nothing; a non-boolean value is a duty with a parameter
            # (e.g. extraction_transformation_required=redact).
            if as_bool is True:
                obligations.append(name)
            elif as_bool is None:
                obligations.append(f"{name}={declared}")
        elif name.endswith(("_allowed", "_permitted")):
            # A permission. False is a prohibition the caller must honor
            # (e.g. rag_caching_allowed=false): surface it, never drop it.
            # True grants and imposes nothing.
            if as_bool is False:
                constraints.append(f"{name}=false")
            elif as_bool is None:
                constraints.append(f"{name}={declared}")
        else:
            # Scoped constraint values (scope, purpose, retention, ...).
            constraints.append(f"{name}={declared}")

    verdict = (
        Verdict.ALLOW_WITH_OBLIGATIONS
        if obligations or constraints
        else Verdict.ALLOW
    )
    return Decision(
        operation,
        verdict,
        reasons=reasons,
        obligations=obligations,
        constraints=constraints,
    )
