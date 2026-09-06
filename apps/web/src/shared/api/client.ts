type ApiRequestOptions = Omit<RequestInit, "body"> & { body?: unknown };

export class ApiError extends Error {
  readonly status: number;
  readonly data: unknown;

  constructor(status: number, data: unknown) {
    super(`API request failed (${status})`);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

export function createApiClient(baseUrl: string | undefined) {
  return async function request<T = unknown>(
    path: string,
    { body, headers: customHeaders, ...options }: ApiRequestOptions = {},
  ): Promise<T> {
    if (!baseUrl) throw new Error("API base URL is not configured");

    const base = new URL(`${baseUrl.replace(/\/+$/, "")}/`);
    const url = new URL(path.replace(/^\/+/, ""), base);
    if (!/^https?:$/.test(base.protocol) || !url.href.startsWith(base.href)) {
      throw new Error("API requests must stay within the configured HTTP(S) base URL");
    }

    const headers = new Headers(customHeaders);
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    if (body !== undefined) headers.set("Content-Type", "application/json");

    const response = await fetch(url, {
      ...options,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    let data: unknown = text || undefined;
    try {
      data = text ? JSON.parse(text) : undefined;
    } catch (error) {
      if (response.ok) throw error;
    }
    if (!response.ok) throw new ApiError(response.status, data);
    return data as T;
  };
}
