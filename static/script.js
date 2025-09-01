// === static/script.js (PATCH NON-STREAM) ===
const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("input");
const formEl = document.getElementById("composer");

const fiturEl = document.getElementById("fitur");
const modeEl = document.getElementById("mode_bahasa");
const chatModeEl = document.getElementById("mode_chat");
const tingkatEl = document.getElementById("tingkat_tutur");
const roomId = document.getElementById("roomSelect").value || "room1";


// function appendBubble(text, who="bot") {
//   const wrap = document.createElement("div");
//   wrap.className = `flex ${who === "user" ? "justify-end" : "justify-start"} my-1`;
//   const b = document.createElement("div");
//   b.className = `px-3 py-2 rounded-xl max-w-xl ${who === "user" ? "bg-emerald-100" : "bg-gray-100"}`;
//   b.innerHTML = text;
//   wrap.appendChild(b);
//   messagesEl.appendChild(wrap);
//   messagesEl.scrollTop = messagesEl.scrollHeight;
// }

// async function persistSettings() {
//   try {
//     await fetch("/chat/settings", {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify({
//         fitur: fiturEl?.value || "chatbot",
//         mode_bahasa: modeEl?.value || "Sunda",
//         chat_mode: chatModeEl?.value || "Ngobrol",
//         tingkat_tutur: tingkatEl?.value || "Loma"
//       })
//     });
//   } catch {}
// }

// // simpan setting tiap ganti dropdown
// [fiturEl, modeEl, chatModeEl, tingkatEl].forEach(el => {
//   el?.addEventListener("change", persistSettings);
// });

// // === KIRIM PESAN (NON-STREAM) ===
// formEl?.addEventListener("submit", async (e) => {
//   e.preventDefault();
//   const text = (inputEl?.value || "").trim();
//   if (!text) return;

//   appendBubble(text, "user");
//   inputEl.value = "";

//   appendBubble("…", "bot");
//   const typing = messagesEl.lastChild;

//   try {
//     await persistSettings();
//     const res = await fetch("/chat/reply", {
//       method: "POST",
//       headers: { "Content-Type": "application/json" },
//       body: JSON.stringify({
//         message: text,
//         fitur: fiturEl?.value || "chatbot",
//         mode_bahasa: modeEl?.value || "Sunda",
//         chat_mode: chatModeEl?.value || "Ngobrol",
//         tingkat_tutur: tingkatEl?.value || "Loma",
//         room_id: roomId
//       })
//     });

//     const data = await res.json();
//     messagesEl.removeChild(typing);
//     appendBubble(data.reply || "Terjadi kesalahan.", "bot");
//   } catch (err) {
//     messagesEl.removeChild(typing);
//     appendBubble("Gagal terhubung ke server.", "bot");
//   }
// });