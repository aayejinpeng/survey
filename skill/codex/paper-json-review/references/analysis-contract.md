# Target Dossier Contract

The generated dossier JSON being reviewed should match this top-level shape:

```json
{
  "title": "string",
  "authors": "string",
  "year": 2025,
  "venue": "string",
  "doi": "string",
  "research_purpose": "string",
  "research_significance": "string",
  "contributions": [
    {
      "point": "string",
      "evidence": "string"
    }
  ],
  "theme_primary": "string",
  "theme_secondary": "string or null",
  "workstream_fit": "1 | 2 | 3",
  "is_close_baseline_to_cute": false,
  "key_technique": "string",
  "key_results": "string",
  "gap_identified": [
    {
      "gap": "string",
      "evidence": "string",
      "relevance_to_cute": "string"
    }
  ],
  "proposal_evidence": {
    "for_state_of_art": "string",
    "for_gap": "string",
    "for_feasibility": "string"
  }
}
```

## Required interpretation rules

### Evidence fields

- `contributions[].evidence` and `gap_identified[].evidence` must be direct English quotes from the paper.
- Quotes should come from the paper text, not from invented summaries.

### Theme clusters

Use exactly one of these strings:

1. `1. CPU-side AI acceleration / in-core accelerator`
2. `2. Matrix extension / AMX / SME`
3. `3. Vector extension / RVV / vector AI enhancement`
4. `4. RISC-V custom ISA / open ISA AI extension`
5. `5. LLM / Transformer / inference acceleration`
6. `6. Quantization / mixed precision / FP8 / BF16 / block scale / mx`
7. `7. Compiler / tensor IR / operator generation`
8. `8. Memory hierarchy / scratchpad / dataflow / systolic`
9. `9. HBM / advanced packaging / multi-node system`

### Workstream mapping

- `1`: CPU matrix compute extension (CUTE), matrix/tensor extensions, CPU-side accelerators, quantization on CPU, scratchpad/memory optimization
- `2`: RVV AI vector enhancement and AI-assisted operator generation, vector extensions, RISC-V ISA, compiler/operator generation
- `3`: HBM, advanced packaging, multi-node AI-CPU systems

Pick the dominant workstream only.

### `is_close_baseline_to_cute`

Set `true` only when the paper is a direct baseline to CUTE work, such as:

- a CPU matrix/tensor extension
- an in-core AI accelerator on RISC-V or similar ISA
- a scratchpad-based matrix dataflow inside a CPU core

Otherwise set `false`.

## Common review failure modes

- Metadata copied incorrectly from the corpus paper
- English evidence quote not present in the paper text
- Chinese summary adds claims absent from the paper
- Numerical results copied with wrong baseline, unit, or multiplier
- `proposal_evidence` turns a mild discussion point into a strong claim
- Theme/workstream classification chosen by keyword match but not by paper focus
- `is_close_baseline_to_cute` set too aggressively
