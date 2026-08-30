"""Parse governance and compliance metadata from a DocLang document.

Per the DocLang specification's *Future Extensions* section (informative;
titled Appendix C in v0.4), governance and compliance metadata MUST be
expressed at the document level
inside ``<head>`` (and MAY be overridden at component level; component-level
overrides are not yet implemented here).

This parser is deliberately tolerant: it reads what is present and reports
it. Validation of the document itself should be done with the reference
validator (``pip install "doclang[schematron-saxon]"`` -> ``doclang validate``).
Elements in no namespace or in the official DocLang namespace
(``https://www.doclang.ai/ns/v0``) are recognized; elements in any other
namespace are ignored rather than mistaken for governance declarations.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .model import Governance

# The DocLang *specification* version whose governance appendix this kit
# tracks (distinct from the reference-toolkit release, currently v0.7.3).
SPEC_VERSION = "0.7"

# Spec versions across which the governance vocabulary and policy controls
# are substantively unchanged (spec 0.4 / toolkit v0.4.0 through spec 0.7 /
# toolkit v0.7.3).
SUPPORTED_SPEC_VERSIONS: frozenset[str] = frozenset({"0.4", "0.5", "0.6", "0.7"})

# The official DocLang XML namespace (the spec's optional default xmlns).
DOCLANG_NAMESPACE = "https://www.doclang.ai/ns/v0"

_ALLOWED_NAMESPACES: frozenset[str] = frozenset({"", DOCLANG_NAMESPACE})


class UnsupportedSpecVersionError(ValueError):
    """The document's root declares a spec version this kit does not track."""


# Element names listed in the DocLang spec's "Governance and compliance
# metadata" (Future Extensions). Grouped here for reference and for `inspect`.
GOVERNANCE_GROUPS: dict[str, tuple[str, ...]] = {
    "licensing_compliance": (
        "licenses",
        "compliance_requirements",
    ),
    "classification_access": (
        "data_classification",
        "acceptable_use",
        "stewardship",
        "access_policy",
        "retention_policy",
        "access_control_level",
    ),
    "pii": (
        "pii_status",
        "pii_sensitivity_level",
        "pii_source_type",
        "controller_processor_role",
        "pii_processing_purpose",
        "pii_lawful_basis",
        "special_category_condition",
        "pii_minimisation_status",
        "pii_transformation_level",
        "reidentification_risk",
        "ai_use_restriction",
        "cross_border_transfer_status",
        "transfer_mechanism",
        "retention_category",
        "dsr_impact_flag",
        "dpia_required",
        "children_pii_present",
        "automated_decisioning_relevance",
        "logging_monitoring_enabled",
    ),
    "extraction": (
        "extraction_permitted",
        "extraction_scope",
        "extraction_purpose",
        "extraction_granularity",
        "pii_extraction_allowed",
        "sensitive_data_extraction_allowed",
        "extraction_transformation_required",
        "extraction_output_constraints",
        "downstream_sharing_permitted",
        "downstream_usage_restrictions",
        "extraction_audit_required",
        "extraction_audit_retention",
        "human_in_the_loop_required",
        "automated_decisioning_dependency",
    ),
    "rag": (
        "rag_permitted",
        "rag_indexing_allowed",
        "rag_embedding_scope",
        "rag_chunking_constraints",
        "rag_query_restrictions",
        "rag_output_attribution_required",
        "rag_output_transformation_required",
        "rag_pii_exposure_allowed",
        "rag_sensitive_data_exposure_allowed",
        "rag_downstream_sharing_permitted",
        "rag_caching_allowed",
        "rag_cache_retention",
        "rag_audit_required",
        "rag_audit_retention",
        "rag_model_scope",
    ),
    "training": (
        "training_permitted",
        "training_scope",
        "training_purpose",
        "training_model_type",
        "training_data_retention",
        "training_dataset_reuse_allowed",
        "training_derivative_sharing_permitted",
        "training_pii_included",
        "training_sensitive_data_included",
        "training_transformation_required",
        "training_provenance_required",
        "training_audit_required",
        "training_audit_retention",
        "model_output_usage_constraints",
        "right_to_be_forgotten_applicability",
    ),
}

KNOWN_ELEMENTS: frozenset[str] = frozenset(
    name for group in GOVERNANCE_GROUPS.values() for name in group
)

# Container elements whose children we flatten into lists of text values.
_CONTAINERS = {
    "licenses": "license",
    "compliance_requirements": "compliance_req",
    "data_classification": "data_class",
    "acceptable_use": "purpose",
}


def _text_with_unit(elem: ET.Element) -> str:
    text = (elem.text or "").strip()
    unit = elem.get("unit")
    return f"{text} {unit}" if unit else text


def _local(tag: object) -> str:
    """Local name of a tag in an accepted namespace, else ``""``.

    Accepted namespaces are the empty namespace and the official DocLang
    namespace; a tag in any other namespace yields ``""`` so it is never
    mistaken for a governance declaration.
    """
    if not isinstance(tag, str):  # comments / processing instructions
        return ""
    if tag.startswith("{"):
        namespace, _, local = tag[1:].partition("}")
        return local if namespace in _ALLOWED_NAMESPACES else ""
    return tag


def parse_governance(path: str | Path) -> Governance:
    """Extract document-level governance metadata from a ``.dclg`` /
    ``.dclg.xml`` file.

    The root's ``version`` attribute, when present, is checked against the
    spec versions this kit tracks (``SUPPORTED_SPEC_VERSIONS``) and surfaced
    as ``Governance.spec_version``; an unsupported declared version raises
    :class:`UnsupportedSpecVersionError`. A missing attribute is tolerated.
    """
    tree = ET.parse(str(path))
    root = tree.getroot()

    spec_version = root.get("version")
    if spec_version is not None and spec_version not in SUPPORTED_SPEC_VERSIONS:
        raise UnsupportedSpecVersionError(
            f"document declares spec version {spec_version!r}; "
            f"this kit tracks {SPEC_VERSION} "
            f"(supported: {', '.join(sorted(SUPPORTED_SPEC_VERSIONS))})"
        )

    head = next((child for child in root if _local(child.tag) == "head"), None)
    gov = Governance(spec_version=spec_version)
    if head is None:
        return gov

    for child in head:
        tag = _local(child.tag)
        if tag in _CONTAINERS:
            item_tag = _CONTAINERS[tag]
            values = [
                (item.text or "").strip()
                for item in child.iter()
                if _local(item.tag) == item_tag and (item.text or "").strip()
            ]
            if values:
                gov.elements[tag] = values
        elif tag in KNOWN_ELEMENTS:
            gov.elements[tag] = _text_with_unit(child)
        # Non-governance head elements (title, date, ...) are ignored here.

    return gov
