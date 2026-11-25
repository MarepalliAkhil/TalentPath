import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { brand } from '@/lib/brand';
import { useSeo } from '@/lib/hooks';

/** Plain-language demo terms and privacy policy (prompt 1). Version must match the backend's TERMS_VERSION. */
const TERMS_VERSION = '2026-11';

function LegalPage({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl">
      <h1 className="font-display text-3xl font-semibold text-ink">{title}</h1>
      <p className="mt-2 text-muted">
        Version {TERMS_VERSION}. {intro}
      </p>
      <div className="legal mt-6 flex flex-col gap-6 text-ink-soft [&_h2]:font-display [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-ink [&_li]:ml-5 [&_li]:list-disc [&_ul]:mt-2 [&_ul]:flex [&_ul]:flex-col [&_ul]:gap-1">
        {children}
      </div>
    </article>
  );
}

const TERMS_SEO = {
  title: `Terms and Conditions | ${brand.name}`,
  description: `The plain-language terms for using ${brand.name}, a portfolio demo where every company and job is fictional.`,
};

export function TermsPage() {
  useSeo(TERMS_SEO);
  return (
    <LegalPage title="Terms and Conditions" intro={`These terms are written for a portfolio demo. Read them in two minutes.`}>
      <section>
        <h2>What this site is</h2>
        <p>
          {brand.name} is a portfolio project that shows how hiring and onboarding software works. Every company, job and
          person in the demo data is fictional. Applying here does not get you a real job.
        </p>
      </section>
      <section>
        <h2>Your account</h2>
        <ul>
          <li>Give true information. Your email, legal name and date of birth are locked after you set them; an admin can correct them.</li>
          <li>Keep your password to yourself. You can change it on your profile at any time.</li>
          <li>Do not upload anything you do not have the right to share, or anything harmful.</li>
        </ul>
      </section>
      <section>
        <h2>Fair use</h2>
        <ul>
          <li>Do not try to break, overload or misuse the service. Uploads and emails are rate-limited.</li>
          <li>We may remove accounts that misuse the service. Demo accounts reset regularly.</li>
        </ul>
      </section>
      <section>
        <h2>No guarantees</h2>
        <p>
          The service is provided as it is, for demonstration. Scores and suggestions are explained, but they never decide
          anything by themselves: people do.
        </p>
      </section>
      <p>
        See also the <Link to="/privacy" className="font-semibold text-primary-strong underline">Privacy Policy</Link>.
      </p>
    </LegalPage>
  );
}

const PRIVACY_SEO = {
  title: `Privacy Policy | ${brand.name}`,
  description: `What ${brand.name} stores about you, why, how it is encrypted, how long it is kept and how to delete it.`,
};

export function PrivacyPage() {
  useSeo(PRIVACY_SEO);
  return (
    <LegalPage title="Privacy Policy" intro="What we store, why, how we protect it, how long we keep it and how to delete it.">
      <section>
        <h2>What we store</h2>
        <ul>
          <li>Account: your name, email, password (as a one-way hash, never the password itself) and role.</li>
          <li>Profile: phone, address, links, skills, education, experience, date of birth and an optional photo.</li>
          <li>Applications: your resume, the application form (including current and expected CTC and notice period), your answers and the stage history.</li>
          <li>For employees: leave, attendance and onboarding records.</li>
          <li>Emails we send you, so you can see them in the app.</li>
        </ul>
      </section>
      <section>
        <h2>Why</h2>
        <p>
          Only to run hiring and onboarding: to show your application to the people hiring for that job, to schedule
          interviews, to send you updates and to set you up as an employee if you are hired.
        </p>
      </section>
      <section>
        <h2>How it is protected</h2>
        <ul>
          <li>Personal fields, resumes and application forms are encrypted in the database (AES-GCM).</li>
          <li>Screening can be blind: recruiters do not see your name, college or city until the interview stage.</li>
          <li>The fit score reads only skills and years of experience. Your CTC, date of birth, college and photo never change it.</li>
          <li>Every sensitive action is written to an audit log. Admins manage accounts but cannot open candidates' documents.</li>
        </ul>
      </section>
      <section>
        <h2>How long we keep it</h2>
        <ul>
          <li>Your account and profile: until you ask us to delete them.</li>
          <li>Applications: for the hiring decision and up to 12 months after, then they can be removed.</li>
          <li>Simulated emails in the outbox: 30 days.</li>
          <li>Demo data (addresses ending in .example) is reset regularly.</li>
        </ul>
      </section>
      <section>
        <h2>How to delete it</h2>
        <ul>
          <li>Your resume: delete it on your profile; every earlier version goes with it.</li>
          <li>Your photo: remove it on your profile.</li>
          <li>Your whole account: ask an admin. People with employment history are deactivated rather than erased, as the law requires records to be kept.</li>
        </ul>
      </section>
      <section>
        <h2>Emails</h2>
        <p>
          You can switch off most categories of email on your profile. Account emails (password resets, invitations) always go.
        </p>
      </section>
    </LegalPage>
  );
}
