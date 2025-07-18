"""
Siddharth Astrology App
-----------------------
User enters: Name, DOB, Time of Birth, Location.
App:
  - Normalizes location to India → State → District (geopy)
  - Calculates age
  - Calls Gemini model to generate Odia astrology-style guidance:
      • Today's horoscope
      • Future (6-12 months)
      • Long-term (2-5 yrs)
      • Career growth sector
      • Marriage window (non-guaranteed)
      • Financial outlook
      • Lucky color & why
      • Action tips
  - Renders result in browser
  - Downloads PDF (Unicode via ReportLab; supports Odia if font provided)

Environment (.env):
  GEMINI_API_KEY=...
  GEMINI_MODEL=models/gemini-2.5-pro-preview-06-05
  GEMINI_MODEL_FALLBACK=models/gemini-1.5-flash
"""

import os
from flask import Flask, render_template, request, send_file, abort
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from india_location import normalize_location

# ------------------------------------------------------------------
# Load environment & configure Gemini
# ------------------------------------------------------------------
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "models/gemini-1.5-flash")
MODEL_FALLBACK = os.getenv("GEMINI_MODEL_FALLBACK", "models/gemini-1.5-flash")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY missing in .env")

genai.configure(api_key=GEMINI_API_KEY)

# ------------------------------------------------------------------
# Font setup (for Odia PDF)
# ------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "fonts", "NotoSansOriya-Regular.ttf")
ODIA_FONT_NAME = "NotoOdia"
HAS_ODIA_FONT = False

if os.path.exists(FONT_PATH):
    try:
        pdfmetrics.registerFont(TTFont(ODIA_FONT_NAME, FONT_PATH))
        HAS_ODIA_FONT = True
        print("Loaded Odia font:", FONT_PATH)
    except Exception as e:
        print("Font load error:", e)

# ------------------------------------------------------------------
# Flask app
# ------------------------------------------------------------------
app = Flask(__name__)
_last_report = None  # in-memory cache of latest report for PDF

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def calc_age(dob_str: str):
    try:
        dob = datetime.strptime(dob_str, "%Y-%m-%d")
    except Exception:
        return None
    today = datetime.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

def _safe_line(text: str) -> str:
    """Replace arrow & degrade non-Latin if Odia font not loaded."""
    text = text.replace("→", "->")
    if HAS_ODIA_FONT:
        return text
    # degrade gracefully: keep Latin1 only
    return text.encode("latin-1", errors="ignore").decode("latin-1", errors="ignore")

def _wrap_text(text: str, max_chars=90):
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    lines = []
    current = []
    count = 0
    for w in words:
        wlen = len(w) + 1
        if count + wlen > max_chars:
            lines.append(" ".join(current))
            current = [w]
            count = wlen
        else:
            current.append(w)
            count += wlen
    if current:
        lines.append(" ".join(current))
    return lines

def make_pdf(report_dict: dict) -> str:
    """
    Create a PDF from the report data. Returns absolute file path.
    """
    filename = f"{report_dict['name']}_astrology.pdf"
    filepath = os.path.join(BASE_DIR, filename)
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    # Title
    if HAS_ODIA_FONT:
        c.setFont(ODIA_FONT_NAME, 18)
    else:
        c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, height-50, "Siddharth Astrology Report")

    # Meta info
    if HAS_ODIA_FONT:
        c.setFont(ODIA_FONT_NAME, 12)
    else:
        c.setFont("Helvetica", 12)
    y = height - 90
    meta_lines = [
        f"ନାମ/Name: {report_dict['name']}",
        f"ଜନ୍ମତାରିଖ/DOB: {report_dict['dob']}",
        f"ସମୟ/Time: {report_dict['tob']}",
        f"ବୟସ/Age: {report_dict['age'] if report_dict['age'] is not None else 'N/A'}",
        f"ସ୍ଥାନ/Location: {report_dict['normalized_location']}",
    ]
    for line in meta_lines:
        c.drawString(50, y, _safe_line(line))
        y -= 16

    y -= 10

    # Prediction
    text_obj = c.beginText(50, y)
    if HAS_ODIA_FONT:
        text_obj.setFont(ODIA_FONT_NAME, 12)
    else:
        text_obj.setFont("Helvetica", 12)

    for raw_line in report_dict["prediction"].splitlines():
        # Empty line spacing
        if not raw_line.strip():
            text_obj.textLine("")
            continue
        for wrapped in _wrap_text(raw_line, max_chars=90):
            text_obj.textLine(_safe_line(wrapped))
    c.drawText(text_obj)

    c.showPage()
    c.save()
    return filepath

def get_ai_prediction(name, dob, tob, normalized_location, age):
    """
    Call Gemini to produce Odia astrology-style report.
    """
    age_str = f"{age} ବର୍ଷ" if age is not None else "ଅଜଣା ବୟସ"
    prompt = f"""
ଆପଣ ଜଣେ ପ୍ରୋଫେସନାଲ୍ ଓଡ଼ିଆ ଜ୍ୟୋତିଷୀ (astrologer)।
ତଳେ ଉପଯୋଗକର୍ତ୍ତାଙ୍କ ତଥ୍ୟ ଦିଆଯାଇଛି:

ନାମ: {name}
ଜନ୍ମତାରିଖ: {dob}
ଜନ୍ମ ସମୟ: {tob}
ବୟସ: {age_str}
ସ୍ଥାନ: {normalized_location}

ଦୟାକରି ସହଜ ଓ ପଠନଯୋଗ୍ୟ ଭାବରେ ଭାଗ କରି ଦିଅନ୍ତୁ:

1. ଆଜିର ରାଶିଫଳ (ସଂକ୍ଷିପ୍ତ)
2. ଅଗାମୀ 6-12 ମାସ ଭବିଷ୍ୟତ ପର୍ଯ୍ୟାଳୋଚନା
3. ଦୀର୍ଘ ଭବିଷ୍ୟତ (2-5 ବର୍ଷ) ଦୃଷ୍ଟିକୋଣ
4. ଚାକିରି / କ୍ୟାରିଅର କେଉଁ କ୍ଷେତ୍ରରେ ବଢ଼ିପାରିବ (ଉଦାହରଣ: IT, ଗଭ ଜବ୍, ଶିକ୍ଷା, ବ୍ୟବସାୟ)
5. ବିବାହର ସମ୍ଭାବ୍ୟ ସମୟ (ବର୍ଷ ରେଞ୍ଜ୍, ନିଶ୍ଚିତ ତାରିଖ ନୁହେଁ)
6. ଆର୍ଥିକ ସ୍ଥିତି ଓ ମନି ମ୍ୟାନେଜ୍ମେଣ୍ଟ ପରାମର୍ଶ
7. ଭଲ / ଭାଗ୍ୟଶାଳୀ ରଙ୍ଗ (କାହିଁକି)
8. 5ଟି ପ୍ରାୟୋଗିକ ପଦକ୍ଷେପ (Action Tips)

ଶୈଳୀ: ସକାରାତ୍ମକ, ଉତ୍ସାହଜନକ, ବ୍ୟବହାରିକ। କୌଣସି ନିଶ୍ଚିତ ଭବିଷ୍ୟତ ଭବିଷ୍ୟବାଣୀ ନ ଦିଅ।
ପଢ଼ିବାର ସୁବିଧା ପାଇଁ ବୁଲେଟ୍/ new line ବ୍ୟବହାର କରନ୍ତୁ।
    """.strip()

    # Try primary model, fallback if needed
    for model_name in (MODEL_NAME, MODEL_FALLBACK):
        try:
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt)
            if resp and getattr(resp, "text", None):
                return resp.text.strip()
        except Exception as e:
            print(f"Gemini error with model {model_name}:", e)

    # Total failure fallback
    return (
        "⚠️ Gemini ସର୍ଭର ସମସ୍ୟା । ସାଧାରଣ ପରାମର୍ଶ:\n"
        "• ସକାରାତ୍ମକ ରୁହନ୍ତୁ\n"
        "• ପ୍ରତିଦିନ ଶିଖନ୍ତୁ\n"
        "• ସ୍ବାସ୍ଥ୍ୟ ଓ ଅର୍ଥ କୁ ପ୍ରାଥମ୍ୟ ଦିଅନ୍ତୁ"
    )

# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    global _last_report
    prediction = None
    normalized_location = None
    pdf_file = None

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        dob = request.form.get("dob", "").strip()
        tob = request.form.get("tob", "").strip()
        location = request.form.get("location", "").strip()

        if name and dob and tob and location:
            normalized_location = normalize_location(location)
            age = calc_age(dob)
            prediction = get_ai_prediction(name, dob, tob, normalized_location, age)

            _last_report = {
                "name": name,
                "dob": dob,
                "tob": tob,
                "age": age,
                "normalized_location": normalized_location,
                "prediction": prediction,
            }
            pdf_file = make_pdf(_last_report)

    return render_template(
        "index.html",
        prediction=prediction,
        normalized_location=normalized_location,
        pdf_file=os.path.basename(pdf_file) if pdf_file else None,
    )

@app.route("/download", methods=["GET"])
def download_pdf():
    if not _last_report:
        return abort(400, "No report available!")
    path = make_pdf(_last_report)  # re-generate latest
    return send_file(path, as_attachment=True)

# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Development server (debug); for production use Gunicorn
    app.run(host="0.0.0.0", port=5000, debug=True)
