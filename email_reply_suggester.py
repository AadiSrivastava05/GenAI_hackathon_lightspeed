import google.generativeai as genai
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import os
from dotenv import load_dotenv
import json
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class EmailReplySuggester:
    def __init__(self, api_key=None):
        """Initialize the email reply suggester with Gemini API"""
        # Use provided API key or get from environment
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY', None)
        
        if not self.api_key:
            logger.warning("No API key provided for EmailReplySuggester.")
            self.model = None
            return
            
        # Initialize Gemini client
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash")
        
        # Mapping raw labels to standardized format
        self.label_map = {
            "question": "Question/Inquiry",
            "request": "Request",
            "acknowledgment": "Acknowledgment",
            "complaint": "Complaint",
            "feedback": "Feedback/Suggestion",
            "apology": "Apology",
            "thanks": "Thanks/Gratitude",
            "follow-up": "Follow-up",
            "notification": "Notification/Update",
            "spam": "Spam/Irrelevant"
        }
        
        # Load company data
        self.company_data = self._load_company_data()
        
    def _load_company_data(self):
        """Load company data for response generation"""
        # In a real application, this would come from a database
        company_data = pd.DataFrame({
            "topic": [
                "product_returns", "subscription_cancellation", "billing_issue", 
                "product_features", "shipping_policy", "business_hours",
                "warranty_info", "contact_info", "pricing", "tech_support",
                "company_history", "job_openings", "product_compatibility", 
                "privacy_policy", "upcoming_releases"
            ],
            "information": [
                "We offer a 30-day return policy for all products. Items must be in original packaging.",
                "You can cancel your subscription anytime through your account settings or by contacting customer support.",
                "For billing issues, please provide your order number and we'll resolve it within 24 hours.",
                "Our premium plan includes unlimited storage, priority support, and access to all premium templates.",
                "We offer free standard shipping on orders over $50. Express shipping is available for $12.99.",
                "Our customer service is available Monday through Friday, 9am-6pm EST.",
                "All hardware comes with a 2-year limited warranty covering manufacturing defects.",
                "You can reach our support team at support@example.com or call 1-800-555-0123.",
                "Our basic plan starts at $9.99/month, professional at $19.99/month, and enterprise plans are custom-priced.",
                "For technical support, please run our diagnostic tool first and provide the error code in your message.",
                "Founded in 2008, we've grown from a small startup to serving over 2 million customers worldwide.",
                "We're currently hiring for engineering, customer support, and marketing positions. Visit careers.example.com.",
                "Our software is compatible with Windows 10+, macOS 10.14+, and all major browsers released after 2020.",
                "We collect usage data to improve our services. You can opt out in your account privacy settings.",
                "Our next major product release is scheduled for Q3 and will include AI-powered recommendations."
            ]
        })
        
        # Generate embeddings for company data (skipped for simplicity in this implementation)
        # In a real application, we would precompute and store these embeddings
        company_data["embedding"] = company_data["topic"].apply(lambda x: self._get_embedding(x))
        
        return company_data

    def _get_embedding(self, text):
        """Get embeddings from Gemini"""
        try:
            # In a real implementation, we would use the embedding model
            # Here we're simulating with random embeddings to avoid API calls during testing
            return np.random.rand(768)  # Typical embedding dimension
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return np.random.rand(768)  # Fallback
    
    def classify_email_intent(self, email_text):
        """Classify the intent of an email"""
        if not self.model:
            return "Unknown"
            
        classification_prompt = f"""
You are an intelligent email classification assistant. 
Given the following email content, classify it into **one of these categories**: 
Question, Request, Acknowledgment, Complaint, Feedback, Apology, Thanks, Follow-up, Notification, or Spam.

Respond ONLY with the label name.

Email:
\"\"\"
{email_text}
\"\"\"
Label:
"""
        try:
            response = self.model.generate_content(classification_prompt)
            raw_label = response.text.strip().lower()
            return self.label_map.get(raw_label, f"Unknown ({raw_label})")
        except Exception as e:
            logger.error(f"Error classifying email: {e}")
            return "Unknown"

    def extract_key_topics(self, email_text):
        """Extract key topics from an email"""
        if not self.model:
            return ["Unknown"]
            
        topic_prompt = f"""
Extract 3-5 key topics or keywords from this email. These should represent what information the sender is looking for.
Return ONLY a JSON array of strings with no explanation.

Email:
\"\"\"
{email_text}
\"\"\"
Topics:
"""
        try:
            response = self.model.generate_content(topic_prompt)
            
            # Try to parse as JSON first
            try:
                topics = json.loads(response.text.strip())
                if isinstance(topics, list):
                    return topics
            except:
                # Fallback: Extract topics using regex if JSON parsing fails
                text = response.text.strip()
                topics = re.findall(r'"([^"]*)"', text)
                if topics:
                    return topics
                
                # Second fallback: just split by commas or newlines
                topics = [t.strip() for t in re.split(r'[,\n]', text) if t.strip()]
                return topics[:5]  # Limit to 5 topics
                
        except Exception as e:
            logger.error(f"Error extracting topics: {e}")
            return ["Unknown"]

    def retrieve_relevant_info(self, topics, email_text):
        """Retrieve relevant information from company data"""
        try:
            # Get embeddings for the email and topics
            combined_query = " ".join(topics) + " " + email_text
            query_embedding = self._get_embedding(combined_query)
            
            # Calculate similarity with each company data entry
            similarities = []
            for idx, row_embedding in enumerate(self.company_data["embedding"]):
                similarity = cosine_similarity(
                    np.array(query_embedding).reshape(1, -1),
                    np.array(row_embedding).reshape(1, -1)
                )[0][0]
                similarities.append((idx, similarity))
            
            # Sort by similarity and get top 3 results
            similarities.sort(key=lambda x: x[1], reverse=True)
            top_results = similarities[:3]
            
            relevant_info = []
            for idx, score in top_results:
                if score > 0.3:  # Threshold to ensure some relevance
                    relevant_info.append({
                        "topic": self.company_data.iloc[idx]["topic"],
                        "information": self.company_data.iloc[idx]["information"],
                        "relevance_score": float(score)
                    })
            
            return relevant_info
        except Exception as e:
            logger.error(f"Error retrieving relevant info: {e}")
            return []

    def generate_email_response(self, email_text, intent_label, relevant_info):
        """Generate email response using RAG approach"""
        if not self.model:
            return "Auto-response generation is not available right now."
            
        # Prepare the context with relevant information
        context = "\n".join([f"- {info['topic']}: {info['information']}" for info in relevant_info])
        
        response_prompt = f"""
You are a helpful customer service representative for a company.
You need to respond to the following email based on its intent and using the relevant company information provided.

EMAIL FROM CUSTOMER:
\"\"\"
{email_text}
\"\"\"

EMAIL INTENT: {intent_label}

RELEVANT COMPANY INFORMATION:
{context}

Write a professional and helpful email response addressing their concerns and using the provided information.
Be concise but comprehensive. Include a proper greeting and sign-off as a customer service representative.
If the information provided doesn't fully address their question, acknowledge this and mention that you'll follow up with more details.
"""
        
        try:
            response = self.model.generate_content(response_prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "Failed to generate an automatic response."

    def process_email(self, email_text):
        """
        Process an email and generate a suggested response
        
        Args:
            email_text (str): The content of the email to process
            
        Returns:
            dict: A dictionary containing the processed email information
        """
        if not self.model:
            return {
                "intent": "Unknown",
                "topics": ["Unknown"],
                "relevant_info": [],
                "response": "Auto-response generation is not available right now."
            }
            
        # Step 1: Classify the email intent
        intent = self.classify_email_intent(email_text)
        logger.info(f"Email Intent: {intent}")
        
        # Step 2: Extract key topics from the email
        topics = self.extract_key_topics(email_text)
        logger.info(f"Extracted Topics: {topics}")
        
        # Step 3: Retrieve relevant information from company database
        relevant_info = self.retrieve_relevant_info(topics, email_text)
        logger.info(f"Found {len(relevant_info)} relevant pieces of information")
        
        # Step 4: Generate a response using RAG
        response = self.generate_email_response(email_text, intent, relevant_info)
        
        return {
            "intent": intent,
            "topics": topics,
            "relevant_info": relevant_info,
            "response": response
        } 