chat_memory = {}

def get_memory(session_id):
    return chat_memory.get(session_id, [])

def update_memory(session_id, user, ai):
    if session_id not in chat_memory:
        chat_memory[session_id] = []

    chat_memory[session_id].append({
        "user": user,
        "ai": ai
    })

    return chat_memory[session_id]