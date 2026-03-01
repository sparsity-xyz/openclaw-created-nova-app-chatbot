import os
import json
import hashlib
import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

IN_ENCLAVE = os.getenv("IN_ENCLAVE", "false").lower() == "true"
ODYN_BASE = "http://127.0.0.1:18000" if IN_ENCLAVE else "http://odyn.sparsity.cloud:18000"


class ChatRequest(BaseModel):
    message: str


@app.get("/api/enclave-info")
def enclave_info():
    """Return the enclave's public key and address."""
    r = httpx.get(f"{ODYN_BASE}/v1/eth/address", timeout=10)
    r.raise_for_status()
    return r.json()


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Always respond with Hi! and sign the response with the enclave key."""
    response_text = "Hi!"

    # Sign the response so clients can verify it came from this enclave
    sign_resp = httpx.post(
        f"{ODYN_BASE}/v1/eth/sign",
        json={"message": response_text},
        timeout=10,
    )
    sign_resp.raise_for_status()
    sig_data = sign_resp.json()

    return {
        "response": response_text,
        "signature": sig_data["signature"],
    }


@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Nova Chatbot</title>
<script src="https://cdn.jsdelivr.net/npm/ethers@6/dist/ethers.umd.min.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }
  .header { padding: 16px 24px; background: #111; border-bottom: 1px solid #222; }
  .header h1 { font-size: 18px; color: #fff; }
  .header .subtitle { font-size: 12px; color: #888; margin-top: 4px; }
  .enclave-info { padding: 12px 24px; background: #0d1117; border-bottom: 1px solid #1a1a2e; font-size: 12px; font-family: monospace; }
  .enclave-info .label { color: #888; }
  .enclave-info .value { color: #58a6ff; word-break: break-all; }
  .chat { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
  .msg { max-width: 600px; padding: 12px 16px; border-radius: 12px; line-height: 1.5; }
  .msg.user { background: #1a3a5c; align-self: flex-end; color: #fff; }
  .msg.bot { background: #1a1a2e; align-self: flex-start; }
  .msg .text { margin-bottom: 8px; }
  .sig-box { font-size: 11px; font-family: monospace; background: #111; padding: 8px; border-radius: 6px; margin-top: 8px; }
  .sig-box .label { color: #888; }
  .sig-box .value { color: #7ee787; word-break: break-all; }
  .sig-box .fail { color: #f85149; }
  .sig-box .pending { color: #d29922; }
  .input-area { padding: 16px 24px; background: #111; border-top: 1px solid #222; display: flex; gap: 12px; }
  .input-area input { flex: 1; padding: 12px 16px; border-radius: 8px; border: 1px solid #333; background: #1a1a1a; color: #fff; font-size: 14px; outline: none; }
  .input-area input:focus { border-color: #58a6ff; }
  .input-area button { padding: 12px 24px; border-radius: 8px; border: none; background: #238636; color: #fff; font-size: 14px; cursor: pointer; }
  .input-area button:hover { background: #2ea043; }
  .input-area button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
</head>
<body>

<div class="header">
  <h1>🔒 Nova Chatbot</h1>
  <div class="subtitle">Running inside a TEE (Trusted Execution Environment) — responses are cryptographically signed</div>
</div>

<div class="enclave-info" id="enclave-info">
  <span class="label">Loading enclave info...</span>
</div>

<div class="chat" id="chat"></div>

<div class="input-area">
  <input type="text" id="input" placeholder="Say anything..." autofocus />
  <button id="send" onclick="sendMessage()">Send</button>
</div>

<script>
let enclavePublicKey = null;
let enclaveAddress = null;

async function loadEnclaveInfo() {
  try {
    const r = await fetch('/api/enclave-info');
    const data = await r.json();
    enclaveAddress = data.address;
    enclavePublicKey = data.public_key;
    document.getElementById('enclave-info').innerHTML =
      '<div><span class="label">Enclave Address: </span><span class="value">' + enclaveAddress + '</span></div>' +
      '<div style="margin-top:4px"><span class="label">Public Key: </span><span class="value">' + enclavePublicKey + '</span></div>';
  } catch(e) {
    document.getElementById('enclave-info').innerHTML = '<span class="label">Failed to load enclave info</span>';
  }
}

function addMessage(text, cls, extra) {
  const chat = document.getElementById('chat');
  const div = document.createElement('div');
  div.className = 'msg ' + cls;
  div.innerHTML = '<div class="text">' + escapeHtml(text) + '</div>' + (extra || '');
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function escapeHtml(t) {
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function verifySignature(message, signature) {
  try {
    const recoveredAddress = ethers.verifyMessage(message, signature);
    const match = recoveredAddress.toLowerCase() === enclaveAddress.toLowerCase();
    return {
      valid: match,
      recoveredAddress: recoveredAddress
    };
  } catch(e) {
    return { valid: false, error: e.message };
  }
}

async function sendMessage() {
  const input = document.getElementById('input');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';

  addMessage(text, 'user');
  document.getElementById('send').disabled = true;

  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    const data = await r.json();

    const verification = await verifySignature(data.response, data.signature);

    let sigHtml = '<div class="sig-box">' +
      '<div><span class="label">Signature: </span><span class="value">' + data.signature + '</span></div>' +
      '<div style="margin-top:4px"><span class="label">Verification: </span>';

    if (verification.valid) {
      sigHtml += '<span class="value">✅ Valid — signed by enclave ' + verification.recoveredAddress + '</span>';
    } else if (verification.error) {
      sigHtml += '<span class="fail">❌ Error: ' + escapeHtml(verification.error) + '</span>';
    } else {
      sigHtml += '<span class="fail">❌ Invalid — recovered ' + verification.recoveredAddress + ' but expected ' + enclaveAddress + '</span>';
    }
    sigHtml += '</div></div>';

    addMessage(data.response, 'bot', sigHtml);
  } catch(e) {
    addMessage('Error: ' + e.message, 'bot');
  }
  document.getElementById('send').disabled = false;
  input.focus();
}

document.getElementById('input').addEventListener('keydown', e => {
  if (e.key === 'Enter') sendMessage();
});

loadEnclaveInfo();
</script>
</body>
</html>"""
