"""
webauthn_endpoints.py — Endpoints WebAuthn para autenticación biométrica PWA.
Reemplaza la dependencia de Capacitor nativo por WebAuthn API del navegador.
Soporta: huella dactilar, FaceID, Windows Hello, PIN de seguridad.
"""

import os, json, time, base64, hashlib, secrets
from flask import jsonify, request

# Almacén en memoria de credenciales y desafíos
_credentials = {}  # username -> [{id, publicKey, counter}]
_challenges = {}  # challenge -> {username, expires}


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _random_bytes(n=32):
    return secrets.token_bytes(n)


def register_webauthn_routes(app):
    @app.route("/api/auth/webauthn/begin-register", methods=["POST"])
    def begin_register():
        data = request.get_json(force=True) or {}
        username = data.get("username", "architect")
        challenge = _random_bytes(32)
        user_id = hashlib.sha256(username.encode()).digest()
        chal_str = _b64(challenge)
        _challenges[chal_str] = {"username": username, "expires": time.time() + 120}
        options = {
            "challenge": chal_str,
            "rp": {"name": "AURA", "id": request.host.split(":")[0]},
            "user": {"id": _b64(user_id), "name": username, "displayName": "Arquitecto AURA"},
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},
                {"type": "public-key", "alg": -257},
            ],
            "timeout": 60000,
            "attestation": "none",
            "excludeCredentials": [
                {"id": _b64(hashlib.sha256(json.dumps(c).encode()).digest()), "type": "public-key"}
                for c in _credentials.get(username, [])
            ],
        }
        return jsonify(options)

    @app.route("/api/auth/webauthn/register", methods=["POST"])
    def finish_register():
        data = request.get_json(force=True)
        if not data or "id" not in data:
            return jsonify({"error": "Credencial inválida"}), 400
        # Extraer clave pública del attestationObject
        try:
            att = base64.urlsafe_b64decode(data["response"]["attestationObject"])
            # Parse simplificado: extraer clave pública COSE
            # En producción usar cbor2 o py_webauthn
            cred_id = data["id"]
            public_key = data["rawId"]  # simplificado
            username = "architect"
            if username not in _credentials:
                _credentials[username] = []
            _credentials[username].append(
                {"id": cred_id, "publicKey": public_key, "counter": 0, "created": time.time()}
            )
            return jsonify({"status": "ok", "credentialId": cred_id})
        except Exception as e:
            return jsonify({"error": f"Error procesando credencial: {str(e)}"}), 400

    @app.route("/api/auth/webauthn/begin-verify", methods=["POST"])
    def begin_verify():
        data = request.get_json(force=True) or {}
        username = data.get("username", "architect")
        challenge = _random_bytes(32)
        chal_str = _b64(challenge)
        _challenges[chal_str] = {"username": username, "expires": time.time() + 120}
        creds = _credentials.get(username, [])
        options = {
            "challenge": chal_str,
            "timeout": 60000,
            "rpId": request.host.split(":")[0],
            "allowCredentials": (
                [
                    {
                        "id": _b64(hashlib.sha256(json.dumps(c).encode()).digest()),
                        "type": "public-key",
                    }
                    for c in creds
                ]
                if creds
                else []
            ),
            "userVerification": "preferred",
        }
        return jsonify(options)

    @app.route("/api/auth/webauthn/verify", methods=["POST"])
    def finish_verify():
        data = request.get_json(force=True)
        if not data or "id" not in data:
            return jsonify({"error": "Assertion inválida"}), 400
        # En producción verificar firma con py_webauthn
        # Por ahora generamos token JWT
        from Shadow_Core.biometric_auth import generate_token

        token = generate_token("architect")
        return jsonify({"status": "ok", "token": token, "expiresIn": 3600})

    @app.route("/api/auth/login", methods=["POST"])
    def pin_login():
        data = request.get_json(force=True) or {}
        pin = data.get("pin", "")
        if pin == "AURA2024!":
            from Shadow_Core.biometric_auth import generate_token

            token = generate_token("architect")
            return jsonify({"status": "ok", "token": token, "expiresIn": 3600})
        return jsonify({"error": "PIN incorrecto"}), 401

    @app.route("/api/auth/validate", methods=["POST"])
    def validate_token():
        token = request.headers.get("Authorization", "")
        if not token.startswith("Bearer "):
            return jsonify({"valid": False}), 403
        try:
            from Shadow_Core.biometric_auth import verify_token

            payload = verify_token(token.split(" ")[1])
            return jsonify({"valid": True, "user": payload["sub"]})
        except ValueError as e:
            return jsonify({"valid": False, "error": str(e)}), 403

    @app.route("/api/sync/session", methods=["POST"])
    def create_sync_session():
        data = request.get_json(force=True) or {}
        token = data.get("token", secrets.token_hex(32))
        expires = time.time() + data.get("expiresIn", 300)
        sessions = getattr(app, "_sync_sessions", {})
        sessions[token] = {
            "device": data.get("device", ""),
            "expires": expires,
            "created": time.time(),
        }
        app._sync_sessions = sessions
        return jsonify({"status": "ok", "token": token, "expiresIn": data.get("expiresIn", 300)})

    @app.route("/api/sync/session/<token>", methods=["GET"])
    def validate_sync_session(token):
        sessions = getattr(app, "_sync_sessions", {})
        session = sessions.get(token)
        if not session or time.time() > session["expires"]:
            return jsonify({"valid": False}), 404
        return jsonify({"valid": True, "device": session["device"]})

    print("✅ WebAuthn + Sync endpoints registrados")
    return app
