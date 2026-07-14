# Pre-obtained confidential-ledger write receipts (committed fixtures)

This directory holds the anchoring evidence the `capsule_emit` trust plugin
replays onto the trace: one `<receipt_jcs_digest>.receipt.json` file per
receipt, each a **verifiable CCF / Azure Confidential Ledger write receipt**
(Merkle inclusion proof + service-identity signature over the tree head)
issued by the independent ledger whose service identity is pinned in
`nest_core.ccf_receipt.PINNED_ACL_SERVICE_IDENTITY_PEM`.

How they get here (operator-gated, out of band — network is allowed only in
this setup step, never in a graded run):

1. Compute each deterministic scenario receipt's JCS digest
   (`nest_core.canonical.jcs_digest`).
2. Append each digest as an application claim to the Azure Confidential
   Ledger instance (data-plane `ledgerUri`) and collect the returned write
   receipt once the transaction commits.
3. Commit each write receipt here as `<digest>.receipt.json`, and pin the
   ledger's service-identity certificate (fetched once from the ACL identity
   endpoint) in `nest_core.ccf_receipt.PINNED_ACL_SERVICE_IDENTITY_PEM`.

Until then this directory is intentionally empty and everything fails closed:
the plugin emits no `ccfreceipt:` lines and the anchored validator grades
FAIL.

**Never** commit receipts minted by `nest_mocks.ccf_ledger` (the LOCAL
TEST-ONLY ledger) here — its private keys are publicly derivable by design, so
its output is not evidence. Tests inject its service identity explicitly and
nothing else trusts it.
