import { Directory, Encoding, Filesystem } from "@capacitor/filesystem";
import { auraService } from "./AURAService";

export class FileEditorService {
  private openFiles: Map<string, string> = new Map();

  // Listar archivos del proyecto AURA via el agente
  async listProjectFiles(path = "AURA_workspace"): Promise<any[]> {
    return new Promise((resolve) => {
      auraService.send("AGENT_NEW_TASK", {
        input: `Lista los archivos en /sdcard/${path} con sus tamanos`,
      });
      auraService.on("AGENT_TASK_COMPLETE", (payload: any) => {
        resolve(payload.files || []);
      });
    });
  }

  // Leer archivo via el agente en Termux
  async readFile(remotePath: string): Promise<string> {
    return new Promise((resolve, reject) => {
      const taskId = `read_${Date.now()}`;
      auraService.send("AGENT_NEW_TASK", {
        task_id: taskId,
        input: `Lee el archivo ${remotePath} y devuelve su contenido completo`,
      });
      auraService.on("AGENT_TASK_COMPLETE", (payload: any) => {
        if (payload.task_id === taskId) {
          resolve(payload.result || "");
        }
      });
      // Timeout despues de 30s
      setTimeout(() => reject(new Error("Timeout leyendo archivo")), 30000);
    });
  }

  // Guardar archivo editado y hacer hot-reload en Godot
  async saveFile(remotePath: string, content: string): Promise<void> {
    auraService.send("AGENT_NEW_TASK", {
      input: `Guarda este contenido en ${remotePath}:\n\`\`\`\n${content}\n\`\`\`\nLuego haz hot-reload si es un archivo .gd de Godot`,
    });
  }

  // Guardar en local (/sdcard/) directamente
  async saveLocal(filename: string, content: string): Promise<void> {
    await Filesystem.writeFile({
      path: filename,
      data: content,
      directory: Directory.ExternalStorage,
      encoding: Encoding.UTF8,
    });
    this.openFiles.set(filename, content);
  }

  // Leer desde local
  async readLocal(filename: string): Promise<string> {
    const result = await Filesystem.readFile({
      path: filename,
      directory: Directory.ExternalStorage,
      encoding: Encoding.UTF8,
    });
    const data = result.data as string;
    this.openFiles.set(filename, data);
    return data;
  }

  // Obtener archivos abiertos en cache
  getOpenFiles(): Map<string, string> {
    return this.openFiles;
  }

  // Cerrar archivo del cache
  closeFile(path: string): void {
    this.openFiles.delete(path);
  }
}

export const fileEditorService = new FileEditorService();
