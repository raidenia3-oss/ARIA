import os
path = 'C:\\Users\\User\\Downloads\\AURA\\_cleanup3.py'
if os.path.exists(path):
    os.remove(path)
    print('Removed')
else:
    print('Already gone')
