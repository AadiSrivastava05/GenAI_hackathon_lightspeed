import google.generativeai as genai
import os
from dotenv import load_dotenv
import logging
from models import Email, EmailCategory, db
from datetime import datetime
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class EmailProcessor:
    def __init__(self, api_key="AIzaSyAzD34ljTgzWdZUpbCl3iynxAqh8uy6irc"):
        # Initialize the Gemini API
        if api_key is None:
            api_key = os.environ.get('GEMINI_API_KEY', None)
        
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        else:
            logger.warning("No API key provided for EmailProcessor.")
            self.model = None
    
    def summarize(self, email_content):
        """
        Use Gemini to summarize the email content, keeping any important keywords.
        
        Args:
            email_content (str): The content of the email to summarize
            
        Returns:
            str: A concise summary of the email in markdown format
        """
        if not self.model:
            return "Email summarization not available (API key not set)."
            
        prompt = f"""
        Summarize the following email in a concise manner. Highlight any important keywords, 
        dates, action items, or critical information. Format your response using Markdown with:
        
        - Headings (## for main sections, ### for subsections)
        - **Bold** for important terms, deadlines, or action items
        - Bullet points for lists of information
        - > Blockquotes for any direct quotes that are important
        
        Keep your summary structured and well-formatted with proper markdown.
        
        EMAIL:
        {email_content}
        """
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Error summarizing email: {e}")
            return "Failed to summarize email."


class EmailPrioritizer:
    def __init__(self, api_key="AIzaSyAzD34ljTgzWdZUpbCl3iynxAqh8uy6irc"):
        # Initialize the Gemini API
        if api_key is None:
            api_key = os.environ.get('GEMINI_API_KEY', None)
        
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        else:
            logger.warning("No API key provided for EmailPrioritizer.")
            self.model = None
    
    def classify(self, email_subject, email_content):
        """
        Classify the email as high, medium, or low priority based on its content and subject.
        
        Args:
            email_subject (str): The subject of the email
            email_content (str): The content of the email
            
        Returns:
            str: The priority level ("high", "medium", or "low")
        """
        if not self.model:
            return "medium"  # Default if no API key
            
        prompt = f"""
        Classify the following email as high priority, medium priority, or low priority.
        
        Consider these factors for high priority:
        - Emails from executives, managers, or important clients
        - Urgent deadlines or time-sensitive matters
        - Critical business issues or emergencies
        - Keywords like "urgent", "ASAP", "important", "deadline"
        
        Consider these factors for medium priority:
        - Regular project updates
        - Questions requiring attention but not immediately
        - Regular client communications
        
        Consider these factors for low priority:
        - Newsletters
        - Non-urgent FYI emails
        - Social notifications
        - Marketing emails
        
        Return only "high", "medium", or "low" as your answer.
        
        EMAIL SUBJECT: {email_subject}
        
        EMAIL CONTENT:
        {email_content}
        """
        
        try:
            response = self.model.generate_content(prompt)
            priority = response.text.strip().lower()
            
            # Normalize the response
            if "high" in priority:
                return "high"
            elif "medium" in priority or "mid" in priority:
                return "medium"
            else:
                return "low"
        except Exception as e:
            logger.error(f"Error classifying email: {e}")
            return "medium"  # Default to medium priority in case of error


class EmailCategorizer:
    def __init__(self, api_key="AIzaSyAzD34ljTgzWdZUpbCl3iynxAqh8uy6irc"):
        # Initialize the Gemini API
        if api_key is None:
            api_key = os.environ.get('GEMINI_API_KEY', None)
        
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
        else:
            logger.warning("No API key provided for EmailCategorizer.")
            self.model = None
    
    def categorize(self, email_subject, email_content):
        """
        Categorize the email based on its content and subject.
        
        Args:
            email_subject (str): The subject of the email
            email_content (str): The content of the email
            
        Returns:
            str: The category name
        """
        if not self.model:
            return "Uncategorized"
            
        prompt = f"""
        Categorize the following email into one of these categories:
        - Work Updates
        - Project
        - Meeting
        - Client Communication
        - HR
        - IT Support
        - Finance
        - Marketing
        - Sales
        - Personal
        - Misc
        
        Return only the category name as your answer.
        
        EMAIL SUBJECT: {email_subject}
        
        EMAIL CONTENT:
        {email_content}
        """
        
        try:
            response = self.model.generate_content(prompt)
            category = response.text.strip()
            return category
        except Exception as e:
            logger.error(f"Error categorizing email: {e}")
            return "Uncategorized"


def get_or_create_category(category_name):
    """
    Get an existing category or create a new one.
    
    Args:
        category_name (str): The name of the category
        
    Returns:
        EmailCategory: The category object
    """
    category = EmailCategory.query.filter_by(name=category_name).first()
    if not category:
        category = EmailCategory(name=category_name)
        db.session.add(category)
        db.session.commit()
    return category


def process_email(subject, content, sender, user_id, api_key="AIzaSyAzD34ljTgzWdZUpbCl3iynxAqh8uy6irc"):
    """
    Process an email by summarizing, classifying priority, and categorizing.
    
    Args:
        subject (str): The email subject
        content (str): The email content
        sender (str): The email sender
        user_id (int): The ID of the user who received the email
        api_key (str, optional): The Gemini API key
        
    Returns:
        Email: The processed email object
    """
    processor = EmailProcessor(api_key)
    prioritizer = EmailPrioritizer(api_key)
    categorizer = EmailCategorizer(api_key)
    
    # Process the email
    summary = processor.summarize(content)
    priority = prioritizer.classify(subject, content)
    category_name = categorizer.categorize(subject, content)
    
    # Get or create the category
    category = get_or_create_category(category_name)
    
    # Create a new email
    email = Email(
        subject=subject,
        content=content,
        sender=sender,
        date_received=datetime.utcnow(),
        is_urgent=(priority == "high"),
        summary=summary,
        category_id=category.id,
        user_id=user_id
    )
    
    db.session.add(email)
    db.session.commit()
    
    return email 