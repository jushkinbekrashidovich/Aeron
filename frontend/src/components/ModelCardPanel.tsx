"use client";

import { useEffect, useState } from "react";

import { describeError, getModel, type ModelCard } from "@/lib/api";
import { formatDate } from "@/lib/dates";

/** Facts about the model that is serving the replay, read from the API's model card. */
export function ModelCardPanel() {
  const [card, setCard] = useState<ModelCard | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    getModel(controller.signal)
      .then(setCard)
      .catch((e) => {
        if (!controller.signal.aborted) setError(describeError(e));
      });
    return () => controller.abort();
  }, []);
  if (error) return <p role="alert">{error}</p>;
  if (!card) return <p>Loading model card…</p>;
  return (
    <dl className="grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[14rem_1fr]">
      <dt className="font-medium">Version</dt>
      <dd>{card.version}</dd>
      <dt className="font-medium">Model</dt>
      <dd>
        {card.model} (LightGBM, feature set “{card.feature_set}”)
      </dd>
      <dt className="font-medium">Trained on targets up to</dt>
      <dd>{formatDate(card.last_training_target_date)}</dd>
      <dt className="font-medium">Training rows by lead</dt>
      <dd>
        {Object.entries(card.per_lead)
          .map(([lead, v]) => `${lead} day: ${v.training_rows}`)
          .join(", ")}
      </dd>
      <dt className="font-medium">Code version</dt>
      <dd>{card.git_commit}</dd>
    </dl>
  );
}
