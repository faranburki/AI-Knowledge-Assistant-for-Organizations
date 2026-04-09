import PyPDF2
import docx

def extract_text(file_path):
    ext = file_path.split('.')[-1].lower()
    text=""
    if ext == "pdf":
        with open(file_path,"rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    elif ext == "docx":
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            text=f.read()
    return text

def split_text(text, words_per_chunk=400):
    words = text.split()
    chunks=[]
    for i in range(0,len(words),words_per_chunk):
        chunks.append(" ".join(words[i:i+words_per_chunk]))
    return chunks