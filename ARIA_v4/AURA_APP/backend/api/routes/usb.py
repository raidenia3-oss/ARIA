"""USB Route"""

from typing import Dict


async def usb_status_route() -> Dict:
    from AURA_APP.backend.expansion.usb_intelligence import USBIntelligence

    usb = USBIntelligence()
    return await usb.get_usb_status()


async def usb_expand_route() -> Dict:
    from AURA_APP.backend.expansion.usb_intelligence import USBIntelligence

    usb = USBIntelligence()
    return await usb.expand_aria_with_usb()
