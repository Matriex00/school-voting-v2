const QUESTIONS_COUNT = 10;

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
const questionTitle = document.getElementById("question-title");
const progressText = document.getElementById("progress-text");
const progressFill = document.getElementById("progress-fill");
const optionsContainer = document.getElementById("options-container");
const prevBtn = document.getElementById("prev-btn");
const nextBtn = document.getElementById("next-btn");
const quizMessage = document.getElementById("quiz-message");

const successTime = document.getElementById("success-time");
const toBlockedBtn = document.getElementById("to-blocked-btn");

let deviceId = localStorage.getItem("device_id");
if (!deviceId) {
  deviceId = `device-${Math.random().toString(36).slice(2, 10)}-${Date.now()}`;
  localStorage.setItem("device_id", deviceId);
}

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
  el.className = "message";
  if (type) {
    el.classList.add(type);
  }
}

function resetQuizState() {
  questions = [];
  answers = [];
  currentQuestionIndex = 0;
  optionsContainer.innerHTML = "";
  nextBtn.disabled = true;
  setMessage(quizMessage, "");
}

function renderQuestion() {
  const item = questions[currentQuestionIndex];
  if (!item) return;

  currentSessionCodeLabel.textContent = activeSessionCode;
  questionTitle.textContent = item.question;
  progressText.textContent = `${currentQuestionIndex + 1} / ${questions.length}`;
  progressFill.style.width = `${((currentQuestionIndex + 1) / questions.length) * 100}%`;

  optionsContainer.innerHTML = "";

  item.options.forEach((optionText, optionIndex) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "option-btn";
    button.textContent = optionText;

    if (answers[currentQuestionIndex] === optionIndex) {
      button.classList.add("selected");
    }

    button.addEventListener("click", () => {
      answers[currentQuestionIndex] = optionIndex;
      renderQuestion();
    });

    optionsContainer.appendChild(button);
  });

  nextBtn.disabled = typeof answers[currentQuestionIndex] !== "number";
  prevBtn.disabled = currentQuestionIndex === 0;
  nextBtn.textContent = currentQuestionIndex === questions.length - 1 ? "Zakończ i wyślij" : "Dalej";
}

async function fetchSessionStatus(sessionCode) {
  const response = await fetch(`/api/session/${encodeURIComponent(sessionCode)}/status`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      device_id: deviceId
    })
  });

  return response.json();
}

async function fetchQuestions(sessionCode) {
  const response = await fetch(`/api/session/${encodeURIComponent(sessionCode)}/questions`);
  return response.json();
}

async function startFlow() {
  const sessionCode = sessionCodeInput.value.trim().toUpperCase();
  if (!sessionCode) {
    setMessage(joinMessage, "Wpisz kod sesji.", "error");
    return;
  }

  startBtn.disabled = true;
  setMessage(joinMessage, "Sprawdzanie sesji...");

  try {
    const statusData = await fetchSessionStatus(sessionCode);

    if (statusData.error) {
      setMessage(joinMessage, statusData.error, "error");
      return;
    }

    activeSessionCode = sessionCode;

    if (!statusData.session_open) {
      setMessage(joinMessage, "Ta sesja jest zamknięta.", "error");
      return;
    }

    if (statusData.device_locked) {
      unlockPasswordInput.value = "";
      setMessage(unlockMessage, "");
      showScreen("blocked");
      return;
    }

    const questionsData = await fetchQuestions(sessionCode);
    if (questionsData.error) {
      setMessage(joinMessage, questionsData.error, "error");
      return;
    }

    questions = questionsData.questions || [];
    answers = new Array(questions.length).fill(null);
    currentQuestionIndex = 0;

    if (!questions.length) {
      setMessage(joinMessage, "Brak pytań w sesji.", "error");
      return;
    }

    renderQuestion();
    showScreen("quiz");
    setMessage(joinMessage, "");
  } catch (error) {
    setMessage(joinMessage, "Błąd połączenia z serwerem.", "error");
  } finally {
    startBtn.disabled = false;
  }
}

async function unlockDevice() {
  const password = unlockPasswordInput.value.trim();
  if (!password) {
    setMessage(unlockMessage, "Wpisz hasło obsługi.", "error");
    return;
  }

  unlockBtn.disabled = true;
  setMessage(unlockMessage, "Trwa odblokowywanie...");

  try {
    const response = await fetch("/api/device/unlock", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        session_code: activeSessionCode,
        device_id: deviceId,
        password
      })
    });

    const data = await response.json();

    if (data.error) {
      setMessage(unlockMessage, data.error, "error");
      return;
    }

    setMessage(unlockMessage, "Urządzenie odblokowane.", "success");
    sessionCodeInput.value = activeSessionCode;
    await startFlow();
  } catch (error) {
    setMessage(unlockMessage, "Błąd połączenia z serwerem.", "error");
  } finally {
    unlockBtn.disabled = false;
  }
}

async function submitSurvey() {
  const payload = answers.map((selectedOptionIndex, questionIndex) => ({
    question_index: questionIndex,
    selected_option_index: selectedOptionIndex
  }));

  nextBtn.disabled = true;
  prevBtn.disabled = true;
  setMessage(quizMessage, "Zapisywanie głosu...");

  try {
    const response = await fetch(`/api/session/${encodeURIComponent(activeSessionCode)}/submit-survey`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        device_id: deviceId,
        answers: payload
      })
    });

    const data = await response.json();

    if (data.error) {
      setMessage(quizMessage, data.error, "error");
      renderQuestion();
      return;
    }

    successTime.textContent = `Czas zapisu głosu: ${data.submitted_at}`;
    setMessage(quizMessage, "");
    showScreen("success");
  } catch (error) {
    setMessage(quizMessage, "Błąd połączenia z serwerem.", "error");
    renderQuestion();
  }
}

startBtn.addEventListener("click", startFlow);

sessionCodeInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    startFlow();
  }
});

unlockBtn.addEventListener("click", unlockDevice);

backToCodeBtn.addEventListener("click", () => {
  showScreen("join");
});

prevBtn.addEventListener("click", () => {
  if (currentQuestionIndex > 0) {
    currentQuestionIndex -= 1;
    renderQuestion();
  }
});

nextBtn.addEventListener("click", async () => {
  if (typeof answers[currentQuestionIndex] !== "number") {
    setMessage(quizMessage, "Wybierz jedną odpowiedź.", "error");
    return;
  }

  if (currentQuestionIndex < questions.length - 1) {
    currentQuestionIndex += 1;
    renderQuestion();
    return;
  }

  await submitSurvey();
});

toBlockedBtn.addEventListener("click", () => {
  unlockPasswordInput.value = "";
  setMessage(unlockMessage, "");
  showScreen("blocked");
});