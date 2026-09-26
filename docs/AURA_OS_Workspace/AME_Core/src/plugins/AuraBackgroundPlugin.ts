/**
 * AuraBackgroundPlugin.ts — Capacitor plugin bridge para servicios Android
 * Conecta AuraPassiveService y FloatingBubbleService con la web app
 */
import { registerPlugin, type PluginListenerHandle } from "@capacitor/core";

export interface AuraBackgroundPlugin {
    startPassiveService(options: { wsUrl: string }): Promise<{ started: boolean }>;
    stopPassiveService(): Promise<{ stopped: boolean }>;
    startBubbleService(): Promise<{ started: boolean }>;
    stopBubbleService(): Promise<{ stopped: boolean }>;
    sendToServer(options: { message: string }): Promise<{ sent: boolean }>;
    isServiceRunning(): Promise<{ running: boolean }>;
    isBubbleVisible(): Promise<{ visible: boolean }>;
    addListener(
        eventName: "onMessage" | "onStatusChange",
        handlerFunc: (data: { message: string }) => void,
    ): Promise<PluginListenerHandle>;
}

const AuraBackground = registerPlugin<AuraBackgroundPlugin>("AuraBackground");

export default AuraBackground;
