import { health } from "../helpers/BodulHalCore";
export async function handle(_request: Request) {
  return new Response(JSON.stringify(health()), {
    status: 200,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}
