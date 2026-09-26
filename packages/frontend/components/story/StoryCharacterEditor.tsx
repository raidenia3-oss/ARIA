"use client";

/**
 * CRUD de personajes (Character Bible).
 * Contrato real:
 * - GET  /api/story/{work_id}/characters → {characters, count}
 * - POST /api/story/{work_id}/characters/{char_id} → {status, char_id, character}
 * - DELETE /api/story/{work_id}/characters/{char_id}
 */

import { useEffect, useState } from "react";
import { JJK } from "@/lib/jjk-theme";
import { parseListInput } from "@/lib/story-format";
import {
  deleteCharacter,
  listCharacters,
  StoryApiError,
  upsertCharacter,
} from "@/lib/story-client";
import type { StoryCharacter } from "@/lib/story-types";

interface Props {
  workId: string;
  onCharacterSaved?: (char: StoryCharacter) => void;
}

const EMPTY_FORM = {
  char_id: "",
  name: "",
  aliases: "",
  voice: "",
  personality: "",
  objectives: "",
  conflicts: "",
  relationships: "",
  backstory: "",
};

const inputStyle = {
  background: JJK.BG,
  color: JJK.TEXT,
  borderColor: `${JJK.ACCENT}33`,
};

export default function StoryCharacterEditor({ workId, onCharacterSaved }: Props) {
  const [characters, setCharacters] = useState<StoryCharacter[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listCharacters(workId);
      setCharacters(res.characters || []);
    } catch (err: unknown) {
      setError(err instanceof StoryApiError ? err.message : "Error al cargar personajes");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (workId) {
      setCharacters([]);
      setForm({ ...EMPTY_FORM });
      void refresh();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workId]);

  const handleSave = async () => {
    const charId =
      form.char_id.trim() || form.name.trim().toLowerCase().replace(/\s+/g, "_");
    if (!charId || !form.name.trim() || busy) return;
    setBusy(true);
    setError(null);
    setSaved(null);
    try {
      const relationships: Record<string, string> = {};
      form.relationships
        .split("\n")
        .map((l) => l.trim())
        .filter(Boolean)
        .forEach((line) => {
          const idx = line.indexOf(":");
          if (idx > 0) {
            relationships[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
          }
        });
      const res = await upsertCharacter(workId, charId, {
        name: form.name.trim(),
        aliases: parseListInput(form.aliases),
        voice: form.voice.trim(),
        personality: parseListInput(form.personality),
        objectives: parseListInput(form.objectives),
        conflicts: parseListInput(form.conflicts),
        relationships,
        backstory: form.backstory.trim(),
      });
      setSaved(`Personaje "${res.character.name}" guardado (${charId}).`);
      setForm({ ...EMPTY_FORM });
      onCharacterSaved?.(res.character);
      await refresh();
    } catch (err: unknown) {
      setError(
        err instanceof StoryApiError
          ? `No se pudo guardar: ${err.message}`
          : "Error desconocido al guardar"
      );
    } finally {
      setBusy(false);
    }
  };

  const handleEdit = (c: StoryCharacter) => {
    setForm({
      char_id: c.char_id,
      name: c.name || "",
      aliases: (c.aliases || []).join(", "),
      voice: c.voice || "",
      personality: (c.personality || []).join(", "),
      objectives: (c.objectives || []).join(", "),
      conflicts: (c.conflicts || []).join(", "),
      relationships: Object.entries(c.relationships || {})
        .map(([k, v]) => `${k}: ${v}`)
        .join("\n"),
      backstory: c.backstory || "",
    });
  };

  const handleDelete = async (charId: string) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await deleteCharacter(workId, charId);
      setSaved(`Personaje "${charId}" eliminado.`);
      await refresh();
    } catch (err: unknown) {
      setError(err instanceof StoryApiError ? err.message : "Error al eliminar");
    } finally {
      setBusy(false);
    }
  };

  const set = (key: keyof typeof EMPTY_FORM, value: string) =>
    setForm({ ...form, [key]: value });

  const text = (
    key: keyof typeof EMPTY_FORM,
    placeholder: string,
    rows = 0,
    wide = false
  ) =>
    rows > 0 ? (
      <textarea
        key={key}
        value={form[key]}
        onChange={(e) => set(key, e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className={`p-2 rounded border text-sm ${wide ? "w-full" : ""}`}
        style={inputStyle}
      />
    ) : (
      <input
        key={key}
        value={form[key]}
        onChange={(e) => set(key, e.target.value)}
        placeholder={placeholder}
        className="p-2 rounded border text-sm"
        style={inputStyle}
        disabled={key === "char_id" && !!form.char_id}
      />
    );

  return (
    <div className="space-y-4">
      <div
        className="rounded-lg p-4 border space-y-2"
        style={{ borderColor: `${JJK.ACCENT}33`, background: JJK.PANEL }}
      >
        <h3 className="font-bold" style={{ color: JJK.TEXT }}>
          👤 {form.char_id ? `Editar personaje: ${form.char_id}` : "Nuevo personaje"}
        </h3>
        <div className="grid grid-cols-2 gap-2">
          {text("char_id", "ID (opcional)")}
          {text("name", "Nombre *")}
          {text("aliases", "Alias (separados por coma)")}
          {text("voice", "Voz / estilo narrativo")}
          {text("personality", "Personalidad (coma)")}
          {text("objectives", "Objetivos (coma)")}
          {text("conflicts", "Conflictos (coma)")}
          {text("relationships", "Relaciones (línea: 'Nombre: rol')")}
        </div>
        {text("backstory", "Historia / trasfondo", 3, true)}
        <div className="flex gap-2">
          <button
            onClick={handleSave}
            disabled={busy || !form.name.trim()}
            className="py-2 px-4 rounded text-white font-semibold text-sm disabled:opacity-50"
            style={{ background: JJK.ACCENT }}
          >
            {busy ? "Guardando…" : "Guardar personaje"}
          </button>
          {form.char_id && (
            <button
              onClick={() => setForm({ ...EMPTY_FORM })}
              className="py-2 px-4 rounded text-sm"
              style={{ border: `1px solid ${JJK.ACCENT}55`, color: JJK.TEXT }}
            >
              Cancelar edición
            </button>
          )}
        </div>
        {saved && (
          <p className="text-xs" style={{ color: JJK.ACCENT2 }}>
            {saved}
          </p>
        )}
        {error && (
          <p className="text-xs" style={{ color: JJK.RED }}>
            ⚠ {error}
          </p>
        )}
      </div>

      <div
        className="rounded-lg p-4 border"
        style={{ borderColor: `${JJK.ACCENT}33`, background: JJK.PANEL }}
      >
        <h3 className="font-bold mb-2" style={{ color: JJK.TEXT }}>
          📖 Biblia de personajes
        </h3>
        {loading ? (
          <p className="text-sm" style={{ color: JJK.TEXT }}>
            Cargando…
          </p>
        ) : characters.length === 0 ? (
          <p className="text-sm" style={{ color: `${JJK.TEXT}99` }}>
            Sin personajes aún.
          </p>
        ) : (
          <ul className="space-y-2">
            {characters.map((c) => (
              <li
                key={c.char_id}
                className="p-3 rounded border text-sm flex justify-between items-start"
                style={{ borderColor: `${JJK.ACCENT}22` }}
              >
                <div>
                  <span className="font-semibold" style={{ color: JJK.TEXT }}>
                    {c.name}
                  </span>
                  <span style={{ color: `${JJK.TEXT}66` }}> ({c.char_id})</span>
                  {c.aliases?.length > 0 && (
                    <div style={{ color: `${JJK.TEXT}88` }}>
                      Alias: {c.aliases.join(", ")}
                    </div>
                  )}
                  {c.voice && <div style={{ color: JJK.ACCENT2 }}>🎙 {c.voice}</div>}
                  {c.personality?.length > 0 && (
                    <div style={{ color: `${JJK.TEXT}88` }}>
                      Personalidad: {c.personality.join(", ")}
                    </div>
                  )}
                  {c.objectives?.length > 0 && (
                    <div style={{ color: `${JJK.TEXT}88` }}>
                      Objetivos: {c.objectives.join(", ")}
                    </div>
                  )}
                  {c.conflicts?.length > 0 && (
                    <div style={{ color: `${JJK.TEXT}88` }}>
                      Conflictos: {c.conflicts.join(", ")}
                    </div>
                  )}
                  {c.relationships && Object.keys(c.relationships).length > 0 && (
                    <div style={{ color: `${JJK.TEXT}88` }}>
                      Relaciones:{" "}
                      {Object.entries(c.relationships)
                        .map(([k, v]) => `${k} → ${v}`)
                        .join("; ")}
                    </div>
                  )}
                  {c.backstory && (
                    <div style={{ color: `${JJK.TEXT}77` }}>{c.backstory}</div>
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  <button
                    onClick={() => handleEdit(c)}
                    className="px-2 py-1 rounded text-xs"
                    style={{ border: `1px solid ${JJK.ACCENT}55`, color: JJK.TEXT }}
                  >
                    ✏️ Editar
                  </button>
                  <button
                    onClick={() => handleDelete(c.char_id)}
                    className="px-2 py-1 rounded text-xs"
                    style={{ border: `1px solid ${JJK.RED}55`, color: JJK.RED }}
                  >
                    🗑
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
