const teacherKeyInput = document.getElementById("teacher-key");

const classNameInput = document.getElementById("class-name");
const openSessionBtn = document.getElementById("open-session-btn");
const openSessionMessage = document.getElementById("open-session-message");

const closeSessionCodeInput = document.getElementById("close-session-code");
const closeSessionBtn = document.getElementById("close-session-btn");
const closeSessionMessage = document.getElementById("close-session-message");

const resultsSessionCodeInput = document.getElementById("results-session-code");
const showResultsBtn = document.getElementById("show-results-btn");
const resultsMessage = document.getElementById("results-message");
const resultsOutput = document.getElementById("results-output");

const summaryCodesInput = document.getElementById("summary-codes");
const summaryReportBtn = document.getElementById("summary-report-btn");
const summaryMessage = document.getElementById("summary-message");

function getTeacherHeaders() {
  const teacherKey = teacherKeyInput.value.trim();
  return {
    "Content-Type": "application/json",
    "X-TEACHER-KEY": teacherKey
  };
}

function setMessage(el, text, type = "") {
  el.textContent = text || "";
  el.className = "message";
  if (type) {
    el.classList.add(type);
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

openSessionBtn.addEventListener("click", async () => {
  const className = classNameInput.value.trim();

  if (!teacherKeyInput.value.trim()) {
    setMessage(openSessionMessage, "Wpisz klucz nauczyciela.", "error");
    return;
  }

  if (!className) {
    setMessage(openSessionMessage, "Wpisz nazwę klasy.", "error");
    return;
  }

  openSessionBtn.disabled = true;
  setMessage(openSessionMessage, "Otwieranie sesji...");

  try {
    const response = await fetch("/api/session/open", {
      method: "POST",
      headers: getTeacherHeaders(),
      body: JSON.stringify({
        class_name: className
      })
    });

    const data = await response.json();

    if (data.error) {
      setMessage(openSessionMessage, data.error, "error");
      return;
    }

    setMessage(
      openSessionMessage,
      `Sesja otwarta poprawnie. Kod sesji: ${data.session_code}`,
      "success"
    );
  } catch (error) {
    setMessage(openSessionMessage, "Błąd połączenia z serwerem.", "error");
  } finally {
    openSessionBtn.disabled = false;
  }
});

closeSessionBtn.addEventListener("click", async () => {
  const code = closeSessionCodeInput.value.trim().toUpperCase();

  if (!teacherKeyInput.value.trim()) {
    setMessage(closeSessionMessage, "Wpisz klucz nauczyciela.", "error");
    return;
  }

  if (!code) {
    setMessage(closeSessionMessage, "Wpisz kod sesji.", "error");
    return;
  }

  closeSessionBtn.disabled = true;
  setMessage(closeSessionMessage, "Generowanie raportu PDF...");

  try {
    const response = await fetch("/api/session/close", {
      method: "POST",
      headers: getTeacherHeaders(),
      body: JSON.stringify({
        session_code: code
      })
    });

    if (!response.ok) {
      const data = await response.json();
      setMessage(closeSessionMessage, data.error || "Nie udało się zamknąć sesji.", "error");
      return;
    }

    const blob = await response.blob();
    downloadBlob(blob, `raport_sesji_${code}.pdf`);
    setMessage(closeSessionMessage, "Raport sesji został pobrany.", "success");
  } catch (error) {
    setMessage(closeSessionMessage, "Błąd połączenia z serwerem.", "error");
  } finally {
    closeSessionBtn.disabled = false;
  }
});

showResultsBtn.addEventListener("click", async () => {
  const code = resultsSessionCodeInput.value.trim().toUpperCase();

  if (!teacherKeyInput.value.trim()) {
    setMessage(resultsMessage, "Wpisz klucz nauczyciela.", "error");
    return;
  }

  if (!code) {
    setMessage(resultsMessage, "Wpisz kod sesji.", "error");
    return;
  }

  showResultsBtn.disabled = true;
  setMessage(resultsMessage, "Pobieranie wyników...");
  resultsOutput.textContent = "";

  try {
    const response = await fetch(`/api/session/${encodeURIComponent(code)}/results`, {
      method: "GET",
      headers: {
        "X-TEACHER-KEY": teacherKeyInput.value.trim()
      }
    });

    const data = await response.json();

    if (data.error) {
      setMessage(resultsMessage, data.error, "error");
      return;
    }

    resultsOutput.textContent = JSON.stringify(data, null, 2);
    setMessage(resultsMessage, "Wyniki pobrane poprawnie.", "success");
  } catch (error) {
    setMessage(resultsMessage, "Błąd połączenia z serwerem.", "error");
  } finally {
    showResultsBtn.disabled = false;
  }
});

summaryReportBtn.addEventListener("click", async () => {
  const rawCodes = summaryCodesInput.value.trim();

  if (!teacherKeyInput.value.trim()) {
    setMessage(summaryMessage, "Wpisz klucz nauczyciela.", "error");
    return;
  }

  if (!rawCodes) {
    setMessage(summaryMessage, "Wpisz kody sesji.", "error");
    return;
  }

  const sessionCodes = rawCodes
    .split(",")
    .map(item => item.trim().toUpperCase())
    .filter(Boolean);

  summaryReportBtn.disabled = true;
  setMessage(summaryMessage, "Generowanie raportu zbiorczego...");

  try {
    const response = await fetch("/api/sessions/summary-report", {
      method: "POST",
      headers: getTeacherHeaders(),
      body: JSON.stringify({
        session_codes: sessionCodes
      })
    });

    if (!response.ok) {
      const data = await response.json();
      setMessage(summaryMessage, data.error || "Nie udało się pobrać raportu.", "error");
      return;
    }

    const blob = await response.blob();
    downloadBlob(blob, "raport_zbiorczy_sesji.pdf");
    setMessage(summaryMessage, "Raport zbiorczy został pobrany.", "success");
  } catch (error) {
    setMessage(summaryMessage, "Błąd połączenia z serwerem.", "error");
  } finally {
    summaryReportBtn.disabled = false;
  }
});