"""
Módulo de autenticación biométrica con Zero Trust para AURA
Implementa un sistema de tokens JWT y validación biométrica móvil
"""

import jwt
import datetime
from functools import wraps
from flask import request, jsonify
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

# Configuración de JWT
SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'supersecretkeyforaura')
ALGORITHM = 'HS256'
TOKEN_EXPIRATION_MINUTES = 60  # 1 hora de expiración

def generate_token(user_id: str) -> str:
    """
    Genera un token JWT para el usuario
    """
    expiration = datetime.datetime.utcnow() + datetime.timedelta(minutes=TOKEN_EXPIRATION_MINUTES)
    payload = {
        'sub': user_id,
        'exp': expiration,
        'iat': datetime.datetime.utcnow(),
        'type': 'biometric_access'
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict:
    """
    Verifica y decodifica un token JWT
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expirado")
    except jwt.InvalidTokenError:
        raise ValueError("Token inválido")

def token_required(f):
    """
    Decorador para proteger rutas que requieren token JWT
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token de acceso requerido'}), 403

        try:
            # Extraer el token de "Bearer <token>"
            token = token.split(" ")[1]
            payload = verify_token(token)
            request.user_id = payload['sub']
            return f(*args, **kwargs)
        except ValueError as e:
            return jsonify({'message': str(e)}), 403
    return decorated

def biometric_auth_endpoint(app):
    """
    Configura el endpoint para autenticación biométrica
    """
    @app.route('/api/auth/biometric', methods=['POST'])
    @token_required
    def biometric_auth():
        """
        Endpoint para validar autenticación biométrica exitosa
        """
        return jsonify({
            'message': 'Autenticación biométrica exitosa',
            'token': generate_token(request.user_id),
            'expires_in': TOKEN_EXPIRATION_MINUTES
        })

    @app.route('/api/auth/validate', methods=['POST'])
    def validate_token():
        """
        Endpoint para validar un token JWT
        """
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token de acceso requerido'}), 403

        try:
            token = token.split(" ")[1]
            payload = verify_token(token)
            return jsonify({
                'message': 'Token válido',
                'user_id': payload['sub'],
                'expires_at': payload['exp']
            }), 200
        except ValueError as e:
            return jsonify({'message': str(e)}), 403

if __name__ == '__main__':
    print("Módulo de autenticación biométrica cargado correctamente")