import sqlite3
import os
from datetime import datetime

class JarvisDB:
    def __init__(self):
        # Resolve database path dynamically relative to this file's folder
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_dir = os.path.join(base_dir, 'db')
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, 'conversations.db')
        
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._init_db()
    
    def _init_db(self):
        # Tabla: Conversaciones
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                user_input TEXT,
                jarvis_response TEXT,
                model_used TEXT,
                offline BOOLEAN
            )
        ''')
        
        # Tabla: Cache de respuestas
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                question TEXT PRIMARY KEY,
                answer TEXT,
                timestamp TEXT,
                source TEXT
            )
        ''')
        
        # Tabla: Cache de páginas web raspadas
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS web_cache (
                url TEXT PRIMARY KEY,
                title TEXT,
                content TEXT,
                headers TEXT,
                timestamp TEXT
            )
        ''')
        
        self.conn.commit()
    
    def save_conversation(self, user_input, response, model, offline=True):
        self.cursor.execute('''
            INSERT INTO conversations 
            (timestamp, user_input, jarvis_response, model_used, offline)
            VALUES (?, ?, ?, ?, ?)
        ''', (datetime.now().isoformat(), user_input, response, model, offline))
        self.conn.commit()
    
    def get_cached_answer(self, question):
        self.cursor.execute(
            'SELECT answer FROM cache WHERE question = ?', 
            (question,)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    def save_to_cache(self, question, answer, source):
        self.cursor.execute('''
            INSERT OR REPLACE INTO cache 
            (question, answer, timestamp, source)
            VALUES (?, ?, ?, ?)
        ''', (question, answer, datetime.now().isoformat(), source))
        self.conn.commit()
        
    def save_web_cache(self, url, title, content, headers_json):
        self.cursor.execute('''
            INSERT OR REPLACE INTO web_cache 
            (url, title, content, headers, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (url, title, content, headers_json, datetime.now().isoformat()))
        self.conn.commit()

    def get_web_cache(self, url):
        self.cursor.execute(
            'SELECT title, content, headers, timestamp FROM web_cache WHERE url = ?', 
            (url,)
        )
        result = self.cursor.fetchone()
        if result:
            return {
                "title": result[0],
                "content": result[1],
                "headers": result[2],
                "timestamp": result[3]
            }
        return None
    
    def close(self):
        self.conn.close()
