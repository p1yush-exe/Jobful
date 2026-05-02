"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { ProtectedRoute } from "@/components/auth/protected-route";
import { Reveal } from "@/components/reveal";
import { SiteHeader } from "@/components/site-header";
import { TagSelector } from "@/components/onboarding/tag-selector";
import { useAuth } from "@/context/auth-context";
import {
  confirmCV,
  generateTagsFromCV,
  getCVData,
  getOnboardingState,
  saveSelectedTags,
  updateUserAccount,
  uploadCV,
  type EducationPreview,
  type ExperiencePreview,
  type ProjectPreview,
  type Tag,
} from "@/services/auth";

const EXPERIENCE_TYPES = [
  "internship", "freelance", "full_time", "part_time", "unpaid_internship", "advisor",
];

const DEGREE_LEVELS = [
  { value: "high_school", label: "High School" },
  { value: "diploma", label: "Diploma / Certificate" },
  { value: "ug", label: "Undergraduate (Bachelor's)" },
  { value: "pg", label: "Postgraduate (Master's / MBA)" },
  { value: "phd", label: "PhD / Doctorate" },
  { value: "other", label: "Other" },
];

const EMPTY_EDU: EducationPreview = {
  institution: "", degree: "", degree_level: "ug",
  field_of_study: null, start_date: null, end_date: null, grade: null, description: null,
  tag: "research",
};

const EMPTY_EXP: ExperiencePreview = {
  company: "", location: null, role: "", experience_type: "full_time",
  start_date: "", end_date: null, description: null, tag: null, keywords: [],
};

const EMPTY_PROJ: ProjectPreview = {
  name: "", description: null, github_url: null, demo_url: null, tag: null, keywords: [],
};

export default function OnboardingPage() {
  return (
    <ProtectedRoute requireOnboardingComplete={false}>
      <EditProfileContent />
    </ProtectedRoute>
  );
}

function EditProfileContent() {
  const router = useRouter();
  const { session, setSession } = useAuth();

  // account fields
  const [fullName, setFullName] = useState("");
  const [rawJobTitle, setRawJobTitle] = useState("");
  const [bio, setBio] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [notionUrl, setNotionUrl] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showPasswordField, setShowPasswordField] = useState(false);

  // tags
  const [allTags, setAllTags] = useState<Tag[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);

  // cv data
  const [education, setEducation] = useState<EducationPreview[]>([]);
  const [experiences, setExperiences] = useState<ExperiencePreview[]>([]);
  const [projects, setProjects] = useState<ProjectPreview[]>([]);

  // cv upload
  const [cvFile, setCvFile] = useState<File | null>(null);
  const [cvParsing, setCvParsing] = useState(false);
  const [cvError, setCvError] = useState<string | null>(null);
  const [cvParsed, setCvParsed] = useState(false);
  const [detectedCvEmail, setDetectedCvEmail] = useState<string | null>(null);

  const [generatingTags, setGeneratingTags] = useState(false);
  const [tagGenerationMessage, setTagGenerationMessage] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!session) return;
    const token = session.access_token;

    Promise.all([
      getOnboardingState(token),
      getCVData(token),
    ])
      .then(([state, cvData]) => {
        setFullName(session.user.full_name);
        setRawJobTitle(state.raw_job_title);
        setBio(state.bio ?? "");
        setPhoneNumber(session.user.phone_number ?? "");
        setGithubUrl(session.user.github_url ?? "");
        setLinkedinUrl(session.user.linkedin_url ?? "");
        setNotionUrl(session.user.notion_url ?? "");
        setDetectedCvEmail(null);
        setAllTags(state.assigned_tags);
        setSelectedTagIds(state.selected_tags.map((t) => t.tag_id));
        setEducation((cvData.education ?? []).map((e) => ({
          institution: e.institution,
          degree: e.degree,
          degree_level: e.degree_level,
          field_of_study: e.field_of_study,
          start_date: e.start_date,
          end_date: e.end_date,
          grade: e.grade,
          description: e.description,
          tag: (e as unknown as { tag: string }).tag ?? "research",
        })));
        setExperiences(cvData.experiences.map((e) => ({
          company: e.company,
          location: e.location,
          role: e.role,
          experience_type: e.experience_type,
          start_date: e.start_date ?? "",
          end_date: e.end_date ?? null,
          description: e.description,
          tag: e.tag,
          keywords: e.keywords ?? [],
        })));
        setProjects(cvData.projects.map((p) => ({
          name: p.name,
          description: p.description,
          github_url: p.github_url ?? null,
          demo_url: p.demo_url ?? null,
          tag: p.tag,
          keywords: p.keywords ?? [],
        })));
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load profile"))
      .finally(() => setLoading(false));
  }, [session]);

  function toggleTag(tagId: string) {
    setTagGenerationMessage(null);
    setSelectedTagIds((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId],
    );
  }

  function updateEdu<K extends keyof EducationPreview>(i: number, k: K, v: EducationPreview[K]) {
    setEducation((prev) => prev.map((e, idx) => idx === i ? { ...e, [k]: v } : e));
  }

  function updateExp<K extends keyof ExperiencePreview>(i: number, k: K, v: ExperiencePreview[K]) {
    setExperiences((prev) => prev.map((e, idx) => idx === i ? { ...e, [k]: v } : e));
  }

  function updateProj<K extends keyof ProjectPreview>(i: number, k: K, v: ProjectPreview[K]) {
    setProjects((prev) => prev.map((p, idx) => idx === i ? { ...p, [k]: v } : p));
  }

  function deriveTagIdsFromDraft() {
    const tagNameToId = new Map(allTags.map((tag) => [tag.tag_name, tag.tag_id]));
    const nextTagIds = new Set<string>();

    for (const edu of education) {
      const tagId = tagNameToId.get(edu.tag);
      if (tagId) nextTagIds.add(tagId);
    }

    for (const exp of experiences) {
      if (!exp.tag) continue;
      const tagId = tagNameToId.get(exp.tag);
      if (tagId) nextTagIds.add(tagId);
    }

    for (const proj of projects) {
      if (!proj.tag) continue;
      const tagId = tagNameToId.get(proj.tag);
      if (tagId) nextTagIds.add(tagId);
    }

    return Array.from(nextTagIds);
  }

  async function handleGenerateTags() {
    if (!session) return;
    setGeneratingTags(true);
    setTagGenerationMessage(null);
    try {
      const draftTagIds = deriveTagIdsFromDraft();
      if (draftTagIds.length > 0) {
        setSelectedTagIds(draftTagIds);
        setTagGenerationMessage(null);
        return;
      }

      const result = await generateTagsFromCV(session.access_token);
      const savedTagIds = result.tags.map((t) => t.tag_id);
      setSelectedTagIds(savedTagIds);
      if (savedTagIds.length === 0) {
        setTagGenerationMessage("We couldn't find tags. Please select tags manually.");
      }
    } catch {
      setTagGenerationMessage("We couldn't find tags. Please select tags manually.");
    } finally {
      setGeneratingTags(false);
    }
  }

  async function handleCVParse() {
    if (!session || !cvFile) return;
    setCvParsing(true);
    setCvError(null);
    setCvParsed(false);
    try {
      const preview = await uploadCV(session.access_token, cvFile);
      // pre-fill form fields — user can edit before saving
      if (preview.education?.length) {
        setEducation(preview.education.map((e) => ({
          institution: e.institution,
          degree: e.degree,
          degree_level: e.degree_level,
          field_of_study: e.field_of_study,
          start_date: e.start_date,
          end_date: e.end_date,
          grade: e.grade,
          description: e.description,
          tag: e.tag,
        })));
      }
      if (preview.experiences?.length) {
        setExperiences(preview.experiences);
      }
      if (preview.projects?.length) {
        setProjects(preview.projects.map((p) => ({
          name: p.name,
          description: p.description,
          github_url: p.github_url ?? null,
          demo_url: p.demo_url ?? null,
          tag: p.tag,
          keywords: p.keywords ?? [],
        })));
      }
      setDetectedCvEmail(preview.contact_details.email);
      if (preview.contact_details.phone_number) setPhoneNumber(preview.contact_details.phone_number);
      if (preview.contact_details.github_url) setGithubUrl(preview.contact_details.github_url);
      if (preview.contact_details.linkedin_url) setLinkedinUrl(preview.contact_details.linkedin_url);
      if (preview.contact_details.notion_url) setNotionUrl(preview.contact_details.notion_url);
      setCvParsed(true);
    } catch (err) {
      setCvError(err instanceof Error ? err.message : "CV parse failed");
    } finally {
      setCvParsing(false);
    }
  }

  async function handleSave() {
    if (!session) return;
    setSaving(true);
    setError(null);
    const token = session.access_token;

    try {
      // 1. tags first — so updateUserAccount sees the correct selected_tags_count
      if (selectedTagIds.length > 0) {
        await saveSelectedTags(token, selectedTagIds);
      }

      // 2. CV data — also inserts cv-derived tags into user_selected_tags
      await confirmCV(token, {
        education,
        experiences,
        projects,
        suggested_tags: [],
      });

      // 3. account last — selected_tags_count is now accurate, onboarding_complete will be correct
      const updatedUser = await updateUserAccount(token, {
        full_name: fullName.trim() || session.user.full_name,
        raw_job_title: rawJobTitle,
        bio: bio || null,
        phone_number: phoneNumber.trim() || null,
        github_url: githubUrl.trim() || null,
        linkedin_url: linkedinUrl.trim() || null,
        notion_url: notionUrl.trim() || null,
        password: showPasswordField && newPassword ? newPassword : null,
      });
      setSession({ ...session, user: { ...session.user, ...updatedUser } });

      setSaved(true);
      window.location.assign("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="ui-shell">
        <SiteHeader />
        <main className="px-4 pt-8 sm:px-6">
          <div className="ui-wrap">
            <div className="ui-card p-8"><p className="ui-kicker">Loading your profile</p></div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="ui-shell">
      <SiteHeader />

      {/* Sticky cancel + save bar */}
      <div className="sticky top-20 z-30 px-4 sm:px-6">
        <div className="ui-wrap">
          <div className="flex items-center justify-between rounded-2xl bg-[rgba(251,250,246,0.9)] px-4 py-3 shadow-[0_8px_24px_rgba(52,61,46,0.08)] backdrop-blur-xl">
            <p className="text-sm font-medium text-[var(--text-soft)]">Editing profile</p>
            <div className="flex gap-3">
              <Link
                href="/dashboard"
                className="inline-flex items-center gap-2 rounded-full border border-red-300 bg-red-50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-red-600 transition hover:bg-red-100"
              >
                Cancel
              </Link>
              <button
                className="ui-button px-5 py-2 text-xs"
                onClick={() => void handleSave()}
                disabled={saving || saved}
              >
                {saved ? "Saved ✓" : saving ? "Saving..." : "Save details"}
              </button>
            </div>
          </div>
        </div>
      </div>

      <main className="px-4 pb-12 pt-4 sm:px-6">
        <div className="ui-wrap space-y-6">

          {error ? (
            <div className="rounded-[1.25rem] bg-[var(--red-soft)] p-4 text-sm text-[#7f2f2f]">{error}</div>
          ) : null}

          {/* Account details */}
          <Reveal className="ui-card p-7 sm:p-8">
            <div className="space-y-5">
              <div>
                <p className="ui-kicker">Account</p>
                <h2 className="ui-title mt-2">Your details.</h2>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="ui-label block">Full name</label>
                  <input className="ui-input" value={fullName} onChange={(e) => setFullName(e.target.value)} />
                </div>
                <div>
                  <label className="ui-label block">Email</label>
                  <input className="ui-input opacity-60" value={session?.user.email.toLowerCase() ?? ""} readOnly />
                </div>
                <div>
                  <label className="ui-label block">Target role</label>
                  <input className="ui-input" value={rawJobTitle} onChange={(e) => setRawJobTitle(e.target.value)} placeholder="Full Stack Developer, ML Engineer…" />
                </div>
                <div className="flex flex-col justify-end">
                  {!showPasswordField ? (
                    <button
                      type="button"
                      className="ui-button ui-button-secondary w-full"
                      onClick={() => setShowPasswordField(true)}
                    >
                      Change password
                    </button>
                  ) : (
                    <div>
                      <label className="ui-label block">New password</label>
                      <input className="ui-input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} placeholder="8+ characters" autoComplete="new-password" />
                    </div>
                  )}
                </div>
                <div className="sm:col-span-2">
                  <label className="ui-label block">Bio</label>
                  <textarea className="ui-textarea" value={bio} onChange={(e) => setBio(e.target.value)} placeholder="Brief background summary" />
                </div>
              </div>
            </div>
          </Reveal>

          {/* CV import — parses PDF and pre-fills education, experiences, projects */}
          <Reveal className="ui-card p-7 sm:p-8">
            <div className="space-y-4">
              <div>
                <p className="ui-kicker">CV import</p>
                <h2 className="ui-title mt-2">
                  {session?.user.cv_uploaded ? "Upload new CV." : "Upload your CV."}
                </h2>
                <p className="mt-3 text-sm leading-6 text-[var(--text-soft)]">
                  {session?.user.cv_uploaded
                    ? "Replace your current CV data — Groq will re-parse and pre-fill education, experiences, and projects below."
                    : "Groq parses your CV and pre-fills education, experiences, and projects below."}
                  {" "}Review and edit anything before saving — nothing is written until you click Save.
                </p>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                <label className="ui-button ui-button-secondary flex-1 cursor-pointer text-center">
                  <input
                    type="file"
                    accept="application/pdf"
                    className="hidden"
                    onChange={(e) => {
                      setCvFile(e.target.files?.[0] ?? null);
                      setCvParsed(false);
                      setCvError(null);
                    }}
                  />
                  {cvFile ? cvFile.name : "Choose PDF (under 5 MB)"}
                </label>
                <button
                  type="button"
                  className="ui-button"
                  disabled={!cvFile || cvParsing}
                  onClick={() => void handleCVParse()}
                >
                  {cvParsing ? "Parsing" : "Parse CV"}
                </button>
              </div>
              {cvError ? (
                <p className="text-sm text-[#7f2f2f]">{cvError}</p>
              ) : cvParsed ? (
                <p className="text-sm text-[var(--green)]">
                  Parsed - education, experiences, projects, and available contact links pre-filled below. Review then save.
                </p>
              ) : null}
            </div>
          </Reveal>

          <Reveal className="ui-card p-7 sm:p-8">
            <div className="space-y-5">
              <div>
                <p className="ui-kicker">Contact details</p>
                <h2 className="ui-title mt-2">Links and header info.</h2>
                <p className="mt-3 text-sm leading-6 text-[var(--text-soft)]">
                  These fields sit after CV import so the parser can fill them first. Account email stays authoritative, but the CV-detected email is shown for reference.
                </p>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="ui-label block">Phone number</label>
                  <input className="ui-input" value={phoneNumber} onChange={(e) => setPhoneNumber(e.target.value)} placeholder="+91 98XXXXXXXX" />
                </div>
                <div>
                  <label className="ui-label block">Detected in CV</label>
                  <input className="ui-input opacity-60" value={detectedCvEmail ?? "No email found in CV"} readOnly />
                </div>
                <div>
                  <label className="ui-label block">GitHub URL</label>
                  <input className="ui-input" value={githubUrl} onChange={(e) => setGithubUrl(e.target.value)} placeholder="https://github.com/username" />
                </div>
                <div>
                  <label className="ui-label block">LinkedIn URL</label>
                  <input className="ui-input" value={linkedinUrl} onChange={(e) => setLinkedinUrl(e.target.value)} placeholder="https://linkedin.com/in/username" />
                </div>
                <div className="sm:col-span-2">
                  <label className="ui-label block">Notion URL</label>
                  <input className="ui-input" value={notionUrl} onChange={(e) => setNotionUrl(e.target.value)} placeholder="https://www.notion.so/..." />
                </div>
              </div>
            </div>
          </Reveal>

          {/* Education */}
          <Reveal className="ui-card p-7 sm:p-8">
            <div className="space-y-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="ui-kicker">Education</p>
                  <h2 className="ui-title mt-2">{education.length} {education.length === 1 ? "qualification" : "qualifications"}.</h2>
                </div>
                <button
                  type="button"
                  className="ui-button ui-button-secondary"
                  onClick={() => setEducation((prev) => [...prev, { ...EMPTY_EDU }])}
                >
                  + Add education
                </button>
              </div>

              <div className="space-y-4">
                {education.map((edu, i) => (
                  <div key={i} className="ui-panel ui-stagger" style={{ ["--index" as string]: i }}>
                    <div className="mb-3 flex items-center justify-between">
                      <p className="ui-kicker">{edu.institution || "New qualification"}</p>
                      <button
                        type="button"
                        onClick={() => setEducation((prev) => prev.filter((_, idx) => idx !== i))}
                        className="rounded-full px-3 py-1 text-xs font-medium text-red-500 hover:bg-red-50 transition"
                      >
                        Remove
                      </button>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="ui-label block">Institution</label>
                        <input className="ui-input" value={edu.institution} onChange={(e) => updateEdu(i, "institution", e.target.value)} placeholder="University / College name" />
                      </div>
                      <div>
                        <label className="ui-label block">Degree</label>
                        <input className="ui-input" value={edu.degree} onChange={(e) => updateEdu(i, "degree", e.target.value)} placeholder="Bachelor of Technology, MBA…" />
                      </div>
                      <div>
                        <label className="ui-label block">Level</label>
                        <select className="ui-select" value={edu.degree_level} onChange={(e) => updateEdu(i, "degree_level", e.target.value)}>
                          {DEGREE_LEVELS.map((d) => (
                            <option key={d.value} value={d.value}>{d.label}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="ui-label block">Field of study</label>
                        <input className="ui-input" value={edu.field_of_study ?? ""} onChange={(e) => updateEdu(i, "field_of_study", e.target.value || null)} placeholder="Computer Science, Finance…" />
                      </div>
                      <div>
                        <label className="ui-label block">Start date</label>
                        <input className="ui-input" type="date" value={edu.start_date ?? ""} onChange={(e) => updateEdu(i, "start_date", e.target.value || null)} />
                      </div>
                      <div>
                        <label className="ui-label block">End date (blank = ongoing)</label>
                        <input className="ui-input" type="date" value={edu.end_date ?? ""} onChange={(e) => updateEdu(i, "end_date", e.target.value || null)} />
                      </div>
                      <div>
                        <label className="ui-label block">Grade / GPA / percentage</label>
                        <input className="ui-input" value={edu.grade ?? ""} onChange={(e) => updateEdu(i, "grade", e.target.value || null)} placeholder="9.1 CGPA, 85%, First class…" />
                      </div>
                      <div className="sm:col-span-2">
                        <label className="ui-label block">Notes</label>
                        <textarea className="ui-textarea" style={{ minHeight: "5rem" }} value={edu.description ?? ""} onChange={(e) => updateEdu(i, "description", e.target.value || null)} placeholder="Relevant coursework, awards, thesis topic…" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {education.length === 0 ? (
                <div className="ui-empty text-center text-sm">No qualifications yet. Click "Add education" to add one.</div>
              ) : null}
            </div>
          </Reveal>

          {/* Experiences */}
          <Reveal className="ui-card p-7 sm:p-8">
            <div className="space-y-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="ui-kicker">Experience</p>
                  <h2 className="ui-title mt-2">{experiences.length} {experiences.length === 1 ? "role" : "roles"}.</h2>
                </div>
                <button
                  type="button"
                  className="ui-button ui-button-secondary"
                  onClick={() => setExperiences((prev) => [...prev, { ...EMPTY_EXP }])}
                >
                  + Add experience
                </button>
              </div>

              <div className="space-y-4">
                {experiences.map((exp, i) => (
                  <div key={i} className="ui-panel ui-stagger" style={{ ["--index" as string]: i }}>
                    <div className="mb-3 flex items-center justify-between">
                      <p className="ui-kicker">{exp.company || "New experience"}</p>
                      <button
                        type="button"
                        onClick={() => setExperiences((prev) => prev.filter((_, idx) => idx !== i))}
                        className="rounded-full px-3 py-1 text-xs font-medium text-red-500 hover:bg-red-50 transition"
                      >
                        Remove
                      </button>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="ui-label block">Company</label>
                        <input className="ui-input" value={exp.company} onChange={(e) => updateExp(i, "company", e.target.value)} />
                      </div>
                      <div>
                        <label className="ui-label block">Role</label>
                        <input className="ui-input" value={exp.role} onChange={(e) => updateExp(i, "role", e.target.value)} />
                      </div>
                      <div>
                        <label className="ui-label block">Location</label>
                        <input className="ui-input" value={exp.location ?? ""} onChange={(e) => updateExp(i, "location", e.target.value || null)} />
                      </div>
                      <div>
                        <label className="ui-label block">Type</label>
                        <select className="ui-select" value={exp.experience_type} onChange={(e) => updateExp(i, "experience_type", e.target.value)}>
                          {EXPERIENCE_TYPES.map((t) => (
                            <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="ui-label block">Start date</label>
                        <input className="ui-input" type="date" value={exp.start_date} onChange={(e) => updateExp(i, "start_date", e.target.value)} />
                      </div>
                      <div>
                        <label className="ui-label block">End date (blank = current)</label>
                        <input className="ui-input" type="date" value={exp.end_date ?? ""} onChange={(e) => updateExp(i, "end_date", e.target.value || null)} />
                      </div>
                      <div className="sm:col-span-2">
                        <label className="ui-label block">Description</label>
                        <textarea className="ui-textarea" value={exp.description ?? ""} onChange={(e) => updateExp(i, "description", e.target.value || null)} />
                      </div>
                      <div className="sm:col-span-2">
                        <label className="ui-label block">Tech keywords (comma-separated)</label>
                        <input
                          className="ui-input"
                          value={exp.keywords.join(", ")}
                          onChange={(e) => updateExp(i, "keywords", e.target.value.split(",").map((k) => k.trim()).filter(Boolean))}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {experiences.length === 0 ? (
                <div className="ui-empty text-center text-sm">No experiences yet. Click "Add experience" to add one.</div>
              ) : null}
            </div>
          </Reveal>

          {/* Projects */}
          <Reveal className="ui-card p-7 sm:p-8">
            <div className="space-y-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="ui-kicker">Projects</p>
                  <h2 className="ui-title mt-2">{projects.length} {projects.length === 1 ? "project" : "projects"}.</h2>
                </div>
                <button
                  type="button"
                  className="ui-button ui-button-secondary"
                  onClick={() => setProjects((prev) => [...prev, { ...EMPTY_PROJ }])}
                >
                  + Add project
                </button>
              </div>

              <div className="space-y-4">
                {projects.map((proj, i) => (
                  <div key={i} className="ui-panel ui-stagger" style={{ ["--index" as string]: i }}>
                    <div className="mb-3 flex items-center justify-between">
                      <p className="ui-kicker">{proj.name || "New project"}</p>
                      <button
                        type="button"
                        onClick={() => setProjects((prev) => prev.filter((_, idx) => idx !== i))}
                        className="rounded-full px-3 py-1 text-xs font-medium text-red-500 hover:bg-red-50 transition"
                      >
                        Remove
                      </button>
                    </div>
                    <div className="grid gap-4">
                      <div>
                        <label className="ui-label block">Project name</label>
                        <input className="ui-input" value={proj.name} onChange={(e) => updateProj(i, "name", e.target.value)} />
                      </div>
                      <div>
                        <label className="ui-label block">Description</label>
                        <textarea className="ui-textarea" value={proj.description ?? ""} onChange={(e) => updateProj(i, "description", e.target.value || null)} />
                      </div>
                      <div>
                        <label className="ui-label block">GitHub URL</label>
                        <input
                          className="ui-input"
                          value={proj.github_url ?? ""}
                          onChange={(e) => updateProj(i, "github_url", e.target.value || null)}
                          placeholder="https://github.com/username/repo"
                        />
                      </div>
                      <div>
                        <label className="ui-label block">Hosted / demo URL</label>
                        <input
                          className="ui-input"
                          value={proj.demo_url ?? ""}
                          onChange={(e) => updateProj(i, "demo_url", e.target.value || null)}
                          placeholder="https://project-demo.example"
                        />
                      </div>
                      <div>
                        <label className="ui-label block">Tech keywords (comma-separated)</label>
                        <input
                          className="ui-input"
                          value={proj.keywords.join(", ")}
                          onChange={(e) => updateProj(i, "keywords", e.target.value.split(",").map((k) => k.trim()).filter(Boolean))}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {projects.length === 0 ? (
                <div className="ui-empty text-center text-sm">No projects yet. Click "Add project" to add one.</div>
              ) : null}
            </div>
          </Reveal>

          {/* Tags — last, generated from education + experience + projects */}
          <Reveal className="ui-card p-7 sm:p-8">
            <div className="space-y-5">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="ui-kicker">Tags</p>
                  <h2 className="ui-title mt-2">Your skill taxonomy.</h2>
                  <p className="mt-3 text-sm leading-6 text-[var(--text-soft)]">
                    Click <strong>Generate tags</strong> to pre-select all tags linked to your education, experiences, and projects. Then add or remove any you like.
                  </p>
                </div>
                <div className="flex flex-col gap-2 shrink-0">
                  <button
                    type="button"
                    className="ui-button"
                    disabled={generatingTags}
                    onClick={() => void handleGenerateTags()}
                  >
                    {generatingTags ? "Generating" : "Generate tags"}
                  </button>
                  <span className="ui-status ui-status-green text-center">{selectedTagIds.length} selected</span>
                  {tagGenerationMessage ? (
                    <p className="max-w-56 text-center text-xs leading-5 text-[#7f2f2f]">{tagGenerationMessage}</p>
                  ) : null}
                </div>
              </div>
              <TagSelector tags={allTags} selectedTagIds={selectedTagIds} onToggle={toggleTag} />
            </div>
          </Reveal>

        </div>
      </main>
    </div>
  );
}
