import time, io, os, shutil, logging
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional, List
from pydantic import BaseModel
import fitz  # PyMuPDF
from PIL import Image
from openai import OpenAI
import sqlite3
import datetime
import hashlib

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("payslip")

try:
    import pytesseract

    def _detect_tess():
        path = shutil.which("tesseract")
        ver = str(pytesseract.get_tesseract_version()) if path else None
        langs = pytesseract.get_languages(config="") if path else []
        return path, ver, langs

    TESSERACT_PATH, TESSERACT_VERSION, TESSERACT_LANGS = _detect_tess()
except Exception:
    pytesseract = None
    TESSERACT_PATH, TESSERACT_VERSION, TESSERACT_LANGS = None, None, []

TESSERACT_AVAILABLE = TESSERACT_PATH is not None

# OCR budgets to avoid long hangs
MAX_OCR_PAGES = int(os.getenv("MAX_OCR_PAGES", "3"))
MAX_TOTAL_SECONDS = int(os.getenv("MAX_TOTAL_SECONDS", "60"))

# Rasterization config for speed/accuracy tradeoff
# ~150–180 DPI equivalent; grayscale to reduce bytes.
SCALE = 1.5  # 72dpi * 1.5 ≈ 108 dpi (fast); bump to 2.0 if needed
MATRIX = fitz.Matrix(SCALE, SCALE)
USE_LANG = "heb+eng"  # will auto-fallback below


def ocr_image_fast(pil_img):
    """Run tesseract OCR with language fallback."""
    if not TESSERACT_AVAILABLE:
        raise HTTPException(status_code=400, detail="OCR is not available on server")
    lang = USE_LANG if "heb" in TESSERACT_LANGS else "eng"
    try:
        return pytesseract.image_to_string(pil_img.convert("L"), lang=lang)
    except Exception:
        # last resort: let tesseract auto-detect
        return pytesseract.image_to_string(pil_img.convert("L"))
log.info(
    "Tesseract available=%s path=%s ver=%s langs_count=%d",
    TESSERACT_AVAILABLE,
    TESSERACT_PATH,
    TESSERACT_VERSION,
    len(TESSERACT_LANGS),
)

if not os.getenv("OPENAI_API_KEY"):
    # Do not raise immediately on import if you prefer; you can check inside the handler instead.
    pass

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "ocr": {
            "available": TESSERACT_AVAILABLE,
            "version": TESSERACT_VERSION,
            "langs_count": len(TESSERACT_LANGS),
        },
    }


@app.get("/debug/ocr")
async def debug_ocr():
    return {
        "available": TESSERACT_AVAILABLE,
        "path": TESSERACT_PATH,
        "version": TESSERACT_VERSION,
        "langs": TESSERACT_LANGS,
    }


@app.get("/", response_class=HTMLResponse)
async def read_frontend():
    with open("frontend.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# Knowledge base content
KNOWLEDGE_BASE = """
# 🧠 Knowledge Base: ניתוח תלושי שכר

מדריך מלא ומעמיק על איך לקרוא, להבין ולנתח תלושי שכר, כולל הגדרות, רכיבי התלוש, ניכויים, פנסיה, והסברים חשובים.

## 📌 1. פרטי העובד והמעביד
- שם העובד/ת ותעודת זהות
- שם העסק, מס' תיק ניכויים, כתובת
- סוג משרה, סטטוס משפחתי, תושב ישראל?
- תאריך תחילת עבודה וותק
- האם משרה יחידה או נוספת
- סוג שכר: חודשי או שעתי

## 💸 2. תשלומים והחזרי הוצאות

### ➤ תשלומים בשל עבודה:
- שכר בסיס, שעות נוספות, עמלות מכירה

### ➤ זכויות סוציאליות:
- דמי הבראה, חגים, מילואים, ימי מחלה, חופשה בתשלום, בידוד

### ➤ החזרי הוצאות:
- נסיעות, טלפון, ארוחות, שווי מתנות (למשל תלושים לחג)

## 🚫 3. ניכויי חובה
- מס הכנסה
- ביטוח לאומי
- ביטוח בריאות
- פנסיה
- דמי טיפול לארגון מקצועי (0.8% אם יש הסכם)

### 💡 חשוב:
המעסיק מחויב לנכות ולהעביר תשלומים אלו על פי חוק. אי ניכוי/אי דיווח = עבירה פלילית.

## 💼 4. ניכויי רשות
- קרן השתלמות
- ארוחות מסובסדות, קניות בהנחה
- מקדמות/חובות
- קנסות (רק אם אושרו בחוק או הסכם)

## 🧮 5. חישוב הפרשות לפנסיה

### ➤ שיעורי הפרשה:
- מעסיק: 6.5%
- עובד: 6%
- לפיצויים: לפחות 6%

### ➤ רכיבים לחישוב פנסיה:
- שכר בסיס + תוספות קבועות
- שעות רגילות
- דמי חופשה, מחלה, בידוד, חגים, בונוסים קבועים

> שעות נוספות *לא* נכללות אלא אם כן נקבע אחרת.

## 🗓️ 6. מידע נוסף בתלוש
- מספר ימי עבודה / שעות / חופשות
- נקודות זיכוי: 2.25 לגבר תושב ישראל, 2.75 לאישה
- סכומי תשלום לביטוח לאומי, בריאות ומס הכנסה

## 📊 7. נתונים מצטברים
- שכר מצטבר לשנה
- סה"כ מסים ששולמו
- הפרשות לפנסיה
- סכומי חופשה ומחלה שנצברו/נוצלו

## 😷 8. חופשה ומחלה
- ימי חופשה שנצברו החודש / נוצלו
- ימי מחלה שנצברו / נוצלו
- חשוב למעקב משפטי (פיצויים, זכויות סוציאליות)

## ⚠️ 9. דגשים חשובים
- חובה על המעסיק למסור תלוש שכר בכל חודש
- חובה לשמור את התלושים (הוכחה לזכויות)
- עבודה "בשחור" מסכנת את העובד, אין זכויות
"""

# Configure OpenAI/Groq API
def setup_api():
    """Setup OpenAI client for Groq API"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not set")
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    return client

# Database functions
def init_database():
    """Initialize SQLite database for user data"""
    conn = sqlite3.connect('payslip_data.db')
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create payslips table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payslips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            filename TEXT,
            file_hash TEXT,
            extracted_text TEXT,
            ai_analysis TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def save_payslip_analysis(user_id, filename, file_hash, extracted_text, ai_analysis):
    """Save payslip analysis to database"""
    conn = sqlite3.connect('payslip_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO payslips (user_id, filename, file_hash, extracted_text, ai_analysis)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, filename, file_hash, extracted_text, ai_analysis))
    payslip_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return payslip_id

def get_user_payslips(user_id):
    """Get all payslips for a user"""
    conn = sqlite3.connect('payslip_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, filename, created_at, extracted_text, ai_analysis
        FROM payslips 
        WHERE user_id = ? 
        ORDER BY created_at DESC
        LIMIT 10
    ''', (user_id,))
    results = cursor.fetchall()
    conn.close()
    return results

def calculate_file_hash(file_content):
    """Calculate hash of file content"""
    return hashlib.md5(file_content).hexdigest()

def extract_text_from_pdf(pdf_content):
    """Extract text from PDF with time/page budgets and OCR fallback."""
    start = time.perf_counter()
    text_out = []
    ocr_pages_used = 0

    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF open failed: {str(e)[:200]}")

    for page_idx, page in enumerate(doc):
        if (time.perf_counter() - start) > MAX_TOTAL_SECONDS:
            log.warning("OCR timeout budget hit at page %s", page_idx)
            break

        direct = (page.get_text("text") or "").strip()
        if direct:
            text_out.append(direct)
            continue

        if ocr_pages_used >= MAX_OCR_PAGES:
            log.info(
                "OCR page budget reached (%d). Skipping OCR for remaining pages.",
                MAX_OCR_PAGES,
            )
            continue

        try:
            pix = page.get_pixmap(matrix=MATRIX, alpha=False, colorspace=fitz.csGRAY)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_text = (ocr_image_fast(img) or "").strip()
            if ocr_text:
                text_out.append(ocr_text)
            ocr_pages_used += 1
        except Exception as e:
            log.exception("OCR failed on page %s: %s", page_idx, e)
            continue

    doc.close()

    full_text = "\n\n".join(text_out).strip()
    elapsed = time.perf_counter() - start
    log.info(
        "Extracted %d chars using %d OCR pages in %.2fs (pages=%d)",
        len(full_text),
        ocr_pages_used,
        elapsed,
        len(doc),
    )
    return full_text, ocr_pages_used, elapsed

def extract_text_from_image(image_content):
    """Extract text from image using OCR"""
    if not TESSERACT_AVAILABLE:
        raise HTTPException(
            status_code=400,
            detail="OCR is not available on server (missing tesseract)",
        )
    try:
        image = Image.open(io.BytesIO(image_content))
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')

        try:
            text = pytesseract.image_to_string(image, lang="heb+eng")
        except Exception:
            text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception:
        raise HTTPException(status_code=400, detail="שגיאה ב-OCR של התמונה.")

def explain_payslip_with_knowledge(text, client):
    """Get AI explanation of the payslip with knowledge base context"""
    try:
        messages = [
            {
                "role": "system", 
                "content": f"""אתה מומחה לתלושי שכר בישראל עם ידע מעמיק על החוק הישראלי. 

{KNOWLEDGE_BASE}

השתמש בידע זה כדי לתת הסבר מדויק, מפורט וברור על תלוש השכר. 
הסבר את המשמעות של כל ניכוי, תוספת ומס בהתבסס על החוק הישראלי.
השתמש בעברית פשוטה וברורה."""
            },
            {
                "role": "user", 
                "content": f"""הנה תוכן התלוש שלי:

{text}

אנא הסבר לי בפירוט:
1. מה המשכורת הגולמית שלי?
2. אילו ניכויים נעשו ומה המשמעות שלהם?
3. מה המשכורת הנקייה שלי?
4. האם יש תוספות מיוחדות?
5. האם הניכויים נראים תקינים לפי החוק?
6. איזה זכויות יש לי כעובד?

תן לי הסבר מפורט ומובן בעברית עם התייחסות לחוק הישראלי."""
            }
        ]
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=3000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה בקבלת הסבר מהבינה המלאכותית: {str(e)}")

def compare_payslips_with_ai(payslips_data, client):
    """Compare multiple payslips using AI with knowledge base"""
    try:
        # Prepare payslips text for comparison
        payslips_text = ""
        for i, payslip in enumerate(payslips_data):
            payslips_text += f"=== תלוש {i+1}: {payslip['filename']} ===\n{payslip['extracted_text']}\n\n"
        
        messages = [
            {
                "role": "system", 
                "content": f"""אתה מומחה לתלושי שכר בישראל עם ידע מעמיק על החוק הישראלי.

{KNOWLEDGE_BASE}

תפקידך לבצע השוואה מפורטת בין תלושי שכר ולהתריע על:
1. הבדלים בשכר ותוספות
2. שינויים בניכויים
3. שגיאות או אי-התאמות לחוק
4. מגמות והתפתחויות
5. המלצות לעובד

תן ניתוח מפורט ומקצועי בעברית פשוטה."""
            },
            {
                "role": "user", 
                "content": f"""אנא השווה בין התלושים הבאים ותן ניתוח מפורט:

{payslips_text}

אני מעוניין לקבל:
1. טבלת השוואה של הסכומים העיקריים
2. ניתוח ההבדלים והסיבות האפשריות
3. האם יש בעיות או שגיאות
4. מגמות שכדאי לשים לב אליהן
5. המלצות והערות חשובות

תן תשובה מאורגנת ומובנת בעברית."""
            }
        ]
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=4000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה בהשוואת תלושים: {str(e)}")

def answer_question_with_context(question, context, previous_analysis, client):
    """Answer user question with payslip context and knowledge base"""
    try:
        messages = [
            {
                "role": "system", 
                "content": f"""אתה מומחה לתלושי שכר בישראל עם ידע מעמיק על החוק הישראלי.

{KNOWLEDGE_BASE}

ענה על שאלות המשתמש בהתבסס על:
1. הקונטקסט של תלוש השכר שלו
2. הידע המקצועי על החוק הישראלי
3. הניתוח הקודם שנעשה

תן תשובות מדויקות ומועילות בעברית פשוטה."""
            },
            {
                "role": "user", 
                "content": f"""תוכן תלוש השכר:
{context}

ניתוח קודם:
{previous_analysis}

השאלה שלי:
{question}

אנא ענה בהתבסס על המידע הקיים והידע המקצועי שלך."""
            }
        ]
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה בקבלת תשובה: {str(e)}")

# Pydantic models
class QuestionRequest(BaseModel):
    question: str
    context: Optional[str] = ""
    previous_analysis: Optional[str] = ""

# Initialize database on startup
init_database()
client = setup_api()

@app.post("/analyze-payslip")
async def analyze_payslip(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    log.info(
        "Analyze request: filename=%s content-type=%s size=%s",
        file.filename,
        file.content_type,
        len(data),
    )

    ct = (file.content_type or "").lower()
    is_pdf = ct in [
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
    ] or file.filename.lower().endswith(".pdf")

    if is_pdf:
        full_text, ocr_pages_used, elapsed = extract_text_from_pdf(data)
    elif ct.startswith("image/"):
        start = time.perf_counter()
        full_text = extract_text_from_image(data)
        elapsed = time.perf_counter() - start
        ocr_pages_used = 1 if full_text else 0
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported type '{ct}'. Upload PDF or image.",
        )

    if not full_text:
        raise HTTPException(
            status_code=400,
            detail="Couldn't extract text. Try a text-based PDF or increase OCR budget.",
        )

    file_hash = calculate_file_hash(data)
    analysis = explain_payslip_with_knowledge(full_text, client)
    user_id = "web_user"
    payslip_id = save_payslip_analysis(
        user_id, file.filename, file_hash, full_text, analysis
    )

    log.info(
        "Analyze done: chars=%d ocr_pages_used=%d elapsed=%.2fs",
        len(full_text),
        ocr_pages_used,
        elapsed,
    )

    return {
        "success": True,
        "extracted_text": full_text,
        "analysis": analysis,
        "payslip_id": payslip_id,
    }


@app.post("/debug/echo")
async def debug_echo(file: UploadFile = File(None)):
    return {
        "have_file": bool(file),
        "filename": getattr(file, "filename", None) if file else None,
        "content_type": getattr(file, "content_type", None) if file else None,
    }

@app.post("/compare-payslips")
async def compare_payslips(files: List[UploadFile] = File(...)):
    """Compare multiple payslip files"""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="נדרשים לפחות 2 קבצים להשוואה")
    
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="ניתן להשוות עד 5 תלושים בו-זמנית")
    
    payslips_data = []
    
    # Process each file
    for i, file in enumerate(files):
        # Read file content
        file_content = await file.read()
        
        # Extract text based on file type
        ct = (file.content_type or "").lower()
        is_pdf = ct in [
            "application/pdf",
            "application/x-pdf",
            "application/octet-stream",
        ] or file.filename.lower().endswith(".pdf")

        if is_pdf:
            extracted_text, _, _ = extract_text_from_pdf(file_content)
        elif ct.startswith("image/"):
            extracted_text = extract_text_from_image(file_content)
        else:
            raise HTTPException(status_code=400, detail=f"קובץ {file.filename}: סוג קובץ לא נתמך")
        
        if not extracted_text or not extracted_text.strip():
            raise HTTPException(status_code=400, detail=f"לא הצלחתי לחלץ טקסט מקובץ {file.filename}")
        
        payslips_data.append({
            "filename": file.filename,
            "extracted_text": extracted_text
        })
    
    # Get AI comparison analysis
    comparison_analysis = compare_payslips_with_ai(payslips_data, client)
    
    # Save comparison to database
    user_id = "web_user"
    for payslip in payslips_data:
        file_hash = calculate_file_hash(payslip["extracted_text"].encode())
        save_payslip_analysis(user_id, payslip["filename"], file_hash, 
                            payslip["extracted_text"], comparison_analysis)
    
    return {
        "success": True,
        "payslips": payslips_data,
        "comparison_analysis": comparison_analysis,
        "total_files": len(files)
    }

@app.post("/ask-question")
async def ask_question(request: QuestionRequest):
    """Answer user question about payslip"""
    answer = answer_question_with_context(
        request.question, 
        request.context, 
        request.previous_analysis, 
        client
    )
    
    return {
        "success": True,
        "answer": answer
    }

@app.get("/get-history")
async def get_history():
    """Get user's payslip history"""
    user_id = "web_user"  # Simple user ID for web interface
    payslips = get_user_payslips(user_id)
    
    history = []
    for payslip in payslips:
        history.append({
            "id": payslip[0],
            "filename": payslip[1],
            "created_at": payslip[2],
            "extracted_text": payslip[3],
            "ai_analysis": payslip[4]
        })
    
    return history

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
