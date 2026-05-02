"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/context/auth-context";

export function ProtectedRoute({
  children,
  requireOnboardingComplete = true,
}: Readonly<{ children: React.ReactNode; requireOnboardingComplete?: boolean }>) {
  const router = useRouter();
  const { session, status } = useAuth();

  useEffect(() => {
    if (status !== "ready") {
      return;
    }

    if (session === null) {
      router.replace("/login");
      return;
    }

    if (requireOnboardingComplete && !session.user.onboarding_complete) {
      router.replace("/onboarding");
    }
  }, [requireOnboardingComplete, router, session, status]);

  if (status !== "ready" || session === null || (requireOnboardingComplete && !session.user.onboarding_complete)) {
    return (
      <div className="ui-shell flex min-h-screen items-center justify-center px-6">
        <div className="ui-card w-full max-w-md p-8 text-center">
          <p className="ui-eyebrow mx-auto w-fit">
            <span className="ui-dot" />
            Loading workspace
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
