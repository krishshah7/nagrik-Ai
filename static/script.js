// ---- Submit page: "Rewrite with AI" button ----
const rewriteBtn = document.getElementById("rewrite-btn");
if (rewriteBtn) {
  rewriteBtn.addEventListener("click", async () => {
    const textarea = document.getElementById("description");
    if (!textarea.value.trim()) return;

    rewriteBtn.textContent = "Rewriting...";
    rewriteBtn.disabled = true;

    try {
      const res = await fetch("/api/rewrite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: textarea.value }),
      });
      const data = await res.json();
      textarea.value = data.rewritten;
    } catch (err) {
      alert("Could not rewrite right now. Please try again.");
    } finally {
      rewriteBtn.textContent = "✨ Rewrite with AI";
      rewriteBtn.disabled = false;
    }
  });
}

// ---- Assistant page: chat with the Router Agent ----
const chatForm = document.getElementById("chat-form");
if (chatForm) {
  const chatWindow = document.getElementById("chat-window");
  const chatInput = document.getElementById("chat-input");

  function addMessage(text, sender) {
    const el = document.createElement("div");
    el.className = `chat-msg ${sender}`;
    el.textContent = text;
    chatWindow.appendChild(el);
    chatWindow.scrollTop = chatWindow.scrollHeight;
    return el;
  }

  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    addMessage(message, "user");
    chatInput.value = "";
    const thinkingEl = addMessage("Thinking...", "bot");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const data = await res.json();
      thinkingEl.textContent = data.answer;
    } catch (err) {
      thinkingEl.textContent = "Something went wrong. Please try again.";
    }
  });
}
