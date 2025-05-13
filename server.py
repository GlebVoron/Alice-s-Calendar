from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime
import uuid

app = Flask(__name__)


# Инициализация БД
def init_db():
    conn = sqlite3.connect('alice_events.db')
    c = conn.cursor()

    # Таблица событий
    c.execute('''CREATE TABLE IF NOT EXISTS events
                 (id TEXT PRIMARY KEY,
                  user_id TEXT,
                  name TEXT,
                  date TEXT,
                  time TEXT,
                  created_at TEXT)''')

    # Таблица напоминаний
    c.execute('''CREATE TABLE IF NOT EXISTS reminders
                 (id TEXT PRIMARY KEY,
                  event_id TEXT,
                  remind_before INTEGER,
                  is_active INTEGER,
                  FOREIGN KEY(event_id) REFERENCES events(id))''')

    conn.commit()
    conn.close()


init_db()


@app.route('/', methods=['POST'])
def handle_alice():
    data = request.json
    request_type = data.get('request', {}).get('type')
    user_id = data.get('session', {}).get('user_id')

    if request_type == 'SimpleUtterance':
        command = data.get('request', {}).get('command', '').lower()
        response = process_command(user_id, command)
    else:
        response = {
            'text': 'Я могу помочь вам управлять событиями и напоминаниями. Что вы хотите сделать?',
            'end_session': False
        }

    return jsonify({
        'version': data.get('version'),
        'session': data.get('session'),
        'response': response
    })


def process_command(user_id, command):
    if 'добавь событие' in command:
        return add_event(user_id, command)
    elif 'удали событие' in command:
        return delete_event(user_id, command)
    elif 'список событий' in command:
        return list_events(user_id)
    elif 'напомни' in command:
        return add_reminder(user_id, command)
    else:
        return {
            'text': 'Я не поняла команду. Вы можете добавить, удалить или посмотреть список событий.',
            'end_session': False
        }


def add_event(user_id, command):
    try:
        # Парсинг команды типа "добавь событие встреча с друзьями 25 декабря в 18:00"
        parts = command.split()
        event_name = ' '.join(parts[2:-3])
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

        return {
            'text': f'Событие "{event_name}" на {date_str} в {time_str} добавлено.',
            'end_session': False
        }
    except Exception as e:
        return {
            'text': 'Не удалось добавить событие. Пожалуйста, повторите в формате: "Добавь событие название дата время"',
            'end_session': False
        }


def delete_event(user_id, command):
    try:
        event_name = command.replace('удали событие', '').strip()

        conn = sqlite3.connect('alice_events.db')
        c = conn.cursor()
        c.execute("DELETE FROM events WHERE user_id = ? AND name = ?",
                  (user_id, event_name))
        deleted_rows = c.rowcount
        conn.commit()
        conn.close()

        if deleted_rows > 0:
            return {
                'text': f'Событие "{event_name}" удалено.',
                'end_session': False
            }
        else:
            return {
                'text': f'Событие "{event_name}" не найдено.',
                'end_session': False
            }
    except Exception as e:
        return {
            'text': 'Не удалось удалить событие.',
            'end_session': False
        }


def list_events(user_id):
    try:
        conn = sqlite3.connect('alice_events.db')
        c = conn.cursor()
        c.execute("SELECT name, date, time FROM events WHERE user_id = ? ORDER BY date, time",
                  (user_id,))
        events = c.fetchall()
        conn.close()

        if not events:
            return {
                'text': 'У вас нет запланированных событий.',
                'end_session': False
            }

        events_text = '\n'.join([f"{name} - {date} в {time}" for name, date, time in events])
        return {
            'text': f'Ваши события:\n{events_text}',
            'end_session': False
        }
    except Exception as e:
        return {
            'text': 'Не удалось получить список событий.',
            'end_session': False
        }


def add_reminder(user_id, command):
    try:
        # Парсинг команды типа "напомни за 30 минут до встреча с друзьями"
        parts = command.split()
        minutes = int(parts[1])
        event_name = ' '.join(parts[4:])

        conn = sqlite3.connect('alice_events.db')
        c = conn.cursor()

        # Находим событие
        c.execute("SELECT id FROM events WHERE user_id = ? AND name = ?",
                  (user_id, event_name))
        event = c.fetchone()

        if not event:
            return {
                'text': f'Событие "{event_name}" не найдено.',
                'end_session': False
            }

        event_id = event[0]
        reminder_id = str(uuid.uuid4())

        c.execute("INSERT INTO reminders VALUES (?, ?, ?, ?)",
                  (reminder_id, event_id, minutes, 1))
        conn.commit()
        conn.close()

        return {
            'text': f'Напоминание за {minutes} минут до "{event_name}" установлено.',
            'end_session': False
        }
    except Exception as e:
        return {
            'text': 'Не удалось установить напоминание. Пожалуйста, повторите в формате: "Напомни за X минут до название события"',
            'end_session': False
        }


if __name__ == '__main__':
    app.run(port=5000)