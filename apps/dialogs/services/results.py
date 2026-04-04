"""Сервис подготовки view-model экрана результатов и экспорта диалога."""

from dataclasses import dataclass

from apps.analysis.models import AnalysisRun
from apps.dialogs.models import DialogSession


@dataclass(slots=True)
class DialogResultsViewModel:
    """Контейнер данных результата диалога для HTML-экрана и PDF.

    Контекст использования:
        Используется как единый источник данных для страницы результатов и PDF,
        чтобы оба представления строились на одинаковом наборе сохранённых данных.

    Параметры:
        dialog: Экземпляр диалоговой сессии пользователя.
        analysis_run: Запуск анализа или ``None``, если анализ ещё недоступен.
        analysis_results: Список сохранённых результатов по критериям.
        messages: Полный транскрипт диалога в порядке отправки.
        total_score: Итоговая сумма фактических баллов ``N``.
        total_max: Итоговая сумма максимальных баллов ``M``.

    Возвращаемое значение:
        Заполненный dataclass с данными для рендеринга UI и PDF.

    Исключения и особые случаи:
        При отсутствии ``analysis_run`` список результатов и суммы остаются пустыми/нулевыми.

    Побочные эффекты:
        Побочные эффекты отсутствуют.
    """

    dialog: DialogSession
    analysis_run: AnalysisRun | None
    analysis_results: list
    messages: list
    total_score: int
    total_max: int


def build_dialog_results_view_model(dialog: DialogSession) -> DialogResultsViewModel:
    """Собирает агрегированную модель данных для экрана результатов.

    Контекст использования:
        Вызывается из пользовательского ``dialogs``-представления и из PDF-сервиса,
        чтобы гарантировать консистентность данных между веб-страницей и документом.

    Параметры:
        dialog: Диалог, который принадлежит текущему пользователю и должен быть показан.

    Возвращаемое значение:
        Объект ``DialogResultsViewModel`` с транскриптом, анализом и суммами.

    Исключения и особые случаи:
        Если анализ ещё не создан, метод возвращает модель без карточек анализа.

    Побочные эффекты:
        Выполняет чтение связанных данных из БД (``messages`` и ``analysis``-связей).
    """

    analysis_run = getattr(dialog, "analysis_run", None)
    analysis_results = []
    total_score = 0
    total_max = 0

    if analysis_run is not None:
        analysis_results = list(analysis_run.results.order_by("sort_order_snapshot", "id"))
        total_score = sum(item.rating for item in analysis_results)
        total_max = sum(item.rating_max for item in analysis_results)

    messages = list(dialog.messages.order_by("sequence_no"))
    return DialogResultsViewModel(
        dialog=dialog,
        analysis_run=analysis_run,
        analysis_results=analysis_results,
        messages=messages,
        total_score=total_score,
        total_max=total_max,
    )
