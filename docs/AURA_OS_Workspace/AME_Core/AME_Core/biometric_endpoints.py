"""
Módulo de endpoints biométricos (Zero Trust) para AURA.
Se integra con servidor_ame.py mediante register_biometric_routes(app).
"""
import os
import sys

# Detectar si el módulo biometric_auth está disponible
try:
    SHADOW_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        '..', 'Shadow-Core'
    )
    if SHADOW_DIR not in sys.path:
        sys.path.insert(0, SHADOW_DIR)
    from biometric_auth import generate_token, TOKEN_EXPIRATION_MINUTES
    BIOMETRIC_AVAILABLE = True
except ImportError:
    BIOMETRIC_AVAILABLE = False
    TOKEN_EXPIRATION_MINUTES = 60


# Almacén temporal de tokens biométricos pre-registrados
BIOMETRIC_REGISTRY = {}


def register_biometric_routes(app):
    """
    Registra los 3 endpoints del módulo biométrico en una app Flask existente.
    Llamar desde servidor_ame.py: register_biometric_routes(app)
    """
    from flask import jsonify, request

    if not BIOMETRIC_AVAILABLE:
        @app.route('/api/biometric/status', methods=['GET'])
        def _biometric_status_unavail():
            return jsonify({
                "status": "unavailable",
                "message": "Módulo biométrico no disponible (Shadow-Core/biometric_auth.py no encontrado)"
            }), 503
        return

    @app.route('/api/biometric/register', methods=['POST'])
    def api_biometric_register():
        """
        Registra una prueba biométrica para un user_id.
        Body: { "user_id": "user_001", "biometric_proof": "abc123hash" }
        """
        data = request.get_json(force=True) or {}
        user_id = str(data.get("user_id", "")).strip()
        proof = str(data.get("biometric_proof", "")).strip()

        if not user_id or not proof:
            return jsonify({
                "status": "error",
                "message": "user_id y biometric_proof requeridos"
            }), 400

        BIOMETRIC_REGISTRY[proof] = user_id
        token = generate_token(user_id)

        return jsonify({
            "status": "ok",
            "message": "Biometría registrada correctamente",
            "user_id": user_id,
            "token": token,
            "expires_in": TOKEN_EXPIRATION_MINUTES
        })

    @app.route('/api/biometric/verify', methods=['POST'])
    def api_biometric_verify():
        """
        Verifica autenticación biométrica y emite token JWT.
        Body: { "user_id": "user_001", "biometric_proof": "abc123hash" }
        """
        data = request.get_json(force=True) or {}
        user_id = str(data.get("user_id", "")).strip()
        proof = str(data.get("biometric_proof", "")).strip()

        if not user_id or not proof:
            return jsonify({
                "status": "error",
                "message": "user_id y biometric_proof requeridos"
            }), 400

        if proof not in BIOMETRIC_REGISTRY or BIOMETRIC_REGISTRY[proof] != user_id:
            return jsonify({
                "status": "error",
                "message": "Autenticación biométrica fallida"
            }), 401

        token = generate_token(user_id)
        return jsonify({
            "status": "ok",
            "message": "Autenticación biométrica exitosa",
            "user_id": user_id,
            "token": token,
            "expires_in": TOKEN_EXPIRATION_MINUTES
        })

    @app.route('/api/biometric/status', methods=['GET'])
    def api_biometric_status():
        """
        Estado del módulo biométrico.
        """
        return jsonify({
            "status": "active" if BIOMETRIC_AVAILABLE else "unavailable",
            "registered_users": len(BIOMETRIC_REGISTRY),
            "token_expiration_minutes": TOKEN_EXPIRATION_MINUTES,
            "endpoints": {
                "register": "/api/biometric/register",
                "verify": "/api/biometric/verify",
                "status": "/api/biometric/status"
            }
        })
