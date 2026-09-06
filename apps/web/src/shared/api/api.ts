import { createApiClient } from "./client";

export const api = createApiClient(process.env.NEXT_PUBLIC_API_URL);
