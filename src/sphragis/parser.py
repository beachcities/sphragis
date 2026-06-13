"""Parse governance and compliance metadata from a DocLang document.

Per the DocLang specification, governance and compliance metadata MUST be
expressed at the document level inside ``<head>`` (and MAY be overridden at
component level; component-level overrides are not yet implemented here).

This parser is deliberately tolerant: it reads what is present and reports
it. Validation of the document itself should be done with the reference
validator (``pip install doclang`` -> ``doclang validate``).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .model import Governance

# Element names defined in the DocLang spec (v0.4.0), "Governance and
# compliance metadata". Grouped here for reference and for `inspect`.
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


def parse_governance(path: str | Path) -> Governance:
    """Extract document-level governance metadata from a ``.dclg.xml`` file."""
    tree = ET.parse(str(path))
    root = tree.getroot()
    head = root.find("head")
    gov = Governance()
    if head is None:
        return gov

    for child in head:
        tag = child.tag
        if tag in _CONTAINERS:
            item_tag = _CONTAINERS[tag]
            values = [
                (item.text or "").strip()
                for item in child.iter(item_tag)
                if (item.text or "").strip()
            ]
            if values:
                gov.elements[tag] = values
        elif tag in KNOWN_ELEMENTS:
            gov.elements[tag] = _text_with_unit(child)
        # Non-governance head elements (title, date, ...) are ignored here.

    return gov
