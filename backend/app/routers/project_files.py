from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.database import get_async_session
from app.models.project_files import ProjectFile
from app.models.projects import Project
from app.models.users import User
from jose import jwt, JWTError
import logging
import os
import uuid
import shutil
import sys
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

# Set default encoding to UTF-8 to prevent charmap issues on Windows
if sys.platform == "win32":
    import locale
    try:
        # Try to set UTF-8 as the default encoding
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except:
        # Fallback if UTF-8 locale is not available
        pass
PyPDF2 = None
PDF_LIBRARY = None

# Try to install and import PDF libraries if not available
def ensure_pdf_libraries():
    global PyPDF2, PDF_LIBRARY
    
    # First try to import PyPDF2
    try:
        import PyPDF2
        PDF_LIBRARY = "PyPDF2"
        return True
    except ImportError:
        pass
    
    # Try pypdf as fallback
    try:
        from pypdf import PdfReader as PyPDF2_PdfReader
        PDF_LIBRARY = "pypdf"
        # Create a compatibility wrapper
        class PyPDF2:
            @staticmethod
            def PdfReader(file):
                return PyPDF2_PdfReader(file)
        return True
    except ImportError:
        pass
    
    # If both failed, try to install them
    try:
        import subprocess
        import sys
        
        logger.info("Attempting to install PDF libraries...")
        
        # Try installing PyPDF2 first
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "PyPDF2"], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            import PyPDF2
            PDF_LIBRARY = "PyPDF2"
            logger.info("Successfully installed and imported PyPDF2")
            return True
        except:
            pass
        
        # Try installing pypdf as fallback
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf"], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            from pypdf import PdfReader as PyPDF2_PdfReader
            PDF_LIBRARY = "pypdf"
            class PyPDF2:
                @staticmethod
                def PdfReader(file):
                    return PyPDF2_PdfReader(file)
            logger.info("Successfully installed and imported pypdf")
            return True
        except:
            pass
            
    except Exception as e:
        logger.warning(f"Failed to install PDF libraries: {e}")
    
    PDF_LIBRARY = None
    PyPDF2 = None
    return False

# Initialize PDF libraries
ensure_pdf_libraries()

# Try to install and import DOCX library if not available
def ensure_docx_library():
    global DOCX_LIBRARY
    
    try:
        from docx import Document
        DOCX_LIBRARY = "python-docx"
        return True
    except ImportError:
        pass
    
    # If import failed, try to install it
    try:
        import subprocess
        import sys
        
        logger.info("Attempting to install python-docx...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-docx"], 
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        from docx import Document
        DOCX_LIBRARY = "python-docx"
        logger.info("Successfully installed and imported python-docx")
        return True
    except Exception as e:
        logger.warning(f"Failed to install python-docx: {e}")
    
    DOCX_LIBRARY = None
    return False

# Initialize DOCX library
ensure_docx_library()

import io

logger = logging.getLogger(__name__)
router = APIRouter()

# Log library availability on startup
logger.info(f"PDF library available: {PDF_LIBRARY}")
logger.info(f"DOCX library available: {DOCX_LIBRARY}")

@router.get("/libraries/status")
async def get_library_status():
    """Check the status of required libraries"""
    return {
        "pdf_library": PDF_LIBRARY,
        "docx_library": DOCX_LIBRARY,
        "pdf_available": PDF_LIBRARY is not None,
        "docx_available": DOCX_LIBRARY is not None
    }

def extract_pdf_text(file_path: str) -> str:
    """Extract text content from a PDF file using the available library."""
    # Use the module-level library detection
    if PDF_LIBRARY is None or PyPDF2 is None:
        logger.error("No PDF library available (PyPDF2 or pypdf)")
        return "[Error: No PDF library available]"
    
    try:
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
            logger.info(f"Extracted text from PDF using {PDF_LIBRARY}, length: {len(text)}")
            return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return f"[Error extracting text from PDF: {str(e)}]"

class ProjectFileResponse(BaseModel):
    file_id: str
    project_id: str
    filename: str
    original_filename: str
    file_size: int
    file_type: str
    upload_order: int
    created_at: str
    file_content: Optional[str] = None

class ProjectFileUploadResponse(BaseModel):
    file_id: str
    filename: str
    original_filename: str
    file_size: int
    file_type: str
    upload_order: int
    message: str

def safe_read_file(file_path: str, filename: str) -> str:
    """Safely read a file with multiple encoding attempts"""
    encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-1', 'ascii']
    
    for encoding in encodings_to_try:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read()
                # Validate content is readable text
                if any(ord(char) < 32 and char not in '\t\n\r' for char in content[:1000]):
                    logger.warning(f"File {filename} contains binary data")
                    return f"[Binary file - content not readable as text: {filename}]"
                return content
        except (UnicodeDecodeError, UnicodeError, OSError, IOError) as e:
            logger.debug(f"Could not read {filename} with {encoding}: {e}")
            continue
        except Exception as e:
            logger.warning(f"Unexpected error reading {filename} with {encoding}: {e}")
            continue
    
    # If all encodings failed
    logger.warning(f"Could not read {filename} with any encoding")
    return f"[File contains non-UTF-8 content that cannot be read as text: {filename}]"

def decode_email_from_token(token: str) -> str:
    """Decode email from JWT token"""
    import os
    SECRET_KEY = os.getenv("SECRET_KEY", "KyleService")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_user_id_from_email(email: str) -> str:
    """Get user_id from email"""
    try:
        async for session in get_async_session():
            result = await session.execute(
                select(User.user_id).where(User.email == email)
            )
            user_id = result.scalar_one_or_none()
            return user_id
    except Exception as e:
        logger.error(f"Error getting user_id from email: {e}")
        return None

@router.get("/projects/{project_id}/files", response_model=List[ProjectFileResponse])
async def get_project_files(request: Request, project_id: str):
    """Get all files for a specific project"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="User not found")

        async for session in get_async_session():
            # Verify project belongs to user
            project_result = await session.execute(
                select(Project)
                .where(Project.project_id == project_id)
                .where(Project.user_id == user_id)
            )
            project = project_result.scalar_one_or_none()
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Get files for this project
            result = await session.execute(
                select(ProjectFile)
                .where(ProjectFile.project_id == project_id)
                .order_by(ProjectFile.upload_order.asc())
            )
            files = result.scalars().all()
            
            file_list = []
            for file in files:
                logger.info(f"📁 File {file.original_filename} - has content: {bool(file.file_content)}, length: {len(file.file_content) if file.file_content else 0}")
                file_list.append(ProjectFileResponse(
                    file_id=str(file.file_id),
                    project_id=str(file.project_id),
                    filename=file.filename,
                    original_filename=file.original_filename,
                    file_size=file.file_size,
                    file_type=file.file_type,
                    upload_order=file.upload_order,
                    created_at=file.created_at.isoformat() if file.created_at else None,
                    file_content=file.file_content
                ))
            
            logger.info(f"Found {len(file_list)} files for project {project_id}")
            return file_list
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project files: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/projects/{project_id}/files", response_model=ProjectFileUploadResponse)
async def upload_project_file(
    request: Request,
    project_id: str,
    file: UploadFile = File(...)
):
    """Upload a file to a project"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="User not found")

        async for session in get_async_session():
            # Verify project belongs to user
            project_result = await session.execute(
                select(Project)
                .where(Project.project_id == project_id)
                .where(Project.user_id == user_id)
            )
            project = project_result.scalar_one_or_none()
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Get next upload order
            order_result = await session.execute(
                select(ProjectFile.upload_order)
                .where(ProjectFile.project_id == project_id)
                .order_by(ProjectFile.upload_order.desc())
                .limit(1)
            )
            next_order = order_result.scalar_one_or_none()
            upload_order = (next_order or 0) + 1
            
            # Generate unique filename
            file_extension = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            
            # Create uploads directory if it doesn't exist
            upload_dir = f"uploads/projects/{project_id}"
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, unique_filename)
            
            # Save file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Read file content for text-based files
            file_content = None
            try:
                logger.info(f"Processing file {file.filename}, content_type: {file.content_type}")
                # Try to read content for text-based files (exclude binary files)
                # Note: PDF and DOCX files are binary but we can extract text from them
                binary_types = [
                    'application/zip', 'application/x-zip-compressed',
                    'image/', 'video/', 'audio/', 'application/octet-stream'
                ]
                binary_extensions = ['.zip', '.rar', '.7z', '.jpg', '.jpeg', '.png', '.gif', '.bmp', 
                                   '.mp4', '.avi', '.mov', '.mp3', '.wav', '.exe', '.dll', '.bin',
                                   '.xlsx', '.xls', '.pptx', '.ppt']
                
                # PDF and DOCX files are binary but we can extract text from them
                is_extractable_binary = (file.filename.lower().endswith(('.pdf', '.docx', '.doc')) or
                                       (file.content_type and file.content_type in ['application/pdf', 'application/vnd.openxmlformats-officedocument', 'application/msword']))
                
                is_binary = (any(file.content_type.startswith(bt) for bt in binary_types) if file.content_type else False) or \
                           any(file.filename.lower().endswith(ext) for ext in binary_extensions)
                
                # Additional binary detection by reading first few bytes
                if not is_binary:
                    try:
                        with open(file_path, 'rb') as f:
                            first_bytes = f.read(1024)
                            # Check for common binary file signatures
                            if (first_bytes.startswith(b'\x89PNG') or  # PNG
                                first_bytes.startswith(b'\xff\xd8\xff') or  # JPEG
                                first_bytes.startswith(b'GIF8') or  # GIF
                                first_bytes.startswith(b'%PDF') or  # PDF
                                first_bytes.startswith(b'PK\x03\x04') or  # ZIP/DOCX
                                any(ord(b) < 32 and b not in b'\t\n\r' for b in first_bytes[:100])):
                                is_binary = True
                                logger.info(f"File {file.filename} detected as binary by content analysis")
                    except Exception as e:
                        logger.warning(f"Could not analyze file content for {file.filename}: {e}")
                
                logger.info(f"File {file.filename} - is_binary: {is_binary}, content_type: {file.content_type}")
                
                # Handle extractable binary files (PDF, DOCX, DOC) - extract text content
                if is_extractable_binary:
                    if file.filename.lower().endswith('.pdf'):
                        logger.info(f"📄 Processing PDF file: {file.filename}")
                        try:
                            file_content = extract_pdf_text(file_path)
                            if file_content and not file_content.startswith("[Error extracting"):
                                logger.info(f"✅ Extracted PDF content for file {file.filename}, length: {len(file_content)}")
                                logger.info(f"📄 PDF content preview: {file_content[:100]}...")
                            else:
                                logger.warning(f"⚠️ Could not extract text from PDF {file.filename}")
                                file_content = None
                        except Exception as e:
                            logger.error(f"❌ Error processing PDF {file.filename}: {e}")
                            file_content = None
                    elif file.filename.lower().endswith(('.docx', '.doc')):
                        logger.info(f"📄 Processing Word document: {file.filename}")
                        try:
                            if file.filename.lower().endswith('.docx'):
                                # Check if python-docx is available
                                if DOCX_LIBRARY is None:
                                    logger.error("❌ python-docx library not available")
                                    file_content = f"[Error: python-docx library not installed. Please install it using: pip install python-docx. Current DOCX_LIBRARY status: {DOCX_LIBRARY}]"
                                else:
                                    # Extract content from DOCX files using python-docx
                                    try:
                                        doc = Document(file_path)
                                        paragraphs = []
                                        for paragraph in doc.paragraphs:
                                            if paragraph.text.strip():
                                                paragraphs.append(paragraph.text.strip())
                                        file_content = '\n'.join(paragraphs)
                                        logger.info(f"✅ Extracted DOCX content for file {file.filename}, length: {len(file_content)}")
                                        logger.info(f"📄 DOCX content preview: {file_content[:100]}...")
                                    except Exception as docx_error:
                                        logger.error(f"❌ Error reading DOCX file {file.filename}: {docx_error}")
                                        file_content = f"[Error reading DOCX file: {file.filename} - {str(docx_error)}]"
                            else:
                                # For .doc files (older format), we'll store a message indicating the limitation
                                file_content = f"[Word document (.doc format): {file.filename} - Content extraction not available for .doc files. Please convert to .docx format for full text extraction.]"
                                logger.info(f"⚠️ DOC file format not supported for content extraction: {file.filename}")
                        except Exception as e:
                            logger.error(f"❌ Error processing Word document {file.filename}: {e}")
                            file_content = f"[Error extracting content from Word document: {file.filename} - {str(e)}]"
                elif (file.content_type and 
                    (file.content_type.startswith('text/') or 
                     file.content_type in ['application/json', 'application/javascript', 'application/x-python-code', 'text/csv', 'application/csv'] or
                     file.filename.endswith(('.txt', '.js', '.py', '.json', '.md', '.html', '.css', '.xml', '.csv', '.log'))) and
                    not is_binary):
                    # Use the safe file reading function
                    file_content = safe_read_file(file_path, file.filename)
                    logger.info(f"✅ Processed file {file.filename}, content length: {len(file_content) if file_content else 0}")
                else:
                    logger.info(f"⚠️ File {file.filename} not processed for content storage (type: {file.content_type})")
            except (UnicodeDecodeError, UnicodeError, OSError) as e:
                logger.warning(f"❌ Encoding error reading file {file.filename}: {e}")
                if "charmap" in str(e) or "0x8d" in str(e):
                    logger.warning(f"❌ Windows charmap encoding error for {file.filename}, storing placeholder")
                    file_content = f"[File contains non-UTF-8 content that cannot be read as text: {file.filename}]"
                else:
                    file_content = f"[Error reading file: {str(e)}]"
            except Exception as e:
                logger.warning(f"❌ Could not read content for file {file.filename}: {e}")
                file_content = None
            
            # Create database record
            logger.info(f"💾 Storing file {file.filename} with content length: {len(file_content) if file_content else 0}")
            if file_content:
                logger.info(f"📄 Content preview: {file_content[:100]}...")
            else:
                logger.warning(f"⚠️ No content to store for file {file.filename}")
            
            project_file = ProjectFile(
                project_id=project_id,
                user_id=user_id,
                filename=unique_filename,
                original_filename=file.filename,
                file_path=file_path,
                file_size=file.size,
                file_type=file.content_type or 'application/octet-stream',
                file_content=file_content,
                upload_order=upload_order
            )
            
            session.add(project_file)
            await session.commit()
            
            logger.info(f"Uploaded file {file.filename} to project {project_id}")
            
            return ProjectFileUploadResponse(
                file_id=str(project_file.file_id),
                filename=project_file.filename,
                original_filename=project_file.original_filename,
                file_size=project_file.file_size,
                file_type=project_file.file_type,
                upload_order=project_file.upload_order,
                message="File uploaded successfully"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/projects/{project_id}/files/{file_id}")
async def delete_project_file(request: Request, project_id: str, file_id: str):
    """Delete a file from a project"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="User not found")

        async for session in get_async_session():
            # Verify project belongs to user
            project_result = await session.execute(
                select(Project)
                .where(Project.project_id == project_id)
                .where(Project.user_id == user_id)
            )
            project = project_result.scalar_one_or_none()
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Find the file
            file_result = await session.execute(
                select(ProjectFile)
                .where(ProjectFile.file_id == file_id)
                .where(ProjectFile.project_id == project_id)
            )
            project_file = file_result.scalar_one_or_none()
            
            if not project_file:
                raise HTTPException(status_code=404, detail="File not found")
            
            # Delete physical file
            if os.path.exists(project_file.file_path):
                os.remove(project_file.file_path)
            
            # Delete database record
            await session.delete(project_file)
            await session.commit()
            
            logger.info(f"Deleted file {file_id} from project {project_id}")
            
            return {"message": "File deleted successfully"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/projects/{project_id}/files/{file_id}/content")
async def get_file_content(request: Request, project_id: str, file_id: str):
    """Get the content of a specific file"""
    try:
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        email = decode_email_from_token(token)
        user_id = await get_user_id_from_email(email)
        
        if not user_id:
            raise HTTPException(status_code=401, detail="User not found")

        async for session in get_async_session():
            # Verify project belongs to user
            project_result = await session.execute(
                select(Project)
                .where(Project.project_id == project_id)
                .where(Project.user_id == user_id)
            )
            project = project_result.scalar_one_or_none()
            
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            # Find the file
            file_result = await session.execute(
                select(ProjectFile)
                .where(ProjectFile.file_id == file_id)
                .where(ProjectFile.project_id == project_id)
            )
            project_file = file_result.scalar_one_or_none()
            
            if not project_file:
                raise HTTPException(status_code=404, detail="File not found")
            
            # Return file content
            logger.info(f"File {file_id} - has stored content: {bool(project_file.file_content)}")
            logger.info(f"File {file_id} - type: {project_file.file_type}")
            logger.info(f"File {file_id} - path exists: {os.path.exists(project_file.file_path) if project_file.file_path else False}")
            
            if project_file.file_content:
                logger.info(f"Returning stored content for file {file_id}, length: {len(project_file.file_content)}")
                return {"content": project_file.file_content, "filename": project_file.original_filename}
            else:
                # For files without stored content, try to read from disk
                if os.path.exists(project_file.file_path):
                    # Check if file is binary before trying to read as text
                    binary_types = [
                        'application/pdf', 'application/zip', 'application/x-zip-compressed',
                        'image/', 'video/', 'audio/', 'application/octet-stream'
                    ]
                    binary_extensions = ['.pdf', '.zip', '.rar', '.7z', '.jpg', '.jpeg', '.png', '.gif', '.bmp', 
                                       '.mp4', '.avi', '.mov', '.mp3', '.wav', '.exe', '.dll', '.bin']
                    
                    # CSV files should be treated as text files
                    text_types = ['text/', 'application/csv', 'text/csv']
                    text_extensions = ['.csv', '.txt', '.js', '.py', '.json', '.md', '.html', '.css', '.xml', '.log']
                    
                    is_binary = (any(project_file.file_type.startswith(bt) for bt in binary_types) if project_file.file_type else False) or \
                               any(project_file.original_filename.lower().endswith(ext) for ext in binary_extensions)
                    
                    # Check if it's a text file (including CSV)
                    is_text = (any(project_file.file_type.startswith(tt) for tt in text_types) if project_file.file_type else False) or \
                             any(project_file.original_filename.lower().endswith(ext) for ext in text_extensions)
                    
                    # Check if it's a PDF file with extracted text
                    if project_file.original_filename.lower().endswith('.pdf'):
                        if project_file.file_content:
                            logger.info(f"PDF file {file_id} has extracted text content, length: {len(project_file.file_content)}")
                            return {"content": project_file.file_content, "filename": project_file.original_filename}
                        else:
                            logger.info(f"PDF file {file_id} has no extracted text content")
                            return {"content": "[PDF file - no text content extracted]", "filename": project_file.original_filename}
                    # Check if it's a DOCX file with extracted text
                    elif project_file.original_filename.lower().endswith('.docx'):
                        if project_file.file_content:
                            logger.info(f"DOCX file {file_id} has extracted text content, length: {len(project_file.file_content)}")
                            return {"content": project_file.file_content, "filename": project_file.original_filename}
                        else:
                            logger.info(f"DOCX file {file_id} has no extracted text content")
                            return {"content": "[DOCX file - no text content extracted]", "filename": project_file.original_filename}
                    elif is_binary and not is_text:
                        logger.info(f"File {file_id} is binary, cannot read as text")
                        logger.info(f"File type: {project_file.file_type}, Filename: {project_file.original_filename}")
                        logger.info(f"is_binary: {is_binary}, is_text: {is_text}")
                        return {"content": "[Binary file - content not readable as text]", "filename": project_file.original_filename}
                    
                    try:
                        # Use the safe file reading function
                        content = safe_read_file(project_file.file_path, project_file.original_filename)
                        logger.info(f"Read content from disk for file {file_id}, length: {len(content)}")
                        logger.info(f"File type: {project_file.file_type}, Filename: {project_file.original_filename}")
                        if project_file.original_filename.lower().endswith('.csv'):
                            logger.info(f"CSV file content preview: {content[:200]}...")
                        return {"content": content, "filename": project_file.original_filename}
                    except Exception as e:
                        logger.error(f"Error reading file from disk: {e}")
                        raise HTTPException(status_code=400, detail="File content could not be read")
                else:
                    logger.error(f"File not found on disk: {project_file.file_path}")
                    raise HTTPException(status_code=404, detail="File not found on disk")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching file content: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")