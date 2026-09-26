"""
Endpoint para el Stark Extraction Engine.
Proporciona funcionalidad para subir imágenes y guardarlas en vision_pool.
"""

from flask import request, jsonify
import os
from AME_Core.vision_pool_manager import ensure_vision_pool_exists, save_uploaded_file

def register_stark_upload_endpoint(app):
    """
    Registra el endpoint para subir imágenes al Stark Extraction Engine.
    """
    @app.route('/api/stark/upload_intel', methods=['POST'])
    def api_stark_upload_intel():
        """
        Endpoint para subir imágenes al Stark Extraction Engine.
        Acepta archivos multipart/form-data y los guarda en vision_pool.
        """
        try:
            # Verificar que el directorio vision_pool exista
            vision_pool_dir = ensure_vision_pool_exists()

            # Verificar que se haya subido un archivo
            if 'file' not in request.files:
                return jsonify({
                    "status": "error",
                    "message": "No se proporcionó ningún archivo."
                }), 400

            file = request.files['file']

            # Verificar que el archivo no esté vacío
            if file.filename == '':
                return jsonify({
                    "status": "error",
                    "message": "El archivo está vacío."
                }), 400

            # Verificar que el archivo sea una imagen
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
            extension = file.filename.split('.')[-1].lower()
            if extension not in allowed_extensions:
                return jsonify({
                    "status": "error",
                    "message": f"Extensión no permitida. Usa: {', '.join(allowed_extensions)}."
                }), 400

            # Guardar el archivo en vision_pool
            unique_filename = save_uploaded_file(file, vision_pool_dir)
            if not unique_filename:
                return jsonify({
                    "status": "error",
                    "message": "Error guardando el archivo."
                }), 500

            # Retornar éxito
            return jsonify({
                "status": "ok",
                "message": "Imagen recibida y guardada correctamente.",
                "filename": unique_filename,
                "path": str(vision_pool_dir / unique_filename),
                "ready_for_analysis": True
            })

        except Exception as e:
            return jsonify({
                "status": "error",
                "message": f"Error procesando la imagen: {str(e)}"
            }), 500