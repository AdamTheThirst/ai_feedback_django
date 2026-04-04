"""Сервис формирования PDF-файла по сохранённым результатам диалога."""

from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from apps.dialogs.services.results import DialogResultsViewModel


class PdfExportError(Exception):
    """Сигнализирует о неуспешной сборке PDF-документа.

    Контекст использования:
        Применяется во view-слое, чтобы показать пользователю дружелюбную ошибку
        и отдельно зафиксировать технический инцидент в аудит-логе.

    Параметры:
        Получает стандартные параметры ``Exception``.

    Возвращаемое значение:
        Экземпляр исключения.

    Исключения и особые случаи:
        Используется как обёртка над внутренними ошибками генерации PDF.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """


def _register_pdf_font() -> str:
    """Регистрирует шрифт с поддержкой кириллицы для отчёта.

    Контекст использования:
        Вызывается при формировании PDF, чтобы русские тексты из результатов,
        карточек и транскрипта корректно отображались в документе.

    Параметры:
        Параметры отсутствуют.

    Возвращаемое значение:
        Имя зарегистрированного шрифта для использования в стилях ReportLab.

    Исключения и особые случаи:
        Если Arial не найден, используется ближайший доступный fallback с
        кириллицей (например, DejaVuSans), чтобы текст PDF оставался читаемым.

    Побочные эффекты:
        Регистрирует шрифт в глобальном реестре ``reportlab.pdfbase.pdfmetrics``.
    """

    candidate_paths = [
        Path("/usr/share/fonts/truetype/msttcorefonts/Arial.ttf"),
        Path("/usr/share/fonts/truetype/msttcorefonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/microsoft/Arial.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    ]
    candidate_names = {
        "arial.ttf": "Arial",
        "Arial.ttf": "Arial",
        "DejaVuSans.ttf": "DejaVuSans",
    }

    for path in candidate_paths:
        if path.exists():
            font_name = candidate_names.get(path.name, "CustomRuFont")
            if font_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_name, str(path)))
            return font_name
    return "Helvetica"


def build_dialog_results_pdf(view_model: DialogResultsViewModel) -> bytes:
    """Формирует бинарный PDF-отчёт по сохранённому результату диалога.

    Контекст использования:
        Используется endpoint-ом экспорта PDF и строит документ только из данных,
        уже сохранённых в БД (без доверия к клиентским данным).

    Параметры:
        view_model: Единая модель данных результата с анализом и транскриптом.

    Возвращаемое значение:
        Байтовый поток PDF-документа для ``HttpResponse``.

    Исключения и особые случаи:
        Выбрасывает ``PdfExportError``, если генерация документа не удалась.

    Побочные эффекты:
        Создаёт PDF в памяти; запись в файловую систему не выполняется.
    """

    try:
        font_name = _register_pdf_font()
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            topMargin=12 * mm,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            bottomMargin=12 * mm,
            title=f"Результат диалога {view_model.dialog.public_id}",
        )

        styles = getSampleStyleSheet()
        base_style = ParagraphStyle(
            "BaseRu",
            parent=styles["BodyText"],
            fontName=font_name,
            fontSize=10,
            leading=14,
            spaceAfter=3,
        )
        title_style = ParagraphStyle("TitleRu", parent=styles["Heading1"], fontName=font_name, fontSize=16, leading=20)
        section_style = ParagraphStyle("SectionRu", parent=styles["Heading2"], fontName=font_name, fontSize=12, leading=16)

        flow = [
            Paragraph("Результат тренажёра обратной связи", title_style),
            Spacer(1, 4 * mm),
            Paragraph(f"Игра: {view_model.dialog.game.title}", base_style),
            Paragraph(f"Сценарий: {view_model.dialog.scenario.title}", base_style),
            Paragraph(f"Дата и время старта: {view_model.dialog.started_at.strftime('%d.%m.%Y %H:%M:%S UTC')}", base_style),
            Paragraph(f"Статус завершения: {view_model.dialog.get_status_display()}", base_style),
            Paragraph(f"Причина завершения: {view_model.dialog.get_ended_reason_display() if view_model.dialog.ended_reason else '—'}", base_style),
            Spacer(1, 3 * mm),
            Paragraph(f"Сумма баллов: {view_model.total_score} из {view_model.total_max}", section_style),
            Spacer(1, 2 * mm),
        ]

        flow.append(Paragraph("Карточки анализа", section_style))
        if view_model.analysis_results:
            for index, result in enumerate(view_model.analysis_results, start=1):
                flow.append(Paragraph(f"{index}. {result.header_snapshot_text} ({result.rating} из {result.rating_max})", base_style))
                flow.append(Paragraph(result.analysis_text.replace("\n", "<br/>"), base_style))
                if result.validation_status != "valid":
                    flow.append(Paragraph(f"Статус валидации: {result.validation_status}", base_style))
                flow.append(Spacer(1, 2 * mm))
        else:
            flow.append(Paragraph("Карточки анализа пока недоступны.", base_style))

        document.build(flow)
        return buffer.getvalue()
    except Exception as exc:  # noqa: BLE001
        raise PdfExportError("Не удалось сформировать PDF-документ результата.") from exc
