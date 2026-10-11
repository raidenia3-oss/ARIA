# test motor híbrido mínimo
from tools.aria_usb.motor.core import ModelConfig
from tools.aria_usb.motor.manager import ModelManager
from tools.aria_usb.motor.router import HybridRouter

cfg = ModelConfig()
mgr = ModelManager(cfg)
r = HybridRouter(mgr, cfg)
res = r.route({})
assert res["model"] == cfg.unified_id
assert res["mode"] == "unified"
print("OK")
