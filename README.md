# Sphragis

[![CI](https://github.com/beachcities/sphragis/actions/workflows/ci.yml/badge.svg)](https://github.com/beachcities/sphragis/actions/workflows/ci.yml)

> ἐσθλῶν μὲν γὰρ ἄπ᾽ ἐσθλὰ μαθήσεαι· ἢν δὲ κακοῖσι συμμίσγῃς, ἀπολεῖς καὶ τὸν ἐόντα νόον.
> *From the good you will learn good things; mix with the bad, and you will lose even the sense you have.*
> — Theognis, *Elegies* 35–36 — named by Aristotle at *Nicomachean Ethics* IX.9, 1170a11–12; quoted at IX.12, 1172a13–14

> λήσει δ᾽ οὔποτε κλεπτόμενα.
> *Stolen, they will never go unnoticed.*
> — Theognis, *Elegies* 19–23 — the original σφραγίς (sphragis), the poet's seal of provenance

Deterministic evaluation of [DocLang](https://github.com/doclang-project/doclang) governance and compliance metadata.

**Sphragis** (σφραγίς, /ˈsfrɑː.ɡɪs/ — "SFRAH-gis"; Ancient Greek [spʰraːɡís]): the seal that travels with a document, guaranteeing where it came from and that it has not been quietly altered. Theognis declared the first one in the 6th century BC — and his corpus still became the most interpolated text of archaic Greece. A declaration without a verification mechanism does not protect anything. This toolkit is the verification mechanism.

## Why

DocLang documents can carry machine-readable governance metadata in their `<head>`: licensing, data classification, PII posture, and per-operation controls for extraction, RAG, and model training (`extraction_permitted`, `rag_indexing_allowed`, `training_permitted`, ...).

The specification defines these elements — today in its *Future Extensions* section (informative; Appendix C in v0.4) — as a **declaration**. It does not define an **enforcement mechanism**. Without one, the declaration ends up pasted into a prompt — and a prompt is a request, not a rule.

`sphragis` is a small, dependency-free evaluation layer that closes this gap: given a DocLang document and an intended operation, it returns a deterministic decision (`allow` / `allow_with_obligations` / `deny`) **before** any probabilistic processing happens. Obligations declared in the document (required transformations, audit logging, human-in-the-loop) are surfaced alongside the verdict so callers can act on them.

## Install
Opening this repository in VS Code or GitHub Codespaces uses the bundled dev container (.devcontainer/), which installs the package and the demo dependencies automatically — no manual setup needed.
To install manually instead:
```bash
pip install -e .
# optional: the reference validator for the documents themselves
# (since toolkit v0.7.1 the Schematron backend is opt-in)
pip install "doclang[schematron-saxon]"
```

## Usage

```bash
# What does this document declare?
sphragis inspect examples/restricted_case.dclg

# May I extract data from it, given the request touches personal data?
sphragis evaluate examples/restricted_case.dclg --op extract --involves-pii
# -> {"verdict": "deny", "reasons": ["operation involves PII and pii_extraction_allowed is declared false"], ...}

# May I use this document for training?
sphragis evaluate examples/open_minimal.dclg --op train
# -> {"verdict": "allow_with_obligations", "obligations": ["training_provenance_required"], ...}
```

As a library:

```python
from sphragis import Operation, evaluate, parse_governance

gov = parse_governance("document.dclg")
decision = evaluate(gov, Operation.RAG_INDEX, strict=True)
```

## Design

- **Strict by default.** In `strict` posture, anything not explicitly permitted is denied — for a multi-gate operation (e.g. `rag_index`), *every* gate must be explicitly true. Pass `--permissive` to treat unspecified declarations as not-denied instead. Sensitive deployments should keep the default.
- **Declaration vs. enforcement.** The verdict is computed from the document's declared metadata only, with no model in the loop. What the caller does with the verdict (block, transform, log) is the caller's enforcement responsibility — this kit gives you a deterministic, auditable input to it.
- **Duties, prohibitions, and grants are kept apart.** The decision separates `obligations` (duties to perform, e.g. `rag_audit_required`) from `constraints` (restrictions to honor: declared prohibitions such as `rag_caching_allowed=false`, and scoped values such as `extraction_scope=tables_only`). A permission declared true, or a requirement declared false, imposes nothing — it never masquerades as an obligation. The verdict name `allow_with_obligations` is kept for wire compatibility; read it as *allow, with conditions attached* (obligations and/or constraints).
- **Stdlib only.** The evaluator has zero runtime dependencies. Document validation is delegated to the reference validator (`doclang validate`).

## Scope and status

- Tracks the governance and compliance metadata of DocLang specification version **0.7** (reference toolkit **v0.7.3**, July 2026 — the two are versioned separately). This metadata lives in the spec's *Future Extensions* section (informative, not yet normative; titled Appendix C in v0.4); the governance vocabulary and policy controls are substantively unchanged from spec 0.4 (toolkit v0.4.0) through spec 0.7 (toolkit v0.7.3), so this kit's interpretation — originally pinned at v0.4.0 — remains current. The spec is young and may change.
- The document root's `version` attribute is checked on parse: a declared spec version outside 0.4–0.7 is rejected (`UnsupportedSpecVersionError`; the CLI reports it as a JSON error with exit code 2); a missing attribute is tolerated.
- Elements are recognized in the empty namespace and the official DocLang namespace (`https://www.doclang.ai/ns/v0`) only; foreign-namespace elements are ignored. The root element must be `<doclang>` in one of those namespaces — anything else is refused (`NotADocLangDocumentError`, reported by the CLI as a JSON error with exit code 2).
- Since spec 0.7 the recommended file extensions are `.dclg` (document) and `.dclx` (archive). The bundled examples use `.dclg`; the evaluator does not depend on the extension.
- The bundled examples are valid DocLang 0.7 documents: CI validates them with the reference toolkit's **XSD and Schematron** checks (`doclang validate`, toolkit v0.7.3). The governance elements they carry come from the spec's informative *Future Extensions* section, and the current 0.7 schema accepts them inside `<head>` — so a separate schema-exempt fixture set is not needed today. Should a future schema tighten `<head>`, governance fixtures will be split from the schema-validated fixtures and the split documented here and in CI.
- Document-level metadata only. Component-level overrides (defined by the spec) are planned.
- Controlled vocabularies for enumerated values (e.g. `extraction_scope`) are organization-defined per the spec; this kit surfaces them as constraints rather than interpreting them.
- This is an independent project, not affiliated with the DocLang project or the LF AI & Data Foundation.

## Demo

An interactive simulator of the policy evaluation lives in `demo/` (kept
separate so the core stays dependency-free):

```bash
pip install -r demo/requirements.txt
streamlit run demo/app.py
```

Pick a governance preset (or build a custom declaration), choose an
operation, and watch how the verdict is reached — including the PII gates,
the strict-posture handling of undeclared elements, and the obligations
attached to an allow.

## Tests

```bash
python3 -m unittest discover -s tests
```

CI additionally builds the wheel, installs it into a clean environment, and
runs `scripts/cli_smoke.sh` against the installed CLI (inspect, the three
verdict paths, and the JSON error paths), plus Ruff, mypy, DocLang XSD and
Schematron validation of the examples, and a check that no reference to the
legacy double extension (`.dclg` + `.xml`) remains anywhere in the repo.

## Related

- [Terminus](https://github.com/beachcities/terminus) — a concept note on the boundary of safe delegation: where machine-readable ends and "may the machine *use* it?" begins. The thinking behind this tool. (CC BY 4.0)

## License

Apache-2.0
