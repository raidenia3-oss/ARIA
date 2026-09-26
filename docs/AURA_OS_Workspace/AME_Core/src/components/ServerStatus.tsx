// ═══════════════════════════════════════════════════════════════
// ServerStatus.tsx — Indicador visual de estado de servidores Colab
// Muestra circulo verde/rojo por cada servidor + boton de reconexión
// ═══════════════════════════════════════════════════════════════

import React, { useEffect, useState } from "react";
import {
    colabServerService,
    ServerStatusInfo,
    ServerStatusMap,
} from "../services/ColabServerService";

/** Color segun estado del servidor */
const statusColor: Record<ServerStatusInfo, string> = {
    active: "#48ffce",
    inactive: "#ff7b72",
    checking: "#d29922",
};

/** Etiqueta segun estado */
const statusLabel: Record<ServerStatusInfo, string> = {
    active: "Activo",
    inactive: "Inactivo",
    checking: "Verificando...",
};

export const ServerStatus: React.FC = () => {
    const [status, setStatus] = useState<ServerStatusMap>(colabServerService.getStatus());

    // Suscribirse a cambios de estado
    useEffect(() => {
        const unsub = colabServerService.onStatusChange(setStatus);
        return unsub;
    }, []);

    /** Reintentar conexion manual */
    const handleReconnect = async (): Promise<void> => {
        setStatus((prev) => ({ ...prev, code: "checking", general: "checking" }));
        const s = await colabServerService.checkServerStatus();
        setStatus(s);
    };

    /** Tamaño del circulo segun estado */
    const dotSize = 8;

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: "6px", padding: "10px 14px" }}>
            <div
                style={{
                    fontSize: "10px",
                    color: "rgba(150,210,255,0.5)",
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                    marginBottom: "2px",
                }}
            >
                Servidores IA Colab
            </div>

            {/* Servidor Código */}
            <div
                onClick={() => colabServerService.checkServerStatus()}
                style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    cursor: "pointer",
                    padding: "4px 6px",
                    borderRadius: "6px",
                    background: "rgba(100,200,255,0.04)",
                }}
            >
                <span
                    style={{
                        width: dotSize,
                        height: dotSize,
                        borderRadius: "50%",
                        background: statusColor[status.code],
                        display: "inline-block",
                    }}
                />
                <span style={{ fontSize: "11px", color: "rgba(200,240,255,0.7)" }}>Código</span>
                <span
                    style={{ fontSize: "9px", color: statusColor[status.code], marginLeft: "auto" }}
                >
                    {statusLabel[status.code]}
                </span>
            </div>

            {/* Servidor General */}
            <div
                onClick={() => colabServerService.checkServerStatus()}
                style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    cursor: "pointer",
                    padding: "4px 6px",
                    borderRadius: "6px",
                    background: "rgba(100,200,255,0.04)",
                }}
            >
                <span
                    style={{
                        width: dotSize,
                        height: dotSize,
                        borderRadius: "50%",
                        background: statusColor[status.general],
                        display: "inline-block",
                    }}
                />
                <span style={{ fontSize: "11px", color: "rgba(200,240,255,0.7)" }}>General</span>
                <span
                    style={{
                        fontSize: "9px",
                        color: statusColor[status.general],
                        marginLeft: "auto",
                    }}
                >
                    {statusLabel[status.general]}
                </span>
            </div>

            {/* Boton de reconexión */}
            {status.code === "inactive" && status.general === "inactive" && (
                <div
                    onClick={handleReconnect}
                    style={{
                        fontSize: "10px",
                        padding: "6px 10px",
                        borderRadius: "8px",
                        border: "0.5px solid rgba(255,123,114,0.3)",
                        background: "rgba(255,123,114,0.08)",
                        color: "#ff7b72",
                        cursor: "pointer",
                        textAlign: "center",
                        marginTop: "4px",
                    }}
                >
                    Intentar reconexión
                </div>
            )}
        </div>
    );
};

export default ServerStatus;
