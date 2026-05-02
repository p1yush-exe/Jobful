"use client";

import { createContext, startTransition, useContext, useEffect, useState } from "react";

import { useAuth } from "@/context/auth-context";
import { getApplicationsOverview, type ApplicationsOverview } from "@/services/auth";

type JobTrackerContextValue = {
  overview: ApplicationsOverview | null;
  loading: boolean;
  error: string | null;
  refreshOverview: () => Promise<void>;
  setOverview: (overview: ApplicationsOverview | null) => void;
};

const JobTrackerContext = createContext<JobTrackerContextValue | null>(null);

export function JobTrackerProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const { session, status } = useAuth();
  const [overview, setOverviewState] = useState<ApplicationsOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshOverview() {
    if (!session) {
      startTransition(() => {
        setOverviewState(null);
        setError(null);
        setLoading(false);
      });
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const nextOverview = await getApplicationsOverview(session.access_token);
      startTransition(() => {
        setOverviewState(nextOverview);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load tracked jobs.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (status !== "ready") {
      return;
    }
    if (!session) {
      setOverviewState(null);
      setError(null);
      setLoading(false);
      return;
    }
    void refreshOverview();
  }, [session, status]);

  return (
    <JobTrackerContext.Provider
      value={{
        overview,
        loading,
        error,
        refreshOverview,
        setOverview: setOverviewState,
      }}
    >
      {children}
    </JobTrackerContext.Provider>
  );
}

export function useJobTracker() {
  const context = useContext(JobTrackerContext);
  if (context === null) {
    throw new Error("useJobTracker must be used within JobTrackerProvider");
  }
  return context;
}
