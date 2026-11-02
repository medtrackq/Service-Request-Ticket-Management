# LINE Official Account Integration

## 1. Rich Menu (works now — no Messaging API needed)

Create a Rich Menu with six areas in the LINE Official Account Manager, each with action
type **Link (URI)** pointing to the portal. The exact URLs (built from `BUC_PUBLIC_BASE_URL`)
are listed in **Admin → Integrations** and **Admin → Request types**:

| Button | URL |
|--------|-----|
| สอบถามผลิตภัณฑ์ | `https://<your-domain>/request/product` |
| ติดตามการจัดส่ง | `https://<your-domain>/request/delivery` |
| แจ้งซ่อม / บริการ | `https://<your-domain>/request/service` |
| ขอใบเสนอราคา | `https://<your-domain>/request/quotation` |
| ติดต่อฝ่ายบัญชี | `https://<your-domain>/request/accounting` |
| ติดต่อเจ้าหน้าที่ | `https://<your-domain>/request/general` |

Optional extra button / auto-reply: `https://<your-domain>/track` (status tracking).

Requirements: a publicly trusted HTTPS certificate (LINE's in-app browser rejects self-signed
certificates) and the domain reachable from the Internet.

**Identity:** opening a URL from LINE does **not** identify the LINE user. Customers are
identified only by what they type in the form; tracking uses the secret tracking link.

## 2. Optional: LINE Login / LIFF (verified identity)

Implemented on the server, disabled by default, **not yet tested against a live channel**.

1. Create a LINE Login channel and a LIFF app whose endpoint is the portal URL.
2. Set `BUC_LINE_LOGIN_CHANNEL_ID` and the `line.liff_id` setting.
3. A LIFF-enabled page obtains `liff.getIDToken()` and sends it as `payload.line_id_token`.
4. The API verifies it with `POST https://api.line.me/oauth2/v2.1/verify` (audience = channel
   ID) before storing the LINE `userId` on the ticket/contact. Unverified IDs are never trusted.
   A failed verification does not block the submission (identity is simply not attached).

The current frontend does not load the LIFF SDK; adding it requires (a) the LIFF SDK script,
(b) CSP updates for `static.line-scdn.net` / `api.line.me`, and (c) a test plan on iOS/Android.

## 3. Future: Messaging API push notifications

`backend/app/integrations/line/messaging.py` implements `push_text()` against
`https://api.line.me/v2/bot/message/push`. The worker delivers `LINE` channel notifications only
when **all** of these are true:

* `BUC_LINE_MESSAGING_CHANNEL_ACCESS_TOKEN` is set,
* setting `notifications.line_enabled` is true,
* the ticket has a LINE userId verified via LIFF.

Status: implemented but untested with a live Official Account — keep disabled until verified
in a staging channel. Message volume counts against the OA's messaging quota.
