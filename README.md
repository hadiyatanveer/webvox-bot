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

### 2. Run the backend

```bash
python3 -m backend.main
```
