export function ErrorText({error}:{error:unknown}) {
  if (!error) return null
  return <p role="alert" className="error">{error instanceof Error ? error.message : String(error)}</p>
}

export function Loading() {
  return <div role="status" className="muted">Loading…</div>
}
