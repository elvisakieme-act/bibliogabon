import { useState } from "react";

import { ApiError } from "@/api/client";
import { apiUpload } from "@/api/upload";
import { useAuth } from "@/auth/useAuth";

function humanBytes(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${Math.round(bytes / (1024 * 1024))} Mo`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} ko`;
  return `${bytes} octets`;
}

/**
 * Dépôt du fichier source.
 *
 * Les bornes viennent du serveur (`/api/staff/v1/` les annonce) et non d'une
 * variable de build : recopiées côté client, elles dériveraient de la
 * configuration réelle. Elles sont vérifiées **avant** d'ouvrir une requête —
 * faire monter 300 Mo pour s'entendre refuser est une perte de temps et de
 * bande passante, sur des connexions où elle coûte.
 *
 * Le refus distant est rendu quand même : un proxy peut être plus strict que
 * le serveur applicatif, et l'écran ne doit pas traiter ce cas comme
 * impossible.
 */
export function SourceUpload({
  documentId,
  maxBytes,
  acceptedMimeTypes,
  onUploaded
}: {
  documentId: number;
  maxBytes: number;
  acceptedMimeTypes: string[];
  onUploaded?: () => void;
}) {
  const { tokens } = useAuth();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [success, setSuccess] = useState("");
  const [replace, setReplace] = useState(false);

  function choose(chosen: File | null) {
    setError("");
    setSuccess("");
    setProgress(null);
    if (!chosen) {
      setFile(null);
      return;
    }
    if (chosen.size > maxBytes) {
      setError(
        `Ce fichier est trop volumineux : ${humanBytes(chosen.size)} pour un maximum de ${humanBytes(maxBytes)}.`
      );
      setFile(null);
      return;
    }
    if (acceptedMimeTypes.length > 0 && !acceptedMimeTypes.includes(chosen.type)) {
      setError(
        `Ce type de fichier n'est pas accepté. Formats acceptés : ${acceptedMimeTypes.join(", ")}.`
      );
      setFile(null);
      return;
    }
    setFile(chosen);
  }

  async function send() {
    if (!file || !tokens?.access) return;
    setError("");
    setSuccess("");
    setProgress(0);
    try {
      const document = await apiUpload<{ ingestion?: { version_label: string } | null }>(
        `/api/staff/v1/documents/${documentId}/source/`,
        file,
        { token: tokens.access, replace, onProgress: setProgress }
      );
      const label = document?.ingestion?.version_label ?? "";
      setSuccess(
        label
          ? `Fichier déposé. Version ${label} en file de traitement.`
          : "Fichier déposé. Le traitement va démarrer."
      );
      setFile(null);
      onUploaded?.();
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Le fichier n'a pas pu être transmis. Réessayez."
      );
    } finally {
      setProgress(null);
    }
  }

  return (
    <section className="space-y-3 rounded border border-slate-200 bg-white p-4">
      <h3 className="font-semibold">Fichier source</h3>

      {error ? (
        <p role="alert" className="rounded bg-red-50 p-3 text-sm text-red-800">
          {error}
        </p>
      ) : null}
      {success ? (
        <p role="status" className="rounded bg-emerald-50 p-3 text-sm text-emerald-800">
          {success}
        </p>
      ) : null}

      <div className="flex flex-col gap-1">
        <label htmlFor="depot-fichier" className="text-sm font-medium">
          Fichier source
        </label>
        <input
          id="depot-fichier"
          type="file"
          accept={acceptedMimeTypes.join(",")}
          className="text-sm"
          onChange={(event) => choose(event.target.files?.[0] ?? null)}
        />
        <p className="text-xs text-slate-500">
          Jusqu&apos;à {humanBytes(maxBytes)}. Le fichier reste privé : aucune adresse publique
          n&apos;y donne accès.
        </p>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={replace}
          onChange={(event) => setReplace(event.target.checked)}
        />
        Remplacer le contenu de la version existante
      </label>

      {progress !== null ? (
        <div className="space-y-1">
          <progress
            value={progress}
            max={1}
            aria-label="Progression de l'envoi"
            className="w-full"
          />
          <p className="text-xs text-slate-600">{Math.round(progress * 100)} %</p>
        </div>
      ) : null}

      <button
        type="button"
        disabled={!file || progress !== null}
        onClick={send}
        className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        Envoyer le fichier
      </button>
    </section>
  );
}
