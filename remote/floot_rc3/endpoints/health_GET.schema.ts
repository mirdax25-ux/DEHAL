import { z } from "zod";
export const schema = z.object({});
export type InputType = z.infer<typeof schema>;
export type OutputType = Record<string, unknown>;
export const getHealth = async (): Promise<OutputType> => {
  const response = await fetch("/_api/health");
  if (!response.ok) throw new Error(await response.text());
  return await response.json();
};
