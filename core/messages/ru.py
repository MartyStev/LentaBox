"""Russian texts. Keys and placeholders must match en.py (tests/test_i18n.py checks it)."""

MESSAGES = {
    "lang_usage": "Использование: /lang ru|en (сейчас: {language})",
    "lang_set": "Язык сообщений: {language}",
    "mute_added": "✅ Стоп-слово добавлено: {word}",
    "mute_exists": "ℹ️ Уже в списке: {word}",
    "mute_limit": "❌ Слишком много стоп-слов (максимум {limit})",
    "mute_invalid": "❌ Слово должно быть от {min} до {max} символов",
    "mute_removed": "✅ Стоп-слово удалено: {word}",
    "mute_not_found": "❌ Такого стоп-слова нет: {word}",
    "mute_list": (
        "🔇 Стоп-слова ({count}):\n{words}\n"
        "Пост, в тексте которого есть любое из них, не публикуется. "
        "Добавить: /mute слово · удалить: /unmute слово"
    ),
    "mute_empty": "Стоп-слов нет. Добавить: /mute слово",
    "digest_header": "📰 Дайджест · новостей: {count}",
    "digest_link": "оригинал",
    "err_unknown_setting": "Неизвестная настройка: {name}",
    "err_on_off": "Ожидается on или off",
    "err_range": "Значение должно быть от {low} до {high}",
    "err_choice": "Допустимо: {options}",
    "err_quiet_hours": "Ожидается ЧЧ:ММ-ЧЧ:ММ, например 23:00-08:00, или off",
    "err_timezone": "Неизвестный часовой пояс. Пример: Europe/Moscow, UTC",
    "alert_digest_failed": "Не удалось отправить дайджест, повторю при следующей проверке: {error}",
    "mode_show": (
        "Режим доставки: {mode}\n"
        "/mode instant - публиковать сразу · /mode digest - сводка заголовков раз в {hours} ч"
    ),
    "mode_set": "✅ Режим доставки: {mode}",
    "digest_show": "Период дайджеста: {hours} ч · в очереди: {queued}\nИзменить: /digest 6 · отправить сейчас: /digest now",
    "digest_set": "✅ Период дайджеста: {hours} ч",
    "digest_sent": "✅ Отправлено историй: {count}",
    "digest_empty": "Очередь дайджеста пуста",
    "quiet_show": "Тихие часы: {window} ({zone})\nИзменить: /quiet 23:00-08:00 · выключить: /quiet off",
    "quiet_off_show": "Тихие часы выключены. Включить: /quiet 23:00-08:00",
    "quiet_set": "✅ Тихие часы: {window} ({zone}). В это время новости копятся и уходят сводкой после окончания",
    "quiet_cleared": "✅ Тихие часы выключены",
    "tz_show": "Часовой пояс: {zone}\nИзменить: /tz Europe/Moscow",
    "tz_set": "✅ Часовой пояс: {zone}",
    "menu_text": (
        "Список доступных команд:\n"
        "/menu - показать это сообщение\n\n"
        "Каналы:\n"
        "/subs [new | tracked | текст | folder Имя] [page N] - подписки аккаунта\n"
        "/track <номера | all | folder Имя> - подключить из списка /subs\n"
        "/untrack <номера | all | folder Имя> - отключить\n"
        "/folders - папки аккаунта\n"
        "/sync [apply] - сверить подписки с отслеживаемыми\n"
        "/autosync [on|off] - автоматически следовать за подписками\n"
        "/list - отслеживаемые каналы\n"
        "/add <ссылка> - добавить канал вручную\n"
        "/remove <ссылка> - удалить канал\n\n"
        "Доставка и фильтры:\n"
        "/mode [instant|digest] - публиковать сразу или сводкой\n"
        "/digest [часы | now] - период сводки или отправить сейчас\n"
        "/quiet [ЧЧ:ММ-ЧЧ:ММ | off] - тихие часы\n"
        "/tz [Зона/Город] - часовой пояс\n"
        "/mute [слово] - стоп-слова: список или добавить\n"
        "/unmute <слово> - убрать стоп-слово\n"
        "/lang [ru|en] - язык сообщений\n\n"
        "Диагностика:\n"
        "/stats [channels] - статистика дедупа за 24ч\n"
        "/why <message_id | ссылка> - причина решения\n"
        "/threshold [cluster|fuzzy значение] - пороги дедупа\n"
        "/pending [id | page N] - публикации для проверки\n"
        "/pending resolve <id> sent|failed - закрыть резерв после проверки"
    ),
    "list_empty": "Список каналов пуст. Подключить: /subs, /add <ссылка>",
    "list_count": "{count} за 24ч",
    "list_header": "📋 Отслеживаемые каналы: {count}",
    "list_footer": "🔄 — подключён из подписок (следует за автосинхронизацией)",
    "add_usage": "Использование: /add <ссылка>",
    "add_not_channel": "❌ Не похоже на канал. Нужен @имя или ссылка https://t.me/имя",
    "add_invite": (
        "❌ Закрытые каналы по пригласительной ссылке не добавляются. "
        "Вступите в канал сами, затем подключите его через /subs и /track."
    ),
    "add_not_broadcast": "❌ Это не канал (пользователь, бот или группа): читаются только каналы",
    "add_ok": "✅ Канал добавлен: {label}",
    "add_error": "❌ Ошибка при добавлении: {error}",
    "remove_usage": "Использование: /remove <ссылка>",
    "remove_ok": "🗑 Канал удалён",
    "remove_error": "❌ Ошибка при удалении: {error}",
    "stats_channels_header": "📊 По каналам за 24ч (отправлено / пропущено):",
    "stats_no_data": "• пока нет данных",
    "stats_header": "📊 Статистика за 24ч:",
    "stats_total": "Всего решений: {count}",
    "stats_sent": "Отправлено: {count}",
    "stats_queued": "В дайджест: {count}",
    "stats_skipped": "Пропущено: {count}",
    "stats_reasons": "Причины:",
    "stats_error": "❌ Ошибка /stats: {error}",
    "why_usage": "Использование: /why <message_id | ссылка на пост>",
    "why_none": "По message_id={id} записей не найдено.",
    "why_header": "🔎 Почему для message_id={id}:",
    "why_error": "❌ Ошибка /why: {error}",
    "threshold_show": (
        "Порог кластера (косинус): {cluster} (по умолчанию {cluster_default})\n"
        "Порог fuzzy (0-100): {fuzzy} (по умолчанию {fuzzy_default})\n"
        "Изменить: /threshold cluster 0.9 · /threshold fuzzy 85 · /threshold reset"
    ),
    "threshold_reset": "Пороги сброшены к значениям из config.py",
    "threshold_usage": "Использование: /threshold cluster|fuzzy <значение> | reset",
    "threshold_save_failed": "❌ Не удалось сохранить порог",
    "pending_resolve_usage": (
        "Использование: /pending resolve <id> sent|failed\n"
        "sent - публикация есть в целевом чате, failed - её там нет (бот повторит отправку)"
    ),
    "pending_resolve_failed": "❌ Не удалось закрыть резерв, подробности в логах.",
    "pending_not_found": "Резерв не найден или уже завершён.",
    "pending_meaning_sent": "помечен отправленным, повтора не будет",
    "pending_meaning_failed": "удалён, отправка будет повторена при следующем проходе",
    "pending_resolved": "✅ Резерв #{id} {meaning}.",
    "pending_usage": "Использование: /pending [id | page N]",
    "pending_empty": "Резервов с неопределённым исходом нет.",
    "pending_header": "⏳ Публикации для проверки:",
    "pending_source": "Источник: {channel}:{message}",
    "pending_next_page": "Следующая страница: /pending page {page}",
    "pending_footer": "Сверьте публикацию с целевым чатом, затем: /pending resolve <id> sent|failed",
    "pending_list_error": "❌ Не удалось получить список резервов.",
    "truncated_mark": "\n\n… Текст сокращён.",
    "footer_channel": "Канал",
    "footer_original": "Оригинал",
    "unknown_channel": "неизвестен",
    "start_message": "🚀 Бот запущен и слушает каналы.\n/menu — список команд",
    "alert_send_unknown": "Исход отправки неизвестен (резерв #{claim_id}). Проверьте целевой чат и /pending.",
    "alert_process_error": "Ошибка обработки {channel}:{message}: {error}",
    "alert_giveup": "Сообщение {channel}:{message} пропущено после {attempts} неудачных попыток.",
    "names_more": " и ещё {extra}",
    "folder_none": "папок нет",
    "folder_not_found": "Папка «{name}» не найдена. Доступные: {known}",
    "scope_folder": "папка «{title}»",
    "scope_filter": "фильтр «{query}»",
    "scope_all": "все",
    "scope_last": "последний список /subs",
    "scope_selection": "выбор",
    "subs_nothing": "Ничего не найдено ({label}).",
    "subs_no_page": "Страницы {page} нет, всего страниц: {pages}",
    "subs_header": "📡 Подписки аккаунта ({label}): {count}, подключено {tracked}. Страница {page}/{pages}",
    "subs_next": "Дальше: /subs {query} page {page}",
    "subs_footer": "Подключить: /track 1 3 5-9 или /track all · Отключить: /untrack 2 4 · Папки: /folders",
    "track_first": "Сначала выполните /subs, чтобы увидеть номера каналов",
    "track_usage": "Использование: /track <номера | all | folder Название>",
    "untrack_usage": "Использование: /untrack <номера | all | folder Название>",
    "track_already": "Все каналы из выбора ({scope}) уже подключены.",
    "track_done": "✅ Подключено ({scope}): {count}\n{names}",
    "untrack_none": "Из выбора ({scope}) ничего не было подключено.",
    "untrack_done": (
        "🗑 Отключено ({scope}): {count}\n{names}\n"
        "Автосинхронизация их не вернёт; вернуть можно через /track."
    ),
    "folders_none": "У аккаунта нет папок чатов.",
    "folders_header": "📁 Папки аккаунта:",
    "folders_item": "• {title}: каналов {count}, не подключено {new}",
    "folders_footer": "Открыть: /subs folder Название · Подключить: /track folder Название",
    "sync_done_title": "✅ Синхронизировано",
    "sync_pending_title": "🔄 Предстоящие изменения",
    "sync_nothing": "Всё синхронизировано: новых подписок и отписок нет.",
    "sync_apply_hint": "Применить: /sync apply",
    "sync_added": "➕ Новые подписки: {count}",
    "sync_removed": "➖ Отписались: {count}",
    "autosync_on_word": "включена",
    "autosync_off_word": "выключена",
    "autosync_show": (
        "Автосинхронизация {state}. Включённая, она раз в {minutes} мин подключает новые подписки "
        "аккаунта и убирает каналы, с которых аккаунт ушёл "
        "(кроме добавленных через /add и отключённых через /untrack).\n"
        "Переключить: /autosync on | off"
    ),
    "autosync_off": "Автосинхронизация выключена.",
    "autosync_enabled_title": "Автосинхронизация включена. Сейчас",
    "autosync_report_title": "Автосинхронизация подписок",
    "command_failed": "❌ Не удалось выполнить /{name}, подробности в логах.",
    "sel_empty": "Не указаны номера",
    "sel_bad_number": "Непонятный номер: {token}",
    "sel_out_of_range": "Номер вне диапазона 1-{size}: {token}",
    "alert_silence": "Уже {hours} ч нет публикаций. Проверьте каналы, сервер эмбеддингов и /stats.",
    "alert_lock_lost": "Потеряна блокировка экземпляра, бот завершает работу.",
    "alert_stall": (
        "Канал {channel} стоит {hours} ч на сообщении {cursor}, в канале уже есть {latest}. "
        "Проверьте /pending и журнал."
    ),
    "alert_claims_expired": (
        "Закрыто резервов с неопределённым исходом: {count} "
        "(старше {hours} ч). Повтора не будет, каналы идут дальше."
    ),
}
