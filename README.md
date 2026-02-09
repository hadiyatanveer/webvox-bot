# webvox-bot
WebVox Framework, an intelligent, voice-driven chatbot framework that integrates language models with structured and unstructured data retrieval.  Unlike rigid chatbot products, WebVox is designed as a framework delivered through APIs. It enables client companies to enrich their websites with natural voice and text-based interactions for tasks.

## Project Structure
```bash
webvox-bot/
├── frontend/
|
├── backend/
│ ├── routes/
│ ├── models/
│ └── schemas/
│
├── services/                  
│ ├── voice_processing/ 
│ ├── voicebot/ 
│ ├── intent_detection/ 
│ ├── information_retrieval/ 
│ ├── action_execution/ 
│ ├── session_security/ 
│ ├── learning_adaptation/ 
│
├── tests/
|
└── requirements.txt
└── README.md
└── Makefile
└── .gitignore
└── .env.example
└── main.py
```

## ⚙️ GraphQL Setup Instructions

The project consists of two main parts:
- GraphQL layer (Hasura + Postgres) — must be started first
- WebVox application (backend + frontend)

Navigate to the GraphQL folder first.
```bash
cd GraphQL
```

1. Create and activate a virtual environment, then install requirements
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Start Hasura and Postgres using Docker
```bash
docker compose up --build -d
```

3. Run Hasura setup script
```bash
python3 hasura_setup.py
```
    
4. Make .env
```bash
export HASURA_ENDPOINT="http://localhost:8080/v1/graphql"
export JWT_TOKEN="your-jwt-token-here"
```

## ⚙️ Setup Instructions

Follow these simple steps to run the project locally.

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/webvox-bot.git
cd webvox-bot
```
### 2. Run the frontend

```bash
cd frontend
npm install
npm install react-scripts@5.0.1
npm start
```

### 3. Run the backend

```bash
python3 -m backend.main
```

### 4. Create static knowledge base

```bash
python3 -m services.vector_db.ingest_static_kb
```
In order to get vector databases made, shorten chunk sizes (data currently too small for large chunks)

