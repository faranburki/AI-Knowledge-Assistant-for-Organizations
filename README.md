# DocQuery

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn)](https://scikit-learn.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Red?style=flat-square&logo=qdrant)](https://qdrant.tech/)
[![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=flat-square&logo=mongodb)](https://www.mongodb.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

An enterprise-grade, multi-tenant **AI-Powered Knowledge Assistant & Document Q&A Platform** designed for organizations. DocQuery automatically reads, chunks, embeds, and indexes your institutional documents into a high-performance vector store (Qdrant), serving precise, context-aware answers to users through an isolated multi-tenant architecture.

---

## Key Features

| Category | Description |
| :--- | :--- |
| **Multi-Tenant Security** | Absolute data isolation. Users only query and search within their registered workspace/organization boundaries. |
| **Intelligent RAG Pipeline** | Dynamic PDF/document chunking, embedding generation, and vector semantic retrieval using **Qdrant DB**. |
| **ML Query Classifier** | Real-time Logistic Regression classifier predicting intent classes (Academic, Finance, Hostel, Attendance, Library, Exams, Administration, General) to route or tag user requests. |
| **Role-Based Access Control** | Creators are automatically designated as Workspace Admins with full management powers (document upload, workspace management), while standard users enjoy clean query access. |
| **Real-Time Analytics** | Interactive dashboard presenting metrics, query trends, response latency statistics, and most frequently asked questions. |
| **Persistent Chat Histories** | Private conversation threads saved securely inside **MongoDB** for seamless continuity. |

---

## Technology Stack

* **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
* **Vector Search Engine**: [Qdrant](https://qdrant.tech/)
* **Primary Database**: [MongoDB](https://www.mongodb.com/) (using Motor for asynchronous ODM)
* **Machine Learning**: [scikit-learn](https://scikit-learn.org/) (TF-IDF vectorizer + Logistic Regression)
* **Frontend**: Vanilla CSS, Modern Glassmorphic Design, Vanilla JS

---

## Setup and Running the Project in a New Folder

Follow this step-by-step guide to clone, install, configure, and launch this project in a completely fresh directory.

### 1. Clone the Repository
Open your terminal/command prompt, navigate to the directory where you want the project to live, and run:
```bash
git clone https://github.com/faranburki/AI-Knowledge-Assistant-for-Organizations.git
```

Now, navigate into the fresh project folder:
```bash
cd AI-Knowledge-Assistant-for-Organizations
```

### 2. Create a Python Virtual Environment
Keep dependencies isolated inside a clean virtual environment:
* **Windows:**
  ```powershell
  python -m venv venv
  ```
* **Linux/Mac:**
  ```bash
  python3 -m venv venv
  ```

### 3. Activate the Virtual Environment
Activate the environment to bind your Python path:
* **Windows (PowerShell):**
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
* **Windows (Command Prompt):**
  ```cmd
  .\venv\Scripts\activate.bat
  ```
* **Linux/Mac:**
  ```bash
  source venv/bin/activate
  ```

### 4. Install Project Dependencies
With the virtual environment active, run the following command to download and install all backend dependencies:
```bash
pip install -r requirements.txt
```

### 5. Setup Local Services (Databases)
Ensure your database servers are started locally:
* **MongoDB**: Standard port `27017` (Runs in the background if installed locally as a service or via Docker).
* **Qdrant Vector DB**: Standard port `6333`. (Can be launched locally via Docker: `docker run -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant`).

### 6. Create the Configuration Environment (.env)
Create a new file named `.env` in the root of the project folder:
* **Windows (PowerShell command):**
  ```powershell
  New-Item -Path .env -ItemType File
  ```
* **Linux/Mac/Git Bash command:**
  ```bash
  touch .env
  ```

Open the `.env` file in your text editor and add the following config keys:
```env
MONGODB_URI=mongodb://localhost:27017/docquery
QDRANT_HOST=localhost
QDRANT_PORT=6333
GROQ_API_KEY=your_groq_api_key_here
JWT_SECRET=your_jwt_signature_key_here
```
*(Replace `your_groq_api_key_here` with a valid API key from the Groq console).*

### 7. Run the Backend Server
Launch the FastAPI development backend:
```bash
uvicorn Backend.main:app --reload
```
Once running, you can access the automatic interactive API documentation at: `http://localhost:8000/docs`

### 8. Open the User Interface (Frontend)
DocQuery is served via a fully responsive single-page web app layout.
To open the frontend:
* Simply double-click and open the file `Frontend/index.html` directly in any web browser (Chrome, Edge, Firefox, or Safari).
* Alternatively, if using VS Code, you can right-click `Frontend/index.html` and select **Open with Live Server**.

---

## Project Structure

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

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.