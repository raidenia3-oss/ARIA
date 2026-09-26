# Gesture Control

This service exposes a lightweight controller that maps gesture names to AURA actions and can dispatch them to the backend AURA API.

## Example

```python
from gesture_control import GestureController

controller = GestureController()
print(controller.map_gesture('open_hand'))
```
