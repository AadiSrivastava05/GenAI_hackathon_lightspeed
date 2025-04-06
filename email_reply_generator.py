import google.generativeai as genai
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import os
from dotenv import load_dotenv
import json
import re

# Load environment variables (optional, for more secure API key management)
load_dotenv()

# Initialize Gemini client
api_key = genai.configure("AIzaSyDoWr96cFqpfl8xuBb4N8VO91fKTpSNkuE")
client = genai.GenerativeModel(api_key=api_key)
chat = client.chats.create(model="gemini-2.0-flash")

# Mapping raw labels to standardized format
label_map = {
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

# Sample company database - in production, this would be a real database connection
# For this example, we'll use a pandas DataFrame to simulate the database
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

# Function to get embeddings from Gemini
def get_embedding(text):
    # Use Gemini's embedding model to get vector representation
    try:
        embedding_model = "embedding-001"  # Use the appropriate embedding model
        embedding = client.embeddings.create(
            model=embedding_model,
            content=text,
        )
        return embedding.embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        # Fallback with random embedding if API fails (not ideal for production)
        return np.random.rand(768)  # Typical embedding dimension

# Precompute embeddings for company data
company_data["embedding"] = company_data["topic"].apply(lambda x: get_embedding(x))

def classify_email_intent(email_text):
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
    response = chat.send_message(classification_prompt)
    raw_label = response.text.strip().lower()
    return label_map.get(raw_label, f"Unknown ({raw_label})")

def extract_key_topics(email_text):
    topic_prompt = f"""
Extract 3-5 key topics or keywords from this email. These should represent what information the sender is looking for.
Return ONLY a JSON array of strings with no explanation.

Email:
\"\"\"
{email_text}
\"\"\"
Topics:
"""
    response = chat.send_message(topic_prompt)
    
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

def retrieve_relevant_info(topics, email_text):
    # Get embeddings for the email and topics
    combined_query = " ".join(topics) + " " + email_text
    query_embedding = get_embedding(combined_query)
    
    # Calculate similarity with each company data entry
    similarities = []
    for idx, row_embedding in enumerate(company_data["embedding"]):
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
                "topic": company_data.iloc[idx]["topic"],
                "information": company_data.iloc[idx]["information"],
                "relevance_score": float(score)
            })
    
    return relevant_info

def generate_email_response(email_text, intent_label, relevant_info):
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
    
    response = chat.send_message(response_prompt)
    return response.text.strip()

def process_email(email_text):
    # Step 1: Classify the email intent
    intent = classify_email_intent(email_text)
    print(f"\nEmail Intent: {intent}")
    
    # Step 2: Extract key topics from the email
    topics = extract_key_topics(email_text)
    print(f"Extracted Topics: {topics}")
    
    # Step 3: Retrieve relevant information from company database
    relevant_info = retrieve_relevant_info(topics, email_text)
    print(f"Found {len(relevant_info)} relevant pieces of information")
    
    # Step 4: Generate a response using RAG
    response = generate_email_response(email_text, intent, relevant_info)
    
    return {
        "intent": intent,
        "topics": topics,
        "relevant_info": relevant_info,
        "response": response
    }

# Main execution loop
if __name__ == "__main__":
    while True:
        prompt = input("\nEnter email text (or type 'exit' to quit):\n")
        if prompt.lower() == "exit":
            break

        result = process_email(prompt)
        
        print("\n" + "="*60)
        print("AUTOMATED EMAIL RESPONSE:")
        print("="*60)
        print(result["response"])
        print("="*60)
        
        # Optionally show the retrieved information used
        show_details = input("\nShow processing details? (y/n): ")
        if show_details.lower() == 'y':
            print("\nTOPICS EXTRACTED:")
            for topic in result["topics"]:
                print(f"- {topic}")
                
            print("\nRELEVANT INFORMATION RETRIEVED:")
            for info in result["relevant_info"]:
                print(f"- {info['topic']} (Score: {info['relevance_score']:.2f})")
                print(f"  {info['information']}")
                
        print("\n" + "-"*60)