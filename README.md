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

The specification defines these elements as a **declaration**. It does not define an **enforcement mechanism**. Without one, the declaration ends up pasted into a prompt — and a prompt is a request, not a rule.

`sphragis` is a small, dependency-free evaluation layer that closes this gap: given a DocLang document and an intended operation, it returns a deterministic decision (`allow` / `allow_with_obligations` / `deny`) **before** any probabilistic processing happens. Obligations declared in the document (required transformations, audit logging, human-in-the-loop) are surfaced alongside the verdict so callers can act on them.

## Install
Opening this repository in VS Code or GitHub Codespaces uses the bundled dev container (.devcontainer/), which installs the package and the demo dependencies automatically — no manual setup needed.
To install manually instead:
```bash
pip install -e .
# optional: the reference validator for the documents themselves
pip install doclang
```

## Usage

```bash
# What does this document declare?
sphragis inspect examples/restricted_case.dclg.xml

# May I extract data from it, given the request touches personal data?
sphragis evaluate examples/restricted_case.dclg.xml --op extract --involves-pii
# -> {"verdict": "deny", "reasons": ["operation involves PII and pii_extraction_allowed is declared false"], ...}

# May I use this document for training?
sphragis evaluate examples/open_minimal.dclg.xml --op train
# -> {"verdict": "allow_with_obligations", "obligations": ["training_provenance_required"], ...}
```

As a library:

```python
from sphragis import Operation, evaluate, parse_governance

gov = parse_governance("document.dclg.xml")
decision = evaluate(gov, Operation.RAG_INDEX, strict=True)
```

## Design

- **Strict by default.** In `strict` posture, anything not explicitly permitted is denied. Pass `--permissive` to treat unspecified declarations as not-denied instead. Sensitive deployments should keep the default.
- **Declaration vs. enforcement.** The verdict is computed from the document's declared metadata only, with no model in the loop. What the caller does with the verdict (block, transform, log) is the caller's enforcement responsibility — this kit gives you a deterministic, auditable input to it.
- **Stdlib only.** The evaluator has zero runtime dependencies. Document validation is delegated to the reference validator (`doclang validate`).

## Scope and status

- Tracks the governance and compliance metadata of the DocLang specification **v0.4.0**. The spec is young and may change; this kit pins its interpretation to that version.
- Document-level metadata only. Component-level overrides (defined by the spec) are planned.
- Controlled vocabularies for enumerated values (e.g. `extraction_scope`) are organization-defined per the spec; this kit surfaces them as obligations rather than interpreting them.
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

## Related

- [Terminus](https://github.com/beachcities/terminus) — a concept note on the boundary of safe delegation: where machine-readable ends and "may the machine *use* it?" begins. The thinking behind this tool. (CC BY 4.0)

## License

Apache-2.0
