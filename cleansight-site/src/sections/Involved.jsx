import { useState } from 'react';
import Section from '../components/Section.jsx';
import Card from '../components/Card.jsx';

const ORG_TYPES = [
  'Environmental-cleaning company',
  'Local government',
  'Business/property manager',
  'School/campus',
  'Researcher',
  'Other',
];

const encode = (formData) => new URLSearchParams(formData).toString();

export default function Involved() {
  const [status, setStatus] = useState('idle'); // idle | sending | success | error

  async function onSubmit(e) {
    e.preventDefault();
    const form = e.currentTarget;
    if (!form.reportValidity()) return;
    setStatus('sending');
    try {
      const data = new FormData(form);
      data.set('form-name', 'needs-survey');
      const res = await fetch('/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: encode(data),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      form.reset();
      setStatus('success');
    } catch {
      setStatus('error');
    }
  }

  return (
    <Section
      id="involved"
      eyebrow="Get involved"
      title="Tell us what you need"
      lead="We are collecting needs from cleaning units, local governments and businesses. A few minutes of your time helps us decide what to build and test next."
    >
      <div className="involved-layout">
        <Card className="form-card">
          {status === 'success' ? (
            <div className="form-status form-status-ok" role="status">
              <h3>Thank you</h3>
              <p>Your answers have been sent. We may contact you about this survey.</p>
              <button type="button" className="btn btn-dark btn-sm" onClick={() => setStatus('idle')}>
                Send another response
              </button>
            </div>
          ) : (
            <form name="needs-survey" method="POST" data-netlify="true" netlify-honeypot="bot-field" onSubmit={onSubmit} className="survey">
              <input type="hidden" name="form-name" value="needs-survey" />
              <p className="hp" aria-hidden="true">
                <label>
                  Do not fill this in: <input name="bot-field" tabIndex={-1} autoComplete="off" />
                </label>
              </p>

              <div className="field">
                <label htmlFor="f-org-type">Organisation type <span className="req">(required)</span></label>
                <select id="f-org-type" name="org-type" required defaultValue="">
                  <option value="" disabled>Choose one</option>
                  {ORG_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label htmlFor="f-org-name">Organisation name <span className="opt">(optional)</span></label>
                <input id="f-org-name" name="org-name" type="text" autoComplete="organization" />
              </div>

              <div className="field">
                <label htmlFor="f-name">Your name <span className="req">(required)</span></label>
                <input id="f-name" name="name" type="text" autoComplete="name" required />
              </div>

              <div className="field">
                <label htmlFor="f-email">Email <span className="req">(required)</span></label>
                <input id="f-email" name="email" type="email" autoComplete="email" required />
              </div>

              <div className="field">
                <label htmlFor="f-area">Area / city <span className="opt">(optional)</span></label>
                <input id="f-area" name="area" type="text" autoComplete="address-level2" />
              </div>

              <div className="field">
                <label htmlFor="f-problems">What litter or drain problems do you face?</label>
                <textarea id="f-problems" name="problems" rows="4" />
              </div>

              <fieldset className="field radios">
                <legend>Would you be interested in a pilot?</legend>
                {['Yes', 'Maybe', 'No'].map((o) => (
                  <label key={o} className="radio">
                    <input type="radio" name="pilot" value={o} /> {o}
                  </label>
                ))}
              </fieldset>

              <label className="check">
                <input type="checkbox" name="consent" value="yes" required />
                <span>
                  I agree CleanSight may contact me about this survey. We collect only these answers and use them for
                  the project.
                </span>
              </label>

              <button type="submit" className="btn btn-primary" disabled={status === 'sending'}>
                {status === 'sending' ? 'Sending…' : 'Send my answers'}
              </button>

              <div aria-live="polite">
                {status === 'error' && (
                  <p className="form-status form-status-bad" role="alert">
                    Sorry, we could not send your answers. Please check your connection and try again.
                  </p>
                )}
              </div>
            </form>
          )}
        </Card>

        <aside className="involved-aside">
          <h3>Why we ask</h3>
          <ul className="tick-list">
            <li>Your answers help us decide which problems to tackle and test next.</li>
            <li>We collect only the answers in this form and use them for the project.</li>
          </ul>
        </aside>
      </div>
    </Section>
  );
}
