#!/usr/bin/env python3
"""Web server for reviewing LLM-generated corpus alongside PDF papers."""

import argparse
import json
import os
from flask import Flask, jsonify, render_template_string, request, send_file

BASE = os.path.dirname(os.path.abspath(__file__))

parser = argparse.ArgumentParser(description="Survey Corpus Reviewer")
parser.add_argument("--topic", default="cpu-ai", help="Topic directory name under data/topics/ (default: cpu-ai)")
parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
args = parser.parse_args()

TOPIC = args.topic
CORPUS_DIR = os.path.join(BASE, "data", "topics", TOPIC, "corpus")
PDF_DIR = os.path.join(BASE, "pdfs", TOPIC)
LLM_DIR = os.path.join(CORPUS_DIR, "llm")
DRAFT_DIR = os.path.join(CORPUS_DIR, "draft")
HUMAN_DIR = os.path.join(CORPUS_DIR, "human_review")
os.makedirs(HUMAN_DIR, exist_ok=True)

app = Flask(__name__)


def _basename_no_ext(filename):
    name = filename
    for suffix in (".review.json", ".revised.json", ".json", ".pdf"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name


def _list_papers():
    papers = {}
    if os.path.isdir(PDF_DIR):
        for f in os.listdir(PDF_DIR):
            if f.endswith(".pdf"):
                bn = _basename_no_ext(f)
                papers.setdefault(bn, {})["pdf"] = f
    if os.path.isdir(LLM_DIR):
        for model in sorted(os.listdir(LLM_DIR)):
            model_dir = os.path.join(LLM_DIR, model)
            if not os.path.isdir(model_dir):
                continue
            for f in os.listdir(model_dir):
                if not f.endswith(".json"):
                    continue
                bn = _basename_no_ext(f)
                entry = papers.setdefault(bn, {})
                models = entry.setdefault("models", {})
                m = models.setdefault(model, {})
                if f.endswith(".review.json"):
                    m["review"] = f
                elif f.endswith(".revised.json"):
                    m["revised"] = f
                else:
                    m["raw"] = f
    # Check for existing human reviews
    if os.path.isdir(HUMAN_DIR):
        for f in os.listdir(HUMAN_DIR):
            if f.endswith(".json"):
                bn = _basename_no_ext(f)
                papers.setdefault(bn, {})["human"] = f
    result = []
    for bn in sorted(papers.keys()):
        info = papers[bn]
        if "models" in info:
            result.append({
                "basename": bn,
                "pdf": info.get("pdf"),
                "models": info["models"],
                "human": info.get("human"),
            })
    return result


@app.route("/")
def index():
    return render_template_string(TEMPLATE)


@app.route("/api/papers")
def api_papers():
    return jsonify(_list_papers())


@app.route("/api/json/<path:filepath>")
def api_json(filepath):
    full = os.path.join(LLM_DIR, filepath)
    if not os.path.isfile(full):
        return jsonify({"error": "not found"}), 404
    with open(full, encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/api/human/<path:basename>", methods=["GET", "PUT"])
def api_human(basename):
    path = os.path.join(HUMAN_DIR, basename + ".json")
    if request.method == "GET":
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                return jsonify(json.load(f))
        return jsonify(None)
    else:
        data = request.get_json(force=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"ok": True})


@app.route("/pdf/<path:filename>")
def serve_pdf(filename):
    full = os.path.join(PDF_DIR, filename)
    if not os.path.isfile(full):
        return "PDF not found", 404
    return send_file(full, mimetype="application/pdf")


# ── Template ──────────────────────────────────────────────────────────────────

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Survey Corpus Reviewer</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;font-family:-apple-system,"Segoe UI",Roboto,"Noto Sans SC",sans-serif;
  background:#faf4f0;color:#4a4a4a}

/* Top bar */
.topbar{height:50px;background:#fff;display:flex;align-items:center;padding:0 16px;
  border-bottom:1px solid #e8ddd4;gap:8px}
.topbar .paper-name{font-size:14px;color:#7c6f64;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.topbar .counter{font-size:12px;color:#b8a89a;white-space:nowrap}
.topbar .saved-badge{font-size:11px;padding:2px 8px;border-radius:10px;margin-left:8px}
.saved-badge.yes{background:#d4edda;color:#3d6b41}
.saved-badge.no{background:#fff3cd;color:#856404}

/* View tab bar */
.viewbar{height:36px;background:#fff;display:flex;align-items:center;padding:0 16px;gap:4px;
  border-bottom:1px solid #e8ddd4}
.vtab{padding:5px 14px;border-radius:16px;font-size:12px;cursor:pointer;transition:all .15s;
  user-select:none}
.vtab.active{background:#f0b4b4;color:#fff;font-weight:600}
.vtab:not(.active){background:#f5ebe0;color:#9a8c7e}
.vtab:not(.active):hover{background:#ede0d4;color:#6b5c4f}
.vtab .shortcut{opacity:.5;margin-left:4px;font-size:10px}
.viewbar .hint{margin-left:auto;font-size:11px;color:#c4b5a5}

/* Main layout */
.main{display:flex;height:calc(100vh - 86px)}
.left{width:50%;overflow-y:auto;padding:12px 16px;border-right:1px solid #e8ddd4;background:#faf4f0}
.right{width:50%;background:#f5ebe0}
.right iframe{width:100%;height:100%;border:none}

/* Sections */
.section{margin-bottom:12px;background:#fff;border-radius:10px;padding:12px 14px;
  border:1px solid #e8ddd4;box-shadow:0 1px 3px rgba(0,0,0,.04)}
.section h2{font-size:13px;color:#d4887a;margin-bottom:6px;padding-bottom:4px;
  border-bottom:1px solid #f5ebe0}
.field{margin-bottom:8px}
.field-name{font-size:11px;color:#b8a89a;font-weight:600;letter-spacing:.3px;margin-bottom:2px}
.field-value{font-size:13px;line-height:1.7;color:#4a4a4a}

/* Badges */
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;margin-left:4px}
.st-supported{background:#d4edda;color:#3d6b41}
.st-partially_supported{background:#ffe8cc;color:#8a5c1e}
.st-incorrect{background:#f8d7da;color:#8a2c32}
.st-format_error{background:#e2d5f1;color:#5c3d7a}
.sev-minor{background:#d4edda;color:#3d6b41}
.sev-major{background:#ffe8cc;color:#8a5c1e}

.checks-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:4px}
.check-item{font-size:11px;padding:3px 8px;border-radius:6px}
.ck-pass{background:#d4edda;color:#3d6b41}
.ck-mixed{background:#ffe8cc;color:#8a5c1e}
.ck-fail{background:#f8d7da;color:#8a2c32}

.item-card{background:#faf4f0;border-radius:8px;padding:10px 12px;margin-bottom:6px;
  border-left:3px solid #f0b4b4}
.item-card .point{font-size:13px;line-height:1.6}
.item-card .evidence{font-size:11px;color:#b8a89a;margin-top:6px;font-style:italic;
  border-top:1px dashed #e8ddd4;padding-top:6px}

/* Human review editor */
.editor-section{margin-bottom:12px;background:#fff;border-radius:10px;padding:12px 14px;
  border:1px solid #e8ddd4}
.editor-section h3{font-size:12px;color:#d4887a;margin-bottom:6px;display:flex;align-items:center;gap:6px}
.editor-section h3 .idx{background:#f0b4b4;color:#fff;border-radius:50%;width:18px;height:18px;
  display:inline-flex;align-items:center;justify-content:center;font-size:10px}
.ed-field{margin-bottom:8px}
.ed-label{font-size:11px;color:#b8a89a;font-weight:600;margin-bottom:2px}
.ed-input{width:100%;border:1px solid #e8ddd4;border-radius:6px;padding:6px 10px;font-size:13px;
  line-height:1.6;font-family:inherit;color:#4a4a4a;background:#faf4f0;resize:vertical}
.ed-input:focus{outline:none;border-color:#f0b4b4;background:#fff}
.ed-input.short{height:28px;resize:none}
textarea.ed-input{min-height:60px}
.ed-array-item{background:#faf4f0;border-radius:8px;padding:10px;margin-bottom:6px;
  border:1px solid #e8ddd4;position:relative}
.ed-array-item .ed-item-idx{font-size:10px;color:#d4887a;font-weight:700}
.ed-remove{position:absolute;top:6px;right:6px;background:none;border:none;color:#d4887a;
  cursor:pointer;font-size:14px;padding:2px 6px;border-radius:4px}
.ed-remove:hover{background:#f8d7da;color:#8a2c32}
.ed-add-btn{display:inline-block;padding:4px 12px;border-radius:14px;border:1px dashed #d4887a;
  background:none;color:#d4887a;font-size:12px;cursor:pointer;margin-top:4px}
.ed-add-btn:hover{background:#f5ebe0}
.save-bar{position:sticky;bottom:0;background:#fff;border-top:1px solid #e8ddd4;padding:8px 0;
  display:flex;align-items:center;gap:8px;margin-top:8px}
.save-btn{padding:6px 20px;border-radius:16px;border:none;background:#f0b4b4;color:#fff;
  font-size:13px;cursor:pointer;font-weight:600}
.save-btn:hover{background:#e8999a}
.save-status{font-size:11px;color:#b8a89a}

.empty-msg{color:#c4b5a5;text-align:center;padding-top:40vh;font-size:13px}
</style>
</head>
<body>

<div class="topbar">
  <span class="paper-name" id="paperName"></span>
  <span class="counter" id="counter"></span>
  <span class="saved-badge no" id="savedBadge" style="display:none">unsaved</span>
</div>

<div class="viewbar" id="viewbar">
  <div class="vtab" data-view="0">GPT Review<span class="shortcut">[1]</span></div>
  <div class="vtab" data-view="1">GLM Extraction<span class="shortcut">[2]</span></div>
  <div class="vtab" data-view="2">GPT Revised<span class="shortcut">[3]</span></div>
  <div class="vtab" data-view="3">Human Edit<span class="shortcut">[4]</span></div>
  <span class="hint">&#8592;&#8594; paper &nbsp; &#8593;&#8595; view</span>
</div>

<div class="main">
  <div class="left" id="leftPanel"><div class="empty-msg">Loading...</div></div>
  <div class="right" id="rightPanel"><div class="empty-msg">No PDF</div></div>
</div>

<script>
const VIEWS=['review','raw','revised','human'];
let papers=[],pi=0,vi=0,cache={},editorDirty=false;

function esc(s){return s==null?'':String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function val(v){
  if(v==null) return '<span style="color:#ccc">null</span>';
  if(typeof v==='boolean') return v?'<span style="color:#3d6b41">Yes</span>':'<span style="color:#8a2c32">No</span>';
  if(typeof v==='object') return '<pre style="white-space:pre-wrap;word-break:break-word;font-size:11px;margin:0;color:#666">'+esc(JSON.stringify(v,null,2))+'</pre>';
  return esc(v);
}

// ── Data ─────────────────────────────────────────────────────────────────────
async function loadPapers(){
  papers=await (await fetch('/api/papers')).json();
  if(papers.length>0) loadPaper(0);
}
async function fetchJson(path){
  if(cache[path]) return cache[path];
  const r=await fetch('/api/json/'+path);
  if(!r.ok) return null;
  cache[path]=await r.json();
  return cache[path];
}

// ── Navigation ───────────────────────────────────────────────────────────────
async function loadPaper(idx){
  if(vi===3) await saveHuman();
  pi=idx; vi=0;
  const p=papers[idx];
  document.getElementById('paperName').textContent=p.basename.replace(/-/g,' ');
  document.getElementById('counter').textContent=(idx+1)+' / '+papers.length;
  document.getElementById('savedBadge').style.display='none';
  const rp=document.getElementById('rightPanel');
  rp.innerHTML=p.pdf?'<iframe src="/pdf/'+encodeURIComponent(p.pdf)+'"></iframe>':'<div class="empty-msg">No PDF</div>';
  renderView();
}
async function switchView(idx){
  if(idx===vi) return;
  if(vi===3) await saveHuman();
  vi=idx; renderView();
}
function renderTabs(){
  document.querySelectorAll('.vtab').forEach(t=>t.classList.toggle('active',parseInt(t.dataset.view)===vi));
}

async function renderView(){
  renderTabs();
  const panel=document.getElementById('leftPanel');
  const p=papers[pi];

  if(vi===3){ renderHuman(p,panel); return; }

  const vk=VIEWS[vi];
  let model,file;
  if(vk==='review'){ model='gpt5.4'; file=(p.models['gpt5.4']||{}).review; }
  else if(vk==='raw'){ model='glm5.1'; file=(p.models['glm5.1']||{}).raw; }
  else if(vk==='revised'){ model='gpt5.4'; file=(p.models['gpt5.4']||{}).revised; }

  if(!file){ panel.innerHTML='<div class="empty-msg">Not available</div>'; return; }
  const data=await fetchJson(model+'/'+file);
  if(!data){ panel.innerHTML='<div class="empty-msg">Failed to load</div>'; return; }

  if(vk==='review') renderReview(data,panel);
  else if(vk==='raw') renderRaw(data,panel);
  else if(vk==='revised') renderRevised(data,panel);
}

// ── View 1: GPT Review ──────────────────────────────────────────────────────
function renderReview(d,panel){
  let h='<div class="json-panel">';
  h+='<div class="section"><h2>Verdict</h2>';
  if(d.overall_verdict){
    const c=d.overall_verdict==='pass'?'color:#3d6b41':d.overall_verdict==='minor_revision'?'color:#8a5c1e':'color:#8a2c32';
    h+='<div class="field"><div class="field-name">Overall</div><div class="field-value" style="'+c+';font-weight:700;font-size:14px">'+esc(d.overall_verdict)+'</div></div>';
  }
  if(d.confidence) h+='<div class="field"><div class="field-name">Confidence</div><div class="field-value">'+esc(d.confidence)+'</div></div>';
  if(d.ready_for_proposal_use!=null) h+='<div class="field"><div class="field-name">Ready for Proposal</div><div class="field-value">'+val(d.ready_for_proposal_use)+'</div></div>';
  if(d.summary) h+='<div class="field"><div class="field-name">Summary</div><div class="field-value">'+esc(d.summary)+'</div></div>';
  h+='</div>';

  if(d.checks){
    h+='<div class="section"><h2>Checks</h2><div class="checks-grid">';
    for(const[k,v] of Object.entries(d.checks)){
      const cls=v==='pass'?'ck-pass':v==='mixed'?'ck-mixed':'ck-fail';
      h+='<div class="check-item '+cls+'">'+esc(k.replace(/_/g,' '))+': '+esc(v)+'</div>';
    }
    h+='</div></div>';
  }

  if(d.field_reviews&&d.field_reviews.length){
    h+='<div class="section"><h2>Field Reviews</h2>';
    for(const fr of d.field_reviews){
      const sc='st-'+(fr.status||'').replace(/\s+/g,'_').toLowerCase();
      const sv=fr.severity?'sev-'+fr.severity:'';
      h+='<div class="item-card">';
      h+='<div class="field-name">'+esc(fr.field)+' <span class="badge '+sc+'">'+esc(fr.status)+'</span>';
      if(fr.severity) h+='<span class="badge '+sv+'">'+esc(fr.severity)+'</span>';
      h+='</div>';
      if(fr.reason) h+='<div class="field-value" style="margin-top:3px">'+esc(fr.reason)+'</div>';
      if(fr.paper_evidence) h+='<div class="evidence">Evidence: '+esc(fr.paper_evidence)+'</div>';
      if(fr.suggested_fix&&fr.suggested_fix!=='保持不变') h+='<div style="margin-top:3px;color:#d4887a;font-size:11px">Fix: '+esc(fr.suggested_fix)+'</div>';
      h+='</div>';
    }
    h+='</div>';
  }

  if(d.issues&&d.issues.length){
    h+='<div class="section"><h2>Issues</h2>';
    for(const iss of d.issues){
      const sv=iss.severity?'sev-'+iss.severity:'';
      h+='<div class="item-card">';
      h+='<div class="field-name">'+esc(iss.field||'');
      if(iss.severity) h+='<span class="badge '+sv+'">'+esc(iss.severity)+'</span>';
      h+='</div>';
      if(iss.problem) h+='<div class="point">'+esc(iss.problem)+'</div>';
      if(iss.paper_evidence) h+='<div class="evidence">Evidence: '+esc(iss.paper_evidence)+'</div>';
      if(iss.recommended_action) h+='<div style="margin-top:3px;color:#d4887a;font-size:11px">Action: '+esc(iss.recommended_action)+'</div>';
      h+='</div>';
    }
    h+='</div>';
  }

  h+='</div>';
  panel.innerHTML=h;
}

// ── View 2: GLM Extraction ──────────────────────────────────────────────────
function renderRaw(d,panel){
  let h='<div class="json-panel">';
  const meta=[['title','Title'],['authors','Authors'],['year','Year'],['venue','Venue'],['doi','DOI'],['url','URL']];
  h+='<div class="section"><h2>Paper Info</h2>';
  for(const[f,l] of meta){ if(d[f]!=null) h+='<div class="field"><div class="field-name">'+l+'</div><div class="field-value">'+esc(d[f])+'</div></div>'; }
  h+='</div>';
  if(d.abstract) h+='<div class="section"><h2>Abstract</h2><div class="field-value">'+esc(d.abstract)+'</div></div>';
  const extra=['citation_count','relevance_score','relevance','matched_keywords','extraction_status'];
  if(extra.some(f=>d[f]!=null)){
    h+='<div class="section"><h2>Metadata</h2>';
    for(const f of extra){ if(d[f]!=null) h+='<div class="field"><div class="field-name">'+f.replace(/_/g,' ')+'</div><div class="field-value">'+val(d[f])+'</div></div>'; }
    h+='</div>';
  }
  const skip=new Set(meta.map(x=>x[0]).concat(extra).concat(['abstract','body_text']));
  for(const[k,v] of Object.entries(d)){
    if(skip.has(k)) continue;
    h+='<div class="section"><h2>'+esc(k.replace(/_/g,' '))+'</h2><div class="field-value"><pre style="white-space:pre-wrap;word-break:break-word;font-size:11px;line-height:1.4;color:#666">'+esc(typeof v==='string'?v:JSON.stringify(v,null,2))+'</pre></div></div>';
  }
  h+='</div>';
  panel.innerHTML=h;
}

// ── View 3: GPT Revised ─────────────────────────────────────────────────────
function renderRevised(d,panel){
  let h='<div class="json-panel">';
  const meta=[['title','Title'],['authors','Authors'],['year','Year'],['venue','Venue'],['doi','DOI']];
  h+='<div class="section"><h2>Paper Info</h2>';
  for(const[f,l] of meta){ if(d[f]!=null) h+='<div class="field"><div class="field-name">'+l+'</div><div class="field-value">'+esc(d[f])+'</div></div>'; }
  const cls=[['theme_primary','Theme'],['theme_secondary','Sub-theme'],['workstream_fit','Workstream'],['is_close_baseline_to_cute','CUTE Baseline']];
  for(const[f,l] of cls){ if(d[f]!==undefined) h+='<div class="field"><div class="field-name">'+l+'</div><div class="field-value">'+val(d[f])+'</div></div>'; }
  h+='</div>';

  const content=[['research_purpose','Purpose'],['research_significance','Significance'],['key_technique','Key Technique'],['key_results','Key Results']];
  h+='<div class="section"><h2>Research</h2>';
  for(const[f,l] of content){ if(d[f]!=null) h+='<div class="field"><div class="field-name">'+l+'</div><div class="field-value">'+esc(d[f])+'</div></div>'; }
  h+='</div>';

  if(d.contributions&&d.contributions.length){
    h+='<div class="section"><h2>Contributions</h2>';
    for(const c of d.contributions){
      h+='<div class="item-card"><div class="point">'+esc(c.point)+'</div>';
      if(c.evidence) h+='<div class="evidence">'+esc(c.evidence)+'</div>';
      h+='</div>';
    }
    h+='</div>';
  }
  if(d.gap_identified&&d.gap_identified.length){
    h+='<div class="section"><h2>Gaps</h2>';
    for(const g of d.gap_identified){
      h+='<div class="item-card"><div class="point">'+esc(g.gap)+'</div>';
      if(g.evidence) h+='<div class="evidence">'+esc(g.evidence)+'</div>';
      if(g.relevance_to_cute) h+='<div style="margin-top:3px;font-size:11px;color:#b08968">CUTE: '+esc(g.relevance_to_cute)+'</div>';
      h+='</div>';
    }
    h+='</div>';
  }
  if(d.proposal_evidence){
    h+='<div class="section"><h2>Proposal Evidence</h2>';
    for(const[k,v] of Object.entries(d.proposal_evidence)){
      h+='<div class="field"><div class="field-name">'+esc(k.replace(/_/g,' '))+'</div><div class="field-value">'+esc(v)+'</div></div>';
    }
    h+='</div>';
  }
  h+='</div>';
  panel.innerHTML=h;
}

// ── View 4: Human Edit ──────────────────────────────────────────────────────
function renderHuman(p,panel){
  // Load GPT revised as base, then overlay human edits
  const revisedFile=(p.models['gpt5.4']||{}).revised;
  const humanFile=p.human;
  if(!revisedFile){
    panel.innerHTML='<div class="empty-msg">No GPT revised data to edit</div>';
    return;
  }
  // Fetch both, then render form
  Promise.all([
    fetchJson('gpt5.4/'+revisedFile),
    humanFile ? fetch('/api/human/'+encodeURIComponent(p.basename)).then(r=>r.json()).catch(()=>null) : Promise.resolve(null)
  ]).then(([base, humanOverwrite])=>{
    const d = humanOverwrite || base || {};
    renderEditForm(d, panel, !humanOverwrite);
  });
}

function renderEditForm(d, panel, isNew){
  editorDirty=false;
  document.getElementById('savedBadge').style.display=isNew?'none':'inline';
  document.getElementById('savedBadge').className='saved-badge yes';
  document.getElementById('savedBadge').textContent='saved';

  let h='<div id="editorRoot">';

  // -- Simple text fields --
  const textFields=[
    ['title','Title','short'],['authors','Authors','short'],['year','Year','short'],
    ['venue','Venue','short'],['doi','DOI','short'],['url','URL','short'],
    ['theme_primary','Theme Primary','short'],['theme_secondary','Theme Secondary','short'],
    ['workstream_fit','Workstream','short'],
    ['research_purpose','Purpose','long'],['research_significance','Significance','long'],
    ['key_technique','Key Technique','long'],['key_results','Key Results','long'],
  ];
  h+='<div class="editor-section"><h3>Basic Info</h3>';
  for(const[key,label,type] of textFields){
    const v=d[key]!=null?d[key]:'';
    h+='<div class="ed-field"><div class="ed-label">'+label+'</div>';
    if(type==='short') h+='<input class="ed-input short" data-key="'+esc(key)+'" value="'+esc(String(v))+'">';
    else h+='<textarea class="ed-input" data-key="'+esc(key)+'">'+esc(String(v))+'</textarea>';
    h+='</div>';
  }
  // Boolean field
  h+='<div class="ed-field"><div class="ed-label">Close Baseline to CUTE</div>';
  h+='<select class="ed-input short" data-key="is_close_baseline_to_cute">';
  h+='<option value="true"'+(d.is_close_baseline_to_cute===true?' selected':'')+'>Yes</option>';
  h+='<option value="false"'+(d.is_close_baseline_to_cute===false?' selected':'')+'>No</option>';
  h+='</select></div>';
  h+='</div>';

  // -- Contributions (array) --
  h+='<div class="editor-section"><h3>Contributions</h3><div id="ed-contributions">';
  const contribs=d.contributions||[];
  contribs.forEach((c,i)=>{
    h+='<div class="ed-array-item" data-array="contributions" data-index="'+i+'">';
    h+='<span class="ed-item-idx">#'+(i+1)+'</span>';
    h+='<button class="ed-remove" onclick="removeArrayItem(this)">&times;</button>';
    h+='<div class="ed-field"><div class="ed-label">Point</div><textarea class="ed-input" data-array="contributions" data-index="'+i+'" data-sub="point">'+esc(c.point||'')+'</textarea></div>';
    h+='<div class="ed-field"><div class="ed-label">Evidence</div><textarea class="ed-input" data-array="contributions" data-index="'+i+'" data-sub="evidence">'+esc(c.evidence||'')+'</textarea></div>';
    h+='</div>';
  });
  h+='</div>';
  h+='<button class="ed-add-btn" onclick="addArrayItem(\'contributions\')">+ Add Contribution</button>';
  h+='</div>';

  // -- Gaps (array) --
  h+='<div class="editor-section"><h3>Gaps Identified</h3><div id="ed-gap_identified">';
  const gaps=d.gap_identified||[];
  gaps.forEach((g,i)=>{
    h+='<div class="ed-array-item" data-array="gap_identified" data-index="'+i+'">';
    h+='<span class="ed-item-idx">#'+(i+1)+'</span>';
    h+='<button class="ed-remove" onclick="removeArrayItem(this)">&times;</button>';
    h+='<div class="ed-field"><div class="ed-label">Gap</div><textarea class="ed-input" data-array="gap_identified" data-index="'+i+'" data-sub="gap">'+esc(g.gap||'')+'</textarea></div>';
    h+='<div class="ed-field"><div class="ed-label">Evidence</div><textarea class="ed-input" data-array="gap_identified" data-index="'+i+'" data-sub="evidence">'+esc(g.evidence||'')+'</textarea></div>';
    h+='<div class="ed-field"><div class="ed-label">Relevance to CUTE</div><textarea class="ed-input" data-array="gap_identified" data-index="'+i+'" data-sub="relevance_to_cute">'+esc(g.relevance_to_cute||'')+'</textarea></div>';
    h+='</div>';
  });
  h+='</div>';
  h+='<button class="ed-add-btn" onclick="addArrayItem(\'gap_identified\')">+ Add Gap</button>';
  h+='</div>';

  // -- Proposal Evidence (object with text fields) --
  if(d.proposal_evidence){
    h+='<div class="editor-section"><h3>Proposal Evidence</h3>';
    for(const[k,v] of Object.entries(d.proposal_evidence)){
      h+='<div class="ed-field"><div class="ed-label">'+esc(k.replace(/_/g,' '))+'</div>';
      h+='<textarea class="ed-input" data-pe-key="'+esc(k)+'">'+esc(v||'')+'</textarea></div>';
    }
    h+='</div>';
  }

  // -- Save bar --
  h+='<div class="save-bar">';
  h+='<button class="save-btn" onclick="doSave()">Save</button>';
  h+='<span class="save-status" id="saveStatus"></span>';
  h+='<span style="margin-left:auto;font-size:11px;color:#ccc">Ctrl+S to save</span>';
  h+='</div>';

  h+='</div>';
  panel.innerHTML=h;

  // Mark dirty on any input
  panel.querySelectorAll('.ed-input,.ed-input').forEach(el=>{
    el.addEventListener('input',()=>{
      editorDirty=true;
      document.getElementById('savedBadge').style.display='inline';
      document.getElementById('savedBadge').className='saved-badge no';
      document.getElementById('savedBadge').textContent='unsaved';
    });
  });
}

function collectFormData(){
  const root=document.getElementById('editorRoot');
  if(!root) return null;
  const d={};
  // Simple fields
  root.querySelectorAll('[data-key]').forEach(el=>{
    const k=el.getAttribute('data-key');
    if(k==='is_close_baseline_to_cute') d[k]=el.value==='true';
    else if(k==='year') d[k]=parseInt(el.value)||0;
    else d[k]=el.value;
  });
  // Array fields
  d.contributions=[];
  root.querySelectorAll('[data-array="contributions"][data-sub="point"]').forEach(el=>{
    const i=parseInt(el.getAttribute('data-index'));
    const evEl=root.querySelector('[data-array="contributions"][data-index="'+i+'"][data-sub="evidence"]');
    d.contributions.push({point:el.value, evidence:evEl?evEl.value:''});
  });
  d.gap_identified=[];
  root.querySelectorAll('[data-array="gap_identified"][data-sub="gap"]').forEach(el=>{
    const i=parseInt(el.getAttribute('data-index'));
    const evEl=root.querySelector('[data-array="gap_identified"][data-index="'+i+'"][data-sub="evidence"]');
    const cuEl=root.querySelector('[data-array="gap_identified"][data-index="'+i+'"][data-sub="relevance_to_cute"]');
    d.gap_identified.push({gap:el.value, evidence:evEl?evEl.value:'', relevance_to_cute:cuEl?cuEl.value:''});
  });
  // Proposal evidence
  const pe={};
  root.querySelectorAll('[data-pe-key]').forEach(el=>{
    pe[el.getAttribute('data-pe-key')]=el.value;
  });
  d.proposal_evidence=pe;
  return d;
}

async function doSave(){
  const d=collectFormData();
  if(!d) return;
  const bn=papers[pi].basename;
  try{
    await fetch('/api/human/'+encodeURIComponent(bn),{
      method:'PUT',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(d)
    });
    editorDirty=false;
    document.getElementById('savedBadge').style.display='inline';
    document.getElementById('savedBadge').className='saved-badge yes';
    document.getElementById('savedBadge').textContent='saved';
    const st=document.getElementById('saveStatus');
    if(st) st.textContent='Saved!';
    // Update paper list to reflect human file exists
    const p=papers[pi];
    if(!p.human) p.human=bn+'.json';
    setTimeout(()=>{if(st) st.textContent='';},2000);
  }catch(e){
    const st=document.getElementById('saveStatus');
    if(st) st.textContent='Error: '+e.message;
  }
}

async function saveHuman(){
  if(vi!==3||!editorDirty) return;
  await doSave();
}

function addArrayItem(arrName){
  const container=document.getElementById('ed-'+arrName);
  if(!container) return;
  const i=container.children.length;
  const div=document.createElement('div');
  div.className='ed-array-item';
  div.setAttribute('data-array',arrName);
  div.setAttribute('data-index',i);
  if(arrName==='contributions'){
    div.innerHTML='<span class="ed-item-idx">#'+(i+1)+'</span><button class="ed-remove" onclick="removeArrayItem(this)">&times;</button>'
      +'<div class="ed-field"><div class="ed-label">Point</div><textarea class="ed-input" data-array="contributions" data-index="'+i+'" data-sub="point"></textarea></div>'
      +'<div class="ed-field"><div class="ed-label">Evidence</div><textarea class="ed-input" data-array="contributions" data-index="'+i+'" data-sub="evidence"></textarea></div>';
  } else if(arrName==='gap_identified'){
    div.innerHTML='<span class="ed-item-idx">#'+(i+1)+'</span><button class="ed-remove" onclick="removeArrayItem(this)">&times;</button>'
      +'<div class="ed-field"><div class="ed-label">Gap</div><textarea class="ed-input" data-array="gap_identified" data-index="'+i+'" data-sub="gap"></textarea></div>'
      +'<div class="ed-field"><div class="ed-label">Evidence</div><textarea class="ed-input" data-array="gap_identified" data-index="'+i+'" data-sub="evidence"></textarea></div>'
      +'<div class="ed-field"><div class="ed-label">Relevance to CUTE</div><textarea class="ed-input" data-array="gap_identified" data-index="'+i+'" data-sub="relevance_to_cute"></textarea></div>';
  }
  container.appendChild(div);
  div.querySelectorAll('.ed-input').forEach(el=>el.addEventListener('input',()=>{
    editorDirty=true;
    document.getElementById('savedBadge').style.display='inline';
    document.getElementById('savedBadge').className='saved-badge no';
    document.getElementById('savedBadge').textContent='unsaved';
  }));
  editorDirty=true;
}

function removeArrayItem(btn){
  const item=btn.closest('.ed-array-item');
  const arrName=item.getAttribute('data-array');
  item.remove();
  // Re-index remaining items
  const container=document.getElementById('ed-'+arrName);
  let idx=0;
  container.querySelectorAll('.ed-array-item').forEach(el=>{
    el.setAttribute('data-index',idx);
    el.querySelector('.ed-item-idx').textContent='#'+(idx+1);
    el.querySelectorAll('.ed-input').forEach(inp=>{
      inp.setAttribute('data-index',idx);
    });
    idx++;
  });
  editorDirty=true;
  document.getElementById('savedBadge').style.display='inline';
  document.getElementById('savedBadge').className='saved-badge no';
  document.getElementById('savedBadge').textContent='unsaved';
}

// ── Keyboard ────────────────────────────────────────────────────────────────
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='TEXTAREA'||e.target.tagName==='INPUT'||e.target.tagName==='SELECT'){
    // Ctrl+S to save in editor
    if((e.ctrlKey||e.metaKey)&&e.key==='s'){ e.preventDefault(); doSave(); }
    return;
  }
  if(e.key==='ArrowLeft'&&pi>0){ e.preventDefault(); loadPaper(pi-1); }
  else if(e.key==='ArrowRight'&&pi<papers.length-1){ e.preventDefault(); loadPaper(pi+1); }
  else if(e.key==='ArrowUp'){ e.preventDefault(); switchView(vi>0?vi-1:VIEWS.length-1); }
  else if(e.key==='ArrowDown'){ e.preventDefault(); switchView(vi<VIEWS.length-1?vi+1:0); }
  else if(e.key>='1'&&e.key<='4'){ e.preventDefault(); switchView(parseInt(e.key)-1); }
});

document.querySelectorAll('.vtab').forEach(t=>{
  t.addEventListener('click',()=>switchView(parseInt(t.dataset.view)));
});

loadPapers();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print(f"  Topic:   {TOPIC}")
    print(f"  PDFs:    {PDF_DIR}")
    print(f"  Corpus:  {CORPUS_DIR}")
    print(f"  LLM:     {LLM_DIR}")
    print(f"  Human:   {HUMAN_DIR}")
    print(f"  URL:     http://localhost:{args.port}")
    app.run(host="0.0.0.0", port=args.port, debug=True)
