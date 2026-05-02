"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ProtectedRoute } from "@/components/auth/protected-route";
import { Reveal } from "@/components/reveal";
import { SiteHeader } from "@/components/site-header";
import { useAuth } from "@/context/auth-context";
import {
  compileApplicationDocument,
  generateApplicationDocument,
  getApplicationDetail,
  getApplicationDocuments,
  type ApplicationDetail,
  type ApplicationDocument,
} from "@/services/auth";

type DocType = "cv" | "cover_letter";

const DOC_LABELS: Record<DocType, string> = {
  cv: "Tailored CV",
  cover_letter: "Cover Letter",
};

export default function ApplicationPage() {
  return (
    <ProtectedRoute>
      <ApplicationContent />
    </ProtectedRoute>
  );
}

function ApplicationContent() {
  const params = useParams<{ applicationId: string }>();
  const applicationId = Array.isArray(params.applicationId) ? params.applicationId[0] : params.applicationId;
  const { session } = useAuth();

  const [application, setApplication] = useState<ApplicationDetail | null>(null);
  const [documents, setDocuments] = useState<ApplicationDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [working, setWorking] = useState<Record<DocType, boolean>>({ cv: false, cover_letter: false });
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorDocument, setEditorDocument] = useState<ApplicationDocument | null>(null);
  const [editorHtml, setEditorHtml] = useState("");
  const [compiling, setCompiling] = useState(false);

  useEffect(() => {
    if (!session || !applicationId) {
      return;
    }
    setLoading(true);
    setError(null);
    Promise.all([
      getApplicationDetail(session.access_token, applicationId),
      getApplicationDocuments(session.access_token, applicationId),
    ])
      .then(([detail, docs]) => {
        setApplication(detail);
        setDocuments(docs.items ?? []);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load application"))
      .finally(() => setLoading(false));
  }, [session, applicationId]);

  const currentDocuments = useMemo(() => {
    const pick = (type: DocType) =>
      documents
        .filter((doc) => doc.document_type === type)
        .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))[0] ?? null;
    return {
      cv: pick("cv"),
      cover_letter: pick("cover_letter"),
    };
  }, [documents]);

  async function refreshDocuments() {
    if (!session || !applicationId) {
      return;
    }
    const docs = await getApplicationDocuments(session.access_token, applicationId);
    setDocuments(docs.items ?? []);
  }

  function openEditor(doc: ApplicationDocument) {
    setEditorDocument(doc);
    setEditorHtml(doc.content || "");
    setEditorOpen(true);
    setMessage(null);
  }

  async function handleGenerate(documentType: DocType) {
    if (!session || !applicationId) {
      return;
    }
    setWorking((current) => ({ ...current, [documentType]: true }));
    setError(null);
    try {
      const result = await generateApplicationDocument(session.access_token, applicationId, documentType);
      await refreshDocuments();
      setEditorDocument({
        document_id: result.document_id,
        application_id: result.application_id,
        document_type: result.document_type,
        title: result.title,
        generation_status: result.status,
        is_current: true,
        content_format: "html",
        content: result.html,
        rendered_format: null,
        rendered_storage_bucket: null,
        rendered_storage_path: null,
        rendered_mime_type: null,
        rendered_file_size_bytes: null,
        generation_params: result.generation_params,
        template_name: "jobful-application-v1",
        provider: null,
        model_name: null,
        prompt_version: null,
        created_at: null,
        updated_at: null,
      });
      setEditorHtml(result.html);
      setEditorOpen(true);
      setMessage(`${DOC_LABELS[documentType]} generated. Review it in the overlay before saving the PDF.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setWorking((current) => ({ ...current, [documentType]: false }));
    }
  }

  async function handleCompile() {
    if (!session || !applicationId || !editorDocument) {
      return;
    }
    setCompiling(true);
    setError(null);
    try {
      const blob = await compileApplicationDocument(session.access_token, applicationId, {
        document_id: editorDocument.document_id,
        document_type: editorDocument.document_type,
        html: editorHtml,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${editorDocument.document_type === "cv" ? "cv" : "cover_letter"}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      await refreshDocuments();
      setMessage("PDF compiled and downloaded.");
      setEditorOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not compile PDF");
    } finally {
      setCompiling(false);
    }
  }

  const tracked = application;

  return (
    <div className="ui-shell">
      <SiteHeader />

      <main className="px-4 pb-10 pt-6 sm:px-6 sm:pt-8">
        <div className="ui-wrap space-y-6">
          <Reveal className="ui-card p-7 sm:p-10">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="space-y-4">
                <p className="ui-eyebrow w-fit"><span className="ui-dot" />Application workspace</p>
                <h1 className="ui-title max-w-3xl">
                  {tracked ? tracked.title : "Application loading"}
                </h1>
                <p className="ui-lead max-w-3xl">
                  Generate a tailored CV and cover letter for this tracked job. The documents stay tied to this application row, and the latest current version is stored in Supabase.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Link href="/dashboard" className="ui-button ui-button-secondary inline-flex">Back to dashboard</Link>
                  {tracked?.apply_url || tracked?.source_url ? (
                    <a href={tracked.apply_url || tracked.source_url || "#"} target="_blank" rel="noopener noreferrer" className="ui-button inline-flex">
                      Open listing
                    </a>
                  ) : null}
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="ui-metric">
                  <p className="ui-kicker">Status</p>
                  <p className="ui-metric-value">{tracked?.status ?? "..."}</p>
                </div>
                <div className="ui-metric">
                  <p className="ui-kicker">Current docs</p>
                  <p className="ui-metric-value">{documents.filter((doc) => doc.is_current).length}</p>
                </div>
              </div>
            </div>
          </Reveal>

          {message ? (
            <Reveal className="ui-card p-5">
              <div className="ui-empty">
                <p className="text-sm text-[var(--text-soft)]">{message}</p>
              </div>
            </Reveal>
          ) : null}
          {error ? (
            <Reveal className="ui-card p-5">
              <div className="rounded-[1.25rem] bg-[var(--red-soft)] p-4 text-sm text-[#7f2f2f]">{error}</div>
            </Reveal>
          ) : null}

          {loading ? (
            <Reveal className="ui-card p-7">
              <div className="ui-empty">Loading application data.</div>
            </Reveal>
          ) : (
            <div className="grid gap-6 xl:grid-cols-2">
              {(Object.keys(DOC_LABELS) as DocType[]).map((documentType) => {
                const currentDoc = currentDocuments[documentType];
                return (
                  <Reveal key={documentType} className="ui-card p-7 sm:p-8">
                    <div className="space-y-5">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="ui-kicker">{DOC_LABELS[documentType]}</p>
                          <h2 className="ui-title mt-2">
                            {currentDoc ? currentDoc.title : "Not generated yet"}
                          </h2>
                        </div>
                        <span className={`ui-status ${currentDoc?.is_current ? "ui-status-green" : "ui-status-yellow"}`}>
                          {currentDoc ? currentDoc.generation_status : "draft"}
                        </span>
                      </div>

                      <div className="ui-panel p-5">
                        <p className="text-sm leading-6 text-[var(--text-soft)]">
                          {documentType === "cv"
                            ? "Generate the job-specific CV. Use the overlay to inspect the rendered HTML, edit it, then print/download the final PDF."
                            : "Generate the matching cover letter. The overlay lets you edit the copy before final PDF storage."}
                        </p>
                      </div>

                      <div className="flex flex-wrap gap-3">
                        <button
                          type="button"
                          className="ui-button"
                          disabled={working[documentType]}
                          onClick={() => void handleGenerate(documentType)}
                        >
                          {working[documentType] ? "Generating" : currentDoc ? "Regenerate" : "Generate"}
                        </button>
                        {currentDoc ? (
                          <button
                            type="button"
                            className="ui-button ui-button-secondary"
                            onClick={() => openEditor(currentDoc)}
                          >
                            Edit
                          </button>
                        ) : null}
                      </div>

                      {currentDoc ? (
                        <div className="space-y-3">
                          <div className="text-sm text-[var(--text-soft)]">
                            Current version stored at: <span className="break-all">{currentDoc.rendered_storage_path || "draft only"}</span>
                          </div>
                          <button
                            type="button"
                            className="ui-button ui-button-secondary"
                            onClick={() => openEditor(currentDoc)}
                          >
                            Print / Download PDF
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </Reveal>
                );
              })}
            </div>
          )}

          <Reveal className="ui-card p-7 sm:p-8">
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="ui-kicker">Document history</p>
                  <h2 className="ui-title mt-2">Saved versions for this application.</h2>
                </div>
                <span className="ui-status ui-status-blue">{documents.length} total</span>
              </div>

              {documents.length === 0 ? (
                <div className="ui-empty">Generate a CV or cover letter to create the first saved document.</div>
              ) : (
                <div className="space-y-3">
                  {documents.map((doc) => (
                    <div key={doc.document_id} className="ui-panel flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="text-sm font-semibold">{doc.title}</p>
                        <p className="text-xs text-[var(--text-dim)]">
                          {doc.document_type} | {doc.generation_status} | {doc.created_at ? doc.created_at.slice(0, 10) : "draft"}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <span className={`ui-status ${doc.is_current ? "ui-status-green" : "ui-status-yellow"}`}>
                          {doc.is_current ? "current" : "archived"}
                        </span>
                        <button type="button" className="ui-button ui-button-secondary" onClick={() => openEditor(doc)}>
                          Review
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Reveal>
        </div>
      </main>

      {editorOpen && editorDocument ? (
        <div className="fixed inset-0 z-50 bg-black/40 p-4 backdrop-blur-sm sm:p-8">
          <div className="mx-auto flex h-full w-full max-w-7xl flex-col overflow-hidden rounded-[2rem] border border-white/30 bg-[var(--surface)] shadow-[0_30px_80px_rgba(52,61,46,0.2)]">
            <div className="flex items-center justify-between gap-4 border-b border-[rgba(95,108,95,0.12)] px-5 py-4">
              <div>
                <p className="ui-kicker">{DOC_LABELS[editorDocument.document_type]}</p>
                <h3 className="mt-1 text-lg font-semibold">{editorDocument.title}</h3>
              </div>
              <div className="flex items-center gap-3">
                <button type="button" className="ui-button ui-button-secondary" onClick={() => setEditorOpen(false)}>
                  Close
                </button>
                <button type="button" className="ui-button" disabled={compiling} onClick={() => void handleCompile()}>
                  {compiling ? "Compiling" : "Print / Download PDF"}
                </button>
              </div>
            </div>

            <div className="grid flex-1 gap-0 lg:grid-cols-2">
              <div className="flex flex-col border-b border-[rgba(95,108,95,0.12)] lg:border-b-0 lg:border-r">
                <div className="border-b border-[rgba(95,108,95,0.12)] px-5 py-3">
                  <p className="ui-kicker">HTML editor</p>
                </div>
                <textarea
                  className="min-h-[18rem] flex-1 rounded-none border-0 bg-transparent p-5 font-mono text-[12px] leading-6 outline-none"
                  value={editorHtml}
                  onChange={(e) => setEditorHtml(e.target.value)}
                />
              </div>
              <div className="flex flex-col">
                <div className="border-b border-[rgba(95,108,95,0.12)] px-5 py-3">
                  <p className="ui-kicker">Preview</p>
                </div>
                <iframe
                  title="document-preview"
                  className="h-full min-h-[24rem] w-full bg-white"
                  srcDoc={editorHtml}
                />
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
