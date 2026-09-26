"""
Módulo para manejar la base de datos SQLite de conversaciones.
"""

import sqlite3
from datetime import datetime
import os

class ChatDatabase:
    def __init__(self, db_path='chat_history.db'):
        self.db_path = db_path
        self.conn = None
        self._initialize_db()

    def _initialize_db(self):
        """Inicializa la base de datos y crea las tablas si no existen."""
        if not os.path.exists(self.db_path):
            self.conn = sqlite3.connect(self.db_path)
            cursor = self.conn.cursor()

            # Crear tabla de conversaciones
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversaciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titulo TEXT NOT NULL,
                    fecha TIMESTAMP NOT NULL
                )
            ''')

            # Crear tabla de mensajes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mensajes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversacion_id INTEGER NOT NULL,
                    rol TEXT NOT NULL,
                    contenido TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    FOREIGN KEY (conversacion_id) REFERENCES conversaciones (id)
                )
            ''')

            self.conn.commit()

    def create_conversation(self, title):
        """Crea una nueva conversación."""
        cursor = self.conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO conversaciones (titulo, fecha)
            VALUES (?, ?)
        ''', (title, timestamp))
        self.conn.commit()
        return cursor.lastrowid

    def add_message(self, conversation_id, role, content):
        """Añade un mensaje a una conversación."""
        cursor = self.conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO mensajes (conversacion_id, rol, contenido, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (conversation_id, role, content, timestamp))
        self.conn.commit()
        return cursor.lastrowid

    def get_conversations(self):
        """Obtiene la lista de todas las conversaciones."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT id, titulo, fecha FROM conversaciones
            ORDER BY fecha DESC
        ''')
        return cursor.fetchall()

    def get_messages(self, conversation_id):
        """Obtiene todos los mensajes de una conversación."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT rol, contenido, timestamp FROM mensajes
            WHERE conversacion_id = ?
            ORDER BY timestamp ASC
        ''', (conversation_id,))
        return cursor.fetchall()

    def close(self):
        """Cierra la conexión a la base de datos."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Instancia global de la base de datos
db = ChatDatabase()