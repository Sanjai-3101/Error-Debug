import os
import difflib
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Raw string prevents backslash and quotation escaping issues
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


def sanitize_and_split(code_str: str):
    """
    Cleans code input by:
    - Removing non-breaking spaces (\xa0) from copy-pasting
    - Normalizing CRLF (\r\n) line breaks
    - Stripping trailing whitespace per line
    - Removing blank lines
    """
    cleaned = code_str.replace('\xa0', ' ').replace('\r\n', '\n')
    lines = [line.rstrip() for line in cleaned.splitlines() if line.strip()]
    return lines


def analyze_differences(registered: str, submitted: str):
    reg_lines = sanitize_and_split(registered)
    sub_lines = sanitize_and_split(submitted)

    if reg_lines == sub_lines:
        return {"match": True, "errors": []}

    errors = []
    matcher = difflib.SequenceMatcher(None, reg_lines, sub_lines)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'replace':
            for orig, inp in zip(reg_lines[i1:i2], sub_lines[j1:j2]):
                errors.append({
                    "type": "mismatch",
                    "expected": orig,
                    "found": inp
                })
        elif tag == 'delete':
            for orig in reg_lines[i1:i2]:
                errors.append({
                    "type": "missing",
                    "expected": orig,
                    "found": None
                })
        elif tag == 'insert':
            for inp in sub_lines[j1:j2]:
                errors.append({
                    "type": "extra",
                    "expected": None,
                    "found": inp
                })

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
