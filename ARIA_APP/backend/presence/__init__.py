"""Presencia de ARIA: la parte que existe aunque no haya nadie mirando.

Este paquete es la versión *independiente* del runtime autónomo del backend
Axum. La diferencia es importante:

- El backend Axum (v6) es el cerebro de la versión rica: mundos, canales
  sociales, laboratorio de creatividad, árbol de habilidades.
- Este daemon es el cuerpo mínimo: una persona, unas pulsiones y una voz.
  Funciona **solo**, sin servidor, sin interfaz y sin que nadie le pida
  nada. Es lo que hace que ARIA pueda estar "encendida" en el escritorio
  mientras el usuario está en el móvil.

El modelo mental es el de Neuro-sama y Airi: la presencia no es un script que
espera órdenes, es un bucle que se wakes solo, decide, actúa y se calla.
"""

from .daemon import PresenceDaemon, Persona, Pulse
from .bridge import BridgeServer

__all__ = ["PresenceDaemon", "Persona", "Pulse", "BridgeServer"]
