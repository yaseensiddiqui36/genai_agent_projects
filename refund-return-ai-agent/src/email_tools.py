"""Email tools for Gmail integration."""

import base64
import logging
import os
import pickle
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict

import yaml
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

try:
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GMAIL_AVAILABLE = True
except ImportError:
    logger.warning(
        "Gmail API packages not available. Install google-api-python-client, google-auth, google-auth-oauthlib"
    )
    GMAIL_AVAILABLE = False

# Email configuration
# Load YAML config
config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(config_path, "r") as f:
    config = yaml.safe_load(f)

SENDER_EMAIL = config['email']['sender_email']

# Gmail API configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.send']
TOKEN_FILE = 'token.pickle'
CREDENTIALS_FILE = 'credentials.json'


def authenticate_gmail():
    """Authenticate and return Gmail service object."""
    if not GMAIL_AVAILABLE:
        return None
        
    creds = None
    
    # Load existing token if it exists
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # If there are no valid credentials available, get them
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logger.warning("Gmail token refresh failed: %s", e)
                creds = None

        if not creds:
            # Check if credentials.json exists
            if not os.path.exists(CREDENTIALS_FILE):
                logger.warning(
                    "Credentials file '%s' not found. Download credentials.json from Google Cloud Console",
                    CREDENTIALS_FILE,
                )
                return None

            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                logger.warning("Gmail authentication flow failed: %s", e)
                return None
        
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as e:
        logger.warning("Failed to build Gmail service: %s", e)
        return None


def create_html_email(subject, sender_email, recipient_email, html_content):
    """Create HTML email message"""
    message = MIMEMultipart('alternative')
    message['to'] = recipient_email
    message['from'] = sender_email
    message['subject'] = subject
    
    html_part = MIMEText(html_content, 'html')
    message.attach(html_part)
    
    return message


def send_email(service, message):
    """Send email using Gmail API"""
    try:
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        send_message = {'raw': raw_message}
        
        result = service.users().messages().send(userId='me', body=send_message).execute()
        return result
    except Exception as e:
        logger.error("Error sending email: %s", e)
        return None


def send_single_email(recipient_email, sender_email, subject, html_content):
    """Send a single email - no LLM processing"""
    service = authenticate_gmail()
    if not service:
        return {'status': 'failed', 'error': 'Failed to authenticate Gmail service'}
    
    message = create_html_email(subject, sender_email, recipient_email, html_content)
    result = send_email(service, message)
    
    if result:
        return {
            'status': 'success', 
            'email': recipient_email,
            'message_id': result.get('id')
        }
    else:
        return {
            'status': 'failed', 
            'email': recipient_email,
            'error': 'Failed to send email'
        }


@tool
def send_email_notification(customer_email: str, subject: str, message: str, request_id: str) -> Dict:
    """Send email notification to customer using Gmail API"""
    try:
        # Convert plain text message to HTML
        html_content = f"""
        <html>
            <body>
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <h2 style="color: #333;">Customer Service Notification</h2>
                    <div style="background-color: #f9f9f9; padding: 20px; border-radius: 5px;">
                        {message.replace(chr(10), '<br>')}
                    </div>
                    <br>
                    <p style="color: #666; font-size: 12px;">
                        Request ID: {request_id}<br>
                        This is an automated message from our customer service system.
                    </p>
                </div>
            </body>
        </html>
        """
        
        result = send_single_email(
            recipient_email=customer_email,
            sender_email=SENDER_EMAIL,
            subject=subject,
            html_content=html_content
        )
        
        if result['status'] == 'success':
            return {
                "success": True,
                "message": "Email notification sent successfully",
                "email_id": result.get('message_id'),
                "recipient": customer_email
            }
        else:
            return {
                "success": False,
                "error": result.get('error', 'Unknown error'),
                "fallback": "Email sending failed - using fallback notification"
            }
        
    except Exception as e:
        # Fallback to console output if email fails
        logger.warning(
            "Email send failed, using console fallback [request_id=%s to=%s subject=%r]: %s",
            request_id, customer_email, subject, e,
        )
        logger.info("Fallback email body: %s", message)

        return {
            "success": False,
            "error": str(e),
            "fallback": "Console notification used as fallback",
            "email_id": f"fallback_{request_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        }



@tool
def log_communication(request_id: str, communication_type: str, content: str) -> Dict:
    """Log communication activity for audit trail"""
    timestamp = datetime.now().isoformat()
    log_entry = f"[{timestamp}] {communication_type}: {content}"

    # In a real implementation, this would save to a database
    logger.info("Communication log: %s", log_entry)

    return {
        "success": True,
        "log_entry": log_entry,
        "timestamp": timestamp
    }

@tool
def generate_request_id() -> str:
    """Generate a unique request ID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"REQ_{timestamp}_{unique_id}"