import os
import difflib
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Registered baseline code to compare against
REGISTERED_CODE = r'''import os, re, urllib.parse, urllib.request
from flask import Flask, abort, jsonify, render_template, request

app = Flask(__name__)

def get_vid(q):
    try:
        req = urllib.request.Request(f"https://www.youtube.com/results?search_query={urllib.parse.quote(q)}", headers={"User-Agent": "Mozilla/5.0"})
        ids = re.findall(r"\"videoId\":\"([^\"]+)\"", urllib.request.urlopen(req, timeout=5).read().decode("utf-8"))
        return ids[0] if ids else None
    except Exception: return None

@app.route("/", methods=["GET"])
def home(): return render_template("index.html")

@app.route("/agent", methods=["POST"])
def ai_agent_router():
    d = request.get_json(silent=True)
    if not d or "text_command" not in d: abort(400, description="Missing 'text_command' in request body")
    
    cmd = d["text_command"].strip().lower()

    if "youtube" in cmd:
        q = cmd
        for p in ["open youtube and search", "open youtube and play", "open youtube", "search for", "search", "and play", "play", "on youtube"]:
            q = q.replace(p, "")
        q = q.strip()
        target = "https://www.youtube.com" if not q else (f"https://www.youtube.com/watch?v={vid}&autoplay=1" if (vid := get_vid(q)) else f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}")

    elif any(k in cmd for k in ["gmail", "email", "mail", "message"]):
        to, body = "", ""
        if tm := re.search(r"(?:update|send|mail|message)?\s*to\s+([a-zA-Z0-9._%+\s]+?)(?=\s+(?:and|type|write|saying|with|content|that|message|$))", cmd):
            c = tm.group(1).strip().replace(" at ", "@").replace(" dot ", ".").replace(" ", "")
            to = c if "@" in c else f"{c}@gmail.com"

        if bm := re.search(r"(?:type|write|saying|content|message|that)\s+(.*)", cmd):
            if b := bm.group(1).strip(): body = b[0].upper() + b[1:]

        target = f"https://mail.google.com/mail/u/0/?view=cm&fs=1&to={urllib.parse.quote(to)}&body={urllib.parse.quote(body)}" if to or body else "https://mail.google.com"

    else:
        target = f"https://www.google.com/search?q={urllib.parse.quote_plus(cmd)}"

    return jsonify({"action": "open_tab", "url": target})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))'''


def analyze_differences(registered: str, submitted: str):
    reg_clean = [l.strip() for l in registered.replace('\xa0', ' ').replace('\r\n', '\n').splitlines() if l.strip()]
    
    # Split raw submitted input to preserve exact user line numbers
    raw_sub_lines = submitted.replace('\xa0', ' ').replace('\r\n', '\n').splitlines()

    if not any(l.strip() for l in raw_sub_lines):
        return {"match": False, "errors": [{"type": "empty", "expected": "Code snippet", "found": "Empty input", "line_no": None}]}

    sub_clean = [l.strip() for l in raw_sub_lines if l.strip()]

    if reg_clean == sub_clean:
        return {"match": True, "errors": []}

    errors = []

    # Map errors directly to the exact line number in the user editor
    for line_idx, raw_line in enumerate(raw_sub_lines, start=1):
        clean_line = raw_line.strip()
        if not clean_line or clean_line in reg_clean:
            continue

        # Find closest match in registered code
        best_match = None
        best_ratio = 0.0
        for reg_line in reg_clean:
            ratio = difflib.SequenceMatcher(None, clean_line, reg_line).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = reg_line

        if best_match and best_ratio > 0.4:
            errors.append({
                "type": "mismatch",
                "line_no": line_idx,
                "expected": best_match,
                "found": clean_line
            })
        else:
            errors.append({
                "type": "extra",
                "line_no": line_idx,
                "expected": None,
                "found": clean_line
            })

    if not errors:
        return {"match": True, "errors": []}

    return {"match": False, "errors": errors}


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


@app.route("/compare", methods=["POST"])
def compare():
    data = request.get_json(silent=True) or {}
    input_code = data.get("input_code", "")
    
    result = analyze_differences(REGISTERED_CODE, input_code)
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
