export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(message: string, code: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.code = code
    this.status = status
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal, headers: { Accept: "application/json" } })
  if (!response.ok) {
    throw await readError(response)
  }
  return (await response.json()) as T
}

export async function apiPost<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    signal,
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    throw await readError(response)
  }
  return (await response.json()) as T
}

export async function apiPostFile<T>(path: string, file: File, signal?: AbortSignal): Promise<T> {
  const form = new FormData()
  form.append("file", file)
  const response = await fetch(path, { method: "POST", body: form, signal, headers: { Accept: "application/json" } })
  if (!response.ok) {
    throw await readError(response)
  }
  return (await response.json()) as T
}

async function readError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { message?: unknown; code?: unknown }
    const message = typeof body.message === "string" ? body.message : response.statusText
    const code = typeof body.code === "string" ? body.code : "http_error"
    return new ApiError(message, code, response.status)
  } catch {
    return new ApiError(response.statusText || "Request failed", "http_error", response.status)
  }
}
