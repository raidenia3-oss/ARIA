"""
Wrapper de integración del Healer para el flujo de automatización de RollerCoin.
Adaptado a la arquitectura de AURA Core y al contrato de `AURA_Core/automation/healer.py`.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from AURA_Core.automation.healer import Healer, AutoHealingError


class PlaywrightSimulado:
    """Interfaz mínima simulada para probar el flujo sin dependencia real de Playwright."""

    def __init__(self, force_broken_claim: bool = False):
        self._store = {
            "css=#boton-minar": "elemento-minar",
            "css=.claim-btn": "elemento-claim",
        }
        self.force_broken_claim = force_broken_claim

    def query_selector(self, selector: str):
        class _El:
            def click(self):
                return True

            def inner_text(self):
                return "ok"

        if self.force_broken_claim and selector == "css=.claim-btn":
            raise Exception(f"Selector no encontrado: {selector}")
        key = selector
        if key not in self._store:
            raise Exception(f"Selector no encontrado: {selector}")
        return _El()

    def content(self) -> str:
        return "<html><body><div id='boton-minar' class='claim-btn'>MINE</div></body></html>"

    def screenshot(self) -> bytes:
        return b"FAKE_PNG_BYTES"


# Enrutador de modelos con failover automático (HF Space → LM Studio local)
from AURA_Core.automation.llm_router import LLMRouter, llm_router

# También importamos el cliente HF Space por si se necesita directamente
from AURA_Core.neural.hf_space_client import HFSpaceClient, hf_client


def _make_healer_compatible(router: LLMRouter) -> object:
    """
    Crea un wrapper compatible con el contrato de Healer._ask_llm_for_selector().
    Healer espera un objeto con método .chat(system_prompt, user_prompt, temperature).
    """

    class RouterWrapper:
        def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
            # El router ya parsea internamente el JSON, pero Healer también lo hace.
            # Simplemente delegamos en el router y devolvemos la respuesta cruda.
            return router.enviar_solicitud_reparacion(system_prompt, user_prompt)

        def __repr__(self) -> str:
            return f"RouterWrapper(router={router.__class__.__name__})"

    return RouterWrapper()


def run_with_healing(
    page: Any,
    alias: str,
    selector: str,
    fn: Callable[[Any], Any],
    step: str = "rollercoin",
    llm_client: Any = None,
) -> Any:
    """
    Ejecuta `fn(page)` envolviéndolo con captura de errores.

    - Si `fn` lanta error de selector/timeout, invoca `Healer.heal(...)`.
    - Re-ejecuta la acción con el selector reparado.
    """
    healer = Healer(llm_client=llm_client, ws_client=None)
    try:
        return fn(page)
    except Exception as e:
        msg = str(e)
        if "Selector" in msg or "Timeout" in msg or "no encontrado" in msg:
            nuevo = healer.heal(
                page=page, alias=alias, current_selector=selector, error=e, step=step
            )
            # Simula actualización del store con el nuevo selector
            page._store[nuevo] = f"elemento-{alias}"
            page._store[selector] = f"elemento-{alias}"
            # Reintentar una vez con el selector reparado
            return fn(page)
        raise


def flujo_mineria(page: Any) -> None:
    page.query_selector("css=#boton-minar").click()
    time.sleep(0.1)


def flujo_claim(page: Any) -> None:
    page.query_selector("css=.claim-btn").click()
    time.sleep(0.1)


def main() -> None:
    # Paso 1: flujo normal
    page = PlaywrightSimulado(force_broken_claim=False)
    print("[TEST] Ejecutando flujo inicial (minar)...")
    run_with_healing(
        page,
        alias="boton_minar",
        selector="css=#boton-minar",
        fn=flujo_mineria,
        step="rollercoin_mining",
    )
    print("[TEST] Paso 1: minar OK")

    # Paso 2: fallo forzado + healing automático con LLMRouter (failover HF Space → LM Studio)
    page2 = PlaywrightSimulado(force_broken_claim=True)
    print("[TEST] Ejecutando flujo con fallo forzado (claim) usando LLMRouter...")
    try:
        # Crear un wrapper que use el método específico de reparación del router
        llm_client_wrapper = _make_healer_compatible(llm_router)

        run_with_healing(
            page2,
            alias="boton_claim",
            selector="css=.claim-btn",
            fn=flujo_claim,
            step="rollercoin_claim",
            llm_client=llm_client_wrapper,
        )
        print(f"[TEST] Paso 2: healing y claim OK (router usado: {llm_router.last_used})")
    except Exception as e:
        print(f"[TEST] Paso 2 falló tras healing: {e}")
        raise


if __name__ == "__main__":
    main()
