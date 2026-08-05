import os
import pdfplumber
import docx
import pytesseract
from PIL import Image
from bs4 import BeautifulSoup
import requests

# Set the Tesseract executable path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Create the raw_text directory if it doesn't exist
os.makedirs("raw_text", exist_ok=True)

# 1. Extract text from PDF (benefits_sample.pdf -> benefits.txt)
print("Processing PDF...")
try:
    pdf_text = ""
    with pdfplumber.open("benefits_sample.pdf") as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                pdf_text += extracted + "\n"
    with open("raw_text/benefits.txt", "w", encoding="utf-8") as f:
        f.write(pdf_text.strip())
    print("✅ Created raw_text/benefits.txt")
except Exception as e:
    print(f"Error in PDF: {e}")

# 2. Extract text from Word Document (claims_process_sample.docx -> claims_process.txt)
print("Processing Word Document...")
try:
    doc = docx.Document("claims_process_sample.docx")
    doc_text = "\n".join([para.text for para in doc.paragraphs])
    with open("raw_text/claims_process.txt", "w", encoding="utf-8") as f:
        f.write(doc_text.strip())
    print("✅ Created raw_text/claims_process.txt")
except Exception as e:
    print(f"Error in Word Doc: {e}")

# 3. Extract text from Scanned Image using OCR (enrollment_sample.png -> enrollment.txt)
print("Processing Scanned Image (OCR)...")
try:
    ocr_text = pytesseract.image_to_string(Image.open("enrollment_sample.png"))
    with open("raw_text/enrollment.txt", "w", encoding="utf-8") as f:
        f.write(ocr_text.strip())
    print("✅ Created raw_text/enrollment.txt")
except Exception as e:
    print(f"Error in OCR: {e}")

# 4. Scrape FAQ Webpage
print("Scraping FAQ Webpage...")
try:
    response = requests.get("https://www.healthcare.gov/glossary/")
    soup = BeautifulSoup(response.text, 'html.parser')

    # Remove nav, footer, script, style tags to keep only main content
    for tag in soup(["nav", "footer", "script", "style", "header"]):
        tag.decompose()

    web_text = soup.get_text(separator='\n', strip=True)
    with open("raw_text/faq_scraped.txt", "w", encoding="utf-8") as f:
        f.write(web_text)
    print("✅ Created raw_text/faq_scraped.txt")
except Exception as e:
    print(f"Error in Web Scraping: {e}")

print("\n🎉 Day 5 Extraction Complete!")