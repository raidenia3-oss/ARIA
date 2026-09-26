import ast
import sys

NEW_CODE = r'''X_REFACTOR = 1
'''

try:
    tree = ast.parse(NEW_CODE)
    print('SYNTAX_OK')
except SyntaxError as e:
    print('SYNTAX_FAIL', e)
    sys.exit(1)

compile(NEW_CODE, '<patch>', 'exec')
print('COMPILE_OK')
