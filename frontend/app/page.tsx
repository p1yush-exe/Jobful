import Link from "next/link";

import { Reveal } from "@/components/reveal";

const features = [
  "Keep registration, CV review, tag selection, search, and tracking in one flow.",
  "Review parsed CV data before anything is saved.",
  "Track applications and update status without losing the original job link.",
];

const summary = [
  { label: "CV review", value: "Manual approval" },
  { label: "Search", value: "Live sources" },
  { label: "Tracking", value: "Status based" },
];

export default function HomePage() {
  return (
    <main className="ui-shell px-4 pb-8 pt-6 sm:px-6 sm:pb-10 sm:pt-8">
      <div className="ui-wrap space-y-8">
        <Reveal className="ui-card px-7 py-7 sm:px-10 sm:py-10">
          <div className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-end">
            <div className="space-y-6">
              <p className="ui-eyebrow w-fit">
                <span className="ui-dot" />
                Job search workspace
              </p>
              <h1 className="ui-hero max-w-4xl">Not Jobless</h1>
              <p className="ui-lead">
                Jobful keeps the application process practical: verify your account, upload and confirm your CV, choose the right tags, and manage live opportunities from one place.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link className="ui-button" href="/register">
                  Create account
                </Link>
                <Link className="ui-button ui-button-secondary" href="/login">
                  Sign in
                </Link>
              </div>
            </div>

            <div className="grid gap-3">
              {summary.map((item, index) => (
                <div key={item.label} className="ui-metric ui-stagger" style={{ ["--index" as string]: index }}>
                  <p className="ui-kicker">{item.label}</p>
                  <p className="ui-metric-value">{item.value}</p>
                </div>
              ))}
            </div>
          </div>
        </Reveal>

        <section className="grid gap-6 lg:grid-cols-[0.92fr_1.08fr]">
          <Reveal className="ui-card p-7 sm:p-10">
            <div className="space-y-4">
              <p className="ui-kicker">What you can do here</p>
              <h2 className="ui-title max-w-2xl">Built for the actual application workflow, not for decoration.</h2>
            </div>
          </Reveal>

          <Reveal className="ui-card p-7 sm:p-8">
            <div className="space-y-4">
              {features.map((item, index) => (
                <div key={item} className="ui-panel ui-stagger flex items-start gap-3" style={{ ["--index" as string]: index }}>
                  <span className="ui-status ui-status-green">{`0${index + 1}`}</span>
                  <p className="text-sm leading-7 text-[var(--text-soft)]">{item}</p>
                </div>
              ))}
            </div>
          </Reveal>
        </section>
      </div>
    </main>
  );
}
