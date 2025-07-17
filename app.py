from flask import Flask, render_template, request, send_file
import os
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

load_dotenv()
app = Flask(__name__)

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Store last prediction for PDF download
last_prediction = {}

def calculate_age(dob):
    birth_date = datetime.strptime(dob, "%Y-%m-%d")
    today = datetime.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def get_ai_prediction(name, dob, tob, location, age):
    user_prompt = f"""
    Generate a structured Odia astrology report with these points:
    1. ଆଜିର ରାଶିଫଳ (Today's horoscope)
    2. ଆଗାମୀ ଭବିଷ୍ୟତ ପରାମର୍ଶ (Future prediction)
    3. କେଉଁ କ୍ଷେତ୍ରରେ ଚାକିରି ବା ବିକାଶ (Career advice)
    4. ବୟସ: {age} ବର୍ଷ
    Keep it motivational, professional and astrologer tone. 
    Use bullet points in Odia language.
    Details: Name={name}, DOB={dob}, TOB={tob}, Location={location}
    """

    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(user_prompt)
    return response.text

@app.route("/", methods=["GET", "POST"])
def index():
    global last_prediction
    prediction = None
    if request.method == "POST":
        name = request.form.get("name")
        dob = request.form.get("dob")
        tob = request.form.get("tob")
        location = request.form.get("location")

        if name and dob and tob and location:
            age = calculate_age(dob)
            prediction = get_ai_prediction(name, dob, tob, location, age)
            last_prediction = {
                "name": name,
                "dob": dob,
                "tob": tob,
                "location": location,
                "age": age,
                "prediction": prediction
            }

    return render_template("index.html", prediction=prediction)

@app.route("/download")
def download_pdf():
    if not last_prediction:
        return "No prediction available yet!"

    filename = f"astrology_report_{last_prediction['name']}.pdf"
    filepath = os.path.join(os.getcwd(), filename)

    c = canvas.Canvas(filepath, pagesize=A4)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(150, 800, "Siddharth Astrology Report")
    c.setFont("Helvetica", 12)
    c.drawString(50, 770, f"Name: {last_prediction['name']}")
    c.drawString(50, 755, f"DOB: {last_prediction['dob']}")
    c.drawString(50, 740, f"Time: {last_prediction['tob']}")
    c.drawString(50, 725, f"Location: {last_prediction['location']}")
    c.drawString(50, 710, f"Age: {last_prediction['age']} years")

    text_obj = c.beginText(50, 680)
    text_obj.setFont("Helvetica", 12)
    text_obj.textLines("Prediction:\n" + last_prediction["prediction"])
    c.drawText(text_obj)

    c.showPage()
    c.save()

    return send_file(filepath, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
