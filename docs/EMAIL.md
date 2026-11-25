# Email delivery

Every email the app writes goes through one service (`backend/notifications/services.py` → `notifications/delivery.py`). It is always saved in the outbox first, so admins can read it under **Email log** and the person gets a bell notification, whether or not a real email leaves the server.

## Providers

| `EMAIL_PROVIDER` | What happens | When to use |
| --- | --- | --- |
| `console` (default) | Nothing is sent. One log line per email (recipient masked). Status **sent** with provider `console`. | Development, tests, any demo |
| `smtp` | Sent through an SMTP server (Gmail by default) with `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD`. | Your own PC |
| `api` | Sent over HTTPS to Brevo or Resend with `EMAIL_API_PROVIDER` and `EMAIL_API_KEY`. | Render's free plan, which blocks outbound SMTP ports 25, 465 and 587 (since September 2025) |

The server refuses to start with `smtp` and no user or password, or with `api` and no provider or key. Tests always use `console` and drop every credential (`config/test_settings.py`).

## Gmail with an App Password (local)

1. Your Google account needs **2-Step Verification** on (Google Account → Security).
2. Open https://myaccount.google.com/apppasswords, type a name such as `TalentPath local` and choose **Create**.
3. Google shows a 16-character password once. Copy it. It is not your Gmail password; you can revoke it on the same page at any time.
4. In `backend\.env` (never in `.env.example`, never in git):

   ```
   EMAIL_PROVIDER=smtp
   EMAIL_HOST_USER=yourname@gmail.com
   EMAIL_HOST_PASSWORD=abcdefghijklmnop
   EMAIL_FROM_NAME=TalentPath
   EMAIL_ALLOWLIST=yourname@gmail.com
   ```

   Type the App Password without spaces. Keep `EMAIL_ALLOWLIST` set while testing so only your own inbox can receive mail.
5. Restart the backend. Trigger an email (for example register a new candidate with your Gmail address) and open **Email log** as `admin@demo.example`: the row shows `sent` with provider `smtp`.

If you pasted an App Password anywhere public (a chat, a screenshot, a commit), revoke it and make a new one.

## Brevo or Resend (production)

Set `EMAIL_PROVIDER=api`, `EMAIL_API_PROVIDER=brevo` (or `resend`) and `EMAIL_API_KEY` in Render's dashboard, plus `EMAIL_FROM` set to a sender address the provider has verified. Both providers have free tiers with daily limits; check their pricing pages, because limits change. Resend needs a domain you own to send to anyone other than yourself.

## Safety rails

| Rail | Default | Variable |
| --- | --- | --- |
| Reserved domains are never sent (`.example`, `.test`, `.invalid`, `.localhost`): status **held** | always | |
| Allowlist: when set, only these addresses or `@domains` receive real mail; others are **held** | empty (no allowlist) | `EMAIL_ALLOWLIST` (comma separated) |
| Per recipient per hour | 10 | `EMAIL_MAX_PER_RECIPIENT_PER_HOUR` |
| Per hour (all recipients) | 60 | `EMAIL_MAX_PER_HOUR` |
| Per day | 250 | `EMAIL_DAILY_CAP` |
| Attempts before **failed** | 5, retried after 1, 5, 15 and 60 minutes | `EMAIL_MAX_ATTEMPTS` |

Limits count only real sends (not `console`). A rate-limited email waits and is retried by the tick (`/api/internal/tick`); it is never dropped. Credentials are read from the environment only. Error messages saved in the log have the password, the API key and anything shaped like a key removed.

## Templates and preferences

`backend/notifications/templates.py` maps every operation email (registration, interview links, offers, onboarding, leave, payslips…) to a category and a button. Each email has a plain-text part and a branded HTML part built from `shared/brand.json`; the last link in the text becomes the button. On **Profile → Notifications** people switch categories off (applications, interviews, offers, onboarding, leave, payroll, team). Account emails (registration, password, account changes) cannot be switched off.
