"""
app.py — Flask backend for the AI Resume Rewriter & ATS Optimizer.

Responsibilities:
    1. Serve the single-page frontend (GET /)
    2. Accept a resume PDF + job description (POST /rewrite)
    3. Extract text from the PDF with PyPDF2
    4. Send a carefully-structured prompt to Gemini (google-genai SDK)
    5. Return the rewritten resume as JSON so the frontend can render it

Run with:
    python app.py
"""

import os
import traceback

from flask import Flask, render_template, request, jsonify
from PyPDF2 import PdfReader
from google import genai
from google.genai import errors as genai_errors
from dotenv import load_dotenv

# ----------------------------------------------------------------------------
# 1. CONFIGURATION
# ----------------------------------------------------------------------------

# Loads variables from a local .env file (GEMINI_API_KEY=...) into os.environ.
# Keeping the API key out of source code is important for a project defense —
# it shows awareness of basic secrets hygiene.
load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.8-flash"

# Flask app instance. template_folder/static_folder default to
# "templates/" and "static/" respectively, which matches our directory layout.
app = Flask(__name__)

# Basic upload constraints — protects the server from giant/garbage uploads.
MAX_FILE_SIZE_MB = 8
ALLOWED_EXTENSIONS = {".pdf"}

# The Gemini client is created once at startup and reused across requests
# (creating a new client per-request would be wasteful).
# If the key is missing, we still let the app boot so `/` loads, but
# `/rewrite` will return a clear JSON error instead of crashing.
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


# ----------------------------------------------------------------------------
# 2. HELPERS
# ----------------------------------------------------------------------------

def allowed_file(filename: str) -> bool:
    """Check the uploaded file has a .pdf extension (case-insensitive)."""
    _, ext = os.path.splitext(filename.lower())
    return ext in ALLOWED_EXTENSIONS


def extract_text_from_pdf(file_stream) -> str:
    """
    Extract raw text from an in-memory PDF file using PyPDF2.

    `file_stream` is the Werkzeug FileStorage object's stream (file-like),
    so PyPDF2 can read it directly without saving to disk first.
    """
    reader = PdfReader(file_stream)

    if len(reader.pages) == 0:
        raise ValueError("The PDF has no pages.")

    pages_text = []
    for page in reader.pages:
        # extract_text() can return None for image-only/scanned pages.
        text = page.extract_text() or ""
        pages_text.append(text)

    full_text = "\n".join(pages_text).strip()

    if not full_text:
        # Common cause: the PDF is a scanned image with no selectable text.
        raise ValueError(
            "No extractable text found in the PDF. "
            "It may be a scanned image rather than a text-based PDF."
        )

    return full_text


def build_prompt(resume_text: str, job_description: str) -> str:
    """
    Construct the prompt sent to Gemini.

    Design notes for the project defense:
    - We give the model a clear ROLE ("expert ATS resume writer").
    - We give it explicit RULES to reduce hallucination (don't invent
      experience, keep it truthful, keep formatting simple).
    - We ask for Markdown output so the frontend can render it directly
      and so it's easy to copy into a real document later.
    - We ask it to append a short "ATS Match Notes" section — this is the
      "optimizer" half of the project, not just a rewrite.
    """
    prompt = f"""
You are an expert ATS (Applicant Tracking System) resume writer and career coach.

Your task: rewrite the candidate's resume below so that it is better optimized
for the TARGET JOB DESCRIPTION, while remaining 100% truthful to the candidate's
actual experience. Do NOT invent companies, titles, dates, or skills that are not
implied by the original resume.

Follow these rules strictly:
1. Rewrite bullet points to use strong action verbs and quantify impact where
   the original text allows it (do not fabricate numbers).
2. Naturally weave in keywords and phrases from the job description that
   genuinely match the candidate's real background, so the resume scores well
   against ATS keyword matching.
3. Keep section structure clean: Summary, Skills, Experience, Education
   (reuse only the sections present in the original resume).
4. Keep the tone professional and concise — avoid filler language.
5. Output valid Markdown only (headings, bullet points, bold where useful).
6. After the rewritten resume, add a section titled "## ATS Match Notes"
   with:
     - A short list of key job-description keywords that were already
       present or were added.
     - 2-4 sentences of honest feedback on remaining gaps between the
       candidate's background and the job description.

--- CANDIDATE RESUME (extracted text) ---
{resume_text}

--- TARGET JOB DESCRIPTION ---
{job_description}

Now produce the rewritten, ATS-optimized resume in Markdown, followed by the
"## ATS Match Notes" section.
""".strip()

    return prompt


# ----------------------------------------------------------------------------
# 3. ROUTES
# ----------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the single-page frontend (upload form + output panel)."""
    return render_template("index.html")


@app.route("/rewrite", methods=["POST"])
def rewrite():
    """
    Main endpoint: accepts multipart/form-data with
        - "resume"            : a .pdf file
        - "job_description"   : a text field
    and returns JSON:
        success -> { "success": true,  "result": "<markdown string>" }
        failure -> { "success": false, "error": "<human-readable message>" }
    """

    # ---- 3a. Guard: is the Gemini client even configured? ----
    if client is None:
        return jsonify(
            success=False,
            error="Server misconfiguration: GEMINI_API_KEY is not set. "
                  "Create a .env file with GEMINI_API_KEY=your_key_here."
        ), 500

    # ---- 3b. Validate the uploaded file ----
    if "resume" not in request.files:
        return jsonify(success=False, error="No resume file was uploaded."), 400

    resume_file = request.files["resume"]

    if resume_file.filename == "":
        return jsonify(success=False, error="No resume file was selected."), 400

    if not allowed_file(resume_file.filename):
        return jsonify(success=False, error="Only .pdf files are supported."), 400

    # Enforce a size limit by seeking to the end of the stream.
    resume_file.stream.seek(0, os.SEEK_END)
    size_mb = resume_file.stream.tell() / (1024 * 1024)
    resume_file.stream.seek(0)  # reset pointer before reading again
    if size_mb > MAX_FILE_SIZE_MB:
        return jsonify(
            success=False,
            error=f"PDF is too large ({size_mb:.1f} MB). Max allowed is {MAX_FILE_SIZE_MB} MB."
        ), 400

    # ---- 3c. Validate the job description field ----
    job_description = request.form.get("job_description", "").strip()
    if not job_description:
        return jsonify(success=False, error="Job description cannot be empty."), 400

    # ---- 3d. Extract text from the PDF ----
    try:
        resume_text = extract_text_from_pdf(resume_file.stream)
    except ValueError as ve:
        # Expected, "nice" errors (empty PDF, scanned image, etc.)
        return jsonify(success=False, error=str(ve)), 400
    except Exception:
        # Unexpected PyPDF2 failure (corrupted file, etc.)
        traceback.print_exc()
        return jsonify(
            success=False,
            error="Could not read the PDF. It may be corrupted or encrypted."
        ), 400

    # ---- 3e. Call Gemini ----
    prompt = build_prompt(resume_text, job_description)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        rewritten_text = response.text

        if not rewritten_text or not rewritten_text.strip():
            return jsonify(
                success=False,
                error="The AI model returned an empty response. Please try again."
            ), 502

    except genai_errors.APIError as api_err:
        # google-genai raises a typed APIError for bad API key, quota issues,
        # invalid model name, safety blocks, etc. We surface a clean message
        # instead of a raw stack trace.
        traceback.print_exc()
        return jsonify(
            success=False,
            error=f"Gemini API error: {api_err.message if hasattr(api_err, 'message') else str(api_err)}"
        ), 502

    except Exception:
        traceback.print_exc()
        return jsonify(
            success=False,
            error="An unexpected error occurred while contacting the AI model."
        ), 500

    # ---- 3f. Success ----
    return jsonify(success=True, result=rewritten_text), 200


# ----------------------------------------------------------------------------
# 4. ENTRY POINT
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    # debug=True gives auto-reload + tracebacks in the browser during
    # development. Turn this off before any real deployment.
    app.run(debug=True, port=5000)
