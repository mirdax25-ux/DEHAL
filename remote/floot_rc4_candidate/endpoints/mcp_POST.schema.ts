import { z } from "zod";

export const schema = z.any();
export type InputType = z.infer<typeof schema>;
export type OutputType = unknown;

export const postMcp = async (body: InputType, init?: RequestInit): Promise<OutputType> => {
  const response = await fetch("/_api/mcp", {
    method: "POST",
    body: JSON.stringify(body),
    ...init,
    headers: { "Content-Type": "application/json", "Accept": "application/json, text/event-stream", ...(init?.headers ?? {}) },
  });
  if (!response.ok) throw new Error(await response.text());
  return JSON.parse(await response.text());
};
