import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.integrations.ame_sync_manager import AMESyncManager, get_ame_sync
from backend.api.ame_sync_routes import router as ame_router
from mobile_client.ame_sync_receiver import AMESyncReceiver, get_ame_receiver
from backend.daemon.aura_daemon import get_daemon
print('All AME sync imports OK')
d = get_daemon()
print('Daemon has ame_sync:', hasattr(d, 'ame_sync'), 'type:', type(d.ame_sync).__name__)
print('Daemon has _run_ame_sync_agent:', hasattr(d, '_run_ame_sync_agent'))
print('AME routes prefix:', ame_router.prefix)