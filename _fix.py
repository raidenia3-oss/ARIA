import os
path = r'C:\Users\User\Downloads\AURA\AURA_APP\backend\atria_integration\__init__.py'
lines = []
lines.append('__all__ = []')
open(path, 'w', encoding='utf-8').write(chr(10).join(lines))
print('done')
