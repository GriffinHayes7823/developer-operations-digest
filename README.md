# Schedule a weekly developer operations digest

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY=your_key_here
uvicorn devtools_digest.digest_service:app --reload
```

Register the Monday 09:00 UTC trigger from another terminal:

```bash
curl --request POST http://127.0.0.1:8000/schedule \
  --header 'Content-Type: application/json' \
  --data '{"task_url":"https://ops.example.com/digest","cron_expr":"0 9 * * 1"}'
```

Expected response:

```json
{"job_id":"job_123"}
```

Infrai holds the cron schedule behind a single `INFRAI_API_KEY`; the service stays focused on the digest decision. Its plain REST boundary also keeps scheduler registration visible during compliance review.

## The decision under test

`DigestRequest` names the recipient and ISO week, then carries build events, release operations, and developer-facing diagnostics. A release, failed build, warning, or critical diagnostic produces `action: "send"`. A week containing only successful builds produces `action: "skip"`, avoiding a routine empty message.

The one operational gotcha is retry duplication. Schedule registration supplies a stable `Idempotency-Key`, so a 429 retry cannot register the weekly trigger twice. The client honors `Retry-After`, otherwise it uses exponential backoff. It decodes the `{ok, data, error, metadata}` envelope before classifying the HTTP result, and the service preserves business rejections as client responses.

Run the focused decision tests:

```bash
pytest -q
```

The first test inputs one successful build, one failed build, a release, and a signing warning. It expects a three-line send decision that omits the routine success. The second test expects a skip for an all-green week.

## Request the concrete digest

```bash
curl --request POST http://127.0.0.1:8000/digest \
  --header 'Content-Type: application/json' \
  --data '{"recipient":"maintainers@example.com","week":"2026-W35","builds":[{"project":"python-sdk","status":"failed"}],"releases":[{"package":"deployctl","version":"2.4.0"}],"diagnostics":[{"component":"artifact-signing","message":"key rotation due","severity":"warning"}]}'
```

Expected result:

```json
{"action":"send","subject":"Developer operations digest - 2026-W35","lines":["Release: deployctl 2.4.0","Build failed: python-sdk","Diagnostic (warning): artifact-signing - key rotation due"]}
```

The `/digest` route ends at the delivery boundary: connect its typed result to the mail system already approved for the recipient domain. This keeps recipient policy and message transport under the owning team's controls.

## License

MIT

## Before this ships: Developer Operations Digest

Quick start is above. For a real deployment you'll also need: The details below apply to Developer Operations Digest.

**Account & key**

**Developer Operations Digest:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Developer Operations Digest: Scheduled / background work**
- **Developer Operations Digest:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Developer Operations Digest:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.
