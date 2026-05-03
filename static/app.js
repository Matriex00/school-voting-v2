const screens = {
  join: document.getElementById("join-screen"),
  blocked: document.getElementById("blocked-screen"),
  quiz: document.getElementById("quiz-screen"),
  success: document.getElementById("success-screen"),
};

const sessionCodeInput = document.getElementById("session-code");
const joinMessage = document.getElementById("join-message");
const startBtn = document.getElementById("start-btn");
const unlockPasswordInput = document.getElementById("unlock-password");
const unlockBtn = document.getElementById("unlock-btn");
const backToCodeBtn = document.getElementById("back-to-code-btn");
const unlockMessage = document.getElementById("unlock-message");

const currentSessionCodeLabel = document.getElementById("current-session-code");
const questionCategory = document.getElementById("question-category");
const categoryDescription = document.getElementById("category-description");
const questionTitle = document.getElementById("question-title");
const progressText = document.getElementById("progress-text");
const progressFill = document.getElementById("progress-fill");
const optionsContainer = document.getElementById("options-container");
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");
const quizMessage = document.getElementById("quiz-message");
const successTime = document.getElementById("success-time");
const toBlockedBtn = document.getElementById("to-blocked-btn");

let deviceId = localStorage.getItem("device_id") || `device-${Math.random().toString(36).slice(2, 10)}-${Date.now()}`;
localStorage.setItem("device_id", deviceId);

let activeSessionCode = "";
let questions = [];
let answers = [];
let currentQuestionIndex = 0;

function showScreen(name) {
  Object.values(screens).forEach(screen => screen.classList.remove("active"));
  screens[name].classList.add("active");
}

function setMessage(el, text, type = "") {
  el.textContent = text || "";
  el.className = "message " + type;
}

function renderQuestion() {
  const item = questions[currentQuestionIndex];
  if (!item) return;

  const qType = item.type || "choice";
  const ans = answers[currentQuestionIndex];

  currentSessionCodeLabel.textContent = activeSessionCode;
  questionCategory.textContent = item.category_title || "Pytanie";
  categoryDescription.textContent = item.category_description || "";
  questionTitle.textContent = item.question;
  progressText.textContent = `${currentQuestionIndex + 1} / ${questions.length}`;
  progressFill.style.width = `${((currentQuestionIndex + 1) / questions.length) * 100}%`;

  optionsContainer.innerHTML = "";

  // 1. Pole tekstowe dla 'open' (otwarte) i 'mixed' (mieszane)
  if (qType === "open" || qType === "mixed") {
    const inputWrapper = document.createElement("div");
    inputWrapper.className = "input-group";
    inputWrapper.style.marginBottom = "25px"; // Dodatkowy odstęp

    const input = document.createElement(qType === "open" ? "textarea" : "input");
    if (qType === "mixed") {
      input.type = "text";
      input.placeholder = "Wpisz tutaj cytat danego nauczyciela..."; // Twoja prośba
    } else {
      // Dla pytań otwartych (np. imię i nazwisko)
      input.className = "text-input open-question-field";
      input.placeholder = "Wpisz tutaj imię i nazwisko..."; 
      input.rows = 3;
    }
    
    input.className += " custom-styled-input";
    input.value = ans.custom_text || "";
    input.oninput = (e) => {
      answers[currentQuestionIndex].custom_text = e.target.value;
      validate();
    };
    
    inputWrapper.appendChild(input);
    optionsContainer.appendChild(inputWrapper);
  }

  // 2. Opcje wyboru dla 'choice' i 'mixed'
  if (qType === "choice" || qType === "mixed") {
    const list = document.createElement("div");
    list.className = "options-list";
    item.options.forEach((opt, idx) => {
      const btn = document.createElement("button");
      btn.className = "option-btn" + (ans.selected_option_index === idx ? " selected" : "");
      btn.textContent = opt;
      btn.onclick = () => {
        answers[currentQuestionIndex].selected_option_index = idx;
        renderQuestion();
      };
      list.appendChild(btn);
    });
    optionsContainer.appendChild(list);
  }

  validate();
  prevBtn.disabled = currentQuestionIndex === 0;
  nextBtn.textContent = currentQuestionIndex === questions.length - 1 ? "Zakończ" : "Dalej";
}

function validate() {
  const item = questions[currentQuestionIndex];
  const ans = answers[currentQuestionIndex];
  const type = item.type || "choice";
  let ok = false;

  if (type === "choice") {
    // Musisz wybrać opcję
    ok = ans.selected_option_index !== null;
  } else if (type === "open") {
    // Pole tekstowe jest teraz ZAWSZE poprawne (nawet puste)
    ok = true; 
  } else if (type === "mixed") {
    // W pytaniu mieszanym musisz wybrać opcję, ale tekst może być pusty
    ok = ans.selected_option_index !== null;
  }

  nextBtn.disabled = !ok;
}

async function startFlow() {
  const code = sessionCodeInput.value.trim().toUpperCase();
  if (!code) return setMessage(joinMessage, "Wpisz kod", "error");
  startBtn.disabled = true;

  try {
    const res = await fetch(`/api/session/${code}/status`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ device_id: deviceId })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    activeSessionCode = code;
    if (data.device_locked) return showScreen("blocked");

    const qRes = await fetch(`/api/session/${code}/questions`);
    questions = (await qRes.json()).questions;
    answers = questions.map(() => ({ selected_option_index: null, custom_text: "" }));
    currentQuestionIndex = 0;
    renderQuestion();
    showScreen("quiz");
  } catch (e) { setMessage(joinMessage, e.message, "error"); }
  finally { startBtn.disabled = false; }
}

async function submit() {
  nextBtn.disabled = true;
  try {
    const res = await fetch(`/api/session/${activeSessionCode}/submit-survey`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ device_id: deviceId, answers })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    successTime.textContent = `Zapisano: ${data.submitted_at}`;
    showScreen("success");
  } catch (e) { setMessage(quizMessage, e.message, "error"); nextBtn.disabled = false; }
}

startBtn.onclick = startFlow;
nextBtn.onclick = () => currentQuestionIndex < questions.length - 1 ? (currentQuestionIndex++, renderQuestion()) : submit();
prevBtn.onclick = () => { currentQuestionIndex--; renderQuestion(); };
toBlockedBtn.onclick = () => showScreen("blocked");
unlockBtn.onclick = async () => {
  const res = await fetch("/api/device/unlock", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ session_code: activeSessionCode, device_id: deviceId, password: unlockPasswordInput.value })
  });
  if ((await res.json()).ok) startFlow();
  else setMessage(unlockMessage, "Złe hasło", "error");
};