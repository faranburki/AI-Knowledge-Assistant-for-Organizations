# DocQuery 🚀

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn)](https://scikit-learn.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Red?style=flat-square&logo=qdrant)](https://qdrant.tech/)
[![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=flat-square&logo=mongodb)](https://www.mongodb.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

An enterprise-grade, multi-tenant **AI-Powered Knowledge Assistant & Document Q&A Platform** designed for organizations. DocQuery automatically reads, chunks, embeds, and indexes your institutional documents into a high-performance vector store (Qdrant), serving precise, context-aware answers to users through an isolated multi-tenant architecture.

---

## ✨ Key Features

| Category | Description |
| :--- | :--- |
| **🔒 Multi-Tenant Security** | Absolute data isolation. Users only query and search within their registered workspace/organization boundaries. |
| **📂 Intelligent RAG Pipeline** | Dynamic PDF/document chunking, embedding generation, and vector semantic retrieval using **Qdrant DB**. |
| **🧠 ML Query Classifier** | Real-time Logistic Regression classifier predicting intent classes (Academic, Finance, Hostel, Attendance, Library, Exams, Administration, General) to route or tag user requests. |
| **👑 Role-Based Access Control** | Creators are automatically designated as Workspace Admins with full management powers (document upload, workspace management), while standard users enjoy clean query access. |
| **📊 Real-Time Analytics** | Interactive dashboard presenting metrics, query trends, response latency statistics, and most frequently asked questions. |
| **💬 Persistent Chat Histories** | Private conversation threads saved securely inside **MongoDB** for seamless continuity. |

---

## 🛠️ Technology Stack

* **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
* **Vector Search Engine**: [Qdrant](https://qdrant.tech/)
* **Primary Database**: [MongoDB](https://www.mongodb.com/) (using Motor for asynchronous ODM)
* **Machine Learning**: [scikit-learn](https://scikit-learn.org/) (TF-IDF vectorizer + Logistic Regression)
* **Frontend**: Vanilla CSS, Modern Glassmorphic Design, Vanilla JS

---

## ⚡ Getting Started & Installation

### 1. Prerequisites
Ensure you have the following installed on your system:
* **Python 3.10+**
* **MongoDB** instance (Local or Atlas cloud URI)
* **Qdrant** instance (Local docker or Qdrant Cloud cluster)
* **Groq API Key** (for fast language model generation)

### 2. Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/faranburki/AI-Knowledge-Assistant-for-Organizations.git
   cd AI-Knowledge-Assistant-for-Organizations
   ```

2. **Create and Activate a Virtual Environment:**
   * **Windows:**
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   * **Linux/Mac:**
     ```bash
     python -m venv venv
     source venv/bin/activate
     ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### 3. Environment Variables Configuration
Create a `.env` file in the root directory and add the following parameters:
```env
MONGODB_URI=mongodb://localhost:27017/docquery
QDRANT_HOST=localhost
QDRANT_PORT=6333
GROQ_API_KEY=your_groq_api_key_here
JWT_SECRET=your_jwt_signature_key_here
```

### 4. Running the Development Server
Launch the FastAPI backend:
```bash
uvicorn Backend.main:app --reload
```
The interactive Swagger API documentation will be available at: `http://localhost:8000/docs`

---

## 🧠 Training & Updating the Intent Classifier

We include a custom, Windows-compatible ML pipeline script (`train_classifier.py`) that merges, cleans, and trains an intent classifier on custom datasets.

### How to Train on Custom Datasets:
1. Put your custom query CSV files inside a folder named `Data/` (e.g. `Data/academic.csv`, `Data/finance.csv`, etc.).
2. Ensure each CSV has:
   * A column containing queries (e.g., headerless or named `query`/`question`).
   * A column containing categories (e.g., headerless or named `category`/`label`).
3. Run the training command:
   ```bash
   python train_classifier.py
   ```
4. **Automated Features:**
   * **Header Detection**: Auto-detects if files are headerless and prevents losing data rows.
   * **Cleaning**: Strips white spaces, drops nulls, and removes duplicates.
   * **Evaluation Report**: Conducts an 80/20 split and shows a complete Precision/Recall report.
   * **Hot Reload**: Automatically compiles and updates the active `Backend/ml/model.pkl` loaded by the server.

---

## 📂 Project Structure

```text
├── Backend/
│   ├── core/           # Security and JWT utilities
│   ├── Database/       # MongoDB connections and schemas
│   ├── ml/             # ML intent classifier & saved model.pkl
│   ├── models/         # Pydantic request/response models
│   ├── routers/        # API endpoints (auth, query, analytics, docs)
│   ├── Services/       # RAG pipeline, file uploaders & vector extraction
│   └── main.py         # App initialization
├── Data/               # Raw training datasets (.csv)
├── Frontend/           # UI elements (HTML, CSS, JS)
├── Models/             # Model weight configurations
└── train_classifier.py # Automated classifier trainer
```

---

## 📄 License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.