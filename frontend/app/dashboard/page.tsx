"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ProtectedRoute } from "@/components/auth/protected-route";
import { Reveal } from "@/components/reveal";
import { SiteHeader } from "@/components/site-header";
import { useAuth } from "@/context/auth-context";
import { useJobTracker } from "@/context/job-tracker-context";
import {
  getCVData,
  getOnboardingState,
  prepareTrackedApplication,
  removeStaleInterestedJob,
  updateApplicationStatus,
  type ApplicationRecord,
  type ApplicationStatus,
  type EducationDetail,
  type ExperienceDetail,
  type ProjectDetail,
  type Tag,
} from "@/services/auth";

const STATUS_ORDER: ApplicationStatus[] = ["interested", "applying", "applied", "response", "placed"];

export default function DashboardPage() {
  return (
    <ProtectedRoute>
      <DashboardContent />
    </ProtectedRoute>
  );
}

function DashboardContent() {
  const { session } = useAuth();
  const { overview, refreshOverview, loading: overviewLoading, error: overviewError } = useJobTracker();

  const [selectedTags, setSelectedTags] = useState<Tag[]>([]);
  const [education, setEducation] = useState<EducationDetail[]>([]);
  const [experiences, setExperiences] = useState<ExperienceDetail[]>([]);
  const [projects, setProjects] = useState<ProjectDetail[]>([]);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [statusSaving, setStatusSaving] = useState<Record<string, boolean>>({});
  const [preparingApply, setPreparingApply] = useState<Record<string, boolean>>({});
  const [removing, setRemoving] = useState<Record<string, boolean>>({});
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session) {
      return;
    }
    Promise.all([
      getOnboardingState(session.access_token),
      getCVData(session.access_token),
    ])
      .then(([state, cvData]) => {
        setSelectedTags(state.selected_tags);
        setEducation(cvData.education ?? []);
        setExperiences(cvData.experiences ?? []);
        setProjects(cvData.projects ?? []);
      })
      .catch(() => {})
      .finally(() => setLoadingProfile(false));
  }, [session]);

  async function handleStatusChange(applicationId: string, nextStatus: ApplicationStatus) {
    if (!session) {
      return;
    }
    setStatusSaving((current) => ({ ...current, [applicationId]: true }));
    try {
      await updateApplicationStatus(session.access_token, applicationId, nextStatus);
      await refreshOverview();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Could not update status.");
    } finally {
      setStatusSaving((current) => ({ ...current, [applicationId]: false }));
    }
  }

  async function handlePrepareApply(item: ApplicationRecord) {
    if (!session) {
      return;
    }
    setPreparingApply((current) => ({ ...current, [item.application_id]: true }));
    try {
      const result = await prepareTrackedApplication(session.access_token, item.application_id);
      await refreshOverview();
      setActionMessage("Custom CV and cover letter generation placeholder is wired. The real generator can take over this apply step next.");
      if (result.apply_url) {
        window.open(result.apply_url, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Could not move this job into apply mode.");
    } finally {
      setPreparingApply((current) => ({ ...current, [item.application_id]: false }));
    }
  }

  async function handleRemoveStale(applicationId: string) {
    if (!session) {
      return;
    }
    setRemoving((current) => ({ ...current, [applicationId]: true }));
    try {
      await removeStaleInterestedJob(session.access_token, applicationId);
      await refreshOverview();
    } catch (err) {
      setActionMessage(err instanceof Error ? err.message : "Could not remove this stale job.");
    } finally {
      setRemoving((current) => ({ ...current, [applicationId]: false }));
    }
  }

  const user = session?.user;
  const trackedItems = overview?.items ?? [];
  const notifications = overview?.notifications ?? [];
  const activeInterested = trackedItems.filter((item) => item.status === "interested" && item.is_active);
  const activePipeline = trackedItems.filter((item) => item.is_active && item.status !== "interested");
  const staleInterested = trackedItems.filter((item) => item.status === "interested" && !item.is_active);
  const staleApplied = trackedItems.filter((item) => item.status !== "interested" && !item.is_active);

  return (
    <div className="ui-shell">
      <SiteHeader />

      <main className="px-4 pb-8 pt-6 sm:px-6 sm:pb-10 sm:pt-8">
        <div className="ui-wrap space-y-6">
          <Reveal className="ui-card p-7 sm:p-10">
            <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr] lg:items-end">
              <div className="space-y-5">
                <p className="ui-eyebrow w-fit"><span className="ui-dot" />Tracked dashboard</p>
                <h1 className="ui-title max-w-3xl">
                  {user ? `${user.full_name}, ` : ""}your tracked jobs pipeline.
                </h1>
                <p className="ui-lead">
                  This is now the operating surface for tracked jobs: interested roles live here, apply actions start here, and stale hiring changes surface here first.
                </p>
                <div className="flex flex-wrap gap-3">
                  <Link href="/jobs" className="ui-button inline-flex">Search more jobs</Link>
                  <Link href="/onboarding" className="ui-button ui-button-secondary inline-flex">Edit profile</Link>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  { label: "Tracked total", value: `${overview?.summary.total ?? 0}` },
                  { label: "Ready to apply", value: `${activeInterested.length}` },
                  { label: "In pipeline", value: `${activePipeline.length}` },
                  { label: "Stale alerts", value: `${notifications.length}` },
                ].map((item, index) => (
                  <div key={item.label} className="ui-metric ui-stagger" style={{ ["--index" as string]: index }}>
                    <p className="ui-kicker">{item.label}</p>
                    <p className="ui-metric-value">{item.value}</p>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>

          {actionMessage ? (
            <Reveal className="ui-card p-5">
              <div className="ui-empty">
                <p className="text-sm text-[var(--text-soft)]">{actionMessage}</p>
              </div>
            </Reveal>
          ) : null}

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <Reveal className="ui-card p-7 sm:p-8">
              <div className="space-y-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="ui-kicker">Interested jobs</p>
                    <h2 className="ui-title mt-2">Tracked and ready for apply mode.</h2>
                  </div>
                  <span className="ui-status ui-status-green">{activeInterested.length} active</span>
                </div>

                {overviewLoading ? (
                  <div className="ui-empty">Refreshing hiring status.</div>
                ) : activeInterested.length === 0 ? (
                  <div className="ui-empty">
                    <p className="text-sm text-[var(--text-soft)]">No active interested jobs right now. Track roles from <Link href="/jobs" className="underline">job search</Link>.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {activeInterested.map((item, index) => (
                      <TrackedJobCard
                        key={item.application_id}
                        item={item}
                        index={index}
                        statusSaving={statusSaving[item.application_id]}
                        preparingApply={preparingApply[item.application_id]}
                        removing={false}
                        onStatusChange={handleStatusChange}
                        onPrepareApply={handlePrepareApply}
                        onRemove={handleRemoveStale}
                      />
                    ))}
                  </div>
                )}
              </div>
            </Reveal>

            <Reveal className="ui-card p-7 sm:p-8">
              <div className="space-y-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="ui-kicker">Notifications</p>
                    <h2 className="ui-title mt-2">Hiring changes detected on login.</h2>
                  </div>
                  <span className={`ui-status ${notifications.length > 0 ? "ui-status-red" : "ui-status-green"}`}>
                    {notifications.length} alert{notifications.length === 1 ? "" : "s"}
                  </span>
                </div>

                {notifications.length === 0 ? (
                  <div className="ui-empty">
                    <p className="text-sm text-[var(--text-soft)]">No stale tracked jobs detected in this session.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {notifications.map((notification, index) => (
                      <div key={notification.application_id} className="ui-panel ui-stagger" style={{ ["--index" as string]: index }}>
                        <div className="flex items-start justify-between gap-4">
                          <div className="space-y-2">
                            <p className="text-sm font-semibold">{notification.title}</p>
                            <p className="text-xs text-[var(--text-dim)]">{notification.company}</p>
                            <p className="text-sm leading-6 text-[var(--text-soft)]">{notification.message}</p>
                            {notification.stale_reason ? (
                              <p className="text-xs text-[var(--text-dim)]">{notification.stale_reason}</p>
                            ) : null}
                          </div>
                          <span className={`ui-status ${notification.can_remove ? "ui-status-yellow" : "ui-status-red"}`}>
                            {notification.kind === "interested_stale" ? "remove" : "watch"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Reveal>
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
            <Reveal className="ui-card p-7 sm:p-8">
              <div className="space-y-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="ui-kicker">Pipeline</p>
                    <h2 className="ui-title mt-2">Jobs already in motion.</h2>
                  </div>
                  <span className="ui-status ui-status-blue">{activePipeline.length} active</span>
                </div>

                {activePipeline.length === 0 ? (
                  <div className="ui-empty">
                    <p className="text-sm text-[var(--text-soft)]">Applied and follow-up roles will appear here after you move interested jobs into apply mode.</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {activePipeline.map((item, index) => (
                      <TrackedJobCard
                        key={item.application_id}
                        item={item}
                        index={index}
                        statusSaving={statusSaving[item.application_id]}
                        preparingApply={false}
                        removing={false}
                        onStatusChange={handleStatusChange}
                        onPrepareApply={handlePrepareApply}
                        onRemove={handleRemoveStale}
                      />
                    ))}
                  </div>
                )}

                {staleApplied.length > 0 ? (
                  <div className="ui-empty">
                    <p className="text-sm text-[var(--text-soft)]">
                      {staleApplied.length} applied or in-progress role{staleApplied.length === 1 ? "" : "s"} became stale. They stay visible for now until you decide the post-closure workflow.
                    </p>
                  </div>
                ) : null}
              </div>
            </Reveal>

            <Reveal className="ui-card p-7 sm:p-8">
              <div className="space-y-5">
                <div>
                  <p className="ui-kicker">Profile snapshot</p>
                  <h2 className="ui-title mt-2">What the upcoming generator will pull from.</h2>
                </div>

                {loadingProfile ? (
                  <div className="ui-empty">Loading profile context.</div>
                ) : (
                  <div className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="ui-panel p-5">
                        <p className="ui-kicker">Selected tags</p>
                        <p className="mt-3 text-2xl font-semibold">{selectedTags.length}</p>
                      </div>
                      <div className="ui-panel p-5">
                        <p className="ui-kicker">CV records</p>
                        <p className="mt-3 text-2xl font-semibold">{education.length + experiences.length + projects.length}</p>
                      </div>
                      <div className="ui-panel p-5">
                        <p className="ui-kicker">Experiences</p>
                        <p className="mt-3 text-2xl font-semibold">{experiences.length}</p>
                      </div>
                      <div className="ui-panel p-5">
                        <p className="ui-kicker">Projects</p>
                        <p className="mt-3 text-2xl font-semibold">{projects.length}</p>
                      </div>
                    </div>
                    <div className="ui-panel p-5">
                      <p className="ui-kicker">CV header contacts</p>
                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        <div>
                          <p className="text-xs uppercase tracking-[0.16em] text-[var(--text-dim)]">Mail</p>
                          <p className="mt-1 text-sm text-[var(--text-soft)]">{user?.email ?? "—"}</p>
                        </div>
                        <div>
                          <p className="text-xs uppercase tracking-[0.16em] text-[var(--text-dim)]">Phone</p>
                          <p className="mt-1 text-sm text-[var(--text-soft)]">{user?.phone_number || "—"}</p>
                        </div>
                        <div>
                          <p className="text-xs uppercase tracking-[0.16em] text-[var(--text-dim)]">GitHub</p>
                          <p className="mt-1 break-all text-sm text-[var(--text-soft)]">{user?.github_url || "—"}</p>
                        </div>
                        <div>
                          <p className="text-xs uppercase tracking-[0.16em] text-[var(--text-dim)]">LinkedIn</p>
                          <p className="mt-1 break-all text-sm text-[var(--text-soft)]">{user?.linkedin_url || "—"}</p>
                        </div>
                        <div className="sm:col-span-2">
                          <p className="text-xs uppercase tracking-[0.16em] text-[var(--text-dim)]">Notion</p>
                          <p className="mt-1 break-all text-sm text-[var(--text-soft)]">{user?.notion_url || "—"}</p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                <div className="ui-empty">
                  <p className="text-sm text-[var(--text-soft)]">
                    The future apply flow is already routed through a dedicated backend placeholder. That is where job-specific CV generation and cover-letter storage can attach next.
                  </p>
                </div>

                {overviewError ? (
                  <div className="rounded-[1.25rem] bg-[var(--red-soft)] p-4 text-sm text-[#7f2f2f]">{overviewError}</div>
                ) : null}
              </div>
            </Reveal>
          </div>

          {staleInterested.length > 0 ? (
            <Reveal className="ui-card p-7 sm:p-8">
              <div className="space-y-5">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="ui-kicker">Stale interested jobs</p>
                    <h2 className="ui-title mt-2">Remove closed tracked roles from your database.</h2>
                  </div>
                  <span className="ui-status ui-status-yellow">{staleInterested.length} removable</span>
                </div>
                <div className="space-y-4">
                  {staleInterested.map((item, index) => (
                    <TrackedJobCard
                      key={item.application_id}
                      item={item}
                      index={index}
                      statusSaving={false}
                      preparingApply={false}
                      removing={removing[item.application_id]}
                      onStatusChange={handleStatusChange}
                      onPrepareApply={handlePrepareApply}
                      onRemove={handleRemoveStale}
                    />
                  ))}
                </div>
              </div>
            </Reveal>
          ) : null}
        </div>
      </main>
    </div>
  );
}

function TrackedJobCard({
  item,
  index,
  statusSaving,
  preparingApply,
  removing,
  onStatusChange,
  onPrepareApply,
  onRemove,
}: {
  item: ApplicationRecord;
  index: number;
  statusSaving: boolean | undefined;
  preparingApply: boolean | undefined;
  removing: boolean | undefined;
  onStatusChange: (applicationId: string, nextStatus: ApplicationStatus) => Promise<void>;
  onPrepareApply: (item: ApplicationRecord) => Promise<void>;
  onRemove: (applicationId: string) => Promise<void>;
}) {
  const canPrepareApply = item.status === "interested" && item.is_active;
  const canRemove = item.status === "interested" && !item.is_active;

  return (
    <div className="ui-panel ui-stagger" style={{ ["--index" as string]: index }}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-3 flex-1">
          <div>
            <h3 className="text-base font-semibold">{item.title}</h3>
            <p className="mt-1 text-sm text-[var(--text-soft)]">
              {item.company}{item.location ? ` · ${item.location}` : ""}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className={`ui-status ${item.is_active ? "ui-status-green" : "ui-status-red"}`}>{item.status}</span>
            {item.job_source ? <span className="ui-status ui-status-blue">{item.job_source}</span> : null}
            {item.salary_range ? <span className="ui-status ui-status-yellow">{item.salary_range}</span> : null}
            {item.posted_at ? <span className="ui-status ui-status-green">{item.posted_at.slice(0, 10)}</span> : null}
          </div>
          {item.description ? (
            <p className="text-sm leading-6 text-[var(--text-soft)] line-clamp-3">{item.description}</p>
          ) : null}
          {!item.is_active && item.stale_reason ? (
            <p className="text-sm text-[#8f4a44]">{item.stale_reason}</p>
          ) : null}
        </div>

        <div className="flex flex-col gap-3 lg:items-end">
          <select
            className="ui-select min-w-[10rem]"
            value={item.status}
            disabled={Boolean(statusSaving) || !item.is_active}
            onChange={(e) => void onStatusChange(item.application_id, e.target.value as ApplicationStatus)}
          >
            {STATUS_ORDER.map((statusValue) => (
              <option key={statusValue} value={statusValue}>{statusValue}</option>
            ))}
          </select>

          <div className="flex flex-wrap gap-3 lg:justify-end">
            {item.source_url || item.apply_url ? (
              <a
                href={item.apply_url || item.source_url || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="ui-button ui-button-secondary"
              >
                View listing
              </a>
            ) : null}

            {canPrepareApply ? (
              <button
                type="button"
                className="ui-button"
                disabled={Boolean(preparingApply)}
                onClick={() => void onPrepareApply(item)}
              >
                {preparingApply ? "Preparing" : "Apply"}
              </button>
            ) : null}

            {canRemove ? (
              <button
                type="button"
                className="ui-icon-button ui-icon-button-danger"
                aria-label={`Remove ${item.title}`}
                disabled={Boolean(removing)}
                onClick={() => void onRemove(item.application_id)}
              >
                {removing ? "..." : "×"}
              </button>
            ) : null}
          </div>

          {canPrepareApply ? (
            <p className="max-w-xs text-right text-xs text-[var(--text-dim)]">
              Placeholder apply path is active here. Your custom CV and cover letter generator can attach to this button next.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
