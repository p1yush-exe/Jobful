"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Reveal } from "@/components/reveal";
import { useAuth } from "@/context/auth-context";
import { getSessionUser, googleStartUrl, login } from "@/services/auth";

function LoginPageContent() {
  const router = useRouter();
  const { setSession } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    async function hydrateSessionFromGoogleCallback() {
      const params = new URLSearchParams(window.location.search);
      const accessToken = params.get("access_token");
      const refreshToken = params.get("refresh_token");
      const callbackError = params.get("error");
      if (callbackError) {
        setError(callbackError);
        return;
      }
      if (!accessToken || !refreshToken) {
        return;
      }

      try {
        const user = await getSessionUser(accessToken);
        setSession({
          verification_required: false,
          access_token: accessToken,
          refresh_token: refreshToken,
          token_type: "bearer",
          user,
        });
        router.replace(user.onboarding_complete ? "/dashboard" : "/onboarding");
      } catch {
        setError("Google sign-in session could not be established");
      }
    }

    void hydrateSessionFromGoogleCallback();
  }, [router, setSession]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    try {
      const result = await login({ email, password });
      if (result.verification_required) {
        throw new Error("Please finish registration before signing in");
      }

      setSession(result);
      router.push(result.user.onboarding_complete ? "/dashboard" : "/onboarding");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="ui-shell px-4 pb-8 pt-6 sm:px-6 sm:pb-10 sm:pt-8">
      <div className="ui-wrap grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <Reveal className="ui-card flex flex-col justify-between p-7 sm:p-10">
          <div className="space-y-5">
            <p className="ui-eyebrow w-fit">
              <span className="ui-dot" />
              Account access
            </p>
            <h1 className="ui-title max-w-lg">Sign in and continue where you left off.</h1>
            <p className="ui-lead max-w-md">
              Return to your profile, CV review, selected tags, saved jobs, and tracked applications.
            </p>
          </div>

          <div className="ui-panel">
            <p className="ui-kicker">Inside the workspace</p>
            <p className="mt-2 text-sm leading-7 text-[var(--text-soft)]">
              Search roles, save the ones you care about, and keep your application status current.
            </p>
          </div>
        </Reveal>

        <Reveal className="ui-card p-7 sm:p-10">
          <div className="space-y-6">
            <div>
              <p className="ui-kicker">Sign in</p>
              <h2 className="ui-title mt-2">Welcome back.</h2>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit}>
              <div>
                <label className="ui-label block">Email</label>
                <input
                  className="ui-input"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  type="email"
                  required
                  autoComplete="email"
                />
              </div>

              <div>
                <label className="ui-label block">Password</label>
                <input
                  className="ui-input"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  type="password"
                  required
                  autoComplete="current-password"
                />
              </div>

              {error ? (
                <div className="rounded-[1.25rem] bg-[var(--red-soft)] p-4 text-sm text-[#7f2f2f] shadow-[inset_0_0_0_1px_rgba(146,77,73,0.08)]">
                  {error}
                </div>
              ) : null}

              <button className="ui-button w-full" disabled={busy} type="submit">
                {busy ? "Signing in" : "Sign in"}
              </button>
            </form>

            {process.env.NEXT_PUBLIC_ENABLE_GOOGLE_SSO === "true" ? (
              <a className="ui-button ui-button-secondary w-full" href={googleStartUrl()}>
                Continue with Google
              </a>
            ) : null}

            <div className="ui-divider" />

            <div className="flex items-center justify-between gap-4">
              <p className="text-sm text-[var(--text-soft)]">Need an account?</p>
              <Link className="ui-button ui-button-secondary px-4 py-3" href="/register">
                Register
              </Link>
            </div>
          </div>
        </Reveal>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return <LoginPageContent />;
}
