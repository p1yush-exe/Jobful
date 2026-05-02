export type SessionUser = {
  user_id: string;
  email: string;
  full_name: string;
  raw_job_title: string;
  bio: string | null;
  phone_number: string | null;
  github_url: string | null;
  linkedin_url: string | null;
  notion_url: string | null;
  email_verified_at: string | null;
  selected_tags_count: number;
  onboarding_complete: boolean;
  cv_uploaded: boolean;
  experience_years: number; // -1=none, 0=<1yr, 1=1-2yrs, N=N to N+1 yrs
};

export type AuthSession = {
  verification_required: false;
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: SessionUser;
};

export type VerificationChallenge = {
  verification_required: true;
  email: string;
  message: string;
  verification_token: string;
  resend_after_seconds: number;
  debug_code: string | null;
};

export type AuthResult = AuthSession | VerificationChallenge;

export type RegisterPayload = {
  full_name: string;
  email: string;
  password: string;
  raw_job_title: string;
  bio?: string | null;
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type RefreshPayload = {
  refresh_token: string;
};

export type ProfilePayload = {
  raw_job_title: string;
  bio?: string | null;
};

export type AccountUpdatePayload = {
  full_name: string;
  raw_job_title: string;
  bio?: string | null;
  phone_number?: string | null;
  github_url?: string | null;
  linkedin_url?: string | null;
  notion_url?: string | null;
  password?: string | null;
};

export type Tag = {
  tag_id: string;
  tag_name: string;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
const STORAGE_KEY = "jobful.session";
export const SESSION_UPDATED_EVENT = "jobful:session-updated";

type BackendAuthResponse = {
  verification_required: boolean;
  user?: SessionUser;
  tokens?: {
    access_token: string;
    refresh_token: string;
    token_type: string;
  };
  email?: string;
  message?: string;
  verification_token?: string;
  resend_after_seconds?: number;
  debug_code?: string | null;
};

function errorMessageFromResponse(data: unknown): string {
  if (!data || typeof data !== "object") {
    return "Request failed";
  }

  const detail = "detail" in data ? data.detail : undefined;
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (!item || typeof item !== "object" || !("msg" in item)) {
          return null;
        }
        return typeof item.msg === "string" ? item.msg : null;
      })
      .filter(Boolean)
      .join(", ") || "Request failed";
  }

  return "Request failed";
}

function dispatchSessionUpdated() {
  if (typeof window === "undefined") {
    return;
  }
  window.dispatchEvent(new CustomEvent(SESSION_UPDATED_EVENT));
}

function buildRequestHeaders(initHeaders: HeadersInit | undefined, includeJsonContentType: boolean): Headers {
  const headers = new Headers(initHeaders);
  if (includeJsonContentType && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

async function fetchWithRefresh(path: string, init: RequestInit, includeJsonContentType = true, allowRefresh = true): Promise<Response> {
  const makeRequest = async (authorizationOverride?: string) => {
    const headers = buildRequestHeaders(init.headers, includeJsonContentType);
    if (authorizationOverride) {
      headers.set("Authorization", authorizationOverride);
    }

    return fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
    });
  };

  let response: Response;
  try {
    response = await makeRequest();
  } catch {
    throw new Error(`Could not reach backend at ${API_BASE_URL}`);
  }

  if (response.status !== 401 || !allowRefresh || path === "/auth/refresh") {
    return response;
  }

  const stored = getStoredSession();
  if (!stored?.refresh_token) {
    return response;
  }

  const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: stored.refresh_token }),
  }).catch(() => null);

  if (!refreshResponse?.ok) {
    storeSession(null);
    dispatchSessionUpdated();
    return response;
  }

  const refreshData = await refreshResponse.json().catch(() => null);
  const nextSession = normalizeSession(refreshData as BackendAuthResponse);
  storeSession(nextSession);
  dispatchSessionUpdated();

  try {
    return await makeRequest(`Bearer ${nextSession.access_token}`);
  } catch {
    throw new Error(`Could not reach backend at ${API_BASE_URL}`);
  }
}

async function requestJson<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetchWithRefresh(path, init);
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(errorMessageFromResponse(data));
  }

  return data as T;
}

function normalizeSession(data: BackendAuthResponse): AuthSession {
  if (!data.tokens || !data.user) {
    throw new Error("Expected an authenticated session response");
  }

  return {
    verification_required: false,
    access_token: data.tokens.access_token,
    refresh_token: data.tokens.refresh_token,
    token_type: data.tokens.token_type,
    user: data.user,
  };
}

function normalizeResult(data: BackendAuthResponse): AuthResult {
  if (data.verification_required) {
    return {
      verification_required: true,
      email: data.email ?? "",
      message: data.message ?? "Enter the code sent to your email.",
      verification_token: data.verification_token ?? "",
      resend_after_seconds: data.resend_after_seconds ?? 60,
      debug_code: data.debug_code ?? null,
    };
  }

  return normalizeSession(data);
}

export function getStoredSession(): AuthSession | null {
  if (typeof window === "undefined") {
    return null;
  }

  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw) as AuthSession;
  } catch {
    return null;
  }
}

export function storeSession(session: AuthSession | null) {
  if (typeof window === "undefined") {
    return;
  }

  if (session === null) {
    window.localStorage.removeItem(STORAGE_KEY);
    dispatchSessionUpdated();
    return;
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  dispatchSessionUpdated();
}

export async function register(payload: RegisterPayload): Promise<AuthResult> {
  return normalizeResult(await requestJson<BackendAuthResponse>("/auth/register", { method: "POST", body: JSON.stringify(payload) }));
}

export async function login(payload: LoginPayload): Promise<AuthResult> {
  return normalizeResult(await requestJson<BackendAuthResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload) }));
}

export async function refreshSession(payload: RefreshPayload): Promise<AuthSession> {
  return normalizeSession(await requestJson<BackendAuthResponse>("/auth/refresh", { method: "POST", body: JSON.stringify(payload) }));
}

export async function verifyEmail(payload: RegisterPayload & { code: string; verification_token: string }): Promise<AuthSession> {
  return normalizeSession(await requestJson<BackendAuthResponse>("/auth/verify-email", { method: "POST", body: JSON.stringify(payload) }));
}

export async function resendVerification(payload: { email: string; full_name: string; verification_token: string }): Promise<VerificationChallenge> {
  return normalizeResult(await requestJson<BackendAuthResponse>("/auth/resend-verification", { method: "POST", body: JSON.stringify(payload) })) as VerificationChallenge;
}

export async function getOnboardingState(accessToken: string) {
  return requestJson<{ user_id: string; raw_job_title: string; bio: string | null; recommended_tags: Tag[]; assigned_tags: Tag[]; selected_tags: Tag[] }>("/onboarding/state", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export async function saveProfile(accessToken: string, payload: ProfilePayload) {
  return requestJson<{ user_id: string; raw_job_title: string; bio: string | null; recommended_tags: Tag[]; assigned_tags: Tag[]; selected_tags: Tag[] }>("/onboarding/profile", {
    method: "PUT",
    body: JSON.stringify(payload),
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export async function saveSelectedTags(accessToken: string, tagIds: string[]) {
  return requestJson<{ user_id: string; raw_job_title: string; bio: string | null; recommended_tags: Tag[]; assigned_tags: Tag[]; selected_tags: Tag[] }>("/onboarding/selected-tags", {
    method: "PUT",
    body: JSON.stringify({ tag_ids: tagIds }),
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export async function getEligibleJobs(accessToken: string) {
  return requestJson<{ items: Array<{ job_id: string; title: string; company: string; location: string | null; salary_range: string | null; posted_at: string }> }>("/jobs/eligible", {
    method: "GET",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export async function logout(payload: RefreshPayload): Promise<void> {
  await requestJson<unknown>("/auth/logout", { method: "POST", body: JSON.stringify(payload) });
}

export async function getSessionUser(accessToken: string): Promise<SessionUser> {
  return requestJson<SessionUser>("/auth/session", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export async function updateAccount(accessToken: string, payload: AccountUpdatePayload): Promise<SessionUser> {
  return requestJson<SessionUser>("/profile/account", {
    method: "PUT",
    body: JSON.stringify(payload),
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}

export function googleStartUrl() {
  return `${API_BASE_URL}/auth/google/start`;
}

// ── CV types ──────────────────────────────────────────────────────────────────

export type ExperiencePreview = {
  company: string;
  location: string | null;
  role: string;
  experience_type: string;
  start_date: string;
  end_date: string | null;
  description: string | null;
  tag: string | null;
  keywords: string[];
};

export type ProjectPreview = {
  name: string;
  description: string | null;
  tag: string | null;
  keywords: string[];
};

export type EducationPreview = {
  institution: string;
  degree: string;
  degree_level: string; // high_school | diploma | ug | pg | phd | other
  field_of_study: string | null;
  start_date: string | null;
  end_date: string | null;
  grade: string | null;
  description: string | null;
  tag: string; // canonical tag — NOT NULL
};

export type CVContactPreview = {
  email: string | null;
  phone_number: string | null;
  github_url: string | null;
  linkedin_url: string | null;
  notion_url: string | null;
};

export type CVPreviewResponse = {
  education: EducationPreview[];
  experiences: ExperiencePreview[];
  projects: ProjectPreview[];
  suggested_tags: string[];
  contact_details: CVContactPreview;
};

export type CVConfirmResponse = {
  education_stored: number;
  experiences_stored: number;
  projects_stored: number;
  suggested_tags: string[];
};

export async function uploadCV(accessToken: string, file: File): Promise<CVPreviewResponse> {
  const form = new FormData();
  form.append("file", file);

  const response = await fetchWithRefresh("/onboarding/upload-cv", {
    method: "POST",
    body: form,
    headers: { Authorization: `Bearer ${accessToken}` },
  }, false);

  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(errorMessageFromResponse(data));
  return data as CVPreviewResponse;
}

export async function confirmCV(
  accessToken: string,
  payload: { education: EducationPreview[]; experiences: ExperiencePreview[]; projects: ProjectPreview[]; suggested_tags: string[] },
): Promise<CVConfirmResponse> {
  return requestJson<CVConfirmResponse>("/onboarding/confirm-cv", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

// ── Job search ────────────────────────────────────────────────────────────────

export type JobResult = {
  source: string;
  external_id: string;
  title: string;
  company: string;
  location: string;
  country: string;
  description: string;
  apply_url: string;
  source_url: string;
  salary_range: string | null;
  posted_at: string;
  employment_type: string;
  work_model: string;
  // enriched by filter pipeline
  brief_description?: string | null;
  tech_stack?: string[];
  why_fit?: string | null;
  matching_experiences?: string[];
  matching_projects?: string[];
  gate_provider?: string | null;
};

export type JobSearchParams = {
  q: string;
  location?: string;
  country?: string;
  source?: string;
  employment_type?: string;   // FULLTIME | PARTTIME | CONTRACTOR | INTERN
  work_model?: string;        // remote | hybrid | onsite
  date_posted?: string;       // today | 3days | week | month
  salary_min?: number;
  allow_unspecified_pay?: boolean;
};

export async function searchJobs(
  accessToken: string,
  params: JobSearchParams,
): Promise<{ items: JobResult[]; total: number }> {
  const qs = new URLSearchParams();
  qs.set("q", params.q);
  if (params.location) qs.set("location", params.location);
  if (params.country) qs.set("country", params.country);
  if (params.source) qs.set("source", params.source);
  if (params.employment_type) qs.set("employment_type", params.employment_type);
  if (params.work_model) qs.set("work_model", params.work_model);
  if (params.date_posted) qs.set("date_posted", params.date_posted);
  if (params.salary_min !== undefined && params.salary_min > 0) qs.set("salary_min", String(params.salary_min));
  if (params.allow_unspecified_pay === false) qs.set("allow_unspecified_pay", "false");
  return requestJson<{ items: JobResult[]; total: number }>(`/jobs/search?${qs}`, {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

// ── Applications ──────────────────────────────────────────────────────────────

export type ApplicationStatus = "interested" | "applying" | "applied" | "response" | "placed";

export type ApplicationRecord = {
  application_id: string;
  status: ApplicationStatus;
  applied_at: string;
  updated_at: string;
  job_id: string;
  job_source?: string | null;
  external_job_key?: string | null;
  title: string;
  description?: string | null;
  company: string;
  location: string | null;
  salary_range: string | null;
  apply_url?: string | null;
  source_url: string | null;
  is_active: boolean;
  stale_reason?: string | null;
  last_checked_at?: string | null;
  stale_detected_at?: string | null;
  posted_at: string | null;
};

export type JobTrackingNotification = {
  application_id: string;
  job_id: string;
  status: ApplicationStatus;
  kind: "interested_stale" | "applied_stale";
  title: string;
  company: string;
  message: string;
  stale_reason?: string | null;
  stale_detected_at?: string | null;
  can_remove: boolean;
};

export type ApplicationsOverview = {
  items: ApplicationRecord[];
  notifications: JobTrackingNotification[];
  summary: {
    total: number;
    active: number;
    stale: number;
    interested: number;
    applying: number;
    applied: number;
  };
  synced_at: string;
};

export async function trackJob(
  accessToken: string,
  job: JobResult,
  initialStatus: ApplicationStatus = "interested",
): Promise<{ application_id: string; status: string }> {
  return requestJson<{ application_id: string; status: string }>("/applications/track", {
    method: "POST",
    body: JSON.stringify({ ...job, status: initialStatus }),
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function updateApplicationStatus(
  accessToken: string,
  applicationId: string,
  status: ApplicationStatus,
): Promise<{ application_id: string; status: string }> {
  return requestJson<{ application_id: string; status: string }>(`/applications/${applicationId}/status`, {
    method: "PUT",
    body: JSON.stringify({ status }),
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function getApplications(accessToken: string): Promise<{ items: ApplicationRecord[] }> {
  return requestJson<{ items: ApplicationRecord[] }>("/applications", {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function getApplicationsOverview(accessToken: string): Promise<ApplicationsOverview> {
  return requestJson<ApplicationsOverview>("/applications/overview", {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function prepareTrackedApplication(
  accessToken: string,
  applicationId: string,
): Promise<{
  application_id: string;
  status: ApplicationStatus;
  generation_status: "placeholder_pending";
  apply_url: string | null;
  documents_to_generate: Array<"cv" | "cover_letter">;
}> {
  return requestJson<{
    application_id: string;
    status: ApplicationStatus;
    generation_status: "placeholder_pending";
    apply_url: string | null;
    documents_to_generate: Array<"cv" | "cover_letter">;
  }>(`/applications/${applicationId}/prepare-apply`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function removeStaleInterestedJob(
  accessToken: string,
  applicationId: string,
): Promise<{ application_id: string; removed_job_id: string | null }> {
  return requestJson<{ application_id: string; removed_job_id: string | null }>(`/applications/${applicationId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

// ── Profile data ──────────────────────────────────────────────────────────────

export type EducationDetail = {
  education_id: string;
  institution: string;
  degree: string;
  degree_level: string;
  field_of_study: string | null;
  start_date: string | null;
  end_date: string | null;
  grade: string | null;
  description: string | null;
  tag: string;
};

export type ExperienceDetail = {
  experience_id: string;
  company: string;
  location: string | null;
  role: string;
  experience_type: string;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
  tag: string | null;
  keywords: string[];
};

export type ProjectDetail = {
  project_id: string;
  name: string;
  description: string | null;
  tag: string | null;
  keywords: string[];
};

export async function updateUserAccount(
  accessToken: string,
  payload: {
    full_name: string;
    raw_job_title: string;
    bio?: string | null;
    phone_number?: string | null;
    github_url?: string | null;
    linkedin_url?: string | null;
    notion_url?: string | null;
    password?: string | null;
  },
): Promise<SessionUser> {
  return requestJson<SessionUser>("/profile/account", {
    method: "PUT",
    body: JSON.stringify(payload),
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function getCVData(accessToken: string): Promise<{ education: EducationDetail[]; experiences: ExperienceDetail[]; projects: ProjectDetail[] }> {
  return requestJson<{ education: EducationDetail[]; experiences: ExperienceDetail[]; projects: ProjectDetail[] }>("/profile/cv-data", {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function generateTagsFromCV(accessToken: string): Promise<{ tags: Tag[] }> {
  return requestJson<{ tags: Tag[] }>("/onboarding/generate-tags", {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export async function getProfileStats(accessToken: string): Promise<{ tag_stats: { tag_name: string; application_count: number }[] }> {
  return requestJson<{ tag_stats: { tag_name: string; application_count: number }[] }>("/profile/stats", {
    method: "GET",
    headers: { Authorization: `Bearer ${accessToken}` },
  });
}

export { API_BASE_URL };
