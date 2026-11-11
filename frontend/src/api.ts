
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  DashboardResponse,
  HealthResponse,
} from "./types";

const API_BASE =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });
  } catch {
    throw new Error(
      "Cannot connect to MailBuddy's backend. Check that FastAPI is running."
    );
  }

  if (!response.ok) {
    if (response.status === 409) {
      throw new Error(
        "An inbox analysis is already running."
      );
    }

    throw new Error(
      `Request failed (${response.status}). Check your backend terminal.`
    );
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () =>
    request<HealthResponse>("/health"),

  conversations: () =>
    request<DashboardResponse>("/conversations"),

  analyze: (settings: AnalyzeRequest) =>
    request<AnalyzeResponse>("/analyze", {
      method: "POST",
      body: JSON.stringify(settings),
    }),
};

export async function resetMailBuddy(): Promise<void> {
  const baseUrl =
    import.meta.env.VITE_API_URL ||
    "http://127.0.0.1:8000";

  const response = await fetch(`${baseUrl}/reset`, {
    method: "POST",
  });

  if (!response.ok) {
    let message = "Failed to reset MailBuddy.";

    if (response.status === 409) {
      message = "Wait for the current scan to finish.";
    }

    throw new Error(message);
  }
}