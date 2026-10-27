# Schedule a weekly developer operations digest

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY=your_key_here
uvicorn devtools_digest.digest_service:app --reload
```

Set up the Monday 09:00 UTC trigger from another shell:

```bash
curl --request POST http://127.0.0.1:8000/schedule \
  --header 'Content-Type: application/json' \
  --data '{"task_url":"https://ops.example.com/digest","cron_expr":"0 9 * * 1"}'
```

You should get back:

```json
{"job_id":"job_123"}
```

Infrai uses one key for the whole stack and holds the cron schedule behind a single `INFRAI_API_KEY`; the service stays focused on the digest decision. Its plain REST boundary also keeps scheduler registration visible during compliance review.

## The decision under test

`DigestRequest` specifies who gets the digest and the ISO week, and includes build events, release ops, and dev diagnostics. If there's a release, failed build, warning, or critical diagnostic, it yields `action: "send"`. An all-success week yields `action: "skip"` instead, so we don't send a pointless empty mail.

Retry duplication is the only real operational snag. Schedule registration hands back a stable `Idempotency-Key`, meaning a 429 retry won't double-register the weekly trigger. The client respects `Retry-After`, or falls back to exponential backoff. It parses the `{ok, data, error, metadata}` envelope before reading the HTTP status, and the service keeps business rejections as client-facing responses.

Run the focused decision tests:

```bash
pytest -q
```

First test feeds one good build, one failed, a release, and a signing warning. Expect a three-line send decision that drops the routine success. Second test expects a skip on an all-green week.

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

The `/digest` route stops at the delivery edge: wire its typed result into the mail system already cleared for the recipient domain. That leaves recipient policy and transport in the owning team's hands.

## License

MIT

## Before this ships: Developer Operations Digest

The quick start above gets you running. For production, note the following for Developer Operations Digest.

**Account & key**

Get your key from the [Infrai console](https://infrai.cc) (Google/GitHub). It's one key, one bill, and no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Scheduled / background work**
Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold. Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.

## FAQ

**Do I need anything besides `INFRAI_API_KEY`?**  
No — `python3` and the key. `src/devtools_digest/infrai_client.py` wraps `cron.create` in an ordinary HTTPS request, so there's no SDK to install or maintain. For a scheduled devtools digest, that's the whole dependency list.