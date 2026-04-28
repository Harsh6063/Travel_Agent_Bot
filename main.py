from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

from agent import run_agent  # your wrapper around travel_agent
from memory import get_memory, update_memory

# -----------------------------
# INIT APP
# -----------------------------
app = FastAPI(title="Travel AI Agent API")

# -----------------------------
# CORS (IMPORTANT for frontend)
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ change in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# REQUEST MODEL
# -----------------------------
class ChatRequest(BaseModel):
    query: str
    budget: str
    session_id: str | None = None

# -----------------------------
# RESPONSE MODEL (optional but good)
# -----------------------------
class ChatResponse(BaseModel):
    session_id: str
    response: str
    results: list

# -----------------------------
# HEALTH CHECK
# -----------------------------
@app.get("/")
def home():
    return {"status": "Travel AI Agent API running 🚀"}

# -----------------------------
# MAIN CHAT ENDPOINT
# -----------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        # -----------------------------
        # SESSION HANDLING
        # -----------------------------
        session_id = req.session_id or str(uuid.uuid4())

        # -----------------------------
        # MEMORY FETCH
        # -----------------------------
        memory = get_memory(session_id)

        # -----------------------------
        # RUN AGENT
        # -----------------------------
        results, response = await run_agent(
            query=req.query,
            budget=req.budget,
            memory=memory
        )

        # -----------------------------
        # UPDATE MEMORY
        # -----------------------------
        update_memory(session_id, req.query, response)

        # -----------------------------
        # RETURN RESPONSE
        # -----------------------------
        return {
            "session_id": session_id,
            "response": response,
            "results": results
        }

    except Exception as e:
        return {
            "session_id": req.session_id or "error",
            "response": f"Error: {str(e)}",
            "results": []
        }
        
