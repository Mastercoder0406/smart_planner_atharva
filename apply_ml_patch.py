"""
apply_ml_patch.py - add ML risk to Smart Planner. Replaces the broken .patch file.
Run from project folder (where app.py is):   python apply_ml_patch.py
Makes backups app.py.bak and static/js/main.js.bak. Safe to run twice. Handles Windows CRLF.
"""
import os, re, shutil, sys

def read(path):
    raw = open(path, "r", encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    return raw.replace("\r\n", "\n"), crlf

def write(path, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    open(path, "w", encoding="utf-8", newline="").write(text)

def patch_app(s):
    if "from ml_risk import RISK" in s:
        return s, "app.py already patched, skipped"
    # 1) imports after model-load block
    m = re.search(r"^(\s*)predictor_model = None\n", s, re.M)
    if not m: sys.exit("ANCHOR NOT FOUND: 'predictor_model = None'")
    add = ("\n# --- Edge-aware ML risk + route cost functions ---\n"
           "from ml_risk import RISK\n"
           "from routing_costs import make_cost_function, HEURISTIC_SCALE\n"
           "print(f\"Risk model source: {RISK.source}\")\n")
    s = s[:m.end()] + add + s[m.end():]
    # 2) heuristic + cost-function chain
    a = re.search(r"^( *)def heuristic\(u, v\):\n", s, re.M)
    b = re.search(r"^ *cost_func = balanced_cost\n", s, re.M)
    if not a or not b or b.start() < a.start(): sys.exit("ANCHOR NOT FOUND: heuristic / balanced_cost block")
    i = a.group(1)
    new = (f"{i}# A* heuristic: straight-line distance. Scaled by n_min (0.8) only in 'balanced',\n"
           f"{i}# the one mode where a penalty can be below 1.0 (footway benefit).\n"
           f"{i}h_scale = HEURISTIC_SCALE.get(route_type, 1.0)\n\n"
           f"{i}def heuristic(u, v):\n"
           f"{i}    try:\n"
           f"{i}        return h_scale * ox.distance.great_circle(G.nodes[u]['y'], G.nodes[u]['x'], G.nodes[v]['y'], G.nodes[v]['x'])\n"
           f"{i}    except KeyError:\n"
           f"{i}        return 0  # Fallback heuristic\n\n"
           f"{i}try:\n"
           f"{i}    # Edge-cost function for this route type (ML risk applied inside)\n"
           f"{i}    cost_func = make_cost_function(\n"
           f"{i}        route_type, G, get_best_edge_data,\n"
           f"{i}        {{\"weather\": current_weather, \"obstacles\": recent_obstacles, \"profile\": user_profile}},\n"
           f"{i}        RISK,\n"
           f"{i}    )\n")
    s = s[:a.start()] + new + s[b.end():]
    # 3) risk in response
    r = re.search(r"^( *)route_bounds = get_route_bounds\(route_coords\)\n\s*\n( *)return jsonify\(\{\n", s, re.M)
    if not r: sys.exit("ANCHOR NOT FOUND: route_bounds / return jsonify")
    i1, i2 = r.group(1), r.group(2)
    rep = (f"{i1}route_bounds = get_route_bounds(route_coords)\n"
           f"{i1}risk_info = RISK.route_risk(G, route, get_best_edge_data, recent_obstacles)\n\n"
           f"{i2}return jsonify({{\n{i2}    \"risk\": risk_info,\n")
    s = s[:r.start()] + rep + s[r.end():]
    # 4) endpoint
    if "#Helper function for routes" not in s: sys.exit("ANCHOR NOT FOUND: '#Helper function for routes'")
    ep = ("@app.route('/api/risk')\ndef api_risk():\n"
          "    \"\"\"Current ML obstacle-risk snapshot (UI badge + demo).\"\"\"\n"
          "    return jsonify(RISK.summary())\n\n\n")
    s = s.replace("#Helper function for routes", ep + "#Helper function for routes", 1)
    return s, "app.py patched"

def patch_js(s):
    if "route.risk" in s:
        return s, "main.js already patched, skipped"
    o1 = "stats: data.stats, segments: data.segments || [], bounds: data.bounds"
    if o1 not in s: sys.exit("ANCHOR NOT FOUND in main.js: routeStats.push")
    s = s.replace(o1, "stats: data.stats, risk: data.risk, segments: data.segments || [], bounds: data.bounds", 1)
    m = re.search(r"^( *)<div>⭐ Accessibility \$\{s\.accessibility_score\}/100</div>\n", s, re.M)
    if not m: sys.exit("ANCHOR NOT FOUND in main.js: Accessibility line")
    line = (f"{m.group(1)}${{route.risk ? `<div>🎲 Obstacle risk ${{route.risk.level}} "
            f"(${{Math.round(route.risk.avg_probability * 100)}}%)</div>` : ''}}\n")
    s = s[:m.end()] + line + s[m.end():]
    return s, "main.js patched"

for need in ("ml_risk.py", "routing_costs.py"):
    if not os.path.exists(need): sys.exit(f"MISSING {need} in this folder")
jobs = [("app.py", patch_app), ("static/js/main.js", patch_js)]
out = []
for path, fn in jobs:
    if not os.path.exists(path): sys.exit(f"MISSING {path}. Run from project folder.")
    text, crlf = read(path)
    new, msg = fn(text)
    out.append((path, text, new, crlf, msg))
for path, old, new, crlf, msg in out:
    if new != old:
        shutil.copy(path, path + ".bak")
        write(path, new, crlf)
    print(msg)
print("DONE. Next: python train_risk_model.py ; python test_ml_routing.py ; python app.py")