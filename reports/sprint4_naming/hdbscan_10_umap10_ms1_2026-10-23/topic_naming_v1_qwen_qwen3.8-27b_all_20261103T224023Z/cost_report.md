# Topic naming cost and rate-limit report — topic_naming_v1_qwen_qwen3.8-27b_all_20261103T224023Z

- Scope **all**, run status **quota_exhausted** (stop: rate limit: daily token limit (local estimate): 178850 + 2218 > 180000 tokens in this machine's last 24 h; Groq reports no TPD header and does not document the reset)
- Model requested `qwen/qwen3.8-27b`; served `qwen/qwen3.8-27b`
- Pricing `groq_qwen_qwen3.8-27b_2026-11-03` (verified 2026-11-03; sha 52ee3ff6493f); source https://console.groq.com/docs/models
- Budget $10.00000000 on estimated cost at published rates (Groq returns no charge) — pre-request checks use an estimate and cannot guarantee an exact cap

| Topics | requested | successful | failed | not attempted | local cache hits | resumed |
|---|---|---|---|---|---|---|
| | 374 | 146 | 0 | 228 | 9 | 0 |

| Tokens | input | output | reasoning | cached input |
|---|---|---|---|---|
| | 135736 | 17108 | 0 | 0 |

**Estimated cost (published rates): $0.17702080** (incomplete: see unknown_cost_attempts / error_attempts_without_usage). **Billed cost: unknown** (not_determinable_from_api: Groq returns no charge and does not document free-tier billing; check the Groq console. Unknown billing is never reported as zero).

- API attempts 140 {'api_error': 3, 'ok': 137}, retries 3; unknown-cost attempts 0; error attempts without usage 3
- Average estimated cost per successful topic: $0.00129212
- Remaining topics 228 → estimated $0.29460396; projected full run $0.48325386

## Rate limits

- Plan `free` × safety 0.9; configured {'rpm': 30, 'rpd': 1000, 'tpm': 8000, 'tpd': 200000, 'input_tpm': None, 'output_tpm': None}; from headers {'rpd': 1000, 'tpm': 8000} (requests headers = per day, tokens headers = per minute)
- Requests {'total': 140, 'successful': 137, 'failed': 3, 'http_429': 0}; waits {'throttle': 1496.2, 'backoff_and_retry_after': 6.875, 'total': 1503.075} s; daily quota exhaustion events 1
- **Provider-reported** RPD {'limit': 1000, 'remaining': 860, 'reset_at_utc': '2026-11-04T02:29:51+00:00'}, TPM {'limit': 8000, 'remaining': 5944, 'reset_at_utc': '2026-11-03T23:08:31+00:00'}, TPD: not reported in headers by Groq; from 429 messages —
- **Local estimate** (this machine, rolling windows; not Groq's reset rule): 167 requests / 178850 tokens in the last 24 h
- Last quota stop: {'reason': "daily token limit (local estimate): 178850 + 2218 > 180000 tokens in this machine's last 24 h; Groq reports no TPD header and does not document the reset", 'source': 'local_estimate', 'available_in_s': 78954.20340919495, 'available_at_utc': '2026-11-04T21:04:10+00:00', 'available_at_is': 'local estimate'}
- Remaining topics 228; resume: python src/topic_naming.py generate --live --resume topic_naming_v1_qwen_qwen3.8-27b_all_20261103T224023Z (not before 2026-11-04T21:04:10+00:00, local estimate)

## Offline estimate before the run (no API call)

| | topics | tokens typical / upper | est. cost typical / upper |
|---|---|---|---|
| selected | 374 | 528693 / 819375 | $0.66231440 / $1.26826160 |
| full run | 374 | 528693 / 819375 | $0.66231440 / $1.26826160 |

Estimates are not billed charges. Unknown amounts are never shown as 0.
