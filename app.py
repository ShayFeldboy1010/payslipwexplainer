import streamlit as st
import fitz  # PyMuPDF
from PIL import Image
import io
from openai import OpenAI
import os
import sqlite3
import datetime
import hashlib
from src.ocr import ocr_image_bytes

# Configure the page
st.set_page_config(
    page_title="ניתוח תלוש שכר",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="collapsed"
)

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
    
    # Create analysis history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analysis_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            payslip_id INTEGER,
            question TEXT,
            answer TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            FOREIGN KEY (payslip_id) REFERENCES payslips (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def get_user_id():
    """Get or create user ID for session"""
    if 'user_id' not in st.session_state:
        # Create a simple user ID based on session
        st.session_state.user_id = hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest()[:10]
        
        # Add user to database
        conn = sqlite3.connect('payslip_data.db')
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (st.session_state.user_id,))
        conn.commit()
        conn.close()
    
    return st.session_state.user_id

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
    ''', (user_id,))
    results = cursor.fetchall()
    conn.close()
    return results

def calculate_file_hash(file_content):
    """Calculate hash of file content"""
    return hashlib.md5(file_content).hexdigest()

# Configure OpenAI/Groq API
def setup_api():
    """Setup OpenAI client for Groq API"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("Please set the OPENAI_API_KEY environment variable with your Groq API key")
        st.stop()
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )
    return client

OCR_SCALE = 2.0


def _ocr_page(image_bytes: bytes) -> str:
    """Run OCR on a PNG byte stream via the configured backend."""
    try:
        return ocr_image_bytes(image_bytes)
    except Exception:
        return ""


def extract_text_from_pdf(pdf_file):
    """Efficiently extract text from a PDF, using OCR only when required."""
    try:
        pdf_bytes = pdf_file.read()
        page_texts = []
        ocr_jobs = {}

        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for index, page in enumerate(doc):
                text = (page.get_text("text") or "").strip()
                if text:
                    page_texts.append(text)
                    continue

                pix = page.get_pixmap(matrix=fitz.Matrix(OCR_SCALE, OCR_SCALE), alpha=False)
                ocr_jobs[index] = pix.tobytes("png")
                page_texts.append("")

        if ocr_jobs:
            for idx, data in ocr_jobs.items():
                page_texts[idx] = _ocr_page(data).strip()

        return "\n\n".join(t for t in page_texts if t).strip()
    except Exception as e:
        st.error(f"שגיאה בעיבוד קובץ PDF: {str(e)}")
        return None

def extract_text_from_image(image_file):
    """Extract text from image using OCR"""
    try:
        image = Image.open(image_file)
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return ocr_image_bytes(buf.getvalue()).strip()
    except Exception as e:
        st.error(f"שגיאה בעיבוד קובץ תמונה: {str(e)}")
        return None

def explain_payslip(text, client):
    """Get AI explanation of the payslip"""
    try:
        messages = [
            {
                "role": "system", 
                "content": """אתה מומחה לתלושי שכר בישראל ועוזר לעובדים להבין את תלוש השכר שלהם. 
                תן הסבר מפורט, ברור ומובן על כל חלק בתלוש. הסבר את המשמעות של כל ניכוי, 
                תוספת ומס. השתמש בעברית פשוטה וברורה."""
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
5. האם הניכויים נראים תקינים?

תן לי הסבר מפורט ומובן בעברית."""
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
        st.error(f"שגיאה בקבלת הסבר מהבינה המלאכותית: {str(e)}")
        return None

def main():
    """Main application"""
    # Initialize database and get user ID
    init_database()
    user_id = get_user_id()
    client = setup_api()
    
    # Custom CSS for RTL support
    st.markdown("""
    <style>
    .main {
        direction: rtl;
        text-align: right;
    }
    .stFileUploader > div {
        direction: rtl;
        text-align: right;
    }
    .stButton > button {
        direction: rtl;
        text-align: center;
    }
    .stTextArea textarea {
        direction: rtl;
        text-align: right;
    }
    .stMarkdown {
        direction: rtl;
        text-align: right;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.title("📄 ניתוח תלוש שכר חכם")
    st.markdown("**העלה את תלוש השכר שלך וקבל הסבר מפורט על כל חלק בתלוש**")
    
    # Sidebar for user history
    with st.sidebar:
        st.subheader("📚 ההיסטוריה שלך")
        user_payslips = get_user_payslips(user_id)
        
        if user_payslips:
            st.write(f"נמצאו {len(user_payslips)} תלושים:")
            for i, payslip in enumerate(user_payslips):
                payslip_id, filename, created_at, extracted_text, ai_analysis = payslip
                with st.expander(f"{filename} ({created_at[:10]})"):
                    if st.button(f"הצג ניתוח", key=f"show_{payslip_id}"):
                        st.session_state.selected_payslip = {
                            'filename': filename,
                            'analysis': ai_analysis,
                            'text': extracted_text
                        }
        else:
            st.write("עדיין לא ניתחת תלושים")
    
    # Show selected payslip from history
    if 'selected_payslip' in st.session_state:
        st.subheader(f"📋 ניתוח קודם: {st.session_state.selected_payslip['filename']}")
        
        with st.expander("📝 הטקסט המקורי"):
            st.text_area(
                "תוכן שחולץ:",
                value=st.session_state.selected_payslip['text'],
                height=150,
                disabled=True,
                key="historical_text"
            )
        
        st.markdown("### 🤖 הניתוח:")
        st.markdown(st.session_state.selected_payslip['analysis'])
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ מחק מההיסטוריה"):
                del st.session_state.selected_payslip
                st.rerun()
        with col2:
            st.download_button(
                label="💾 הורד ניתוח",
                data=st.session_state.selected_payslip['analysis'],
                file_name=f"analysis_{st.session_state.selected_payslip['filename']}.txt",
                mime="text/plain"
            )
        
        st.markdown("---")
    
    # Instructions
    with st.expander("📖 הוראות שימוש"):
        st.markdown("""
        1. העלה קובץ PDF או תמונה של תלוש השכר שלך
        2. המערכת תחלץ את הטקסט מהקובץ באמצעות טכנולוגיית OCR
        3. בינה מלאכותית תנתח את התלוש ותספק הסבר מפורט
        4. תקבל הסבר על משכורת גולמית, ניכויים, מסים ומשכורת נקייה
        
        **פורמטים נתמכים:** PDF, PNG, JPG, JPEG
        """)
    
    # File uploader
    uploaded_file = st.file_uploader(
        "📤 בחר קובץ תלוש שכר",
        type=["pdf", "png", "jpg", "jpeg"],
        help="העלה קובץ PDF או תמונה של תלוש השכר שלך"
    )
    
    if uploaded_file is not None:
        st.success("✅ הקובץ נטען בהצלחה!")
        
        # Show file details
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("שם הקובץ", uploaded_file.name)
        with col2:
            st.metric("גודל הקובץ", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("סוג הקובץ", uploaded_file.type)
        
        # Process button
        if st.button("🔍 נתח את התלוש", type="primary"):
            with st.spinner("מעבד את הקובץ... זה עלול לקחת כמה שניות..."):
                
                # Extract text based on file type
                if uploaded_file.type == "application/pdf":
                    extracted_text = extract_text_from_pdf(uploaded_file)
                else:
                    extracted_text = extract_text_from_image(uploaded_file)
                
                if extracted_text and extracted_text.strip():
                    # Show extracted text in expander
                    with st.expander("📝 הטקסט שחולץ מהקובץ"):
                        st.text_area(
                            "תוכן שחולץ:",
                            value=extracted_text,
                            height=200,
                            disabled=True
                        )
                    
                    # Calculate file hash for deduplication
                    file_hash = calculate_file_hash(uploaded_file.getvalue())
                    
                    # Get AI explanation
                    with st.spinner("מקבל הסבר מהבינה המלאכותית..."):
                        explanation = explain_payslip(extracted_text, client)
                    
                    if explanation:
                        # Save to database
                        payslip_id = save_payslip_analysis(
                            user_id, 
                            uploaded_file.name, 
                            file_hash, 
                            extracted_text, 
                            explanation
                        )
                        
                        st.subheader("🤖 ניתוח התלוש שלך")
                        st.markdown(explanation)
                        st.success(f"✅ הניתוח נשמר במאגר הנתונים (מזהה: {payslip_id})")
                        
                        # Download explanation
                        st.download_button(
                            label="💾 הורד הסבר",
                            data=explanation,
                            file_name=f"payslip_analysis_{uploaded_file.name}.txt",
                            mime="text/plain"
                        )
                    else:
                        st.error("לא הצלחתי לקבל הסבר. אנא נסה שוב.")
                
                else:
                    st.error("""
                    לא הצלחתי לחלץ טקסט מהקובץ. אנא וודא ש:
                    - איכות התמונה טובה ויש ניגודיות גבוהה
                    - הטקסט קריא ולא מטושטש
                    - הקובץ לא פגום
                    """)
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #888; font-size: 0.8em;'>"
        "🔒 הפרטיות שלך חשובה לנו - הקבצים לא נשמרים במערכת"
        "</div>",
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
