with open('index.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Reemplaza \n literales por saltos de línea reales
fixed = content.replace('\\n', '\n')
fixed = fixed.replace('\\t', '\t')
fixed = fixed.replace('\\"', '"')
fixed = fixed.replace("\\'", "'")

with open('index.py', 'w', encoding='utf-8') as f:
    f.write(fixed)

print(f'Listo! Líneas: {fixed.count(chr(10))}')