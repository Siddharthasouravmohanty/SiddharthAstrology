import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def main():
    print("Listing available Gemini models...")
    for m in genai.list_models():
        # Only show ones that support generate_content
        if "generateContent" in m.supported_generation_methods:
            print("-", m.name)

if __name__ == "__main__":
    main()
