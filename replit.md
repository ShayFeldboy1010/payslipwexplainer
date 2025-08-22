# Overview

This is a Streamlit-based web application for analyzing Hebrew payslips (salary slips). The application allows users to upload PDF documents and extract text content using a combination of direct PDF text extraction and OCR (Optical Character Recognition) technology. The extracted text can then be processed using AI models through the Groq API.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Primary Interface**: Modern HTML/CSS/JavaScript frontend with Tailwind CSS and RTL Hebrew support
- **Secondary Interface**: Streamlit fallback application
- **UI Features**: 
  - Drag-and-drop file upload
  - Real-time chat interface with AI
  - User history and analysis storage
  - Professional dark theme with Hebrew RTL layout
- **Technologies**: HTML5, Tailwind CSS, Lucide Icons, Vanilla JavaScript

## Backend Architecture
- **Primary Backend**: FastAPI REST API server (port 8000)
- **Secondary Backend**: Streamlit application (port 5000)
- **API Endpoints**:
  - POST /analyze-payslip: Single file upload and analysis
  - POST /compare-payslips: Multiple file comparison (2-5 files)
  - POST /ask-question: Interactive Q&A about payslips
  - GET /get-history: User analysis history
  - GET /: Serves frontend HTML
- **Processing Pipeline**: 
  1. PDF/Image upload handling via FastAPI
  2. Text extraction (hybrid approach)
  3. AI-powered analysis with integrated knowledge base
  4. Real-time chat responses
- **Text Extraction Strategy**: Two-tier approach - direct PDF text extraction with OCR fallback

## Data Processing
- **Primary Method**: PyMuPDF (fitz) for direct PDF text extraction
- **Fallback Method**: Tesseract OCR for image-based text extraction
- **Language Support**: Hebrew and English OCR capabilities

# Key Components

## PDF Processing Module
- **PyMuPDF Integration**: Handles PDF file reading and page iteration
- **Direct Text Extraction**: Attempts to extract selectable text from PDF pages
- **OCR Fallback**: Converts PDF pages to images and applies OCR when direct extraction fails
- **Multi-language OCR**: Configured for Hebrew and English text recognition

## AI Integration
- **API Provider**: Groq API (accessed through OpenAI client interface)
- **Model**: llama-3.3-70b-versatile (updated from deprecated mixtral-8x7b-32768)
- **Base URL**: Custom endpoint at "https://api.groq.com/openai/v1"
- **Authentication**: API key-based authentication with hardcoded fallback
- **Knowledge Base**: Integrated comprehensive Hebrew payslip knowledge base covering:
  - Israeli labor law and regulations
  - Payslip components and calculations
  - Mandatory and optional deductions
  - Pension and social benefits
  - Employee rights and protections

## Database Integration
- **Database Type**: SQLite3 (local file-based database)
- **Database File**: payslip_data.db
- **Tables**:
  - users: User sessions with unique IDs
  - payslips: Stored payslip analyses with file hashes
  - analysis_history: Historical analysis records
- **Features**:
  - User session management
  - Payslip analysis storage and retrieval
  - Historical data access via sidebar
  - File deduplication using MD5 hashes

## Error Handling
- Exception handling for PDF processing errors
- User-friendly error messages in Hebrew
- Graceful degradation when text extraction fails

# Data Flow

1. **File Upload**: User uploads PDF document through Streamlit interface
2. **Document Processing**: 
   - PDF is opened using PyMuPDF
   - Each page is processed sequentially
   - Direct text extraction is attempted first
   - If no text is found, page is converted to image for OCR
3. **Text Aggregation**: Extracted text from all pages is combined
4. **AI Processing**: Combined text can be sent to Groq API for analysis
5. **Results Display**: Processed results are displayed in the Streamlit interface

# External Dependencies

## Core Libraries
- **streamlit**: Web application framework
- **PyMuPDF (fitz)**: PDF processing and manipulation
- **pytesseract**: Python wrapper for Tesseract OCR engine
- **PIL (Pillow)**: Image processing for OCR pipeline
- **openai**: API client for AI model interaction

## System Dependencies
- **Tesseract OCR Engine**: Must be installed on the system
- **Hebrew Language Pack**: Required for Hebrew OCR functionality

## API Dependencies
- **Groq API**: External AI service for text analysis
- **API Key Management**: Currently uses hardcoded key with environment variable fallback

# Deployment Strategy

## Environment Requirements
- Python runtime with required packages
- Tesseract OCR engine installation
- Hebrew language data for Tesseract
- Network access to Groq API endpoints

## Configuration
- **API Key**: Set via OPENAI_API_KEY environment variable
- **OCR Languages**: Configured for "heb+eng" (Hebrew + English)
- **Streamlit Config**: Centered layout, Hebrew interface

## Security Considerations
- **API Key Exposure**: Current implementation has hardcoded API key (security risk)
- **File Upload**: PDF files are processed in memory without persistent storage
- **Error Information**: Error messages may expose system details

## Scalability Notes
- **Single-threaded Processing**: Sequential page processing may be slow for large documents
- **Memory Usage**: Large PDF files loaded entirely into memory
- **API Rate Limits**: No rate limiting implementation for external API calls