"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Reveal } from "@/components/reveal";
import { useAuth } from "@/context/auth-context";
import {
  googleStartUrl,
  register,
  resendVerification,
  verifyEmail,
  type RegisterPayload,
  type VerificationChallenge,
} from "@/services/auth";

export default function RegisterPage() {
  const router = useRouter();
  const { setSession } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rawJobTitle, setRawJobTitle] = useState("");
  const [bio, setBio] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [verificationChallenge, setVerificationChallenge] = useState<VerificationChallenge | null>(null);
  const [pendingRegistration, setPendingRegistration] = useState<RegisterPayload | null>(null);
  const [verificationCode, setVerificationCode] = useState("");
  const [verificationBusy, setVerificationBusy] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setVerificationChallenge(null);
    setPendingRegistration(null);
    setVerificationCode("");

    try {
      const registrationPayload = {
        full_name: fullName,
        email,
        password,
        raw_job_title: rawJobTitle,
        bio: bio || null,
      };
      const result = await register(registrationPayload);
      if (result.verification_required) {
        setPendingRegistration(registrationPayload);
        setVerificationChallenge(result);
        setVerificationCode(result.debug_code ?? "");
        return;
      }

      setSession(result);
      router.push(result.user.onboarding_complete ? "/dashboard" : "/onboarding");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleVerify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!verificationChallenge || !pendingRegistration) {
      return;
    }

    setVerificationBusy(true);
    setError(null);

    try {
      const session = await verifyEmail({
        ...pendingRegistration,
        code: verificationCode,
        verification_token: verificationChallenge.verification_token,
      });
      setSession(session);
      router.push(session.user.onboarding_complete ? "/dashboard" : "/onboarding");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Verification failed");
    } finally {
      setVerificationBusy(false);
    }
  }

  async function handleResend() {
    if (!verificationChallenge || !pendingRegistration) {
      return;
    }

    setVerificationBusy(true);
    setError(null);

    try {
      const challenge = await resendVerification({
        email: verificationChallenge.email,
        full_name: pendingRegistration.full_name,
        verification_token: verificationChallenge.verification_token,
      });
      setVerificationChallenge(challenge);
      setVerificationCode(challenge.debug_code ?? "");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Could not resend verification code");
    } finally {
      setVerificationBusy(false);
    }
  }

  return (
    <main className="ui-shell px-4 pb-8 pt-6 sm:px-6 sm:pb-10 sm:pt-8">
      <div className="ui-wrap space-y-6">
        <Reveal className="ui-card p-7 sm:p-10">
          <div className="grid gap-8 lg:grid-cols-[0.75fr_1.25fr]">
            <div className="space-y-5">
              <p className="ui-eyebrow w-fit">
                <span className="ui-dot" />
                New account
              </p>
              <h1 className="ui-title max-w-md">Create your account and set your target role.</h1>
              <p className="ui-lead max-w-md">
                Start with your basics here. CV confirmation and tag selection come right after this step.
              </p>
            </div>

            <form className="grid gap-5 sm:grid-cols-2" onSubmit={handleSubmit}>
              <div>
                <label className="ui-label block">Full name</label>
                <input className="ui-input" value={fullName} onChange={(event) => setFullName(event.target.value)} required />
              </div>

              <div>
                <label className="ui-label block">Email</label>
                <input className="ui-input" value={email} onChange={(event) => setEmail(event.target.value)} type="email" required />
              </div>

              <div>
                <label className="ui-label block">Password</label>
                <input className="ui-input" value={password} onChange={(event) => setPassword(event.target.value)} type="password" required />
              </div>

              <div>
                <label className="ui-label block">Target role</label>
                <input
                  className="ui-input"
                  value={rawJobTitle}
                  onChange={(event) => setRawJobTitle(event.target.value)}
                  placeholder="Backend engineer, product analyst, frontend engineer"
                  required
                />
              </div>

              <div className="sm:col-span-2">
                <label className="ui-label block">Short bio</label>
                <textarea
                  className="ui-textarea"
                  value={bio}
                  onChange={(event) => setBio(event.target.value)}
                  placeholder="Short summary of your background."
                />
              </div>

              {error ? (
                <div className="sm:col-span-2 rounded-[1.25rem] bg-[var(--red-soft)] p-4 text-sm text-[#7f2f2f] shadow-[inset_0_0_0_1px_rgba(146,77,73,0.08)]">
                  {error}
                </div>
              ) : null}

              <button className="ui-button sm:col-span-2" disabled={busy} type="submit">
                {busy ? "Creating account" : "Create account"}
              </button>
            </form>
          </div>

          {process.env.NEXT_PUBLIC_ENABLE_GOOGLE_SSO === "true" ? (
            <div className="mt-5">
              <a className="ui-button ui-button-secondary w-full" href={googleStartUrl()}>
                Continue with Google
              </a>
            </div>
          ) : null}

          <div className="mt-6 flex items-center justify-between gap-4 border-t border-[rgba(95,108,95,0.12)] pt-6">
            <p className="text-sm text-[var(--text-soft)]">Already registered?</p>
            <Link className="ui-button ui-button-secondary px-4 py-3" href="/login">
              Sign in
            </Link>
          </div>
        </Reveal>

        {verificationChallenge ? (
          <Reveal className="ui-card p-7 sm:p-8">
            <form className="space-y-5" onSubmit={handleVerify}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="ui-kicker">Email verification</p>
                  <h2 className="ui-title mt-2">Verify your email.</h2>
                </div>
                <span className="ui-status ui-status-blue">Pending</span>
              </div>

              <p className="text-sm leading-7 text-[var(--text-soft)]">{verificationChallenge.message}</p>

              <div>
                <label className="ui-label block">Verification code</label>
                <input
                  className="ui-input"
                  value={verificationCode}
                  onChange={(event) => setVerificationCode(event.target.value)}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  required
                />
              </div>

              {verificationChallenge.debug_code ? <p className="ui-kicker">Dev code: {verificationChallenge.debug_code}</p> : null}

              <div className="flex flex-wrap gap-3">
                <button className="ui-button" disabled={verificationBusy} type="submit">
                  {verificationBusy ? "Verifying" : "Verify and continue"}
                </button>
                <button className="ui-button ui-button-secondary" disabled={verificationBusy} type="button" onClick={() => void handleResend()}>
                  Resend code
                </button>
              </div>
            </form>
          </Reveal>
        ) : null}
      </div>
    </main>
  );
}
