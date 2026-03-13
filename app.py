from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from agent import chat

app = FastAPI(title="Chinook Music Store Support")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    output: str


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Chinook Music Store</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: system-ui, sans-serif; background: #f5f5f5; height: 100vh; display: flex; flex-direction: column; }
        header { background: #1a1a2e; color: white; padding: 16px 24px; }
        header h1 { font-size: 18px; font-weight: 600; }
        header p { font-size: 13px; color: #888; }
        #messages { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 12px; }
        .msg { max-width: 70%; padding: 10px 14px; border-radius: 12px; font-size: 14px; line-height: 1.5; white-space: pre-wrap; }
        .user { align-self: flex-end; background: #1a1a2e; color: white; }
        .bot { align-self: flex-start; background: white; border: 1px solid #ddd; }
        .bot.loading { color: #999; font-style: italic; }
        form { display: flex; gap: 8px; padding: 16px 24px; background: white; border-top: 1px solid #ddd; }
        input { flex: 1; padding: 10px 14px; border: 1px solid #ddd; border-radius: 8px; font-size: 14px; outline: none; }
        input:focus { border-color: #1a1a2e; }
        button { padding: 10px 20px; background: #1a1a2e; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
    </style>
</head>
<body>
    <header>
        <h1>Chinook Music Store</h1>
        <p>Ask about tracks, albums, artists, or your purchase history</p>
    </header>
    <div id="messages"></div>
    <form id="form">
        <input id="input" type="text" placeholder="Ask a question..." autocomplete="off" />
        <button type="submit">Send</button>
    </form>
    <script>
        const form = document.getElementById('form');
        const input = document.getElementById('input');
        const messages = document.getElementById('messages');

        function addMsg(text, cls) {
            const div = document.createElement('div');
            div.className = 'msg ' + cls;
            div.textContent = text;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
            return div;
        }

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const text = input.value.trim();
            if (!text) return;
            input.value = '';
            addMsg(text, 'user');
            const loader = addMsg('Thinking...', 'bot loading');
            form.querySelector('button').disabled = true;
            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                const data = await res.json();
                loader.textContent = data.output;
                loader.className = 'msg bot';
            } catch (err) {
                loader.textContent = 'Error: ' + err.message;
                loader.className = 'msg bot';
            }
            form.querySelector('button').disabled = false;
            input.focus();
        });
    </script>
</body>
</html>
"""


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        result = await chat(request.message)
        return ChatResponse(output=result["output"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok"}
