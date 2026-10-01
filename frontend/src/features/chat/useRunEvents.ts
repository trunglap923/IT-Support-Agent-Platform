import { useCallback, useEffect, useState } from "react";

import {
  consumeRunEvents,
  getRunSnapshot,
  type RunConnectionState,
  type RunEventData,
  type RunSnapshot,
  type RunStatus,
} from "../../api/run-events";

const knownStatuses = new Set<RunStatus>([
  "queued",
  "running",
  "waiting_approval",
  "resume_queued",
  "completed",
  "failed",
  "cancelled",
]);

export function streamedTextAfterEvent(
  current: string,
  event: RunEventData,
): string {
  if (event.type === "assistant.stream.started") return "";
  if (event.type !== "assistant.stream.delta") return current;
  const delta = event.payload.delta;
  return typeof delta === "string" ? current + delta : current;
}

function statusFromEvent(event: RunEventData): RunStatus | null {
  const value = event.type.startsWith("run.") ? event.type.slice(4) : "";
  return knownStatuses.has(value as RunStatus) ? (value as RunStatus) : null;
}

export function useRunEvents(runId: string) {
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null);
  const [events, setEvents] = useState<RunEventData[]>([]);
  const [streamedText, setStreamedText] = useState("");
  const [connectionState, setConnectionState] = useState<RunConnectionState>("closed");
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    const receivedSequences = new Set<number>();
    let active = true;

    void Promise.resolve()
      .then(() => {
        if (!active) return;
        setSnapshot(null);
        setEvents([]);
        setStreamedText("");
        setError(null);
        setConnectionState("connecting");
      })
      .then(() => getRunSnapshot(runId, controller.signal))
      .then(async (initial) => {
        if (!active) return;
        setSnapshot(initial);
        if (["completed", "failed", "cancelled"].includes(initial.status)) {
          setConnectionState("closed");
          return;
        }
        const finalSnapshot = await consumeRunEvents(runId, {
          signal: controller.signal,
          onConnectionState: (state) => {
            if (active) setConnectionState(state);
          },
          onEvent: (event) => {
            if (!active || receivedSequences.has(event.sequence)) return;
            receivedSequences.add(event.sequence);
            setEvents((current) => [...current, event]);
            setStreamedText((current) => streamedTextAfterEvent(current, event));
            const status = statusFromEvent(event);
            if (status) setSnapshot((current) => (current ? { ...current, status } : current));
          },
        });
        if (active) setSnapshot(finalSnapshot);
      })
      .catch((caught: unknown) => {
        if (active && !(caught instanceof DOMException && caught.name === "AbortError")) {
          setConnectionState("closed");
          setError(caught instanceof Error ? caught.message : "Không thể theo dõi run.");
        }
      });

    return () => {
      active = false;
      controller.abort();
    };
  }, [runId, attempt]);

  return { snapshot, events, streamedText, connectionState, error, retry };
}
