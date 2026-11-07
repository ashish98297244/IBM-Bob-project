"""
app.py — Flask web app for the AI-Powered LaTeX Diagram Generator.

Run with:
    python app.py

Then open: http://localhost:5000
"""

from __future__ import annotations

import sys
import io
from pathlib import Path

# UTF-8 output for Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, render_template, request, jsonify, send_from_directory

from latex_diagram_agent.config import get_config
from latex_diagram_agent.core.diagram_agent import DiagramAgent
from latex_diagram_agent.generators.tikz_generator import detect_diagram_type, post_process
from latex_diagram_agent.utils.file_utils import save_tex, timestamped_stem
from latex_diagram_agent.utils.nlp_utils import classify_intent

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Agent initialization (single shared instance)
# ---------------------------------------------------------------------------
config = get_config()
agent  = DiagramAgent(config)
last_result = None   # tracks current diagram result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    global last_result
    data = request.get_json()
    description = (data or {}).get("description", "").strip()

    if not description:
        return jsonify({"error": "Description is required."}), 400

    try:
        diagram_type = detect_diagram_type(description)
        result = agent.generate(description=description, diagram_type=diagram_type)
        result.tikz_code = post_process(result.tikz_code, description)
        last_result = result

        return jsonify({
            "tikz_code":        result.tikz_code,
            "iteration":        result.iteration,
            "is_valid":         result.is_valid,
            "validation_notes": result.validation_notes,
            "diagram_type":     diagram_type or "auto",
            "output_file":      str(result.output_file) if result.output_file else "",
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/refine", methods=["POST"])
def refine():
    global last_result
    data = request.get_json()
    instruction = (data or {}).get("instruction", "").strip()

    if not instruction:
        return jsonify({"error": "Instruction is required."}), 400

    if last_result is None:
        return jsonify({"error": "No diagram yet. Use /generate first."}), 400

    try:
        intent = classify_intent(instruction)
        result = agent.refine(instruction)
        result.tikz_code = post_process(result.tikz_code)
        last_result = result

        return jsonify({
            "tikz_code":        result.tikz_code,
            "iteration":        result.iteration,
            "is_valid":         result.is_valid,
            "validation_notes": result.validation_notes,
            "intent":           intent.name,
            "output_file":      str(result.output_file) if result.output_file else "",
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/save", methods=["POST"])
def save():
    global last_result
    if last_result is None:
        return jsonify({"error": "Nothing to save. Generate a diagram first."}), 400

    data     = request.get_json()
    filename = (data or {}).get("filename", "").strip()
    session  = agent.get_session()

    if filename:
        stem = Path(filename).stem
    else:
        base = session.original_description[:30].replace(" ", "_") if session else "diagram"
        stem = timestamped_stem(base)

    path = save_tex(last_result.tikz_code, config.output_dir, stem)
    return jsonify({"saved_to": str(path)})


@app.route("/history", methods=["GET"])
def history():
    session = agent.get_session()
    if session is None:
        return jsonify({"history": []})

    return jsonify({
        "description": session.original_description,
        "iterations":  session.iteration_count,
        "history": [
            {
                "index":      i,
                "iteration":  r.iteration,
                "is_valid":   r.is_valid,
                "output_file": str(r.output_file) if r.output_file else "",
            }
            for i, r in enumerate(session.history)
        ],
    })


@app.route("/outputs/<path:filename>")
def serve_output(filename):
    return send_from_directory(config.output_dir, filename)


@app.route("/preview")
def preview_page():
    """Return a standalone HTML page that renders the current TikZ via TikZJax."""
    import re as _re
    global last_result
    if last_result is None:
        return "<p style='font-family:sans-serif;padding:20px'>No diagram yet.</p>", 200

    tikz_code = last_result.tikz_code

    # Extract just the tikzpicture environment (TikZJax must NOT receive \documentclass)
    m = _re.search(
        r"(\\begin\{tikzpicture\}[\s\S]*?\\end\{tikzpicture\})",
        tikz_code, _re.IGNORECASE
    )
    body = m.group(1).strip() if m else tikz_code.strip()

    # Collect all \usetikzlibrary{...} calls and merge into one preamble line
    libs_raw = _re.findall(r"\\usetikzlibrary\{([^}]+)\}", tikz_code)
    # Flatten, deduplicate, strip spaces
    lib_names = []
    seen = set()
    for chunk in libs_raw:
        for name in chunk.split(","):
            name = name.strip()
            if name and name not in seen:
                seen.add(name)
                lib_names.append(name)

    # Build preamble for TikZJax: goes BEFORE the tikzpicture, outside the script tag
    # TikZJax reads \usetikzlibrary inside the script body as preamble
    preamble = ""
    if lib_names:
        preamble = "\\usetikzlibrary{" + ",".join(lib_names) + "}\n"

    tikzjax_content = preamble + body

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="/static/tikzjax-fonts.css">
  <script src="/static/tikzjax.js"></script>
  <style>
    body {{
      margin: 24px auto;
      max-width: 900px;
      background: #fff;
      display: flex;
      flex-direction: column;
      align-items: center;
      font-family: sans-serif;
    }}
    svg {{ max-width: 100%; height: auto; display: block; }}
    #loading {{
      margin: 60px auto 0;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 12px;
      color: #666;
      font-size: 13px;
    }}
    .spin {{
      width: 32px; height: 32px;
      border: 3px solid #dde;
      border-top-color: #5b8dee;
      border-radius: 50%;
      animation: spin .8s linear infinite;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    #err {{
      display: none;
      color: #c00;
      font-size: 12px;
      margin-top: 8px;
      text-align: center;
      max-width: 500px;
    }}
  </style>
</head>
<body>
  <div id="loading">
    <div class="spin"></div>
    <span>Rendering TikZ diagram…</span>
  </div>
  <div id="err"></div>

  <script type="text/tikz">
{tikzjax_content}
  </script>

  <script>
    (function() {{
      var attempts = 0;
      var maxAttempts = 100;  // 10 seconds

      function check() {{
        var svg = document.querySelector('svg');
        if (svg) {{
          document.getElementById('loading').style.display = 'none';
          // notify parent iframe to resize
          try {{
            parent.postMessage({{
              type: 'tikz-ready',
              height: document.documentElement.scrollHeight
            }}, '*');
          }} catch(_) {{}}
          return;
        }}
        attempts++;
        if (attempts >= maxAttempts) {{
          document.getElementById('loading').style.display = 'none';
          var errEl = document.getElementById('err');
          errEl.style.display = 'block';
          errEl.textContent = 'TikZJax did not produce an SVG. '
            + 'Check the Code tab — the LaTeX may need pdflatex to compile.';
          try {{
            parent.postMessage({{ type: 'tikz-ready', height: 120 }}, '*');
          }} catch(_) {{}}
          return;
        }}
        setTimeout(check, 100);
      }}

      // Start polling after TikZJax has had a moment to initialise
      setTimeout(check, 300);
    }})();
  </script>
</body>
</html>"""
    return html, 200


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n  AI-Powered LaTeX Diagram Generator — Web App")
    print("  Open in browser: http://localhost:5000\n")
    app.run(debug=True, port=5000)
