import os
import difflib
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Registered code baseline
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


def normalize_code_lines(code_str: str):
    """Normalize hidden characters, spaces, and linebreaks."""
    cleaned = code_str.replace('\xa0', ' ').replace('\r\n', '\n')
    return [line.strip() for line in cleaned.splitlines() if line.strip()]


def find_best_matching_line(line, target_lines):
    """Finds the line in target_lines that is most similar to `line`."""
    best_ratio = 0.0
    best_match = None
    for target in target_lines:
        ratio = difflib.SequenceMatcher(None, line, target).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = target
    return best_match, best_ratio


def analyze_differences(registered: str, submitted: str):
    reg_lines = normalize_code_lines(registered)
    sub_lines = normalize_code_lines(submitted)

    if not sub_lines:
        return {"match": False, "errors": [{"type": "empty", "expected": "Some code", "found": "Empty input"}]}

    # Exact match check
    if reg_lines == sub_lines:
        return {"match": True, "errors": []}

    errors = []

    # Check each submitted line individually against registered code
    for sub_line in sub_lines:
        if sub_line in reg_lines:
            continue  # Line exists in registered code perfectly!

        # If line doesn't match, find the closest expected line in registered code
        best_expected, score = find_best_matching_line(sub_line, reg_lines)

        if best_expected and score > 0.4:
            errors.append({
                "type": "mismatch",
                "expected": best_expected,
                "found": sub_line
            })
        else:
            errors.append({
                "type": "extra",
                "expected": None,
                "found": sub_line
            })

    # If no errors were generated for submitted lines, it's a successful partial match
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
