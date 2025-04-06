# Employee Reports & Email Management System

An integrated Flask application for managing employee work updates and internal emails with AI-powered features.

## Features

### Employee Update System
- Submit and track work updates
- Manager dashboard to view employee updates
- Generate visual reports from update data

### Email Management System
- Internal email system between employees
- Email categorization with AI
- Automatic email summarization
- Priority flagging for important messages

### AI-Powered Email Features
- Smart email categorization
- Content summarization
- Automatic priority detection
- AI-suggested replies using context-aware generation

## Technology Stack

- **Backend:** Flask, SQLAlchemy
- **Frontend:** Bootstrap, JavaScript
- **Database:** SQLite
- **AI:** Google Gemini API

## Setup Instructions

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root with your Gemini API Key:
   ```
   GEMINI_API_KEY=your-api-key-here
   ```
4. Run the application:
   ```
   python app.py
   ```

## Usage

### Employee Updates
- Employees can log in and submit daily/weekly updates
- Managers can view all employees' updates and generate reports

### Email System
- View and manage internal emails in the mailbox
- Use AI to categorize and summarize email content
- Flag important emails as urgent
- Generate AI-suggested replies to emails

## AI Reply Generator

The application features an advanced email reply generator that:

1. Classifies the intent of incoming emails
2. Extracts key topics from the email content
3. Retrieves relevant information from company knowledge base
4. Generates tailored responses based on the email context

This helps employees respond to internal communications more efficiently with context-aware, professionally formatted replies.