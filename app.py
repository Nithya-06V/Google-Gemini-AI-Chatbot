import hmac
import logging
import os
import secrets
import sqlite3
from urllib.parse import quote

from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from services.gemini_service import GeminiServiceError, generate_chat_response

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def get_db_connection():
    connection = sqlite3.connect(Config.DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def init_db():
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    connection = get_db_connection()
    connection.executescript(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
        '''
    )
    connection.commit()
    connection.close()
    ensure_default_admin_user()


def ensure_default_admin_user():
    connection = get_db_connection()
    username = Config.ADMIN_USERNAME.strip() or 'admin'
    password = Config.ADMIN_PASSWORD or 'admin123'
    existing = connection.execute(
        'SELECT id FROM users WHERE username = ?',
        (username,),
    ).fetchone()
    if existing is None:
        connection.execute(
            'INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, CURRENT_TIMESTAMP)',
            (username, generate_password_hash(password)),
        )
        connection.commit()
    connection.close()


def get_user_by_username(username):
    connection = get_db_connection()
    user = connection.execute(
        'SELECT * FROM users WHERE username = ?',
        (username,),
    ).fetchone()
    connection.close()
    return dict(user) if user else None


def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    connection = get_db_connection()
    user = connection.execute(
        'SELECT * FROM users WHERE id = ?',
        (user_id,),
    ).fetchone()
    connection.close()
    return dict(user) if user else None


def ensure_csrf_token():
    if not session.get('csrf_token'):
        session['csrf_token'] = secrets.token_urlsafe(32)
    return session['csrf_token']


def validate_csrf_if_present():
    token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
    if token is None:
        return None
    if not hmac.compare_digest(token, session.get('csrf_token', '')):
        return jsonify({'error': 'Invalid CSRF token.'}), 400
    return None


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['JSON_SORT_KEYS'] = False

    init_db()

    @app.before_request
    def ensure_session_token():
        ensure_csrf_token()

    @app.route('/')
    def index():
        if session.get('user_id'):
            return redirect(url_for('chat'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if session.get('user_id'):
            return redirect(url_for('chat'))

        if request.method == 'POST':
            username = (request.form.get('username') or '').strip()
            password = request.form.get('password') or ''

            if not username or not password:
                return render_template('login.html', error='Please enter both username and password.'), 400

            user = get_user_by_username(username)
            if user and check_password_hash(user['password_hash'], password):
                session.clear()
                session['user_id'] = user['id']
                session['username'] = user['username']
                ensure_csrf_token()
                next_url = request.args.get('next') or url_for('chat')
                return redirect(next_url)

            return render_template('login.html', error='Invalid username or password.'), 200

        return render_template('login.html')

    @app.route('/chat')
    def chat():
        if not session.get('user_id'):
            login_url = url_for('login')
            return redirect(f'{login_url}?next={quote(request.path, safe="")}')
        return render_template('chatbot.html', username=session.get('username', 'User'))

    @app.route('/settings')
    def settings():
        if not session.get('user_id'):
            login_url = url_for('login')
            return redirect(f'{login_url}?next={quote(request.path, safe="")}')
        return render_template('settings.html', username=session.get('username', 'User'))

    @app.route('/logout', methods=['POST'])
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.route('/api/conversations', methods=['GET'])
    def list_conversations():
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required.'}), 401

        connection = get_db_connection()
        rows = connection.execute(
            '''
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
            FROM conversations c
            WHERE c.user_id = ?
            ORDER BY c.updated_at DESC, c.id DESC
            ''',
            (user['id'],),
        ).fetchall()
        connection.close()

        conversations = [dict(row) for row in rows]
        return jsonify({'conversations': conversations})

    @app.route('/api/conversations', methods=['POST'])
    def create_conversation():
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required.'}), 401

        csrf_error = validate_csrf_if_present()
        if csrf_error is not None:
            return csrf_error

        payload = request.get_json(silent=True) or {}
        title = (payload.get('title') or 'New Chat').strip() or 'New Chat'

        connection = get_db_connection()
        cursor = connection.execute(
            'INSERT INTO conversations (user_id, title, created_at, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)',
            (user['id'], title[:80]),
        )
        connection.commit()
        conversation_id = cursor.lastrowid
        connection.close()

        return jsonify({'conversation_id': conversation_id, 'title': title[:80]}), 201

    @app.route('/api/conversations/<int:conversation_id>', methods=['GET'])
    def get_conversation(conversation_id):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required.'}), 401

        connection = get_db_connection()
        conversation = connection.execute(
            'SELECT * FROM conversations WHERE id = ? AND user_id = ?',
            (conversation_id, user['id']),
        ).fetchone()
        if not conversation:
            connection.close()
            return jsonify({'error': 'Conversation not found.'}), 404

        messages = connection.execute(
            'SELECT id, conversation_id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, id ASC',
            (conversation_id,),
        ).fetchall()
        connection.close()

        return jsonify({
            'conversation': dict(conversation),
            'messages': [dict(message) for message in messages],
        })

    @app.route('/api/conversations/<int:conversation_id>', methods=['PATCH'])
    def update_conversation(conversation_id):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required.'}), 401

        csrf_error = validate_csrf_if_present()
        if csrf_error is not None:
            return csrf_error

        payload = request.get_json(silent=True) or {}
        title = (payload.get('title') or '').strip()
        if not title:
            return jsonify({'error': 'A title is required.'}), 400

        connection = get_db_connection()
        row = connection.execute(
            'SELECT id FROM conversations WHERE id = ? AND user_id = ?',
            (conversation_id, user['id']),
        ).fetchone()
        if not row:
            connection.close()
            return jsonify({'error': 'Conversation not found.'}), 404

        connection.execute(
            'UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (title[:80], conversation_id),
        )
        connection.commit()
        connection.close()
        return jsonify({'success': True, 'title': title[:80]})

    @app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
    def delete_conversation(conversation_id):
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required.'}), 401

        csrf_error = validate_csrf_if_present()
        if csrf_error is not None:
            return csrf_error

        connection = get_db_connection()
        cursor = connection.execute(
            'DELETE FROM conversations WHERE id = ? AND user_id = ?',
            (conversation_id, user['id']),
        )
        connection.commit()
        connection.close()

        if cursor.rowcount == 0:
            return jsonify({'error': 'Conversation not found.'}), 404
        return jsonify({'success': True})

    @app.route('/api/chat', methods=['POST'])
    def chat_api():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({'error': 'Request body must be valid JSON.'}), 400

        if not isinstance(payload, dict):
            return jsonify({'error': 'Request body must be a JSON object.'}), 400

        user = get_current_user()
        if not user:
            return jsonify({'error': 'Authentication required.'}), 401

        csrf_error = validate_csrf_if_present()
        if csrf_error is not None:
            return csrf_error

        message = (payload.get('message') or '').strip()
        if not message:
            return jsonify({'error': 'Message cannot be empty.'}), 400
        if len(message) > app.config['MAX_MESSAGE_LENGTH']:
            return jsonify({'error': 'Message is too long. Please keep it under 4000 characters.'}), 400

        conversation_id = payload.get('conversation_id')
        connection = get_db_connection()
        if conversation_id is not None:
            conversation = connection.execute(
                'SELECT * FROM conversations WHERE id = ? AND user_id = ?',
                (conversation_id, user['id']),
            ).fetchone()
            if conversation is None:
                connection.close()
                return jsonify({'error': 'Conversation not found.'}), 404
        else:
            title = message[:60].strip() or 'New Chat'
            cursor = connection.execute(
                'INSERT INTO conversations (user_id, title, created_at, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)',
                (user['id'], title),
            )
            conversation_id = cursor.lastrowid
            connection.commit()

        connection.execute(
            'INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
            (conversation_id, 'user', message),
        )

        history = connection.execute(
            '''
            SELECT role, content FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 12
            ''',
            (conversation_id,),
        ).fetchall()
        connection.close()

        history_list = [
            {'role': row['role'], 'content': row['content']}
            for row in reversed(history)
        ]

        try:
            answer = generate_chat_response(history_list, message)
        except GeminiServiceError as exc:
            logger.warning('Gemini service error: %s', exc)
            return jsonify({'error': str(exc), 'conversation_id': conversation_id}), 500
        except Exception as exc:  # pragma: no cover - defensive path
            logger.exception('Unexpected model error while chatting.')
            return jsonify({'error': 'Unable to generate a response right now.', 'conversation_id': conversation_id}), 500

        insert_conn = get_db_connection()
        insert_conn.execute(
            'INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
            (conversation_id, 'assistant', answer),
        )
        insert_conn.execute(
            'UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (conversation_id,),
        )
        insert_conn.commit()
        insert_conn.close()

        return jsonify({
            'success': True,
            'response': answer,
            'conversation_id': conversation_id,
        })

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template('404.html'), 404

    return app


app = create_app()


if __name__ == '__main__':
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=5000)
