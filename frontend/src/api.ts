
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


export type MailBuddyFeedback = {
  thread_id: string;
  priority: "critical" | "high" | "medium" | "low";
  category:
    | "career"
    | "academics"
    | "personal"
    | "financial"
    | "security"
    | "news"
    | "promotion"
    | "social"
    | "other";
  note: string;
  remember_preference: boolean;
};

const feedbackBaseUrl =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";

export async function loadFeedback(
  threadId: string
): Promise<MailBuddyFeedback | null> {
  const response = await fetch(
    `${feedbackBaseUrl}/feedback/${encodeURIComponent(threadId)}`
  );

  if (!response.ok) {
    throw new Error("Could not load feedback.");
  }

  return response.json();
}

export async function submitFeedback(
  data: MailBuddyFeedback
): Promise<void> {
  const response = await fetch(
    `${feedbackBaseUrl}/feedback`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(data),
    }
  );

  if (!response.ok) {
    const result = await response.json().catch(() => null);

    throw new Error(
      typeof result?.detail === "string"
        ? result.detail
        : "Could not save feedback."
    );
  }
}
