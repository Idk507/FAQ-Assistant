from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
import json
import uuid
from datetime import datetime
import asyncio
import io
import PyPDF2
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor

# Import the regulatory FAQ system
from main import RegulatoryFAQSystem
from config.azure_config import AZURE_OPENAI_CONFIG

# Global variables for the system
system = None
chat_sessions = {}
feedback_data = []  # Store all feedback for analytics

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for FastAPI"""
    global system
    # Startup
    try:
        system = RegulatoryFAQSystem()
        print("✅ Regulatory FAQ System initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize system: {e}")
        system = None

    yield

    # Shutdown
    print("🔄 Shutting down Regulatory FAQ System...")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Regulatory FAQ Assistant",
    description="AI-powered regulatory FAQ generation and customer query answering system",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/img", StaticFiles(directory="img"), name="img")

# Templates
templates = Jinja2Templates(directory="templates")

# Global variables for chat sessions
chat_sessions = {}

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatSession(BaseModel):
    session_id: str
    title: str
    messages: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

class FeedbackData(BaseModel):
    message_id: str
    feedback_type: str  # "positive" or "negative"
    session_id: str
    timestamp: datetime
    query: Optional[str] = None  # The user's query that led to this response

# PDF Processing Functions
async def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF using pdfplumber (more accurate)"""
    try:
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

            if not text.strip():
                # Fallback to PyPDF2 if pdfplumber fails
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"

            return text.strip()
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        # Final fallback to PyPDF2
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e2:
            print(f"Error with PyPDF2 fallback: {e2}")
            raise HTTPException(status_code=400, detail="Unable to extract text from PDF. The PDF may be corrupted or contain only images.")

def validate_pdf_file(file: UploadFile) -> None:
    """Validate PDF file"""
    # Check file type
    if not file.content_type == "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # Check file size (10MB limit)
    if file.size and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main chat interface"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "Regulatory FAQ Assistant"
    })

@app.post("/api/chat")
async def chat(message: ChatMessage, background_tasks: BackgroundTasks):
    """Handle chat messages"""
    global system, chat_sessions

    if system is None:
        raise HTTPException(status_code=500, detail="System is still initializing. Please try again in a moment.")

    try:
        # Create or get session
        session_id = message.session_id or str(uuid.uuid4())

        if session_id not in chat_sessions:
            chat_sessions[session_id] = ChatSession(
                session_id=session_id,
                title=message.message[:50] + "..." if len(message.message) > 50 else message.message,
                messages=[],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

        session = chat_sessions[session_id]

        # Add user message
        user_message = {
            "role": "user",
            "content": message.message,
            "timestamp": datetime.now().isoformat()
        }
        session.messages.append(user_message)

        # Get response from the regulatory system
        response = await system.answer_customer_query(message.message, session_id)

        # Get the cleaned answer (already processed by the system)
        cleaned_answer = response.get("answer", "I apologize, but I'm experiencing technical difficulties.")

        # Generate unique message ID
        message_id = f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Add assistant message
        assistant_message = {
            "role": "assistant",
            "content": cleaned_answer,
            "suggestions": response.get("suggestions", []),
            "timestamp": response.get("timestamp", datetime.now().isoformat()),
            "message_id": message_id,
            "metadata": {
                "used_realtime_search": response.get("used_realtime_search", False),
                "context_sources": response.get("context_sources", 0)
            }
        }
        session.messages.append(assistant_message)

        # Update session
        session.updated_at = datetime.now()

        return {
            "session_id": session_id,
            "response": assistant_message["content"],
            "message_id": message_id,
            "suggestions": assistant_message["suggestions"],
            "timestamp": assistant_message["timestamp"],
            "metadata": assistant_message["metadata"]
        }

    except Exception as e:
        print(f"Error processing chat: {e}")
        raise HTTPException(status_code=500, detail="Failed to process message")

@app.post("/api/process-regulation")
async def process_regulation(
    request: Request,
    pdf_file: Optional[UploadFile] = File(None),
    regulatory_text: Optional[str] = Form(None),
    context: Optional[str] = Form(None)
):
    """Process a new regulatory update - supports both PDF upload and text input"""
    global system

    if system is None:
        raise HTTPException(status_code=500, detail="System is still initializing. Please try again in a moment.")

    try:
        final_text = ""

        # Handle PDF file if provided
        if pdf_file:
            validate_pdf_file(pdf_file)
            file_content = await pdf_file.read()
            extracted_text = await extract_text_from_pdf(file_content)
            final_text = extracted_text
            print(f"✅ Extracted {len(extracted_text)} characters from PDF: {pdf_file.filename}")

        # Handle text input (from form or JSON)
        if regulatory_text and regulatory_text.strip():
            if final_text:
                final_text += "\n\n" + regulatory_text.strip()
            else:
                final_text = regulatory_text.strip()

        # Also try to get JSON data if it's a JSON request
        if not final_text:
            try:
                json_data = await request.json()
                final_text = json_data.get("regulatory_text", "")
                if not context:
                    context = json_data.get("context", "")
            except:
                pass

        if not final_text:
            raise HTTPException(status_code=400, detail="No regulatory content provided. Please upload a PDF or enter text.")

        # Process the regulatory update
        result = await system.process_regulatory_update(final_text, context or "")

        return {
            "status": "success",
            "message": f"Successfully processed regulatory update. Generated {result['faqs_generated']} FAQs.",
            "source": "PDF upload" if pdf_file else "Text input",
            "details": result
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing regulation: {e}")
        raise HTTPException(status_code=500, detail="Failed to process regulatory update")

@app.get("/api/sessions")
async def get_sessions():
    """Get all chat sessions"""
    global chat_sessions

    sessions_list = []
    for session_id, session in chat_sessions.items():
        sessions_list.append({
            "session_id": session.session_id,
            "title": session.title,
            "message_count": len(session.messages),
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "last_message": session.messages[-1]["content"][:100] + "..." if session.messages else ""
        })

    # Sort by updated_at (most recent first)
    sessions_list.sort(key=lambda x: x["updated_at"], reverse=True)

    return {"sessions": sessions_list}

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get a specific chat session"""
    global chat_sessions

    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = chat_sessions[session_id]
    return {
        "session_id": session.session_id,
        "title": session.title,
        "messages": session.messages,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat()
    }

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session"""
    global chat_sessions

    if session_id not in chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    del chat_sessions[session_id]
    return {"message": "Session deleted successfully"}

@app.get("/api/system-status")
async def get_system_status():
    """Get system status"""
    global system

    if system is None:
        return {
            "status": "initializing",
            "message": "System is initializing..."
        }

    try:
        status = system.get_system_status()
        return {
            "status": "ready",
            "details": status
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/api/voice_query")
async def voice_query(message: ChatMessage, background_tasks: BackgroundTasks):
    """Handle voice input queries - same as regular chat but for voice"""
    global system, chat_sessions

    if system is None:
        await initialize_system()
        if system is None:
            raise HTTPException(status_code=500, detail="System is still initializing. Please try again in a moment.")

    try:
        # Create or get session
        session_id = message.session_id or str(uuid.uuid4())

        if session_id not in chat_sessions:
            chat_sessions[session_id] = ChatSession(
                session_id=session_id,
                title=message.message[:50] + "..." if len(message.message) > 50 else message.message,
                messages=[],
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

        session = chat_sessions[session_id]

        # Add user message
        user_message = {
            "role": "user",
            "content": message.message,
            "timestamp": datetime.now().isoformat(),
            "source": "voice"
        }
        session.messages.append(user_message)

        # Get response from the regulatory system
        response = await system.answer_customer_query(message.message, session_id)

        # Get the cleaned answer (already processed by the system)
        cleaned_answer = response.get("answer", "I apologize, but I'm experiencing technical difficulties.")

        # Generate unique message ID
        message_id = f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        # Add assistant message
        assistant_message = {
            "role": "assistant",
            "content": cleaned_answer,
            "suggestions": response.get("suggestions", []),
            "timestamp": response.get("timestamp", datetime.now().isoformat()),
            "message_id": message_id,
            "metadata": {
                "used_realtime_search": response.get("used_realtime_search", False),
                "context_sources": response.get("context_sources", 0),
                "source": "voice_query"
            }
        }
        session.messages.append(assistant_message)

        # Update session
        session.updated_at = datetime.now()

        return {
            "session_id": session_id,
            "response": assistant_message["content"],
            "message_id": message_id,
            "suggestions": assistant_message["suggestions"],
            "timestamp": assistant_message["timestamp"],
            "metadata": assistant_message["metadata"]
        }

    except Exception as e:
        print(f"Error processing voice query: {e}")
        raise HTTPException(status_code=500, detail="Failed to process voice query")

@app.post("/api/feedback")
async def submit_feedback(feedback: FeedbackData):
    """Submit user feedback for a message"""
    global feedback_data, chat_sessions

    try:
        # Find the corresponding user query from the session
        query = None
        if feedback.session_id in chat_sessions:
            session = chat_sessions[feedback.session_id]
            # Find the user message that preceded this assistant message
            for i, msg in enumerate(session.messages):
                if msg.get("message_id") == feedback.message_id:
                    # Look backwards for the user query
                    for j in range(i-1, -1, -1):
                        if session.messages[j].get("role") == "user":
                            query = session.messages[j].get("content")
                            break
                    break

        # Create feedback entry
        feedback_entry = {
            "message_id": feedback.message_id,
            "feedback_type": feedback.feedback_type,
            "session_id": feedback.session_id,
            "timestamp": feedback.timestamp.isoformat(),
            "query": query
        }

        feedback_data.append(feedback_entry)

        return {"message": "Feedback submitted successfully", "feedback_id": len(feedback_data) - 1}

    except Exception as e:
        print(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")

@app.get("/api/analytics")
async def get_analytics():
    """Get analytics data for feedback"""
    global feedback_data

    try:
        # Calculate basic stats
        positive_count = sum(1 for f in feedback_data if f["feedback_type"] == "positive")
        negative_count = sum(1 for f in feedback_data if f["feedback_type"] == "negative")
        total_feedback = len(feedback_data)

        # Get recent feedback (last 10)
        recent_feedback = sorted(feedback_data, key=lambda x: x["timestamp"], reverse=True)[:10]

        # Prepare chart data (last 7 days)
        chart_data = {
            "labels": [],
            "positive": [],
            "negative": []
        }

        # Generate last 7 days
        from datetime import datetime, timedelta
        for i in range(6, -1, -1):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            chart_data["labels"].append(date)

            # Count positive and negative for this date
            positive = sum(1 for f in feedback_data
                          if f["timestamp"].startswith(date) and f["feedback_type"] == "positive")
            negative = sum(1 for f in feedback_data
                          if f["timestamp"].startswith(date) and f["feedback_type"] == "negative")

            chart_data["positive"].append(positive)
            chart_data["negative"].append(negative)

        return {
            "positive_count": positive_count,
            "negative_count": negative_count,
            "total_feedback": total_feedback,
            "recent_feedback": recent_feedback,
            "chart_data": chart_data
        }

    except Exception as e:
        print(f"Error getting analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics")

@app.get("/api/analytics/export")
async def export_analytics():
    """Export analytics data as CSV"""
    global feedback_data

    try:
        return {
            "feedback": feedback_data,
            "export_timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error exporting analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to export analytics")

@app.get("/api/download-chat/{session_id}")
async def download_chat_pdf(session_id: str):
    """Download chat session as PDF"""
    global chat_sessions

    try:
        if session_id not in chat_sessions:
            raise HTTPException(status_code=404, detail="Chat session not found")

        session = chat_sessions[session_id]

        # Create PDF buffer
        buffer = io.BytesIO()

        # Create PDF document
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()

        # Create custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=30,
            alignment=1,  # Center alignment
            textColor=HexColor('#0ea5e9')
        )

        user_style = ParagraphStyle(
            'UserMessage',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=10,
            leftIndent=20,
            backgroundColor=HexColor('#f0f9ff'),
            borderColor=HexColor('#0ea5e9'),
            borderWidth=1,
            borderPadding=10,
            borderRadius=5
        )

        assistant_style = ParagraphStyle(
            'AssistantMessage',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=10,
            leftIndent=20,
            backgroundColor=HexColor('#fef3c7'),
            borderColor=HexColor('#f59e0b'),
            borderWidth=1,
            borderPadding=10,
            borderRadius=5
        )

        timestamp_style = ParagraphStyle(
            'Timestamp',
            parent=styles['Normal'],
            fontSize=10,
            textColor=HexColor('#6b7280'),
            spaceAfter=15,
            alignment=2  # Right alignment
        )

        # Build PDF content
        content = []

        # Title
        title = session.title or f"Chat Session - {session_id[:8]}"
        content.append(Paragraph(title, title_style))
        content.append(Spacer(1, 20))

        # Session info
        session_info = f"Created: {session.created_at.strftime('%Y-%m-%d %H:%M:%S')} | Messages: {len(session.messages)}"
        content.append(Paragraph(session_info, timestamp_style))
        content.append(Spacer(1, 30))

        # Messages
        for i, msg in enumerate(session.messages):
            if msg.get('role') == 'user':
                # User message
                timestamp = msg.get('timestamp', '')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        content.append(Paragraph(f"You - {dt.strftime('%H:%M:%S')}", timestamp_style))
                    except:
                        pass

                content.append(Paragraph(msg.get('content', ''), user_style))

            elif msg.get('role') == 'assistant':
                # Assistant message
                timestamp = msg.get('timestamp', '')
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        content.append(Paragraph(f"Assistant - {dt.strftime('%H:%M:%S')}", timestamp_style))
                    except:
                        pass

                content.append(Paragraph(msg.get('content', ''), assistant_style))

                # Add suggestions if available
                suggestions = msg.get('suggestions', [])
                if suggestions:
                    content.append(Paragraph("Related Questions:", styles['Heading4']))
                    for j, suggestion in enumerate(suggestions, 1):
                        content.append(Paragraph(f"{j}. {suggestion}", styles['Bullet']))
                    content.append(Spacer(1, 10))

        # Build and save PDF
        doc.build(content)

        # Return PDF as streaming response
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="chat_session_{session_id}.pdf"'
            }
        )

    except Exception as e:
        print(f"Error generating PDF for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
