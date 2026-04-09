# Analyze Paper (Claude CLI)

Analyze a paper JSON file from the corpus and produce a structured JSON dossier for proposal writing.

## Arguments

The user provides:

1. A paper JSON file path (from `workspace/corpus/`), or a paper title keyword to search for.

If no argument is given, list all available papers in the corpus and ask the user to pick one.

## Corpus Location

```
/root/opencute/slides/2026.04_todo_yjp-ktbg/workspace/corpus/
```

## Input JSON Fields

Each corpus JSON contains: `title`, `authors`, `year`, `venue`, `abstract`, `body_text`, `doi`, `citation_count`, `relevance_score`, `relevance`, `matched_keywords`.

## Workflow

1. Locate the target JSON file:
   - If a file path is given, read it directly.
   - If a keyword is given, search `ls workspace/corpus/` for matching filenames.
   - If nothing is given, list all files in `workspace/corpus/` and ask the user to pick.

2. Read the JSON file. Analyze `abstract` and `body_text` fields thoroughly.

3. Output **only** a single JSON object (no markdown, no prose wrapper). The JSON must be valid and parseable.

## Output Format

```json
{
  "title": "<original English title>",
  "authors": "<authors>",
  "year": 2025,
  "venue": "<venue>",
  "doi": "<doi>",

  "research_purpose": "用中文概括研究目的（1-3句话）",
  "research_significance": "用中文阐述研究意义（2-4句话）",

  "contributions": [
    {
      "point": "贡献点的中文概括",
      "evidence": "支持该贡献点的原文关键句（英文原文摘录）"
    }
  ],

  "theme_primary": "<主题簇编号和名称>",
  "theme_secondary": "<次要主题簇，或 null>",
  "workstream_fit": "<1 或 2 或 3>",
  "is_close_baseline_to_cute": false,

  "key_technique": "从 methodology 中提取的关键技术/方法（中文，2-4句话，包含具体设计细节）",
  "key_results": "主要实验结果/性能数据（中文，2-3句话，包含具体数值）",
  "gap_identified": [
    {
      "gap": "该论文承认的局限性或未解决问题的中文概括（1-2句话）",
      "evidence": "论文原文中支撑该 gap 的直接引用（英文原文摘录，从 conclusion/future work/limitations 段落提取）",
      "relevance_to_cute": "该 gap 与 CUTE 三项工作的关联（中文，1-2句话，说明对哪项工作有启发）"
    }
  ],

  "proposal_evidence": {
    "for_state_of_art": "该论文在国内外研究现状中可作为什么论据（中文，2-3句话，说明该论文代表了什么技术路线的什么水平）",
    "for_gap": "该论文揭示的研究空白分析（中文，2-3句话，具体说明：1）什么问题未被解决；2）为什么现有方案不够；3）这对开题报告的 gap 论证有何支撑）",
    "for_feasibility": "该论文的实验数据/方法对可行性的佐证（中文，2-3句话，具体说明：1）该论文的什么实验结果/性能数据可引用；2）该数据对哪项工作的可行性有何支撑；3）如有关键数字请一并给出）"
  }
}
```

## Theme Clusters (主题簇)

When assigning `theme_primary` and `theme_secondary`, choose from these 9 clusters:

1. CPU-side AI acceleration / in-core accelerator
2. Matrix extension / AMX / SME
3. Vector extension / RVV / vector AI enhancement
4. RISC-V custom ISA / open ISA AI extension
5. LLM / Transformer / inference acceleration
6. Quantization / mixed precision / FP8 / BF16 / block scale / mx
7. Compiler / tensor IR / operator generation
8. Memory hierarchy / scratchpad / dataflow / systolic
9. HBM / advanced packaging / multi-node system

Format: `"1. CPU-side AI acceleration"` or `"3. Vector extension / RVV"`.

## Workstream Mapping (工作映射)

Assign `workstream_fit` based on theme and content:

- **"1"** — CPU 矩阵算力扩展 (CUTE): clusters 1, 2, 4, 5, 6, 8 or papers about matrix/tensor extensions, CPU-side accelerators, quantization on CPU, scratchpad/memory optimization
- **"2"** — RVV AI 向量增强 + AI 辅助算子生成: clusters 3, 4, 7 or papers about vector extensions, RISC-V ISA, compiler/operator generation
- **"3"** — HBM + 高级封装 + 多节点 AI-CPU 系统架构: clusters 9, 5 or papers about HBM, packaging, multi-node systems, large-scale inference

A paper may primarily fit one workstream. If it spans multiple, pick the dominant one.

## `is_close_baseline_to_cute` Rules

Set `true` only if the paper is a **direct baseline** to CUTE work:
- Proposes a CPU matrix/tensor extension (AMX, SME, custom matrix unit)
- Implements an in-core accelerator for AI on RISC-V or similar ISA
- Designs a scratchpad-based data flow for matrix operations inside a CPU core

Otherwise set `false`.

## Rules

- Output **only** valid JSON. No markdown fences, no prose, no commentary before or after. Start with `{` and end with `}`.
- **CRITICAL**: In Chinese text fields, do NOT use ASCII double quotes `"` (U+0022) for emphasis or quotation — use Chinese quotation marks `「」` instead. ASCII `"` inside a JSON string value will break parsing.
- Analysis must be based on the actual paper text. Do NOT fabricate or hallucinate content.
- `evidence` fields must be direct quotes from the original English text.
- Chinese summaries should be concise and accurate; keep proper nouns in English.
- If the paper text is insufficient to extract a field, use `"信息不足，无法从文本中提取"`.
- For contributions, extract 2-5 key points only. Quality over quantity.
- `gap_identified` must be an array of 1-5 items, each from the paper's own conclusion/future work/limitations, not invented.
- `proposal_evidence.for_gap` and `for_feasibility` should be substantive (2-3 sentences each) with specific data/arguments, not vague one-liners.
