"use client";

/**
 * AME Vault adapter (BLOQUE 36) — re-export del módulo canónico de cifrado.
 *
 * ``@lib/secure-vault`` (AES-256-GCM + Session Lock) es el módulo oficial para
 * el cifrado at-rest de los buffers guardados en la tarjeta SD del móvil.
 * Este archivo mantiene compatibilidad con imports de ``@/lib/ame-vault``.
 */

export {
  default,
  SecureVault,
  type VaultBlob,
  type SecureVaultConfig,
  type SecureVaultStatus,
  type VaultReader,
  type VaultWriter,
} from "./secure-vault";

export { SecureVault as VaultSession } from "./secure-vault";
