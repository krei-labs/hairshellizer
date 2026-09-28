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

  function render(data) {
    chatBox.innerHTML = "";
    data.messages.forEach((m) => {
      const div = document.createElement("div");
      div.className = "chat-bubble " + (m.is_me ? "me" : "them");
      div.innerHTML = `<div class="small fw-semibold">${m.is_me ? "You" : m.sender_name}</div>
                        <div>${m.message.replace(/</g, "&lt;")}</div>
                        <div class="small text-muted">${m.created_at}</div>`;
      chatBox.appendChild(div);
    });
    chatBox.scrollTop = chatBox.scrollHeight;

    const expiredBanner = document.getElementById("chat-expired-banner");
    if (expiredBanner) {
      expiredBanner.classList.toggle("d-none", data.status === "ACTIVE");
    }
    const form = document.getElementById("chat-send-form");
    if (form) {
      form.classList.toggle("d-none", data.status !== "ACTIVE");
    }
  }

  function poll() {
    fetch(pollUrl)
      .then((res) => res.json())
      .then(render)
      .catch(() => {});
  }

  poll();
  setInterval(poll, 5000);
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
