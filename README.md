# Trade State Lab

An AI-assisted educational showcase of reliable financial-data state before an AI handoff. All examples are synthetic; no employer systems, client data or production results are represented.

[Open the interactive showcase](https://saumya-saumya.github.io/trade-state-lab/)

## Decisions the lab makes visible

- Highest validated business version wins, rather than latest ingestion time.
- Cancellation remains part of the history; active filtering follows reconstruction.
- Exact replay preserves canonical business state.
- Different payloads for one business-event key trigger quarantine.
- Source namespaces and currencies remain separate.
- Missing or conflicting evidence makes the context packet ineligible.

## Run the Python checks

Python standard library only. From the repository root:

```text
python -m unittest -v test_trade_state.py
```

The included suite contains 18 tests. Refer to the dated machine-readable report in `test-results.json`; this is an educational check, not a throughput benchmark.

## Inspect the website locally

From the repository root:

```text
python -m http.server 8765
```

Open `http://localhost:8765/`. The browser runs the four examples locally. No model, cloud credentials or paid services are required.

## Scope and limitations

Small in-memory reconstruction using Python/SQLite and a browser implementation. Integer minor units; no FX conversion or cross-currency netting. Historical conflicting versions conservatively quarantine the whole trade. The JSON context packet is deterministic; no LLM is called and no model accuracy is measured. This does not establish distributed delivery guarantees, recovery durability, regulatory completeness or production capacity.

## Hosting

Buildless static website for GitHub Pages, published from `main` / root. The canonical metadata uses the intended Pages project URL; deployment is verified separately.

## Repository map

- `index.html`, `style.css`, `lab.js`: interactive showcase.
- `fixtures.json`: synthetic examples with expected browser outputs, also consumed by the Python tests.
- `trade_state.py`, `test_trade_state.py`: inspectable Python implementation and tests.
- `latest-state.sql`: latest-state query after validation.
- `trade-state-lab.zip`: self-contained Python/fixtures/tests download.
- `test-results.json`: dated verification report.

## Attribution

Personal showcase for Saumya S., created with AI assistance. Publication is not evidence of an independently completed skill demonstration or professional AI deployment. No employer endorsement is implied.
