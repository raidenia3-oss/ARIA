import os
for f in ['C:\\Users\\User\\Downloads\\AURA\\backend_debug.log', 'C:\\Users\\User\\Downloads\\AURA\\backend_debug_err.log']:
    print(f'=== {f} ===')
    if os.path.exists(f):
        with open(f) as fh:
            lines = fh.readlines()
            for l in lines[-40:]:
                print(l.rstrip())
    else:
        print('NOT FOUND')