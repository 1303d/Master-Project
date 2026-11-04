# Topic naming cost and rate-limit report — topic_naming_v1_claude-sonnet-5-5_pilot_20261104T001309Z

- Provider `anthropic`; scope **pilot**, run status **completed**
- Model requested `claude-sonnet-5-5`; served `claude-sonnet-5-5`
- Pricing `anthropic_claude-sonnet-5-5_2026-11-03` (verified 2026-11-03; sha e1ca9a7b88e6); source https://platform.claude.com/docs/en/about-claude/pricing
- Budget $1.00000000 on estimated cost at published rates (Anthropic returns no charge) — pre-request checks use an estimate and cannot guarantee an exact cap

| Topics | requested | successful | failed | not attempted | local cache hits | resumed |
|---|---|---|---|---|---|---|
| | 20 | 20 | 0 | 0 | 0 | 0 |

| Tokens | input | output | reasoning | cache write | cache read |
|---|---|---|---|---|---|
| | 34151 | 3733 | 0 | 0 | 0 |

**Estimated cost (published rates): $0.10563200** (input $0.06830200, output $0.03733000, cache $0.00000000; complete). **Billed cost: unknown** (not_determinable_from_api: the Messages API returns usage but no charge; check Usage / Billing in the Claude Console. Unknown billing is never reported as zero).

- API attempts 20 {'ok': 20}, retries 0; latency ms {'n': 20, 'mean': 2709.9, 'median': 2514.4, 'max': 4370.2}; unknown-cost attempts 0; error attempts without usage 0
- Average estimated cost per successful topic: $0.00528160
- Remaining topics 354 → estimated $1.86968640; projected full run $1.97531840

## Rate limits

- Plan `conservative` × safety 0.9; configured {'rpm': 50, 'rpd': None, 'tpm': None, 'tpd': None, 'input_tpm': 30000, 'output_tpm': 8000}; from headers {'tpm': 6000000, 'rpm': 10000, 'input_tpm': 5000000, 'output_tpm': 1000000}; header meaning {'anthropic-ratelimit-requests-*': 'requests per minute (token bucket)', 'anthropic-ratelimit-input-tokens-*': 'uncached input + cache-write tokens per minute', 'anthropic-ratelimit-output-tokens-*': 'output tokens per minute', 'anthropic-ratelimit-tokens-*': 'the most restrictive token limit', '*-reset': 'RFC 3339 time of full replenishment'}
- Requests {'total': 20, 'successful': 20, 'failed': 0, 'http_429': 0}; waits {'throttle': 0.0, 'backoff_and_retry_after': 0.0, 'total': 0.0} s; daily quota exhaustion events 0
- **Provider-reported**: RPD {'limit': None, 'remaining': None, 'reset_at_utc': None}, TPM {'limit': 6000000, 'remaining': 5999000, 'reset_at_utc': '2026-11-04T00:14:04+00:00'}, RPM {'limit': 10000, 'remaining': 9999, 'reset_at_utc': '2026-11-04T00:14:04+00:00'}, ITPM {'limit': 5000000, 'remaining': 4999000, 'reset_at_utc': '2026-11-04T00:14:04+00:00'}, OTPM {'limit': 1000000, 'remaining': 1000000, 'reset_at_utc': '2026-11-04T00:14:04+00:00'}; from 429 messages —
- **Local estimate** (this machine, rolling windows): 20 requests / 37884 tokens in the last minute; 20 / 37884 in 24 h
- Last quota stop: —
- Remaining topics 0; resume: not needed (not before unknown, not applicable)

## Offline estimate before the run (no API call)

| | topics | tokens typical / upper | est. cost typical / upper |
|---|---|---|---|
| selected | 20 | 34411 / 59854 | $0.10082200 / $0.28354800 |
| full run | 374 | 659593 / 1141763 | $1.91758600 / $5.34733400 |

Estimates are not billed charges. Unknown amounts are never shown as 0.
