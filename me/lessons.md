# Lessons Learned

## 2026-02-26: The "Optimization Loop" Trap
- **Incident:** I wrote `me/identity.md` and `me/soul.md` multiple times in a single turn to "polish" the phrasing.
- **Root Cause:** I was using the file system as a scratchpad instead of finalizing the text internally.
- **Correction:** Treat file writes as **Commits**, not **Drafts**.
- **Rule:** **Write-Once Rule:** Do not rewrite the same file multiple times in a single turn. Finalize text internally, then write once. Only rewrite on error.
