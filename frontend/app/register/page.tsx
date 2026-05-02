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

  function handleGoBack() {
    setVerificationChallenge(null);
    setPendingRegistration(null);
    setVerificationCode("");
    setError(null);
  }

  return (
    <main className="ui-shell px-4 pb-6 pt-6 sm:px-6 sm:pb-8 sm:pt-8">
      <div className="ui-wrap">
        {verificationChallenge ? (
          <Reveal className="ui-card mx-auto max-w-2xl p-7 sm:p-10">
            <form className="space-y-5" onSubmit={handleVerify}>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p className="ui-eyebrow w-fit"><span className="ui-dot" />Email verification</p>
                  <h1 className="ui-title mt-3 max-w-md">Check your email and enter the code.</h1>
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
                  autoFocus
                />
              </div>

              {verificationChallenge.debug_code ? (
                <p className="ui-kicker">Dev code: {verificationChallenge.debug_code}</p>
              ) : null}

              {error ? (
                <div className="rounded-[1.25rem] bg-[var(--red-soft)] p-4 text-sm text-[#7f2f2f] shadow-[inset_0_0_0_1px_rgba(146,77,73,0.08)]">
                  {error}
                </div>
              ) : null}

              <div className="flex flex-wrap gap-3">
                <button className="ui-button" disabled={verificationBusy} type="submit">
                  {verificationBusy ? "Verifying" : "Verify and continue"}
                </button>
                <button className="ui-button ui-button-secondary" disabled={verificationBusy} type="button" onClick={() => void handleResend()}>
                  Resend code
                </button>
                <button className="ui-button ui-button-secondary" disabled={verificationBusy} type="button" onClick={handleGoBack}>
                  Edit details
                </button>
              </div>
            </form>
          </Reveal>
        ) : (
          <Reveal className="ui-card p-7 sm:p-10">
            <div className="grid gap-8 lg:grid-cols-[0.75fr_1.25fr]">
              <div className="space-y-5">
                <p className="ui-eyebrow w-fit">
                  <span className="ui-dot" />
                  New account
                </p>
                <h1 className="ui-title max-w-md">Create your account.</h1>
                <p className="ui-lead max-w-md">
                  Basics first. CV upload and tag selection come right after.
                </p>
                <div className="border-t border-[rgba(95,108,95,0.12)] pt-4">
                  <p className="text-sm text-[var(--text-soft)]">
                    Already registered?{" "}
                    <Link className="font-semibold text-[var(--green)] underline-offset-4 hover:underline" href="/login">
                      Sign in
                    </Link>
                  </p>
                </div>
              </div>

              <form className="grid gap-4 sm:grid-cols-2" onSubmit={handleSubmit}>
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
                    placeholder="Backend engineer, product analyst"
                    required
                  />
                </div>

                <div className="sm:col-span-2">
                  <label className="ui-label block">Short bio</label>
                  <textarea
                    className="ui-textarea"
                    value={bio}
                    onChange={(event) => setBio(event.target.value)}
                    placeholder="One line about your background."
                    rows={2}
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

                {process.env.NEXT_PUBLIC_ENABLE_GOOGLE_SSO === "true" ? (
                  <a className="ui-button ui-button-secondary sm:col-span-2" href={googleStartUrl()}>
                    Continue with Google
                  </a>
                ) : null}
              </form>
            </div>
          </Reveal>
        )}
      </div>
    </main>
  );
}
