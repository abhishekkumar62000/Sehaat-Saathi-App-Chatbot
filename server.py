import os
import sys
import time
import json
import base64
import random
import datetime
from typing import Optional, List
from pathlib import Path

# Force UTF-8 on Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fpdf import FPDF
from PIL import Image
from PyPDF2 import PdfReader

# Import existing core modules
from AI_Doctor_Agents import get_system_prompt
from RealTimeData import emergency_services
from auth_database import patient_db

try:
    from groq import Groq
    GROQ_CLIENT_AVAILABLE = True
except ImportError:
    GROQ_CLIENT_AVAILABLE = False

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except Exception:
    PYTESSERACT_AVAILABLE = False

# Initialize FastAPI App
app = FastAPI(title="Sehaat Saathi - AI Doctor & Healthcare Platform", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files if directory exists or root images
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
groq_client = None
if GROQ_API_KEY and GROQ_CLIENT_AVAILABLE:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        print(f"[WARN] Groq init warning: {e}")

# --- Helper: OCR Image Reader ---
def extract_text_from_image(image_file):
    try:
        if os.name == 'nt' and PYTESSERACT_AVAILABLE:
            ocr_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                r"C:\Users\DELL\AppData\Local\Tesseract-OCR\tesseract.exe"
            ]
            for path in ocr_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
        img = Image.open(image_file)
        img = img.convert('L')
        text = pytesseract.image_to_string(img) if PYTESSERACT_AVAILABLE else ""
        return text.strip() if text else None
    except Exception as e:
        print(f"[ERROR] OCR error: {e}")
        return None

# --- PDF Classes ---
class PrescriptionPDF(FPDF):
    def header(self):
        self.set_fill_color(0, 51, 102)
        self.rect(0, 0, 210, 42, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font('Times', 'B', 24)
        self.cell(0, 14, 'SEHAAT SAATHI MEDICAL CENTER', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 5, 'Advanced AI-Integrated Diagnostic & Healthcare Network', 0, 1, 'C')
        self.set_font('Arial', '', 9)
        self.cell(0, 5, 'Health City Tower | National Digital Health Mission (NDHM) Ready', 0, 1, 'C')
        self.ln(8)

    def footer(self):
        self.set_y(-25)
        self.set_draw_color(0, 102, 204)
        self.set_text_color(0, 102, 204)
        self.set_font('Arial', 'B', 8)
        self.rect(145, 260, 50, 14)
        self.text(147, 265, 'DIGITALLY VERIFIED')
        self.text(147, 270, 'SEHAAT SAATHI AI-MD')
        self.set_y(-12)
        self.set_font('Arial', '', 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 5, 'AI Clinical Tele-Consultation. In severe emergency, call 112 / 108.', 0, 1, 'C')

def create_prescription_pdf(patient_name, age, gender, weight, conditions, advice, doctor_name="Dr. Sehaat (General Physician)"):
    pdf = PrescriptionPDF()
    pdf.add_page()
    
    # Patient info box
    pdf.set_y(48)
    pdf.set_fill_color(245, 250, 255)
    pdf.rect(10, 48, 190, 36, 'F')
    pdf.set_draw_color(0, 51, 102)
    pdf.rect(10, 48, 190, 36)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(0, 51, 102)
    pdf.set_xy(15, 52)
    pdf.cell(100, 8, f"PATIENT: {patient_name.upper()}")
    pdf.set_font("Arial", '', 10)
    pdf.set_text_color(60, 60, 60)
    pdf.set_xy(130, 52)
    pdf.cell(60, 8, f"DATE: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}", align='R')
    
    pdf.set_font("Arial", 'B', 10)
    pdf.set_xy(15, 62)
    pdf.cell(30, 7, "AGE / GENDER:")
    pdf.set_font("Arial", '', 10)
    pdf.cell(40, 7, f"{age} YRS / {gender}")
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(20, 7, "WEIGHT:")
    pdf.set_font("Arial", '', 10)
    pdf.cell(30, 7, f"{weight} KG")
    
    pdf.ln(7)
    pdf.set_font("Arial", 'B', 10)
    pdf.set_x(15)
    pdf.cell(35, 7, "CHIEF COMPLAINTS:")
    pdf.set_font("Arial", 'I', 9)
    pdf.set_text_color(140, 40, 40)
    pdf.cell(0, 7, f"{conditions or 'General Tele-Consultation'}")
    
    pdf.ln(12)
    pdf.set_font("Times", 'B', 24)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(20, 12, "Rx", ln=True)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)
    
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 7, f"ATTENDING SPECIALIST: {doctor_name.upper()}", ln=True)
    pdf.ln(2)
    
    # Clean emojis for Latin-1 PDF encoding
    clean_advice = advice.replace("👨‍⚕️", "").replace("💊", "•").replace("🩺", "").replace("✅", "[x]").replace("⚠️", "Caution: ").replace("🫀", "").replace("🧠", "").replace("🦴", "").replace("👶", "").replace("💅", "").replace("👂", "").replace("👩‍⚕️", "").replace("🔬", "").replace("🌱", "").replace("🤝", "")
    pdf.set_font("Times", '', 11)
    pdf.set_text_color(25, 25, 25)
    
    for line in clean_advice.split('\n'):
        line_clean = line.strip().encode('latin-1', 'replace').decode('latin-1')
        if not line_clean:
            pdf.ln(2)
            continue
        if ":" in line_clean and len(line_clean) < 40 and not line_clean.startswith("•"):
            pdf.ln(2)
            pdf.set_font("Times", 'B', 11)
            pdf.multi_cell(0, 6, line_clean)
            pdf.set_font("Times", '', 11)
        else:
            pdf.multi_cell(0, 6, line_clean)
            
    return pdf.output(dest='S').encode('latin-1')

def generate_opd_ticket(hospital, name, token, time_slot):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 20)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(190, 15, txt="SEHAAT SAATHI - DIGITAL OPD PASS", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", size=12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(190, 9, txt=f"Hospital: {hospital}", ln=True)
    pdf.cell(190, 9, txt=f"Digital Token ID: #{token}", ln=True)
    pdf.line(10, 48, 200, 48)
    pdf.ln(8)
    pdf.set_font("Arial", 'B', 13)
    pdf.cell(190, 9, txt=f"Patient Name: {name}", ln=True)
    pdf.cell(190, 9, txt=f"Priority Status: CONFIRMED QUEUE POSITION", ln=True)
    pdf.cell(190, 9, txt=f"Reporting Slot: {time_slot}", ln=True)
    pdf.cell(190, 9, txt=f"Issued On: {datetime.datetime.now().strftime('%d-%m-%Y %H:%M')}", ln=True)
    pdf.ln(12)
    pdf.set_font("Arial", 'I', 10)
    pdf.set_text_color(180, 0, 0)
    pdf.multi_cell(190, 7, txt="IMPORTANT: Please show this digital token at the hospital emergency/OPD desk 15 minutes before the reporting slot.")
    pdf.ln(8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(190, 8, txt="Powered by Sehaat Saathi Real-Time Emergency Network", ln=True, align='C')
    return pdf.output(dest='S').encode('latin-1')

def create_ics_file(med_name, dosage, time_str):
    now = datetime.datetime.now()
    try:
        h, m = map(int, time_str.split(':'))
        start_dt = now.replace(hour=h, minute=m, second=0)
        if start_dt < now:
            start_dt += datetime.timedelta(days=1)
    except Exception:
        start_dt = now + datetime.timedelta(hours=1)
    end_dt = start_dt + datetime.timedelta(minutes=30)
    
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//SehaatSaathi//MedicineReminder//EN
BEGIN:VEVENT
SUMMARY:💊 Take Medicine: {med_name} ({dosage})
DTSTART:{start_dt.strftime('%Y%m%dT%H%M00')}
DTEND:{end_dt.strftime('%Y%m%dT%H%M00')}
DESCRIPTION:Prescribed via Sehaat Saathi AI.\\nDosage: {dosage}\\nStay Healthy!
LOCATION:Home
STATUS:CONFIRMED
BEGIN:VALARM
TRIGGER:-PT15M
DESCRIPTION:Medicine Reminder
ACTION:DISPLAY
END:VALARM
END:VEVENT
END:VCALENDAR"""
    return ics_content.encode('utf-8')

# --- Pydantic Request Models ---
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    doctor_role: str
    patient_name: Optional[str] = "Patient"
    patient_age: Optional[int] = 30
    patient_gender: Optional[str] = "Male"
    patient_weight: Optional[float] = 65.0
    patient_conditions: Optional[str] = "None"
    patient_allergies: Optional[str] = "None"
    messages: List[ChatMessage]

class OPDRequest(BaseModel):
    hospital: str
    patient_name: str
    time_slot: Optional[str] = "Within 45 Minutes"

class RxRequest(BaseModel):
    patient_name: str
    age: int
    gender: str
    weight: float
    conditions: str
    advice: str
    doctor_name: Optional[str] = "Dr. Sehaat (General Physician)"

class ReminderRequest(BaseModel):
    med_name: str
    dosage: str
    time_str: str

class ToolAIRequest(BaseModel):
    tool_type: str
    payload: dict

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok", "app": "SehaatSaathi"}

@app.api_route("/api/config", methods=["GET", "HEAD"])
async def get_config():
    return {
        "status": "online",
        "groq_connected": bool(groq_client),
        "states": list(emergency_services.state_districts.keys()),
        "doctors": [
            {"id": "General Physician (General Medicine)", "name": "Dr. Sehaat", "title": "Senior General Physician", "avatar": "👨‍⚕️", "desc": "Internal medicine, fevers, viral infections, general diagnostics"},
            {"id": "Cardiologist (Heart Specialist)", "name": "Dr. Hriday", "title": "Interventional Cardiologist", "avatar": "🫀", "desc": "Hypertension, chest pain triage, cardiovascular health"},
            {"id": "Neurologist (Brain & Nerves)", "name": "Dr. Megha", "title": "Consultant Neurologist", "avatar": "🧠", "desc": "Headaches, migraines, nerve health, sleep hygiene"},
            {"id": "Orthopedic Surgeon (Bone & Joint)", "name": "Dr. Haddi", "title": "Orthopedic Specialist", "avatar": "🦴", "desc": "Joints, back pain, sports rehabilitation, R.I.C.E. protocol"},
            {"id": "Pediatrician (Child Specialist)", "name": "Dr. Khushi", "title": "Gentle Pediatrician", "avatar": "👶", "desc": "Child health, infant nutrition, age-based safe dosing"},
            {"id": "Dermatologist (Skin & Hair)", "name": "Dr. Twacha", "title": "Board-Certified Dermatologist", "avatar": "💅", "desc": "Acne, rashes, hair fall, evidence-based skin regimens"},
            {"id": "ENT Specialist (Ear, Nose, Throat)", "name": "Dr. Kan-Nak", "title": "Otolaryngologist", "avatar": "👂", "desc": "Sore throat, sinuses, ear infections, vertigo"},
            {"id": "Gynecologist (Women's Health)", "name": "Dr. Sthree", "title": "Senior Gynecologist & OB", "avatar": "👩‍⚕️", "desc": "PCOS/PCOD, reproductive wellness, menstrual health"},
            {"id": "Psychiatrist/Therapist (Mental Health)", "name": "Dr. Manas", "title": "Clinical Psychologist & CBT", "avatar": "🧘", "desc": "Anxiety, mood, grounded mindfulness, CBT techniques"},
            {"id": "Clinical Pharmacist (Medicine Expert)", "name": "Dr. Aushadh", "title": "PhD Clinical Pharmacist", "avatar": "💊", "desc": "Drug interactions, dosing schedules, OTC molecule checks"},
            {"id": "Consult Panel (Multi-Doctor Board)", "name": "Sehaat Medical Board", "title": "Multi-Specialist Joint Board", "avatar": "🤝", "desc": "Comprehensive 360-degree case review by Physician, Specialist & Pharmacist"},
            {"id": "Medical Consultant (Report Analyst)", "name": "Dr. Analyst", "title": "Diagnostic & Lab Consultant", "avatar": "🔬", "desc": "Lab reports, blood panels, biomarkers, radiology breakdown"},
            {"id": "Ayurvedic Practitioner (Natural Remedies)", "name": "Vaidya Veda", "title": "Master of Ayurveda (BAMS)", "avatar": "🌿", "desc": "Natural home remedies, holistic wellness, dosha balancing"}
        ]
    }

@app.get("/api/hospitals")
async def get_hospitals(state: str = "Bihar", district: Optional[str] = None):
    available_cities = emergency_services.state_districts.get(state, [])
    active_city = district if district in available_cities else (available_cities[0] if available_cities else "Patna")
    
    # Retrieve or generate hospital availability for city
    hospital_names = emergency_services.hospitals.get(active_city, [
        f"{active_city} Super Speciality Hospital",
        f"{active_city} Civil Hospital",
        f"LifeCare Hospital {active_city}"
    ])
    
    results = []
    for h in hospital_names:
        total_beds = random.randint(45, 180)
        icu_beds = random.randint(2, 22)
        oxygen_beds = random.randint(10, 45)
        ventilators = random.randint(1, 8)
        status = "Available" if icu_beds > 5 else ("Filling Fast" if icu_beds > 0 else "Full")
        results.append({
            "name": h,
            "city": active_city,
            "state": state,
            "total_beds": total_beds,
            "icu_beds": icu_beds,
            "oxygen_beds": oxygen_beds,
            "ventilators": ventilators,
            "status": status,
            "ambulance_contact": "+91 108",
            "distance": f"{random.uniform(1.2, 8.5):.1f} km"
        })
    
    return {
        "state": state,
        "district": active_city,
        "available_districts": available_cities,
        "hospitals": results
    }

@app.post("/api/chat")
async def chat_consultation(req: ChatRequest):
    if not groq_client:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured on the server.")
    
    system_prompt = get_system_prompt(
        role=req.doctor_role,
        age=req.patient_age,
        gender=req.patient_gender,
        condition=req.patient_conditions,
        allergies=req.patient_allergies
    )
    
    prompt_messages = [{"role": "system", "content": system_prompt}]
    for m in req.messages[-10:]: # Keep last 10 messages for memory
        prompt_messages.append({"role": m.role, "content": m.content})
        
    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=prompt_messages,
            temperature=0.3,
            max_tokens=800
        )
        reply = completion.choices[0].message.content
        return {"reply": reply}
    except Exception as e:
        print(f"[ERROR] Groq Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"AI Doctor Error: {str(e)}")

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    if not groq_client:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured.")
        
    system_prompt = get_system_prompt(
        role=req.doctor_role,
        age=req.patient_age,
        gender=req.patient_gender,
        condition=req.patient_conditions,
        allergies=req.patient_allergies
    )
    
    prompt_messages = [{"role": "system", "content": system_prompt}]
    for m in req.messages[-10:]:
        prompt_messages.append({"role": m.role, "content": m.content})
        
    def stream_generator():
        try:
            stream = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=prompt_messages,
                temperature=0.3,
                max_tokens=800,
                stream=True
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    yield f"data: {json.dumps({'chunk': delta})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
    return StreamingResponse(stream_generator(), media_type="text/event-stream")

@app.post("/api/upload-report")
async def upload_report(file: UploadFile = File(...)):
    filename = file.filename.lower()
    extracted_text = ""
    try:
        contents = await file.read()
        import io
        if filename.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(contents))
            for page in reader.pages:
                extracted_text += page.extract_text() or ""
        elif filename.endswith((".png", ".jpg", ".jpeg", ".webp")):
            extracted_text = extract_text_from_image(io.BytesIO(contents)) or ""
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF or Image.")
            
        if not extracted_text.strip():
            extracted_text = f"Report file received ({file.filename}), but optical text could not be extracted directly. Please type key values."
            
        return {"filename": file.filename, "extracted_text": extracted_text[:3000]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

@app.post("/api/generate-rx")
async def download_rx(req: RxRequest):
    pdf_bytes = create_prescription_pdf(
        patient_name=req.patient_name,
        age=req.age,
        gender=req.gender,
        weight=req.weight,
        conditions=req.conditions,
        advice=req.advice,
        doctor_name=req.doctor_name
    )
    safe_name = req.patient_name.replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=SehaatSaathi_Prescription_{safe_name}.pdf"}
    )

@app.post("/api/generate-opd-ticket")
async def download_opd_ticket(req: OPDRequest):
    token = f"{random.randint(100, 999)}-SS"
    pdf_bytes = generate_opd_ticket(
        hospital=req.hospital,
        name=req.patient_name,
        token=token,
        time_slot=req.time_slot or "Within 45 Minutes"
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=OPD_Ticket_{token}.pdf"}
    )

@app.post("/api/generate-ics")
async def download_ics(req: ReminderRequest):
    ics_bytes = create_ics_file(
        med_name=req.med_name,
        dosage=req.dosage,
        time_str=req.time_str
    )
    safe_name = req.med_name.replace(" ", "_")
    return Response(
        content=ics_bytes,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename=Reminder_{safe_name}.ics"}
    )

@app.post("/api/tool-ai")
async def run_tool_ai(req: ToolAIRequest):
    if not groq_client:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is not configured.")
        
    tool = req.tool_type
    p = req.payload
    
    if tool == "diet":
        prompt = f"""
        Act as an Expert Clinical Dietitian & Nutritionist. Create a healthy, delicious 1-day meal plan.
        Patient Profile: Age {p.get('age')}, Weight {p.get('weight')}kg, Height {p.get('height')}cm.
        Goal: {p.get('goal')}. Diet: {p.get('diet')} ({p.get('cuisine')} style).
        
        Provide:
        - 🌅 Breakfast (with calorie & protein estimate)
        - ☕ Mid-Morning Snack
        - 🍛 Lunch (with calorie & protein estimate)
        - 🍵 Evening Snack
        - 🥗 Dinner (light & easy to digest)
        - 💡 2 Actionable Clinical Nutrition Tips
        """
    elif tool == "workout":
        prompt = f"""
        Act as a Sports Medicine & Fitness Trainer. Create a {p.get('duration')} min {p.get('level')} workout routine for {p.get('type')}.
        Available Equipment: {p.get('equipment')}.
        Provide:
        1. Warm-up (3-5 min)
        2. Main Exercise Circuit with sets, reps, and form safety precautions
        3. Cool-down & recovery stretch
        """
    elif tool == "food_lens":
        prompt = f"""
        Analyze these food items: "{p.get('query')}".
        Calculate estimated:
        - Total Calories
        - Protein (g), Carbs (g), Fats (g)
        - Glycemic & Health Quality Rating
        - "Burn it Off": Minutes of brisk walking or cycling required to burn these calories.
        """
    elif tool == "lab_simplifier":
        prompt = f"""
        Act as a Senior Clinical Pathologist. Analyze and simplify these lab test results for a patient:
        "{p.get('report')}"
        For each test value:
        1. Indicate Normal / High / Low compared to standard adult reference ranges.
        2. Plain-English meaning of this biomarker in 1 sentence.
        3. Natural lifestyle or dietary action to improve it.
        Add standard clinical disclaimer.
        """
    elif tool == "yoga":
        prompt = f"""
        Create a {p.get('duration')} Yoga sequence specifically tailored for {p.get('goal')}.
        Provide 4-5 targeted Asanas (both Sanskrit and English names), their precise therapeutic benefits, and breathing cues.
        """
    elif tool == "health_news":
        prompt = """
        Generate 5 interesting, scientifically grounded healthcare breakthroughs & wellness updates for today.
        Format with catchy headlines, brief 2-sentence takeaways, and practical advice for daily living.
        """
    elif tool == "generic_savings":
        prompt = f"""
        Analyze the branded medicine: "{p.get('medicine')}".
        Provide:
        1. Active Pharmaceutical Ingredient (API / Generic Salt).
        2. Standard therapeutic use.
        3. Estimated Indian market branded cost vs Pradhan Mantri Jan Aushadhi generic price.
        4. Percentage cost savings for the patient.
        5. Quality confirmation (WHO-GMP generic standards).
        """
    else:
        raise HTTPException(status_code=400, detail="Unknown tool type")
        
    try:
        completion = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert clinical medical & wellness assistant at Sehaat Saathi."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=1200
        )
        return {"result": completion.choices[0].message.content}
    except Exception as e:
        print(f"[ERROR] Tool AI error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/media/{filename}")
async def get_media_file(filename: str):
    file_path = Path(__file__).parent / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/sw.js")
async def service_worker():
    """Minimal service worker to satisfy PWA/browser requests."""
    sw_content = """
// SehaatSaathi - Minimal Service Worker
const CACHE = 'sehaat-v1';
self.addEventListener('install', e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(clients.claim()));
self.addEventListener('fetch', e => {
    if (e.request.method !== 'GET') return;
    e.respondWith(
        fetch(e.request).catch(() => caches.match(e.request))
    );
});
"""
    return Response(content=sw_content, media_type="application/javascript")

@app.get("/manifest.json")
async def pwa_manifest():
    """PWA Web App Manifest for mobile Add-to-Home-Screen."""
    manifest = {
        "name": "SehaatSaathi - AI Doctor",
        "short_name": "SehaatSaathi",
        "description": "India's 1st AI Powered Virtual HealthCare Platform",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f0c29",
        "theme_color": "#00d2ff",
        "icons": [
            {"src": "/media/SehaatSaathi.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/media/SehaatSaathi.png", "sizes": "512x512", "type": "image/png"}
        ]
    }
    return JSONResponse(content=manifest)

# Root page
@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def serve_home():
    template_path = Path(__file__).parent / "templates" / "index.html"
    if template_path.exists():
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Templates index.html not found</h1>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
