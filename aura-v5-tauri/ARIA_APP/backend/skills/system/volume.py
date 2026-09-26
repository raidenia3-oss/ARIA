from typing import Any, Dict


def run(params: Dict[str, Any]) -> Dict[str, Any]:
    volume = params.get("volume")
    muted = params.get("muted")
    try:
        from comtypes import CLSCTX_ALL  # type: ignore
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore

        device = AudioUtilities.GetSpeakers()
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        vol = interface.QueryInterface(IAudioEndpointVolume)
        if volume is not None:
            vol.SetMasterVolumeLevelScalar(min(max(float(volume) / 100.0, 0.0), 1.0), None)
        if muted is not None:
            vol.SetMute(1 if muted else 0, None)
        current = vol.GetMasterVolumeLevelScalar()
        is_muted = vol.GetMute()
        return {"volume": f"{int(current*100)}%", "muted": bool(is_muted)}
    except Exception as e:
        return {
            "volume": "N/A",
            "muted": False,
            "error": str(e),
            "note": "pycaw requires Windows + comtypes",
        }
