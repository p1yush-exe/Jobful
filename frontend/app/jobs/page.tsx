"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ProtectedRoute } from "@/components/auth/protected-route";
import { Reveal } from "@/components/reveal";
import { SiteHeader } from "@/components/site-header";
import { useAuth } from "@/context/auth-context";
import { useJobTracker } from "@/context/job-tracker-context";
import {
  getOnboardingState,
  searchJobs,
  trackJob,
  type ApplicationRecord,
  type JobResult,
  type Tag,
} from "@/services/auth";

const JOBS_PER_PAGE = 10;
const DAY_MS = 86_400_000;

const COUNTRIES = ["in", "us", "gb", "au", "ca", "de", "sg", "ae"];
const EMP_TYPES = [
  { value: "", label: "Any type" },
  { value: "FULLTIME", label: "Full time" },
  { value: "PARTTIME", label: "Part time" },
  { value: "CONTRACTOR", label: "Contract" },
  { value: "INTERN", label: "Internship" },
];
const WORK_MODELS = [
  { value: "", label: "Any model" },
  { value: "remote", label: "Remote" },
  { value: "hybrid", label: "Hybrid" },
  { value: "onsite", label: "On-site" },
];

export default function JobsPage() {
  return (
    <ProtectedRoute>
      <JobsContent />
    </ProtectedRoute>
  );
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

function ageLabel(postedAt: string): "day" | "week" | "older" | "unknown" {
  if (!postedAt) return "unknown";
  try {
    const age = Date.now() - new Date(postedAt).getTime();
    if (age <= DAY_MS) return "day";
    if (age <= 7 * DAY_MS) return "week";
    return "older";
  } catch {
    return "unknown";
  }
}

function JobCard({
  job,
  index,
  tracked,
  busy,
  onTrack,
}: {
  job: JobResult;
  index: number;
  tracked: ApplicationRecord | undefined;
  busy: boolean;
  onTrack: (job: JobResult) => void;
}) {
  const [open, setOpen] = useState(false);
  const hasFit = Boolean(job.why_fit || job.tech_stack?.length || job.matching_experiences?.length || job.matching_projects?.length);

  return (
    <div className="ui-panel ui-stagger" style={{ ["--index" as string]: index }}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex-1 space-y-3">
          <div>
            <h3 className="text-base font-semibold">{job.title}</h3>
            <p className="mt-1 text-sm text-[var(--text-soft)]">
              {job.company}{job.location ? ` · ${job.location}` : ""}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <span className="ui-status ui-status-blue">{job.source}</span>
            {job.employment_type ? (
              <span className="ui-status ui-status-yellow">
                {job.employment_type.toLowerCase().replace("_", " ")}
              </span>
            ) : null}
            {job.work_model ? <span className="ui-status ui-status-green">{job.work_model}</span> : null}
            {job.salary_range ? <span className="ui-status ui-status-yellow">{job.salary_range}</span> : null}
            {job.posted_at ? <span className="ui-status">{job.posted_at.slice(0, 10)}</span> : null}
            {job.gate_provider === "algorithmic" ? (
              <span className="ui-status" title="Matched via skill overlap">skill match</span>
            ) : job.gate_provider === "ai" || job.gate_provider === "groq" ? (
              <span className="ui-status ui-status-green" title="Verified by AI gate">AI verified</span>
            ) : null}
            {tracked ? (
              <span className={`ui-status ${tracked.is_active ? "ui-status-green" : "ui-status-red"}`}>
                {tracked.status}
              </span>
            ) : null}
          </div>

          {/* Tech stack chips */}
          {job.tech_stack && job.tech_stack.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {job.tech_stack.map((t) => (
                <span key={t} className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-2 py-0.5 text-xs font-mono text-[var(--text-soft)]">
                  {t}
                </span>
              ))}
            </div>
          ) : null}

          {/* Brief description */}
          <p className="text-sm leading-6 text-[var(--text-soft)] line-clamp-2">
            {job.brief_description || job.description}
          </p>

          {/* Know more */}
          {hasFit ? (
            <div>
              <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                className="text-xs font-medium text-[var(--green)] underline-offset-2 hover:underline"
              >
                {open ? "▲ Less" : "▼ Know more"}
              </button>
              {open ? (
                <div className="mt-3 space-y-2 rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-4 text-sm leading-6">
                  {job.why_fit ? (
                    <div>
                      <p className="ui-kicker mb-1">Why you fit</p>
                      <p className="text-[var(--text-soft)]">{job.why_fit}</p>
                    </div>
                  ) : null}
                  {job.matching_experiences && job.matching_experiences.length > 0 ? (
                    <div>
                      <p className="ui-kicker mb-1">Matching experience</p>
                      <ul className="list-inside list-disc text-[var(--text-soft)]">
                        {job.matching_experiences.map((e, i) => <li key={i}>{e}</li>)}
                      </ul>
                    </div>
                  ) : null}
                  {job.matching_projects && job.matching_projects.length > 0 ? (
                    <div>
                      <p className="ui-kicker mb-1">Matching projects</p>
                      <ul className="list-inside list-disc text-[var(--text-soft)]">
                        {job.matching_projects.map((p, i) => <li key={i}>{p}</li>)}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        {/* Actions */}
        <div className="flex shrink-0 flex-wrap gap-3">
          {job.apply_url || job.source_url ? (
            <a
              href={job.apply_url || job.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="ui-button ui-button-secondary"
            >
              Open listing
            </a>
          ) : null}
          <button
            type="button"
            className="ui-button"
            disabled={busy || Boolean(tracked)}
            onClick={() => onTrack(job)}
          >
            {tracked ? "Tracked" : busy ? (
              <span className="flex items-center gap-2"><Spinner />Saving</span>
            ) : "Track"}
          </button>
        </div>
      </div>
    </div>
  );
}

function BucketSection({
  label,
  jobs,
  offset,
  tracked,
  busy,
  onTrack,
}: {
  label: string;
  jobs: JobResult[];
  offset: number;
  tracked: Map<string, ApplicationRecord>;
  busy: Record<string, boolean>;
  onTrack: (job: JobResult) => void;
}) {
  if (jobs.length === 0) return null;
  return (
    <div className="space-y-3">
      <p className="ui-kicker">{label} · {jobs.length} role{jobs.length === 1 ? "" : "s"}</p>
      {jobs.map((job, i) => {
        const key = `${job.source}:${job.external_id}`;
        return (
          <JobCard
            key={key}
            job={job}
            index={offset + i}
            tracked={tracked.get(key)}
            busy={Boolean(busy[key])}
            onTrack={onTrack}
          />
        );
      })}
    </div>
  );
}

function JobsContent() {
  const { session } = useAuth();
  const { overview, refreshOverview, loading: overviewLoading } = useJobTracker();

  const [userTags, setUserTags] = useState<Tag[]>([]);
  const [selectedTagId, setSelectedTagId] = useState<string | null>(null);
  const [country, setCountry] = useState("in");
  const [empType, setEmpType] = useState("");
  const [workModel, setWorkModel] = useState("");
  const [salaryMin, setSalaryMin] = useState(0);
  const [allowUnspecifiedPay, setAllowUnspecifiedPay] = useState(true);

  const [results, setResults] = useState<JobResult[]>([]);
  const [visibleCount, setVisibleCount] = useState(JOBS_PER_PAGE);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [tracking, setTracking] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!session) return;
    void getOnboardingState(session.access_token)
      .then((state) => setUserTags(state.selected_tags))
      .catch(() => {});
  }, [session]);

  const trackedApplications = overview?.items ?? [];
  const trackedByKey = new Map<string, ApplicationRecord>();
  for (const item of trackedApplications) {
    const key = `${item.job_source ?? "unknown"}:${item.external_job_key ?? ""}`;
    if (item.external_job_key) trackedByKey.set(key, item);
  }

  function selectTag(tagId: string) {
    setSelectedTagId((prev) => {
      if (prev === tagId) return null;
      setResults([]);
      setSearched(false);
      setVisibleCount(JOBS_PER_PAGE);
      setSearchError(null);
      return tagId;
    });
  }

  async function handleSearch() {
    if (!session || !selectedTagId) return;
    const tagName = userTags.find((t) => t.tag_id === selectedTagId)?.tag_name;
    if (!tagName) return;

    setSearching(true);
    setSearchError(null);
    setResults([]);
    setVisibleCount(JOBS_PER_PAGE);

    try {
      const res = await searchJobs(session.access_token, {
        q: tagName,
        country,
        employment_type: empType,
        work_model: workModel,
        salary_min: salaryMin,
        allow_unspecified_pay: allowUnspecifiedPay,
      });

      // dedupe by source:external_id
      const seen = new Set<string>();
      const deduped: JobResult[] = [];
      for (const job of res.items) {
        const key = `${job.source}:${job.external_id}`;
        if (!seen.has(key)) { seen.add(key); deduped.push(job); }
      }
      setResults(deduped);
      setSearched(true);
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  async function handleTrack(job: JobResult) {
    if (!session) return;
    const key = `${job.source}:${job.external_id}`;
    setTracking((c) => ({ ...c, [key]: true }));
    try {
      await trackJob(session.access_token, job, "interested");
      await refreshOverview();
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Could not track this job.");
    } finally {
      setTracking((c) => ({ ...c, [key]: false }));
    }
  }

  // Slice and bucket
  const visible = results.slice(0, visibleCount);
  const byAge = {
    day:  visible.filter((j) => ageLabel(j.posted_at) === "day"),
    week: visible.filter((j) => ageLabel(j.posted_at) === "week"),
    older: visible.filter((j) => ageLabel(j.posted_at) === "older" || ageLabel(j.posted_at) === "unknown"),
  };
  const hasMore = visibleCount < results.length;
  const staleInterested = trackedApplications.filter((i) => !i.is_active && i.status === "interested");
  const activePipeline = trackedApplications.filter((i) => i.is_active);
  const selectedTagName = userTags.find((t) => t.tag_id === selectedTagId)?.tag_name ?? null;

  return (
    <div className="ui-shell">
      <SiteHeader />

      <main className="px-4 pb-8 pt-6 sm:px-6 sm:pb-10 sm:pt-8">
        <div className="ui-wrap space-y-6">

          {/* Hero */}
          <Reveal className="ui-card p-7 sm:p-10">
            <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-end">
              <div className="space-y-5">
                <p className="ui-eyebrow w-fit"><span className="ui-dot" />Job sourcing</p>
                <h1 className="ui-title max-w-3xl">Pick one tag. Filtered, relevant roles only.</h1>
                <p className="ui-lead">
                  Results are pre-filtered algorithmically against your experience and skills, then verified by AI where needed. Only roles that actually fit come through.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  { label: "Tracked", value: `${overview?.summary.total ?? 0}` },
                  { label: "Active", value: `${overview?.summary.active ?? 0}` },
                  { label: "Stale alerts", value: `${overview?.summary.stale ?? 0}` },
                  { label: "Showing", value: searched ? `${visible.length} / ${results.length}` : "—" },
                ].map((item, i) => (
                  <div key={item.label} className="ui-metric ui-stagger" style={{ ["--index" as string]: i }}>
                    <p className="ui-kicker">{item.label}</p>
                    <p className="ui-metric-value">{item.value}</p>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>

          <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">

            {/* Search setup */}
            <Reveal className="ui-card p-7 sm:p-8">
              <div className="space-y-6">
                <div>
                  <p className="ui-kicker">Tag</p>
                  <h2 className="ui-title mt-2">Select one tag to search.</h2>
                </div>

                {userTags.length === 0 ? (
                  <div className="ui-empty text-sm">
                    No selected tags yet. <Link href="/onboarding" className="underline">Complete your profile</Link> first.
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {userTags.map((tag) => (
                      <button
                        key={tag.tag_id}
                        type="button"
                        data-selected={selectedTagId === tag.tag_id}
                        onClick={() => selectTag(tag.tag_id)}
                        className="ui-chip px-4 py-2 text-sm"
                      >
                        {tag.tag_name}
                      </button>
                    ))}
                  </div>
                )}

                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  <div>
                    <label className="ui-label block">Country</label>
                    <select className="ui-select" value={country} onChange={(e) => setCountry(e.target.value)}>
                      {COUNTRIES.map((c) => <option key={c} value={c}>{c.toUpperCase()}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="ui-label block">Employment type</label>
                    <select className="ui-select" value={empType} onChange={(e) => setEmpType(e.target.value)}>
                      {EMP_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="ui-label block">Work model</label>
                    <select className="ui-select" value={workModel} onChange={(e) => setWorkModel(e.target.value)}>
                      {WORK_MODELS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="ui-label block">Min salary</label>
                    <input
                      className="ui-input"
                      type="number"
                      min={0}
                      step={10000}
                      value={salaryMin || ""}
                      onChange={(e) => setSalaryMin(Number(e.target.value) || 0)}
                      placeholder="0"
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <label className="flex items-center gap-3 text-sm text-[var(--text-soft)]">
                    <input
                      type="checkbox"
                      checked={allowUnspecifiedPay}
                      onChange={(e) => setAllowUnspecifiedPay(e.target.checked)}
                      className="h-4 w-4 accent-[var(--green)]"
                    />
                    Include jobs without stated pay
                  </label>
                  <button
                    type="button"
                    className="ui-button min-w-[140px]"
                    disabled={searching || !selectedTagId}
                    onClick={() => void handleSearch()}
                  >
                    {searching ? (
                      <span className="flex items-center justify-center gap-2">
                        <Spinner />Searching…
                      </span>
                    ) : !selectedTagName ? "Select a tag" : searched
                      ? `Search more jobs under "${selectedTagName}"`
                      : `Search "${selectedTagName}"`}
                  </button>
                </div>

                {searchError ? (
                  <div className="rounded-[1.25rem] bg-[var(--red-soft)] p-4 text-sm text-[#7f2f2f]">{searchError}</div>
                ) : null}
              </div>
            </Reveal>

            {/* Pipeline info */}
            <Reveal className="ui-card p-7 sm:p-8">
              <div className="space-y-5">
                <div>
                  <p className="ui-kicker">Filter pipeline</p>
                  <h2 className="ui-title mt-2">Only relevant roles return.</h2>
                </div>
                <div className="space-y-4">
                  <div className="ui-panel p-5">
                    <p className="text-sm font-semibold">Tier 0 — algorithmic</p>
                    <p className="mt-2 text-sm leading-6 text-[var(--text-soft)]">
                      Seniority extraction, region blocks, and skill-token overlap against your saved keywords. No API cost. Fast.
                    </p>
                  </div>
                  <div className="ui-panel p-5">
                    <p className="text-sm font-semibold">Tier 1 — AI gate</p>
                    <p className="mt-2 text-sm leading-6 text-[var(--text-soft)]">
                      Inconclusive jobs go to Groq. Returns fit analysis, tech stack, and a brief description. Only runs when algorithmic match is unclear.
                    </p>
                  </div>
                  <div className="ui-panel p-5">
                    <p className="text-sm font-semibold">Track → apply pipeline</p>
                    <p className="mt-2 text-sm leading-6 text-[var(--text-soft)]">
                      Save strong matches as interested. Custom CV + cover letter generation slots in from the dashboard.
                    </p>
                  </div>
                </div>
                <div className="ui-empty">
                  <p className="text-sm text-[var(--text-soft)]">
                    {overviewLoading ? "Refreshing." : `${activePipeline.length} active · ${staleInterested.length} stale`}
                  </p>
                </div>
              </div>
            </Reveal>
          </div>

          {/* Results */}
          {searched ? (
            results.length === 0 ? (
              <Reveal className="ui-empty p-6 text-center">
                No roles passed the filter for <strong>{selectedTagName}</strong>. Try a different tag, adjust filters, or ensure your profile keywords are filled in.
              </Reveal>
            ) : (
              <Reveal className="ui-card p-7 sm:p-8">
                <div className="space-y-6">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="ui-kicker">Results · {selectedTagName}</p>
                      <h2 className="ui-title mt-2">
                        {visible.length} of {results.length} roles shown.
                      </h2>
                    </div>
                    <span className="ui-status ui-status-green">{results.length} passed filters</span>
                  </div>

                  <BucketSection label="Last 24 hours" jobs={byAge.day} offset={0} tracked={trackedByKey} busy={tracking} onTrack={handleTrack} />
                  <BucketSection label="Last 7 days" jobs={byAge.week} offset={byAge.day.length} tracked={trackedByKey} busy={tracking} onTrack={handleTrack} />
                  <BucketSection label="Older" jobs={byAge.older} offset={byAge.day.length + byAge.week.length} tracked={trackedByKey} busy={tracking} onTrack={handleTrack} />

                  {hasMore ? (
                    <button
                      type="button"
                      className="ui-button ui-button-secondary w-full"
                      onClick={() => setVisibleCount((v) => v + JOBS_PER_PAGE)}
                    >
                      Find more — {results.length - visibleCount} remaining
                    </button>
                  ) : (
                    <p className="text-center text-sm text-[var(--text-soft)]">
                      All {results.length} filtered results shown. Switch tag or adjust filters for more.
                    </p>
                  )}
                </div>
              </Reveal>
            )
          ) : null}

        </div>
      </main>
    </div>
  );
}
