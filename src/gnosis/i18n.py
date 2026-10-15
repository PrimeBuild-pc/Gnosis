"""Small, shared locale whitelist for bot replies and RAG output."""

LANGUAGES = {"en": "English", "it": "Italian", "es": "Spanish", "ru": "Russian", "zh": "Chinese"}

MESSAGES = {
    "en": {
        "unauthorized": "Not authorized: check the workspace, server ID and server roles.",
        "answer_error": "Answer unavailable. Check the worker status.",
        "digest_error": "Digest unavailable. Check the worker status.",
        "no_digest": "No digest available.",
        "digest_denied": "Digest unavailable with your current permissions.",
        "help": "Hello! Use /ask <question> to query the collected sources, /digest for the latest weekly digest, or /help for help.",
        "ask_usage": "Usage: /ask <question>",
        "ask_description": "Ask a question about the collected sources",
        "question_description": "Your question",
        "question_name": "question",
        "digest_description": "Latest weekly digest",
        "help_description": "Show commands and help",
        "no_sources": "I cannot find enough information in the collected sources.",
        "unverified_answer": "I cannot provide a verifiable answer using the retrieved sources.",
    },
    "it": {
        "unauthorized": "Non autorizzato: verifica workspace, ID server e ruoli del server.",
        "answer_error": "Risposta non disponibile. Controlla lo stato del worker.",
        "digest_error": "Digest non disponibile. Controlla lo stato del worker.",
        "no_digest": "Nessun digest disponibile.",
        "digest_denied": "Digest non disponibile per le tue autorizzazioni attuali.",
        "help": "Ciao! Usa /ask <domanda> per consultare le fonti raccolte, /digest per l'ultimo digest settimanale o /help per aiuto.",
        "ask_usage": "Uso: /ask <domanda>",
        "ask_description": "Chiedi qualcosa alle fonti raccolte",
        "question_description": "La tua domanda",
        "question_name": "domanda",
        "digest_description": "Ultimo digest settimanale",
        "help_description": "Mostra comandi e aiuto",
        "no_sources": "Non trovo informazioni sufficienti nelle fonti raccolte.",
        "unverified_answer": "Non posso formulare una risposta verificabile con le fonti recuperate.",
    },
    "es": {
        "unauthorized": "No autorizado: comprueba el espacio de trabajo, el ID del servidor y sus roles.",
        "answer_error": "Respuesta no disponible. Comprueba el estado del worker.",
        "digest_error": "Resumen no disponible. Comprueba el estado del worker.",
        "no_digest": "No hay ningún resumen disponible.",
        "digest_denied": "El resumen no está disponible con tus permisos actuales.",
        "help": "¡Hola! Usa /ask <pregunta> para consultar las fuentes recopiladas, /digest para el último resumen semanal o /help para obtener ayuda.",
        "ask_usage": "Uso: /ask <pregunta>",
        "ask_description": "Haz una pregunta sobre las fuentes recopiladas",
        "question_description": "Tu pregunta",
        "question_name": "pregunta",
        "digest_description": "Último resumen semanal",
        "help_description": "Mostrar comandos y ayuda",
        "no_sources": "No encuentro información suficiente en las fuentes recopiladas.",
        "unverified_answer": "No puedo dar una respuesta verificable con las fuentes recuperadas.",
    },
    "ru": {
        "unauthorized": "Нет доступа: проверьте рабочее пространство, ID сервера и роли сервера.",
        "answer_error": "Ответ недоступен. Проверьте состояние worker.",
        "digest_error": "Дайджест недоступен. Проверьте состояние worker.",
        "no_digest": "Нет доступных дайджестов.",
        "digest_denied": "Дайджест недоступен с вашими текущими правами.",
        "help": "Привет! Используйте /ask <вопрос> для поиска по собранным источникам, /digest для последнего еженедельного дайджеста или /help для справки.",
        "ask_usage": "Использование: /ask <вопрос>",
        "ask_description": "Задать вопрос по собранным источникам",
        "question_description": "Ваш вопрос",
        "question_name": "вопрос",
        "digest_description": "Последний еженедельный дайджест",
        "help_description": "Показать команды и справку",
        "no_sources": "В собранных источниках недостаточно информации.",
        "unverified_answer": "Не могу дать проверяемый ответ на основе найденных источников.",
    },
    "zh": {
        "unauthorized": "未获授权：请检查工作区、服务器 ID 和服务器角色。",
        "answer_error": "暂时无法回答。请检查 worker 状态。",
        "digest_error": "摘要暂不可用。请检查 worker 状态。",
        "no_digest": "暂无可用摘要。",
        "digest_denied": "您当前的权限无法查看此摘要。",
        "help": "你好！使用 /ask <问题> 查询已收集的来源，使用 /digest 查看最新每周摘要，或使用 /help 获取帮助。",
        "ask_usage": "用法：/ask <问题>",
        "ask_description": "针对已收集的来源提问",
        "question_description": "你的问题",
        "question_name": "问题",
        "digest_description": "最新每周摘要",
        "help_description": "显示命令和帮助",
        "no_sources": "在已收集的来源中找不到足够的信息。",
        "unverified_answer": "无法根据检索到的来源提供可验证的回答。",
    },
}


def normalize_locale(value: str | None) -> str:
    language = value.lower().replace("_", "-").split("-", 1)[0] if isinstance(value, str) else "en"
    return language if language in LANGUAGES else "en"


def message(key: str, locale: str = "en") -> str:
    return MESSAGES[normalize_locale(locale)][key]
