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

    if os.path.exists(regular_path) and os.path.exists(bold_path):
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
    title = ParagraphStyle("CustomTitle", parent=styles["Title"], fontName=FONT_BOLD, fontSize=20, alignment=TA_CENTER, textColor=colors.HexColor("#0f172a"), spaceAfter=10)
    subtitle = ParagraphStyle("CustomSubtitle", parent=styles["Normal"], fontName=FONT_REGULAR, fontSize=10, alignment=TA_CENTER, textColor=colors.HexColor("#475569"), spaceAfter=12)
    heading = ParagraphStyle("CustomHeading", parent=styles["Heading2"], fontName=FONT_BOLD, fontSize=13, textColor=colors.HexColor("#0f172a"), spaceBefore=10, spaceAfter=8)
    body = ParagraphStyle("CustomBody", parent=styles["BodyText"], fontName=FONT_REGULAR, fontSize=10, textColor=colors.HexColor("#1e293b"), alignment=TA_LEFT)
    italic_body = ParagraphStyle("ItalicBody", parent=body, fontName=FONT_REGULAR, fontSize=9, leftIndent=10, textColor=colors.HexColor("#475569"))
    return {"title": title, "subtitle": subtitle, "heading": heading, "body": body, "italic": italic_body}

def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT_REGULAR, 9)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawRightString(195 * mm, 10 * mm, f"Strona {doc.page}")
    canvas.restoreState()

def build_info_table(rows):
    table = Table(rows, colWidths=[55 * mm, 115 * mm])
    table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("FONTNAME", (0, 0), (0, -1), FONT_BOLD),
        ("FONTNAME", (1, 0), (1, -1), FONT_REGULAR),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    return table

def build_question_table(question_stat, include_percentage=True):
    rows = [["Odpowiedź", "Liczba głosów", "Udział procentowy"]] if include_percentage else [["Odpowiedź", "Liczba głosów"]]
    for opt in question_stat["options"]:
        row = [opt["option_text"], str(opt["votes"])]
        if include_percentage: row.append(f"{opt['percentage']:.2f}%".replace(".", ","))
        rows.append(row)
    
    col_widths = [110 * mm, 30 * mm, 30 * mm] if include_percentage else [140 * mm, 30 * mm]
    table = Table(rows, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    return table

def add_custom_texts_section(story, styles, submissions):
    """Pomocnicza funkcja do wyciągania cytatów i nazwisk z głosów."""
    custom_entries = []
    for sub in submissions:
        for ans in sub.get("answers", []):
            if ans.get("custom_text"):
                custom_entries.append(ans["custom_text"])
    
    if custom_entries:
        story.append(Paragraph("Wpisane dane dodatkowe (Nauczyciele/Cytaty):", styles["heading"]))
        for entry in custom_entries:
            story.append(Paragraph(f"• {entry}", styles["italic"]))
        story.append(Spacer(1, 4 * mm))

def aggregate_results(results_list):
    if not results_list: return []
    q_count = len(results_list[0]["question_stats"])
    aggregated = []
    for q_idx in range(q_count):
        q_text = results_list[0]["question_stats"][q_idx]["question_text"]
        total_sub = sum(item["summary"]["submissions_count"] for item in results_list)
        combined_opts = []
        for opt_idx in range(len(results_list[0]["question_stats"][q_idx]["options"])):
            opt_text = results_list[0]["question_stats"][q_idx]["options"][opt_idx]["option_text"]
            votes = sum(item["question_stats"][q_idx]["options"][opt_idx]["votes"] for item in results_list)
            percentage = (votes / total_sub * 100) if total_sub > 0 else 0.0
            combined_opts.append({"option_text": opt_text, "votes": votes, "percentage": round(percentage, 2)})
        aggregated.append({"question_text": q_text, "options": combined_opts})
    return aggregated

def build_session_report_pdf(results_data):
    styles = build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"Raport {results_data['session']['code']}")
    story = []

    session = results_data["session"]
    story.append(Paragraph("Raport sesji głosowania", styles["title"]))
    story.append(Paragraph(f"Sesja: {session['code']} | Klasa: {session['class_name']}", styles["subtitle"]))
    
    story.append(Paragraph("Informacje podstawowe", styles["heading"]))
    story.append(build_info_table([
        ["Kod sesji", session["code"]], ["Klasa", session["class_name"]],
        ["Data rozpoczęcia", session["start_ts"] or "-"], ["Data zakończenia", session["end_ts"] or "-"],
        ["Liczba głosów", str(results_data["summary"]["submissions_count"])]
    ]))

    # DODANO: Sekcja z cytatami/nauczycielami dla tej sesji
    add_custom_texts_section(story, styles, results_data.get("submissions", []))

    story.append(Paragraph("Zestawienie odpowiedzi", styles["heading"]))
    for q_stat in results_data["question_stats"]:
        story.append(Paragraph(f"<b>Pytanie:</b> {q_stat['question_text']}", styles["body"]))
        story.append(build_question_table(q_stat, False))
        story.append(Spacer(1, 4 * mm))

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)
    return buffer

def build_summary_report_pdf(results_list):
    styles = build_styles()
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Raport zbiorczy")
    story = []

    story.append(Paragraph("Raport zbiorczy sesji głosowania", styles["title"]))
    story.append(Spacer(1, 6 * mm))

    # Lista sesji z ich cytatami
    for idx, result in enumerate(results_list, start=1):
        if idx > 1: story.append(PageBreak())
        session = result["session"]
        story.append(Paragraph(f"Sesja {session['code']} - {session['class_name']}", styles["heading"]))
        
        # Wyświetlanie cytatów dla każdej sesji z osobna
        add_custom_texts_section(story, styles, result.get("submissions", []))

        for q_stat in result["question_stats"]:
            story.append(Paragraph(f"Q: {q_stat['question_text']}", styles["body"]))
            story.append(build_question_table(q_stat, False))
            story.append(Spacer(1, 3 * mm))

    # Podsumowanie końcowe (zagregowane)
    story.append(PageBreak())
    story.append(Paragraph("PODSUMOWANIE KOŃCOWE (Wszystkie sesje)", styles["title"]))
    
    # DODANO: Wszystkie cytaty ze wszystkich sesji na końcu raportu zbiorczego
    all_submissions = []
    for r in results_list: all_submissions.extend(r.get("submissions", []))
    story.append(Paragraph("Wszystkie wpisane nazwiska i cytaty z całego okresu:", styles["heading"]))
    add_custom_texts_section(story, styles, all_submissions)

    aggregated = aggregate_results(results_list)
    for q_stat in aggregated:
        story.append(Paragraph(f"<b>Pytanie:</b> {q_stat['question_text']}", styles["body"]))
        story.append(build_question_table(q_stat, True))
        story.append(Spacer(1, 4 * mm))

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    buffer.seek(0)
    return buffer