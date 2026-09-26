import json
import sys
import os
from PIL import Image
from PIL.ExifTags import TAGS

def extract_metadata(image_path):
    """Extrae metadatos EXIF de una imagen de forma ligera."""
    try:
        image = Image.open(image_path)
        info = image._getexif()
        
        if not info:
            return {"error": "No se encontraron metadatos EXIF."}

        metadata = {}
        for tag, value in info.items():
            tag_name = TAGS.get(tag, tag)
            # Convertir bytes a string para que sea serializable en JSON
            if isinstance(value, bytes):
                try:
                    value = value.decode('utf-8', 'ignore')
                except:
                    value = str(value)
            metadata[tag_name] = value
            
        return metadata
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Falta la ruta de la imagen"}))
        sys.exit(1)

    img_path = sys.argv[1]
    result = extract_metadata(img_path)
    
    # Guardar en JSON optimizado
    output_file = f"meta_{os.path.basename(img_path)}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=None, separators=(',', ':'))
    
    print(json.dumps({"status": "success", "file": output_file}))