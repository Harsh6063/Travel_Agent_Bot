# 🌍 AI Travel Agent — Smart Trip Planner with MCP + LLM

An intelligent **AI-powered travel assistant** that recommends destinations, fetches real-time weather, and suggests stays using Airbnb — all through a modern chat interface.

Built using **FastAPI + Next.js + MCP Servers + LLM (Groq)**.

---

## 🚀 Features

* 💬 **Chat-based Travel Planning**

  * Ask naturally: *“Delhi hotels”*, *“Goa weather”*, *“mountain trip under budget”*

* 🧠 **LLM-powered Recommendations**

  * Smart explanations using Groq (LLaMA 3)

* 🏨 **Airbnb Integration (MCP)**

  * Fetches real stays dynamically
  * Budget filtering (Low / Medium / High)
  * Per-night pricing

* 🌦️ **Weather System (Production Ready)**

  * Real-time weather (API-based)
  * 7-day forecast support
  * Clean UI weather cards

* 🧠 **Memory System**

  * Remembers previous context (budget, location)

* ⚡ **FastAPI Backend**

  * Async architecture
  * MCP tool orchestration

* 🎨 **Modern UI (Next.js)**

  * ChatGPT-style interface
  * Clean cards for results
  * Smooth UX

---

## 🧠 Problem Statement

Planning a trip involves multiple steps:

* Searching destinations
* Checking weather
* Comparing hotel prices
* Filtering by budget

This process is **fragmented, time-consuming, and not user-friendly**.

👉 This project solves it by providing a **single conversational AI interface** that:

* Understands user intent
* Fetches real-time data
* Suggests optimized travel plans

---

## 🏗️ Tech Stack

### Backend

* FastAPI
* MCP (Model Context Protocol)
* Async Python
* Groq API (LLaMA 3)

### Frontend

* Next.js
* Tailwind CSS
* Axios

### Data / Tools

* Airbnb MCP Server
* Weather API / MCP
* FAISS (for destination search)

---

## 🔧 Architecture

```text
User (Chat UI)
     ↓
Next.js Frontend
     ↓
FastAPI Backend
     ↓
Intent Detection → Tool Routing
     ↓
-------------------------------
|  LLM (Groq)                |
|  Airbnb MCP               |
|  Weather API              |
|  FAISS Search             |
-------------------------------
     ↓
Structured Response → UI Cards
```

---

## ⚙️ Installation

### 1️⃣ Clone repo

```bash
git clone https://github.com/your-username/travel-agent
cd travel-agent
```

---

### 2️⃣ Backend setup

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env`:

```env
GROQ_API_KEY=your_key_here
```

Run backend:

```bash
uvicorn main:app --reload
```

---

### 3️⃣ Frontend setup

```bash
cd frontend
npm install
npm run dev
```

---

## 💬 Example Queries

* `Delhi hotels`
* `Goa weather`
* `low`
* `mountain trip with budget`
* `best religious places in India`

---

## 📊 Output Example

```text
📍 Goa (Beach)
🌦️ 30°C | Sunny
🏨 Top Stays:
 - ₹2500/night
 - ₹3200/night

🧠 Perfect for relaxing beach vacations...
```

---

## 🔥 Key Innovations

* 🧠 Hybrid AI system (LLM + Tools)
* ⚡ Async MCP orchestration
* 💬 Conversational memory flow
* 🎯 Intent-driven tool calling
* 📦 Real-time data integration

---

## ⚠️ Challenges Faced

* MCP weather parsing issues (text-based responses)
* Async handling of multiple tools
* Budget filtering UX
* UI consistency

---

## 🚀 Future Improvements

* 📊 Ranking system (best stay by price + rating)
* 🌍 Multi-city itinerary planning
* 🧾 Booking integration
* 🗺️ Map visualization
* 🧠 Long-term memory

---

## 👨‍💻 Author

**Harsh Arora**


Give it a star ⭐ on GitHub and share!
