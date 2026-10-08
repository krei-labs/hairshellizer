// Quantity stepper buttons (used on product detail + cart pages)
document.addEventListener("click", function (e) {
  const btn = e.target.closest("[data-qty-btn]");
  if (!btn) return;
  const input = document.querySelector(btn.dataset.target);
  if (!input) return;
  const step = parseInt(btn.dataset.qtyBtn, 10);
  const max = parseInt(input.max || "9999", 10);
  const min = parseInt(input.min || "1", 10);
  let value = parseInt(input.value || "1", 10) + step;
  value = Math.max(min, Math.min(max, value));
  input.value = value;
});

// Simple polling for chat conversation pages (no WebSockets needed).
(function initChatPolling() {
  const chatBox = document.getElementById("chat-messages");
  if (!chatBox) return;
  const conversationId = chatBox.dataset.conversationId;
  const pollUrl = `/chat/${conversationId}/messages.json`;

  // Statuses in which messages can still be sent. ACTIVE is the legacy name
  // for PENDING. This list must match CHAT_OPEN_STATUSES in models.py; the old
  // code only accepted "ACTIVE", so the send box vanished for Pending/Delivered.
  const OPEN_STATUSES = ["ACTIVE", "PENDING", "DELIVERED"];
  let lastSnapshot = "";

  function buildBubble(m) {
    // Use textContent (never innerHTML) so names and messages typed by users
    // cannot inject HTML/JS into another user's browser.
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble " + (m.is_me ? "me" : "them");

    const who = document.createElement("div");
    who.className = "small fw-semibold";
    who.textContent = m.is_me ? "You" : m.sender_name;

    const body = document.createElement("div");
    body.textContent = m.message;

    const when = document.createElement("div");
    when.className = "small text-muted";
    when.textContent = m.created_at;

    bubble.append(who, body, when);
    return bubble;
  }

  function render(data) {
    const snapshot = JSON.stringify([data.status, data.messages]);
    if (snapshot === lastSnapshot) return;   // nothing changed: don't redraw
    lastSnapshot = snapshot;

    // Only jump to the newest message if the reader was already at the bottom,
    // so polling doesn't yank them away while they scroll through history.
    const wasAtBottom = chatBox.scrollHeight - chatBox.scrollTop - chatBox.clientHeight < 40;
    chatBox.replaceChildren(...data.messages.map(buildBubble));
    if (wasAtBottom) chatBox.scrollTop = chatBox.scrollHeight;

    const isOpen = OPEN_STATUSES.includes(data.status);
    const expiredBanner = document.getElementById("chat-expired-banner");
    if (expiredBanner) expiredBanner.classList.toggle("d-none", isOpen);
    const form = document.getElementById("chat-send-form");
    if (form) form.classList.toggle("d-none", !isOpen);
  }

  function poll() {
    if (document.hidden) return;             // don't hit the server from background tabs
    fetch(pollUrl, { credentials: "same-origin" })
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then(render)
      .catch(() => {});
  }

  poll();
  setInterval(poll, 5000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
})();

// ---------------------------------------------------------------------
// Interactivity: scroll reveal, navbar shadow, back-to-top, count-up
// ---------------------------------------------------------------------
(function initInteractions() {
  // Scroll reveal
  const revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && revealEls.length) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("visible"));
  }

  // Navbar shadow + back-to-top visibility
  const nav = document.getElementById("mainNav");
  const topBtn = document.getElementById("backToTop");
  function onScroll() {
    const y = window.scrollY || document.documentElement.scrollTop;
    if (nav) nav.classList.toggle("scrolled", y > 10);
    if (topBtn) topBtn.classList.toggle("show", y > 400);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
  if (topBtn) topBtn.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));

  // Count-up numbers (elements with data-count)
  document.querySelectorAll("[data-count]").forEach((el) => {
    const target = parseInt(el.dataset.count, 10);
    const obs = new IntersectionObserver((entries) => {
      if (!entries[0].isIntersecting) return;
      obs.disconnect();
      let current = 0;
      const step = Math.max(1, Math.ceil(target / 40));
      const timer = setInterval(() => {
        current += step;
        if (current >= target) { current = target; clearInterval(timer); }
        el.textContent = current;
      }, 30);
    }, { threshold: 0.5 });
    obs.observe(el);
  });
})();
