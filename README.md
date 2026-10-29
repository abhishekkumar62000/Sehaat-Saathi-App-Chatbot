# Sehaat Saathi App – AI Doctor Chatbot 🧑‍⚕️

> **India's 1st AI Powered Virtual HealthCare Platform** — FastAPI + Groq AI + Tailwind CSS

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template)

---

## 🚀 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Uvicorn |
| AI Model | Groq (`qwen/qwen3.8-27b`) |
| Frontend | Tailwind CSS + Alpine.js |
| Database | SQLite (auth) |
| PDF | FPDF2 |

## ✨ Features

- 🩺 **13 AI Doctor Personas** — General Physician, Cardiologist, Neurologist, Pediatrician, and more
- 💬 **Real-Time Streaming Chat** with SSE
- 📋 **Patient Registration Form** with profile memory
- 📄 **Prescription PDF Generator**
- 🏥 **OPD Token Generator**
- 🧘 **14 Wellness Tools** — BMI, Diet Plan, Sleep, Yoga, Symptom Checker & more
- 📱 **Mobile Responsive** — Sidebar drawer toggle for phones
- 🌐 **Hindi + English** language support
- 🇮🇳 Patriotic UI — Saffron/Green/Cyan tricolor theme

## 🛠️ Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/abhishekkumar62000/Sehaat-Saathi-App-Chatbot.git
cd Sehaat-Saathi-App-Chatbot

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your Groq API key
echo GROQ_API_KEY=your_key_here > .env

# 5. Run the server
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Open [http://localhost:8000](http://localhost:8000) 🎉

## ☁️ Deploy to Railway (FREE, Recommended)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Select this repo
4. Add Environment Variable: `GROQ_API_KEY = your_key`
5. Railway auto-detects `Procfile` → deploys instantly

Live URL will be provided by Railway (e.g., `https://sehaat-saathi.up.railway.app`)

## 🐳 Docker Deploy

```bash
docker build -t sehaat-saathi .
docker run -p 8000:8000 -e GROQ_API_KEY=your_key sehaat-saathi
```

## ⚠️ Disclaimer

> This app provides AI-generated health information for **educational purposes only**. Always consult a licensed medical professional for diagnosis and treatment.

---

Made with ❤️ by [Abhishek Kumar](https://github.com/abhishekkumar62000)
