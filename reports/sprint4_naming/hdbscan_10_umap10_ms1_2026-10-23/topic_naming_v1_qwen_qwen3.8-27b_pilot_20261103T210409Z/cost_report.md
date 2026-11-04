# Topic naming cost and rate-limit report — topic_naming_v1_qwen_qwen3.8-27b_pilot_20261103T210409Z

- Scope **pilot**, run status **completed**
- Model requested `qwen/qwen3.8-27b`; served `qwen/qwen3.8-27b`
- Pricing `groq_qwen_qwen3.8-27b_2026-11-03` (verified 2026-11-03; sha 52ee3ff6493f); source https://console.groq.com/docs/models
- Budget $1.00000000 on estimated cost at published rates (Groq returns no charge) — pre-request checks use an estimate and cannot guarantee an exact cap

| Topics | requested | successful | failed | not attempted | local cache hits | resumed |
|---|---|---|---|---|---|---|
| | 24 | 24 | 0 | 0 | 0 | 0 |

| Tokens | input | output | reasoning | cached input |
|---|---|---|---|---|
| | 22952 | 3054 | 0 | 0 |

**Estimated cost (published rates): $0.03057760** (incomplete: see unknown_cost_attempts / error_attempts_without_usage). **Billed cost: unknown** (not_determinable_from_api: Groq returns no charge and does not document free-tier billing; check the Groq console. Unknown billing is never reported as zero).

- API attempts 27 {'api_error': 3, 'ok': 24}, retries 3; unknown-cost attempts 0; error attempts without usage 3
- Average estimated cost per successful topic: $0.00127407
- Remaining topics 350 → estimated $0.44592333; projected full run $0.47650093

## Rate limits

- Plan `free` × safety 0.9; configured {'rpm': 30, 'rpd': 1000, 'tpm': 8000, 'tpd': 200000, 'input_tpm': None, 'output_tpm': None}; from headers {'rpd': 1000, 'tpm': 8000} (requests headers = per day, tokens headers = per minute)
- Requests {'total': 27, 'successful': 24, 'failed': 3, 'http_429': 0}; waits {'throttle': 231.702, 'backoff_and_retry_after': 8.539, 'total': 240.241} s; daily quota exhaustion events 0
- **Provider-reported** RPD {'limit': 1000, 'remaining': 973, 'reset_at_utc': '2026-11-03T21:48:46+00:00'}, TPM {'limit': 8000, 'remaining': 6001, 'reset_at_utc': '2026-11-03T21:10:08+00:00'}, TPD: not reported in headers by Groq; from 429 messages —
- **Local estimate** (this machine, rolling windows; not Groq's reset rule): 27 requests / 26006 tokens in the last 24 h
- Last quota stop: —
- Remaining topics 0; resume: not needed (not before unknown, not applicable)

## Offline estimate before the run (no API call)

| | topics | tokens typical / upper | est. cost typical / upper |
|---|---|---|---|
| selected | 24 | 33635 / 52168 | $0.04226800 / $0.08105600 |
| full run | 374 | 528693 / 819375 | $0.66231440 / $1.26826160 |

Estimates are not billed charges. Unknown amounts are never shown as 0.
