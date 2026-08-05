import os
import sys

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Backend.Services.text_processor import extract_text, split_text

def main():
    try:
        text = extract_text("RRRR.pdf")
        chunks = split_text(text, chunk_size=1000, overlap=200)
        
        with open("test_output.txt", "w", encoding="utf-8") as f:
            f.write(f"--- FULL EXTRACTED TEXT ---\n{text}\n\n")
            f.write(f"--- TOTAL CHUNKS: {len(chunks)} ---\n")
            for i, chunk in enumerate(chunks):
                f.write(f"--- CHUNK {i+1} ---\n{chunk}\n")
    except Exception as e:
        with open("test_output.txt", "w", encoding="utf-8") as f:
            f.write(f"ERROR: {str(e)}")

if __name__ == "__main__":
    main()
