import logging
import os
import io
import shutil
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional, Tuple, List
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
    TESSERACT_AVAILABLE = shutil.which("tesseract") is not None
except Exception:
    TESSERACT_AVAILABLE = False

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
    return {"status": "ok"}


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
    """Extract text from PDF using PyMuPDF and OCR"""
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        all_text = ""

        for page_num in range(len(doc)):
            page = doc[page_num]
            # First try to extract text directly
            direct_text = page.get_text()

            if direct_text.strip():
                all_text += direct_text + "\n"
            else:
                if not TESSERACT_AVAILABLE:
                    # Skip OCR on this page; continue to next
                    continue
                try:
                    pix = page.get_pixmap()
                    img_bytes = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_bytes))
                    page_text = pytesseract.image_to_string(img, lang="heb+eng")
                    all_text += page_text + "\n"
                except Exception as ocr_err:
                    # Don’t abort; just log/skip this page
                    all_text += "\n"

        doc.close()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"שגיאה בעיבוד קובץ PDF: {str(e)}")

    if not all_text.strip():
        if not TESSERACT_AVAILABLE:
            raise HTTPException(status_code=400, detail="לא הצלחתי לחלץ טקסט. ייתכן שהקובץ סרוק ואין OCR בשרת. התקן Tesseract או העלה PDF עם טקסט חי.")
        raise HTTPException(status_code=400, detail="לא הצלחתי לחלץ טקסט מהקובץ.")

    return all_text.strip()

def extract_text_from_image(image_content):
    """Extract text from image using OCR"""
    if not TESSERACT_AVAILABLE:
        raise HTTPException(status_code=400, detail="OCR לא זמין בשרת. התקן Tesseract כדי לעבד תמונות.")
    try:
        image = Image.open(io.BytesIO(image_content))
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')

        text = pytesseract.image_to_string(image, lang="heb+eng")
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


async def get_uploaded_file(request: Request) -> Tuple[Optional[UploadFile], dict]:
    """
    Try to extract a single uploaded file from common field names.
    Returns (file, meta) where meta includes debug info for logs.
    """
    meta = {"fields": [], "content_types": [], "sizes": []}
    try:
        form = await request.form()
    except Exception as e:
        log.exception("Failed reading multipart form")
        raise HTTPException(status_code=400, detail="Failed to read form-data") from e

    for k, v in form.items():
        meta["fields"].append(k)
        if isinstance(v, UploadFile):
            meta["content_types"].append(getattr(v, "content_type", None))
            try:
                pos = v.file.tell()
                v.file.seek(0, os.SEEK_END)
                meta["sizes"].append(v.file.tell())
                v.file.seek(pos)
            except Exception:
                meta["sizes"].append(None)

    candidates = ["file", "pdf", "document", "upload", "payslip", "files", "files[]"]
    for name in candidates:
        if name in form:
            item = form[name]
            if isinstance(item, list) and item and isinstance(item[0], UploadFile):
                return item[0], meta
            if isinstance(item, UploadFile):
                return item, meta

    for v in form.values():
        if isinstance(v, list):
            for vv in v:
                if isinstance(vv, UploadFile):
                    return vv, meta
        if isinstance(v, UploadFile):
            return v, meta

    return None, meta

@app.post("/analyze-payslip")
async def analyze_payslip(request: Request):
    file, meta = await get_uploaded_file(request)
    log.info("POST /analyze-payslip fields=%s content_types=%s sizes=%s", meta.get("fields"), meta.get("content_types"), meta.get("sizes"))

    if not file:
        return JSONResponse(
            status_code=400,
            content={"detail": "No file found in form-data. Expected field name 'file' (also accepts: pdf, document, upload, files).",
                     "debug": meta},
        )

    ct = (file.content_type or "").lower()
    log.info("Detected content-type: %s; filename: %s", ct, file.filename)

    valid_pdf = ct in ["application/pdf", "application/x-pdf"]
    valid_image = ct.startswith("image/")

    try:
        data = await file.read()
    except Exception as e:
        log.exception("Failed reading uploaded file")
        raise HTTPException(status_code=400, detail="Failed to read uploaded file") from e
    finally:
        try:
            await file.close()
        except Exception:
            pass

    if not data or len(data) == 0:
        return JSONResponse(status_code=400, content={"detail": "Uploaded file is empty"})

    text = ""
    if valid_pdf:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            for page in doc:
                direct = page.get_text("text") or ""
                if direct.strip():
                    text += direct + "\n"
                else:
                    if TESSERACT_AVAILABLE:
                        pix = page.get_pixmap()
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        try:
                            page_text = pytesseract.image_to_string(img, lang="heb+eng")
                        except Exception:
                            page_text = pytesseract.image_to_string(img)
                        text += (page_text or "") + "\n"
            doc.close()
        except Exception as e:
            log.exception("PDF parse failed")
            return JSONResponse(status_code=400, content={"detail": f"PDF parse failed: {str(e)[:200]}"})
    elif valid_image:
        if not TESSERACT_AVAILABLE:
            return JSONResponse(
                status_code=400,
                content={"detail": "OCR is not available on server (missing tesseract). Upload a text-based PDF or enable OCR."},
            )
        try:
            img = Image.open(io.BytesIO(data))
            try:
                text = pytesseract.image_to_string(img, lang="heb+eng")
            except Exception:
                text = pytesseract.image_to_string(img)
        except Exception as e:
            log.exception("Image OCR failed")
            return JSONResponse(status_code=400, content={"detail": f"Image OCR failed: {str(e)[:200]}"})
    else:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Unsupported content-type '{ct}'. Please upload PDF or image."},
        )

    if not (text and text.strip()):
        if valid_pdf and not TESSERACT_AVAILABLE:
            return JSONResponse(
                status_code=400,
                content={"detail": "Couldn't extract text. The PDF looks scanned and server OCR is disabled. Enable tesseract or upload a text PDF."},
            )
        return JSONResponse(status_code=400, content={"detail": "Couldn't extract any text from the file."})

    file_hash = calculate_file_hash(data)
    analysis = explain_payslip_with_knowledge(text, client)
    user_id = "web_user"
    payslip_id = save_payslip_analysis(user_id, file.filename, file_hash, text, analysis)

    return {
        "success": True,
        "extracted_text": text,
        "analysis": analysis,
        "payslip_id": payslip_id,
    }


@app.post("/debug/echo")
async def debug_echo(request: Request):
    file, meta = await get_uploaded_file(request)
    headers = dict(request.headers)
    return {
        "have_file": bool(file),
        "filename": getattr(file, "filename", None) if file else None,
        "content_type": getattr(file, "content_type", None) if file else None,
        "meta": meta,
        "headers_subset": {k: headers.get(k) for k in ["content-type", "user-agent", "content-length"]},
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
        if file.content_type == "application/pdf":
            extracted_text = extract_text_from_pdf(file_content)
        elif file.content_type.startswith("image/"):
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
