/**
 * AURA Sentinel Agent - Navegador Integrado con Persistencia
 * Motor de automatización basado en Puppeteer con directorio de datos persistente.
 * Almacenamiento seguro de credenciales mediante SecretStorage de VS Code.
 */

import * as puppeteer from "puppeteer";
import * as vscode from "vscode";

export interface BrowserConfig {
    userDataDir: string;
    headless: boolean;
    timeout: number;
}

export class BrowserManager {
    private context: vscode.ExtensionContext;
    private config: BrowserConfig;
    private browser: puppeteer.Browser | null = null;
    private page: puppeteer.Page | null = null;

    constructor(context: vscode.ExtensionContext, config?: Partial<BrowserConfig>) {
        this.context = context;
        this.config = {
            userDataDir:
                config?.userDataDir ||
                `${process.env.USERPROFILE || process.env.HOME}/.vscode/aura-sentinel-browser`,
            headless: config?.headless ?? true,
            timeout: config?.timeout || 30000,
        };
    }

    async launch(): Promise<void> {
        if (this.browser) {
            console.warn("[BrowserManager] El navegador ya está abierto.");
            return;
        }

        try {
            this.browser = await puppeteer.launch({
                headless: this.config.headless ? "new" : false,
                userDataDir: this.config.userDataDir,
                args: [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
                defaultViewport: { width: 1280, height: 800 },
            });

            this.page = await this.browser.newPage();
            this.page.setDefaultTimeout(this.config.timeout);

            console.log("[BrowserManager] Navegador lanzado correctamente.");
        } catch (error) {
            console.error("[BrowserManager] Error al lanzar navegador:", error);
            throw new Error(
                `No se pudo iniciar el navegador automatizado: ${error instanceof Error ? error.message : String(error)}`,
            );
        }
    }

    async navigate(url: string): Promise<void> {
        if (!this.page) {
            throw new Error("Navegador no inicializado. Llama a launch() primero.");
        }

        try {
            await this.page.goto(url, { waitUntil: "networkidle2" });
            console.log(`[BrowserManager] Navegado a: ${url}`);
        } catch (error) {
            console.error(`[BrowserManager] Error navegando a ${url}:`, error);
            throw new Error(`Error navegando a ${url}: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    async executeScript(script: string, ...args: any[]): Promise<any> {
        if (!this.page) {
            throw new Error("Navegador no inicializado.");
        }

        try {
            const result = await this.page.evaluate(script, ...args);
            return result;
        } catch (error) {
            console.error("[BrowserManager] Error ejecutando script:", error);
            throw new Error(`Error ejecutando script: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    async screenshot(path: string): Promise<void> {
        if (!this.page) {
            throw new Error("Navegador no inicializado.");
        }

        try {
            await this.page.screenshot({ path, fullPage: true });
            console.log(`[BrowserManager] Captura guardada en: ${path}`);
        } catch (error) {
            console.error("[BrowserManager] Error tomando captura:", error);
            throw new Error(`Error tomando captura: ${error instanceof Error ? error.message : String(error)}`);
        }
    }

    async saveCredential(key: string, value: string): Promise<void> {
        try {
            await this.context.secrets.store(key, value);
            console.log(`[BrowserManager] Credencial guardada: ${key}`);
        } catch (error) {
            console.error(`[BrowserManager] Error guardando credencial ${key}:`, error);
            throw error;
        }
    }

    async getCredential(key: string): Promise<string | undefined> {
        try {
            const value = await this.context.secrets.get(key);
            return value;
        } catch (error) {
            console.error(`[BrowserManager] Error obteniendo credencial ${key}:`, error);
            return undefined;
        }
    }

    async deleteCredential(key: string): Promise<void> {
        try {
            await this.context.secrets.delete(key);
            console.log(`[BrowserManager] Credencial eliminada: ${key}`);
        } catch (error) {
            console.error(`[BrowserManager] Error eliminando credencial ${key}:`, error);
            throw error;
        }
    }

    async close(): Promise<void> {
        if (this.browser) {
            try {
                await this.browser.close();
                console.log("[BrowserManager] Navegador cerrado.");
            } catch (error) {
                console.error("[BrowserManager] Error cerrando navegador:", error);
            } finally {
                this.browser = null;
                this.page = null;
            }
        }
    }

    getPage(): puppeteer.Page | null {
        return this.page;
    }

    getBrowser(): puppeteer.Browser | null {
        return this.browser;
    }

    isLaunched(): boolean {
        return this.browser !== null && this.page !== null;
    }
}

export function createBrowserManager(
    context: vscode.ExtensionContext,
    config?: Partial<BrowserConfig>,
): BrowserManager {
    return new BrowserManager(context, config);
}
