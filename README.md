# AI Resume Rewriter & ATS Optimizer

A web app that rewrites a candidate's resume to better match a target job description, optimized for Applicant Tracking Systems (ATS). Upload a PDF resume, paste a job description, and get back a rewritten, keyword-optimized version along with notes on remaining gaps.

## Features

- Upload a resume as a PDF and extract its text automatically
- Paste any target job description
- AI-powered rewrite that:
  - Strengthens bullet points with action verbs
  - Weaves in genuine keyword matches from the job description (no fabricated experience)
  - Flags remaining gaps between the resume and the job description
- Clean two-column UI: inputs on the left, results on the right
- Graceful error handling for missing files, empty inputs, bad PDFs, and API failures

## Tech Stack

| Layer      | Technology                              |
|------------|------------------------------------------|
| Backend    | Python, Flask                            |
| PDF Parsing| PyPDF2                                   |
| AI Model   | Google Gemini (`gemini-2.5-flash` via `google-genai` SDK) |
| Frontend   | HTML, CSS, vanilla JavaScript (no frameworks) |

## Project Structure

```
ai-resume-rewriter/
├── static/
│   └── style.css        # Layout, typography, responsive styling
├── templates/
│   └── index.html        # Input form + output display + fetch() logic
├── app.py                 # Flask server, PDF parsing, Gemini integration
├── requirements.txt       # Python dependencies
├── .env.example            # Template for the required API key
└── .gitignore
```

## Setup

### 1. Clone and enter the project
```bash
git clone <your-repo-url>
cd ai-resume-rewriter
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Add your Gemini API key
```bash
cp .env.example .env
```
Edit `.env` and paste a real key from [Google AI Studio](https://aistudio.google.com/app/apikey):
```
GEMINI_API_KEY=your_real_key_here
```

### 5. Run the app
```bash
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

## How It Works

1. **Frontend (`templates/index.html`)** — collects the resume file and job description, submits them to `/rewrite` via `fetch()` as `multipart/form-data`, and renders the Markdown response.
2. **Backend (`app.py`)**:
   - `GET /` serves the HTML form.
   - `POST /rewrite` validates the upload, extracts text with `PyPDF2`, builds a structured prompt, and calls Gemini via `client.models.generate_content()`.
   - Returns JSON: `{"success": true, "result": "<markdown>"}` on success, or `{"success": false, "error": "..."}` on failure.

## Known Limitations

- Only works with text-based PDFs — scanned/image-only resumes will fail extraction (no OCR).
- The AI output is only as good as the prompt and the underlying model; results should be reviewed before use.
- No persistent storage — nothing is saved between requests.

## Possible Future Improvements

- OCR fallback for scanned PDFs
- Export the rewritten resume back to PDF/DOCX
- Support multiple resume versions / history
- User accounts and saved job descriptions

## License

Built as a college project. Free to use and adapt.
