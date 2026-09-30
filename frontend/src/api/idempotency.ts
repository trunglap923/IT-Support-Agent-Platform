export interface ClientRequestIdentity {
  fingerprint: string;
  id: string;
}

export function getOrCreateClientRequest(
  current: ClientRequestIdentity | null,
  fingerprint: string,
  createId: () => string = () => crypto.randomUUID(),
): ClientRequestIdentity {
  if (current?.fingerprint === fingerprint) return current;
  return { fingerprint, id: createId() };
}
