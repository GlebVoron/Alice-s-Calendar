from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime
import uuid
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


# Инициализация БД
def init_db():
    conn = sqlite3.connect('alice_events.db')
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS events
                 (id TEXT PRIMARY KEY,
                  user_id TEXT,
                  name TEXT,
                  date TEXT,
                  time TEXT,
                  created_at TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (id TEXT PRIMARY KEY,
                  event_id TEXT,
                  remind_before INTEGER,
                  is_active INTEGER,
                  FOREIGN KEY(event_id) REFERENCES events(id))''')

    conn.commit()
    conn.close()


init_db()


@app.route('/post', methods=['POST'])
def main():
    try:
        # Логируем входящий запрос
        logging.info(f'Incoming request: {request.json}')

        # Проверяем, что запрос содержит JSON
        if not request.json:
            logging.error('Empty request received')
            return jsonify({
                "response": {
                    "text": "Произошла ошибка. Пустой запрос.",
                    "end_session": False
                },
                "version": "1.0"
            }), 400

        # Создаем базовую структуру ответа
        response = {
            "version": request.json.get("version", "1.0"),
            "session": request.json["session"],
            "response": {
                "end_session": False
            }
        }

        # Обрабатываем запрос
        handle_dialog(request.json, response)

        # Логируем исходящий ответ
        logging.info(f'Outgoing response: {response}')

        return jsonify(response)

    except Exception as e:
        logging.error(f'Error processing request: {str(e)}')
        return jsonify({
            "response": {
                "text": "Произошла внутренняя ошибка.",
                "end_session": False
            },
            "version": "1.0"
        }), 500


def handle_dialog(req, res):
    user_id = req['session']['user_id']

    if req['session']['new']:
        # Приветствие для нового пользователя
        res['response']['text'] = (
            "Привет! Я помогу вам управлять событиями и напоминаниями. "
            "Вы можете сказать: 'добавить событие', 'список событий' или 'помощь'."
        )
        res['response']['buttons'] = [
            {"title": "Добавить событие", "hide": True},
            {"title": "Список событий", "hide": True},
            {"title": "Помощь", "hide": True}
        ]
    else:
        # Обработка команд
        command = req['request']['original_utterance'].lower()

        if 'помощь' in command:
            res['response']['text'] = (
                "Я умею:\n"
                "- Добавлять события: 'Добавь событие встреча 25 декабря в 18:00'\n"
                "- Показывать список событий: 'Список событий'\n"
                "- Удалять события: 'Удали событие встреча'\n"
                "- Добавлять напоминания: 'Напомни за 30 минут до встреча'"
            )
        elif 'привет' in command:
            res['response']['text'] = "Снова здравствуйте! Чем могу помочь?"
        else:
            res['response']['text'] = "Я не поняла вашу команду. Скажите 'помощь' для списка доступных команд."

        res['response']['buttons'] = [
            {"title": "Помощь", "hide": True},
            {"title": "Список событий", "hide": True}]


def get_main_suggests():
    suggests = [
        {'title': 'Добавь событие', 'hide': True},
        {'title': 'Удали событие', 'hide': True},
        {'title': 'Список событий', 'hide': True},
        {'title': 'Помощь', 'hide': True}
    ]
    return suggests


def add_event(user_id, command):
    try:
        parts = command.split()
        if len(parts) < 6:
            return "Недостаточно данных. Формат: Добавь событие [название] [дата] в [время]"

        # Извлекаем название события (между "добавь событие" и датой)
        event_name_start = parts.index('событие') + 1
        event_name_end = -3  # последние 3 части - это дата, "в" и время
        event_name = ' '.join(parts[event_name_start:event_name_end])

        date_str = parts[-3]
        time_str = parts[-1]

        event_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()

        conn = sqlite3.connect('alice_events.db')
        c = conn.cursor()
        c.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
                  (event_id, user_id, event_name, date_str, time_str, created_at))
        conn.commit()
        conn.close()

        return f'Событие "{event_name}" на {date_str} в {time_str} добавлено.'
    except Exception as e:
        logging.error(f"Error adding event: {e}")
        return "Не удалось добавить событие. Проверьте формат команды."


def delete_event(user_id, command):
    try:
        event_name = command.replace('удали событие', '').strip()
        if not event_name:
            return "Укажите название события для удаления."

        conn = sqlite3.connect('alice_events.db')
        c = conn.cursor()
        c.execute("DELETE FROM events WHERE user_id = ? AND name = ?",
                  (user_id, event_name))
        deleted_rows = c.rowcount
        conn.commit()

        # Удаляем связанные напоминания
        if deleted_rows > 0:
            c.execute("DELETE FROM reminders WHERE event_id IN "
                      "(SELECT id FROM events WHERE user_id = ? AND name = ?)",
                      (user_id, event_name))
            conn.commit()

        conn.close()

        if deleted_rows > 0:
            return f'Событие "{event_name}" и связанные напоминания удалены.'
        else:
            return f'Событие "{event_name}" не найдено.'
    except Exception as e:
        logging.error(f"Error deleting event: {e}")
        return "Не удалось удалить событие."


def list_events(user_id):
    try:
        conn = sqlite3.connect('alice_events.db')
        c = conn.cursor()
        c.execute('''SELECT e.name, e.date, e.time, 
                     GROUP_CONCAT(r.remind_before, ', ') 
                     FROM events e
                     LEFT JOIN reminders r ON e.id = r.event_id
                     WHERE e.user_id = ?
                     GROUP BY e.id
                     ORDER BY e.date, e.time''',
                  (user_id,))
        events = c.fetchall()
        conn.close()

        if not events:
            return 'У вас нет запланированных событий.'

        events_text = []
        for name, date, time, reminders in events:
            event_info = f"{name} - {date} в {time}"
            if reminders:
                event_info += f" (напоминания за {reminders} минут)"
            events_text.append(event_info)

        return 'Ваши события:\n' + '\n'.join(events_text)
    except Exception as e:
        logging.error(f"Error listing events: {e}")
        return "Не удалось получить список событий."


def add_reminder(user_id, command):
    try:
        parts = command.split()
        if len(parts) < 5 or parts[1] != 'за' or parts[3] != 'до':
            return "Неверный формат. Пример: Напомни за 30 минут до встреча с друзьями"

        minutes = int(parts[2])
        event_name = ' '.join(parts[4:])

        conn = sqlite3.connect('alice_events.db')
        c = conn.cursor()

        c.execute("SELECT id FROM events WHERE user_id = ? AND name = ?",
                  (user_id, event_name))
        event = c.fetchone()

        if not event:
            conn.close()
            return f'Событие "{event_name}" не найдено.'

        event_id = event[0]
        reminder_id = str(uuid.uuid4())

        c.execute("INSERT INTO reminders VALUES (?, ?, ?, ?)",
                  (reminder_id, event_id, minutes, 1))
        conn.commit()
        conn.close()

        return f'Напоминание за {minutes} минут до "{event_name}" установлено.'
    except Exception as e:
        logging.error(f"Error adding reminder: {e}")
        return "Не удалось установить напоминание. Проверьте формат команды."


if __name__ == '__main__':
    app.run()