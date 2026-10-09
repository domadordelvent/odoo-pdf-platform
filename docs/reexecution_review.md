# Error handling and reexecution review

`action_process()` now rejects a recordset containing a non-draft job before
changing states or generating attachments. Previously a second call on a done
job generated new outputs and replaced the relation, leaving the old attachments
linked to the job but absent from its output list. Rejection preserves done,
processing and failed states and their existing error messages.

The existing retry flow is unchanged: a failure rolls back the job savepoint,
records failed and a safe message, and can be reset to draft and processed again.
Partial output attachments are rolled back transactionally. Compression uses
TemporaryDirectory and removes temporary inputs and outputs on ordinary errors,
timeouts and invalid results; no cleanup change was necessary.

Pending: the state check is not an explicit lock across concurrent HTTP requests.
Two requests may both initially observe draft. PostgreSQL/Odoo transaction
conflicts and retries may prevent duplicate commits, but this was not verified
with independent concurrent transactions. An explicit locking/idempotency change
and concurrent-request tests need a separate review.

Abrupt worker termination (for example SIGKILL or a server crash) cannot run
TemporaryDirectory cleanup and can leave a temporary directory. Odoo attachment
filestore objects written in a rolled-back transaction rely on its normal garbage
collector; they are not application temporary files. These lifecycle concerns
were left outside this narrow correction. V1, V2 and V3 were not changed.
