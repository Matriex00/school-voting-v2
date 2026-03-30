import os
from dotenv import load_dotenv
import json
import string
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func

from questions_config import QUESTIONS
from pdf_utils import build_session_report_pdf, build_summary_report_pdf

load_dotenv()

# --------------------------------------------------
# KONFIGURACJA
# --------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")
TEACHER_KEY = os.getenv("TEACHER_KEY", "nauczyciel123")
SERVICE_PASSWORD = os.getenv("SERVICE_PASSWORD", "1234")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "zmien_ten_klucz")

APP_TIMEZONE = "Europe/Warsaw"

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = FLASK_SECRET_KEY

if DATABASE_URL:
    app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL.replace(
        "postgresql://", "postgresql+psycopg://"
    )
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///local.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# --------------------------------------------------
# MODELE
# --------------------------------------------------

class VotingSession(db.Model):
    __tablename__ = "voting_sessions"

    id = db.Column(db.Integer, primary_key=True)
    class_name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(16), unique=True, index=True, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="OPEN")
    start_ts = db.Column(db.DateTime(timezone=True), nullable=False, default=func.now())
    end_ts = db.Column(db.DateTime(timezone=True), nullable=True)

    submissions = db.relationship(
        "SurveySubmission",
        backref="session",
        lazy=True,
        cascade="all, delete-orphan"
    )
    device_locks = db.relationship(
        "DeviceLock",
        backref="session",
        lazy=True,
        cascade="all, delete-orphan"
    )


class SurveySubmission(db.Model):
    __tablename__ = "survey_submissions"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey("voting_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    device_id = db.Column(db.String(128), nullable=False, index=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=False, default=func.now())

    answers = db.relationship(
        "SurveyAnswer",
        backref="submission",
        lazy=True,
        cascade="all, delete-orphan"
    )


class SurveyAnswer(db.Model):
    __tablename__ = "survey_answers"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(
        db.Integer,
        db.ForeignKey("survey_submissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    question_index = db.Column(db.Integer, nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    selected_option_index = db.Column(db.Integer, nullable=False)
    selected_option_text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)


class DeviceLock(db.Model):
    __tablename__ = "device_locks"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey("voting_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    device_id = db.Column(db.String(128), nullable=False, index=True)
    is_locked = db.Column(db.Boolean, nullable=False, default=False)
    locked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    unlocked_at = db.Column(db.DateTime(timezone=True), nullable=True)


class Backup(db.Model):
    __tablename__ = "backups"

    id = db.Column(db.Integer, primary_key=True)
    session_code = db.Column(db.String(16), nullable=False, index=True)
    payload = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=func.now())


class Audit(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(128), nullable=False)
    details = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=func.now())


# --------------------------------------------------
# HELPERY
# --------------------------------------------------

def now_ts():
    return datetime.now(ZoneInfo(APP_TIMEZONE))


def teacher_key_from_request():
    return request.headers.get("X-TEACHER-KEY") or request.headers.get("x-teacher-key")


def require_teacher():
    key = teacher_key_from_request()
    return key == TEACHER_KEY


def log_audit(action: str, details: str):
    db.session.add(Audit(action=action, details=details))
    db.session.commit()


def gen_code(length=4):
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


def generate_unique_session_code(length=4):
    while True:
        code = gen_code(length)
        if not VotingSession.query.filter_by(code=code).first():
            return code


def get_or_create_device_lock(session_id: int, device_id: str):
    lock = DeviceLock.query.filter_by(session_id=session_id, device_id=device_id).first()
    if not lock:
        lock = DeviceLock(
            session_id=session_id,
            device_id=device_id,
            is_locked=False
        )
        db.session.add(lock)
        db.session.commit()
    return lock


def parse_answers_payload(answers):
    if not isinstance(answers, list):
        return None, "Odpowiedzi muszą być listą"

    if len(answers) != len(QUESTIONS):
        return None, f"Musisz udzielić odpowiedzi na dokładnie {len(QUESTIONS)} pytań"

    parsed_answers = []

    for expected_index, item in enumerate(answers):
        if not isinstance(item, dict):
            return None, "Nieprawidłowy format odpowiedzi"

        question_index = item.get("question_index")
        selected_option_index = item.get("selected_option_index")

        if question_index != expected_index:
            return None, "Nieprawidłowa kolejność pytań"

        if not isinstance(selected_option_index, int):
            return None, "Brak poprawnie wybranej odpowiedzi"

        question = QUESTIONS[question_index]
        options = question["options"]

        if selected_option_index < 0 or selected_option_index >= len(options):
            return None, "Wybrano nieprawidłową odpowiedź"

        parsed_answers.append({
            "question_index": question_index,
            "question_text": question["question"],
            "selected_option_index": selected_option_index,
            "selected_option_text": options[selected_option_index],
        })

    return parsed_answers, None


def serialize_submission(submission: SurveySubmission):
    ordered_answers = sorted(submission.answers, key=lambda a: a.question_index)
    return {
        "submission_id": submission.id,
        "device_id": submission.device_id,
        "submitted_at": submission.submitted_at.astimezone(ZoneInfo(APP_TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S"),
        "answers": [
            {
                "question_index": ans.question_index,
                "question_text": ans.question_text,
                "selected_option_index": ans.selected_option_index,
                "selected_option_text": ans.selected_option_text,
            }
            for ans in ordered_answers
        ]
    }


def serialize_session_results(session_obj: VotingSession):
    submissions = (
        SurveySubmission.query
        .filter_by(session_id=session_obj.id)
        .order_by(SurveySubmission.submitted_at.asc(), SurveySubmission.id.asc())
        .all()
    )

    submissions_count = len(submissions)
    question_stats = []

    for question_index, question in enumerate(QUESTIONS):
        option_counts = [0] * len(question["options"])

        for submission in submissions:
            for ans in submission.answers:
                if ans.question_index == question_index:
                    if 0 <= ans.selected_option_index < len(option_counts):
                        option_counts[ans.selected_option_index] += 1

        options_data = []
        for i, opt in enumerate(question["options"]):
            votes = option_counts[i]
            percentage = (votes / submissions_count * 100) if submissions_count > 0 else 0.0
            options_data.append({
                "option_index": i,
                "option_text": opt,
                "votes": votes,
                "percentage": round(percentage, 2)
            })

        question_stats.append({
            "question_index": question_index,
            "question_text": question["question"],
            "options": options_data
        })

    return {
        "session": {
            "id": session_obj.id,
            "class_name": session_obj.class_name,
            "code": session_obj.code,
            "status": session_obj.status,
            "start_ts": session_obj.start_ts.astimezone(ZoneInfo(APP_TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S") if session_obj.start_ts else None,
            "end_ts": session_obj.end_ts.astimezone(ZoneInfo(APP_TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S") if session_obj.end_ts else None,
        },
        "summary": {
            "questions_count": len(QUESTIONS),
            "submissions_count": submissions_count,
        },
        "question_stats": question_stats,
        "submissions": [serialize_submission(submission) for submission in submissions],
    }


# --------------------------------------------------
# STRONY
# --------------------------------------------------

@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/admin")
def admin():
    return app.send_static_file("admin.html")


@app.route("/api/health")
def health():
    return jsonify({
        "ok": True,
        "questions_count": len(QUESTIONS)
    })


# --------------------------------------------------
# API SESJI
# --------------------------------------------------

@app.route("/api/session/open", methods=["POST"])
def open_session():
    if not require_teacher():
        return jsonify({"error": "Brak dostępu"}), 403

    data = request.get_json(silent=True) or {}
    class_name = (data.get("class_name") or "").strip()

    if not class_name:
        return jsonify({"error": "Podaj nazwę klasy"}), 400

    code = generate_unique_session_code(4)

    session_obj = VotingSession(
        class_name=class_name,
        code=code,
        status="OPEN",
        start_ts=now_ts()
    )
    db.session.add(session_obj)
    db.session.commit()

    log_audit("OPEN_SESSION", f"Otwarto sesję {code} dla klasy {class_name}")

    return jsonify({
        "ok": True,
        "session_code": code,
        "session_id": session_obj.id,
        "class_name": class_name
    })


@app.route("/api/session/<session_code>/status", methods=["POST"])
def session_status(session_code):
    data = request.get_json(silent=True) or {}
    device_id = (data.get("device_id") or "").strip()

    if not device_id:
        return jsonify({"error": "Brak identyfikatora urządzenia"}), 400

    session_obj = VotingSession.query.filter_by(code=session_code).first()
    if not session_obj:
        return jsonify({"error": "Nie znaleziono sesji"}), 404

    lock = get_or_create_device_lock(session_obj.id, device_id)

    return jsonify({
        "ok": True,
        "session_exists": True,
        "session_open": session_obj.status == "OPEN",
        "session_code": session_obj.code,
        "class_name": session_obj.class_name,
        "device_locked": bool(lock.is_locked),
        "questions_count": len(QUESTIONS),
    })


@app.route("/api/session/<session_code>/questions", methods=["GET"])
def get_questions(session_code):
    session_obj = VotingSession.query.filter_by(code=session_code, status="OPEN").first()
    if not session_obj:
        return jsonify({"error": "Sesja nie istnieje albo jest zamknięta"}), 404

    return jsonify({
        "questions": [
            {
                "question_index": idx,
                "question": item["question"],
                "options": item["options"]
            }
            for idx, item in enumerate(QUESTIONS)
        ]
    })


@app.route("/api/session/<session_code>/submit-survey", methods=["POST"])
def submit_survey(session_code):
    session_obj = VotingSession.query.filter_by(code=session_code, status="OPEN").first()
    if not session_obj:
        return jsonify({"error": "Sesja nie istnieje albo jest zamknięta"}), 404

    data = request.get_json(silent=True) or {}
    device_id = (data.get("device_id") or "").strip()
    answers = data.get("answers")

    if not device_id:
        return jsonify({"error": "Brak identyfikatora urządzenia"}), 400

    lock = get_or_create_device_lock(session_obj.id, device_id)
    if lock.is_locked:
        return jsonify({"error": "To urządzenie jest zablokowane. Poproś obsługę o odblokowanie."}), 403

    parsed_answers, error = parse_answers_payload(answers)
    if error:
        return jsonify({"error": error}), 400

    submission = SurveySubmission(
        session_id=session_obj.id,
        device_id=device_id,
        submitted_at=now_ts()
    )
    db.session.add(submission)
    db.session.flush()

    for item in parsed_answers:
        db.session.add(SurveyAnswer(
            submission_id=submission.id,
            question_index=item["question_index"],
            question_text=item["question_text"],
            selected_option_index=item["selected_option_index"],
            selected_option_text=item["selected_option_text"],
            is_correct=False
        ))

    lock.is_locked = True
    lock.locked_at = now_ts()
    lock.unlocked_at = None

    payload = {
        "session_code": session_obj.code,
        "submission_id": submission.id,
        "device_id": device_id,
        "submitted_at": submission.submitted_at.isoformat(),
        "answers": parsed_answers
    }
    db.session.add(Backup(
        session_code=session_obj.code,
        payload=json.dumps(payload, ensure_ascii=False)
    ))

    db.session.commit()

    log_audit("SUBMIT_SURVEY", f"Oddano głos w sesji {session_obj.code} z urządzenia {device_id}")

    return jsonify({
        "ok": True,
        "message": "Pomyślnie zagłosowano",
        "submission_id": submission.id,
        "submitted_at": submission.submitted_at.astimezone(ZoneInfo(APP_TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route("/api/device/unlock", methods=["POST"])
def unlock_device():
    data = request.get_json(silent=True) or {}
    session_code = (data.get("session_code") or "").strip()
    device_id = (data.get("device_id") or "").strip()
    password = (data.get("password") or "").strip()

    if not session_code or not device_id or not password:
        return jsonify({"error": "Brakuje wymaganych danych"}), 400

    if password != SERVICE_PASSWORD:
        return jsonify({"error": "Nieprawidłowe hasło obsługi"}), 403

    session_obj = VotingSession.query.filter_by(code=session_code).first()
    if not session_obj:
        return jsonify({"error": "Nie znaleziono sesji"}), 404

    lock = get_or_create_device_lock(session_obj.id, device_id)
    lock.is_locked = False
    lock.unlocked_at = now_ts()

    db.session.commit()

    log_audit("UNLOCK_DEVICE", f"Odblokowano urządzenie {device_id} w sesji {session_code}")

    return jsonify({
        "ok": True,
        "message": "Urządzenie odblokowane"
    })


@app.route("/api/session/<session_code>/results", methods=["GET"])
def session_results(session_code):
    if not require_teacher():
        return jsonify({"error": "Brak dostępu"}), 403

    session_obj = VotingSession.query.filter_by(code=session_code).first()
    if not session_obj:
        return jsonify({"error": "Nie znaleziono sesji"}), 404

    return jsonify(serialize_session_results(session_obj))


@app.route("/api/session/close", methods=["POST"])
def close_session():
    if not require_teacher():
        return jsonify({"error": "Brak dostępu"}), 403

    data = request.get_json(silent=True) or {}
    session_code = (data.get("session_code") or "").strip()

    if not session_code:
        return jsonify({"error": "Podaj kod sesji"}), 400

    session_obj = VotingSession.query.filter_by(code=session_code, status="OPEN").first()
    if not session_obj:
        return jsonify({"error": "Sesja nie istnieje albo jest już zamknięta"}), 404

    session_obj.status = "CLOSED"
    session_obj.end_ts = now_ts()
    db.session.commit()

    results_data = serialize_session_results(session_obj)
    pdf_buffer = build_session_report_pdf(results_data)

    log_audit("CLOSE_SESSION", f"Zamknięto sesję {session_code}")

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"raport_sesji_{session_code}.pdf"
    )


@app.route("/api/sessions/summary-report", methods=["POST"])
def summary_report():
    if not require_teacher():
        return jsonify({"error": "Brak dostępu"}), 403

    data = request.get_json(silent=True) or {}
    session_codes = data.get("session_codes")

    if not isinstance(session_codes, list) or not session_codes:
        return jsonify({"error": "Podaj listę kodów sesji"}), 400

    cleaned_codes = [str(code).strip().upper() for code in session_codes if str(code).strip()]
    if not cleaned_codes:
        return jsonify({"error": "Lista kodów sesji jest pusta"}), 400

    sessions = (
        VotingSession.query
        .filter(VotingSession.code.in_(cleaned_codes))
        .order_by(VotingSession.start_ts.asc(), VotingSession.id.asc())
        .all()
    )

    if not sessions:
        return jsonify({"error": "Nie znaleziono podanych sesji"}), 404

    results_list = [serialize_session_results(session_obj) for session_obj in sessions]
    pdf_buffer = build_summary_report_pdf(results_list)

    log_audit("SUMMARY_REPORT", f"Wygenerowano raport zbiorczy dla sesji: {', '.join(cleaned_codes)}")

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="raport_zbiorczy_sesji.pdf"
    )


# --------------------------------------------------
# START
# --------------------------------------------------

with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)