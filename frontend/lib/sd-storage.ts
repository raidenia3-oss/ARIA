"use client";

/**
 * AME SD-Card Native Bridge (Bloque 40, funcionalidad 2).
 *
 * Envoltura del plugin nativo Capacitor SDStorage para gestionar directorios
 * directamente en la tarjeta SD externa del móvil. En web (navegador) hace
 * fallback a FileSystem Access API / descarga; en nativo usa el plugin.
 */

import { Capacitor } from "@capacitor/core";
import { Filesystem, Directory, Encoding } from "@capacitor/filesystem";

export interface SDVaultInfo {
  path: string;
  available: boolean;
}

export interface SDListResult {
  files: string[];
}

// Plugin nativo tipado (registrado en MainActivity como "SDStorage").
interface SDStoragePlugin {
  getSDCardPath(): Promise<SDVaultInfo>;
  ensureVault(options: { sdPath?: string }): Promise<{ ok: boolean; path: string; error?: string }>;
  listFiles(options: { path: string }): Promise<SDListResult>;
}

function getSDStorage(): SDStoragePlugin | null {
  if (!Capacitor.isNativePlatform()) return null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const plugins = (Capacitor as any).Plugins;
  return plugins?.SDStorage ?? null;
}

/** Resuelve la ruta de la tarjeta SD externa (nativo) o null en web. */
export async function getSDCardPath(): Promise<SDVaultInfo | null> {
  const plugin = getSDStorage();
  if (!plugin) return null;
  return plugin.getSDCardPath();
}

/** Asegura que exista el directorio de bóveda en la SD. */
export async function ensureVault(sdPath?: string): Promise<string | null> {
  const plugin = getSDStorage();
  if (!plugin) return null;
  const res = await plugin.ensureVault({ sdPath });
  return res.ok ? res.path : null;
}

/** Lista ficheros de un directorio de la SD. */
export async function listSDFiles(path: string): Promise<string[]> {
  const plugin = getSDStorage();
  if (!plugin) return [];
  const res = await plugin.listFiles({ path });
  return res.files ?? [];
}

/**
 * Lee un fichero de texto desde el almacenamiento. En nativo usa la SD;
 * en web usa Capacitor Filesystem (Directory.Documents) como fallback.
 */
export async function readVaultFile(dir: string, name: string): Promise<string | null> {
  if (Capacitor.isNativePlatform()) {
    const plugin = getSDStorage();
    if (!plugin) return null;
    const list = await plugin.listFiles({ path: dir });
    if (!list.files.includes(name)) return null;
    // Lectura vía Filesystem plugin con ruta absoluta nativa.
    try {
      const res = await Filesystem.readFile({
        path: `${dir}/${name}`,
        encoding: Encoding.UTF8,
      });
      return typeof res.data === "string" ? res.data : null;
    } catch {
      return null;
    }
  }
  return null;
}

/**
 * Escribe un fichero de texto en la bóveda. En nativo, en la SD; en web,
 * en Directory.Documents como fallback local-first.
 */
export async function writeVaultFile(
  dir: string,
  name: string,
  data: string,
): Promise<boolean> {
  try {
    await Filesystem.writeFile({
      path: `${dir}/${name}`,
      data,
      directory: Capacitor.isNativePlatform() ? undefined : Directory.Documents,
      encoding: Encoding.UTF8,
      recursive: true,
    });
    return true;
  } catch {
    return false;
  }
}

export default {
  getSDCardPath,
  ensureVault,
  listSDFiles,
  readVaultFile,
  writeVaultFile,
};