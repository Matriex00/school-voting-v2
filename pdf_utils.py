import os
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)

FONT_REGULAR_NAME = "ReportFont"
FONT_BOLD_NAME = "ReportFontBold"


def register_fonts():
    fonts_dir = os.path.join(os.getcwd(), "fonts")
    regular_path = os.path.join(fonts_dir, "DejaVuSans.ttf")
    bold_path = os.path.join(fonts_dir, "DejaVuSans-Bold.ttf")

    regular_exists = os.path.exists(regular_path)
    bold_exists = os.path.exists(bold_path)

    if regular_exists and bold_exists:
        try:
            pdfmetrics.registerFont(TTFont(FONT_REGULAR_NAME, regular_path))
            pdfmetrics.registerFont(TTFont(FONT_BOLD_NAME, bold_path))
            return FONT_REGULAR_NAME, FONT_BOLD_NAME
        except Exception:
            pass

    return "Helvetica", "Helvetica-Bold"


FONT_REGULAR, FONT_BOLD = register_fonts()


def build_styles():
    styles = getSampleStyleSheet()

    title = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontName=FONT_BOLD,
        fontSize=20,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=10,
    )

    subtitle = ParagraphStyle(
        "CustomSubtitle",
        parent=styles["Normal"],
        fontName=FONT_REGULAR,
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=12,
    )

    heading = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=10,
        spaceAfter=8,
    )

    body = ParagraphStyle(
        "CustomBody",
        parent=styles["BodyText"],
        fontName=FONT_REGULAR,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#1e293b"),
        alignment=TA_LEFT,
    )

    return {
        "title": title,
        "subtitle": subtitle,
        "heading": heading,
        "body": body,
    }


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT_REGULAR, 9)
    canvas.setFillColor(colors.HexColor("#64748b"))
    page_text = f"Strona {doc.page}"
    canvas.drawRightString(195 * mm, 10 * mm, page_text)
    canvas.restoreState()


def build_info_table(rows):
    table = Table(rows, colWidths=[55 * mm, 115 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("FONTNAME", (0, 0), (0, -1), FONT_BOLD),
        ("FONTNAME", (1, 0), (1, -1), FONT_REGULAR),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def build_question_table(question_stat, include_percentage=True):
    if include_percentage:
        rows = [["Odpowiedź", "Liczba głosów", "Udział procentowy"]]
        for option in question_stat["options"]:
            rows.append([
                option["option_text"],
                str(option["votes"]),
                f"{option['percentage']:.2f}%".replace(".", ",")
            ])
        col_widths = [110 * mm, 30 * mm, 30 * mm]
    else:
        rows = [["Odpowiedź", "Liczba głosów"]]
        for option in question_stat["options"]:
            rows.append([
                option["option_text"],
                str(option["votes"])
            ])
        col_widths = [140 * mm, 30 * mm]

    table = Table(rows, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def aggregate_results(results_list):
    if not results_list:
        return []

    questions_count = len(results_list[0]["question_stats"])
    aggregated = []

    for question_index in range(questions_count):
        question_text = results_list[0]["question_stats"][question_index]["question_text"]
        option_count = len(results_list[0]["question_stats"][question_index]["options"])

        total_submissions = sum(item["summary"]["submissions_count"] for item in results_list)
        combined_options = []

        for option_index in range(option_count):
            option_text = results_list[0]["question_stats"][question_index]["options"][option_index]["option_text"]
            votes = sum(
                item["question_stats"][question_index]["options"][option_index]["votes"]
                for item in results_list
            )
            percentage = (votes / total_submissions * 100) if total_submissions > 0 else 0.0

            combined_options.append({
                "option_index": option_index,
                "option_text": option_text,
                "votes": votes,
                "percentage": round(percentage, 2)
            })

        aggregated.append({
            "question_index": question_index,
            "question_text": question_text,
            "options": combined_options
        })

    return aggregated


def build_session_report_pdf(results_data):
    styles = build_styles()
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Raport sesji {results_data['session']['code']}",
        author="System głosowania"
    )

    story = []

    session_info = results_data["session"]
    summary = results_data["summary"]
    question_stats = results_data["question_stats"]

    story.append(Paragraph("Raport sesji głosowania", styles["title"]))
    story.append(Paragraph(
        f"Sesja: <b>{session_info['code']}</b> | Klasa: <b>{session_info['class_name']}</b>",
        styles["subtitle"]
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Informacje podstawowe", styles["heading"]))
    story.append(build_info_table([
        ["Kod sesji", session_info["code"]],
        ["Klasa", session_info["class_name"]],
        ["Status", session_info["status"]],
        ["Data rozpoczęcia", session_info["start_ts"] or "-"],
        ["Data zakończenia", session_info["end_ts"] or "-"],
        ["Liczba pytań", str(summary["questions_count"])],
        ["Liczba oddanych głosów", str(summary["submissions_count"])],
    ]))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Zestawienie odpowiedzi w sesji", styles["heading"]))

    for question_stat in question_stats:
        story.append(Paragraph(
            f"<b>Pytanie {question_stat['question_index'] + 1}:</b> {question_stat['question_text']}",
            styles["body"]
        ))
        story.append(Spacer(1, 2 * mm))
        story.append(build_question_table(question_stat, include_percentage=False))
        story.append(Spacer(1, 4 * mm))

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)
    return buffer


def build_summary_report_pdf(results_list):
    styles = build_styles()
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Raport zbiorczy sesji",
        author="System głosowania"
    )

    story = []

    total_sessions = len(results_list)
    total_votes = sum(item["summary"]["submissions_count"] for item in results_list)
    total_questions = results_list[0]["summary"]["questions_count"] if results_list else 0

    story.append(Paragraph("Raport zbiorczy sesji głosowania", styles["title"]))
    story.append(Paragraph(
        "Zestawienie wszystkich sesji oraz podsumowanie końcowe",
        styles["subtitle"]
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Podsumowanie ogólne", styles["heading"]))
    story.append(build_info_table([
        ["Liczba sesji w raporcie", str(total_sessions)],
        ["Liczba pytań", str(total_questions)],
        ["Łączna liczba oddanych głosów", str(total_votes)],
    ]))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Każda sesja osobno", styles["heading"]))

    for idx, result in enumerate(results_list, start=1):
        session_info = result["session"]
        summary = result["summary"]

        if idx > 1:
            story.append(PageBreak())

        story.append(Paragraph(
            f"Sesja {session_info['code']} | klasa {session_info['class_name']}",
            styles["heading"]
        ))

        story.append(build_info_table([
            ["Kod sesji", session_info["code"]],
            ["Klasa", session_info["class_name"]],
            ["Status", session_info["status"]],
            ["Start", session_info["start_ts"] or "-"],
            ["Koniec", session_info["end_ts"] or "-"],
            ["Liczba oddanych głosów", str(summary["submissions_count"])],
        ]))

        story.append(Spacer(1, 5 * mm))

        for question_stat in result["question_stats"]:
            story.append(Paragraph(
                f"<b>Pytanie {question_stat['question_index'] + 1}:</b> {question_stat['question_text']}",
                styles["body"]
            ))
            story.append(Spacer(1, 2 * mm))
            story.append(build_question_table(question_stat, include_percentage=False))
            story.append(Spacer(1, 4 * mm))

    story.append(PageBreak())
    story.append(Paragraph("Podsumowanie końcowe wszystkich sesji", styles["heading"]))

    aggregated_questions = aggregate_results(results_list)

    for question_stat in aggregated_questions:
        story.append(Paragraph(
            f"<b>Pytanie {question_stat['question_index'] + 1}:</b> {question_stat['question_text']}",
            styles["body"]
        ))
        story.append(Spacer(1, 2 * mm))
        story.append(build_question_table(question_stat, include_percentage=True))
        story.append(Spacer(1, 4 * mm))

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)
    return buffer