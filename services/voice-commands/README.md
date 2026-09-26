# Voice Commands

This service provides a small voice-command router that translates offline voice commands into AURA backend actions.

## Example

```python
from voice_commands import VoiceCommandRouter

router = VoiceCommandRouter()
print(router.route('publicar estado'))
```
