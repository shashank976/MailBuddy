
import { useEffect, useMemo, useState } from "react";
import {
  Archive,
  ArrowDownToLine,
  Check,
  ChevronDown,
  ChevronRight,
  CircleAlert,
  Clock3,
  ExternalLink,
  Inbox,
  LoaderCircle,
  Mail,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  X,
} from "lucide-react";

import { api } from "./api";

import type {
  AnalyzeRequest,
  ConversationCard,
  DashboardGroup,
  HealthResponse,
} from "./types";

import "./styles.css";

const DEFAULT_PRIORITIES =
  "Prioritize recruiting emails, software engineering internships, " +
  "academic deadlines, security alerts, and important personal messages. " +
  "Treat routine promotions and newsletters as low priority.";

const DEFAULT_SETTINGS: AnalyzeRequest = {
  hours: 24,
  max_threads: 20,
  max_workers: 2,
  user_priorities: DEFAULT_PRIORITIES,
};

type Filter = DashboardGroup | "all";

const GROUPS: {
  id: DashboardGroup;
  label: string;
  description: string;
}[] = [
  {
    id: "needs_attention",
    label: "Needs Attention",
    description: "May require a response or review",
  },
  {
    id: "important_updates",
    label: "Important Updates",
    description: "Worth checking",
  },
  {
    id: "low_priority",
    label: "Low Priority",
    description: "Can wait",
  },
  {
    id: "cleanup",
    label: "Cleanup",
    description: "Potential archive or unsubscribe",
  },
];

function formatDate(timestamp: number): string {
  return new Date(timestamp).toLocaleDateString(
    undefined,
    {
      month: "short",
      day: "numeric",
    }
  );
}

function formatDateTime(timestamp: number): string {
  return new Date(timestamp).toLocaleString(
    undefined,
    {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }
  );
}

function senderName(sender: string): string {
  const match = sender.match(/^(.*?)\s*</);

  return (
    match?.[1] || sender || "Unknown"
  )
    .replace(/"/g, "")
    .trim();
}

function groupName(group: DashboardGroup): string {
  return (
    GROUPS.find((item) => item.id === group)
      ?.label ?? "Other"
  );
}

function getInitialSettings(): AnalyzeRequest {
  try {
    const saved = localStorage.getItem(
      "mailbuddy.preferences"
    );

    if (!saved) return { ...DEFAULT_SETTINGS };

    const parsed: Partial<AnalyzeRequest> =
      JSON.parse(saved);

    return {
      hours:
        typeof parsed.hours === "number" &&
        [24, 48, 72, 168].includes(parsed.hours)
          ? parsed.hours
          : DEFAULT_SETTINGS.hours,

      max_threads:
        typeof parsed.max_threads === "number" &&
        [5, 10, 20, 50].includes(parsed.max_threads)
          ? parsed.max_threads
          : DEFAULT_SETTINGS.max_threads,

      max_workers:
        typeof parsed.max_workers === "number" &&
        parsed.max_workers >= 1 &&
        parsed.max_workers <= 4
          ? parsed.max_workers
          : DEFAULT_SETTINGS.max_workers,

      user_priorities:
        typeof parsed.user_priorities === "string"
          ? parsed.user_priorities.slice(0, 2000)
          : DEFAULT_SETTINGS.user_priorities,
    };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

function GroupIcon({
  group,
  size = 17,
}: {
  group: DashboardGroup;
  size?: number;
}) {
  if (group === "needs_attention") {
    return <CircleAlert size={size} />;
  }

  if (group === "important_updates") {
    return <Mail size={size} />;
  }

  if (group === "low_priority") {
    return <Clock3 size={size} />;
  }

  return <Archive size={size} />;
}

function MailBuddyLogo() {
  return (
    <div className="brand">
      <img
        src="/mailbuddy.png"
        alt="MailBuddy mascot"
        className="brand-image"
      />

      <div className="brand-copy">
        <strong>mailbuddy</strong>
        <span>your inbox sidekick</span>
      </div>
    </div>
  );
}

function ConversationRow({
  card,
  selected,
  onSelect,
}: {
  card: ConversationCard;
  selected: boolean;
  onSelect: () => void;
}) {
  const sender = senderName(
    card.senders[0] || "Unknown"
  );

  return (
    <button
      type="button"
      className={`conversation-row ${
        selected ? "selected" : ""
      }`}
      onClick={onSelect}
      aria-pressed={selected}
    >
      <div className="conversation-avatar">
        {sender.charAt(0).toUpperCase()}
      </div>

      <div className="conversation-content">
        <div className="conversation-topline">
          <span className="conversation-sender">
            {sender}
          </span>

          <time className="conversation-date">
            {formatDate(
              card.latest_received_at_ms
            )}
          </time>
        </div>

        <div className="conversation-subject">
          {card.subject || "(No subject)"}
        </div>

        <p className="conversation-summary">
          {card.summary}
        </p>

        <div className="conversation-meta">
          <span
            className={`priority-label priority-${card.priority}`}
          >
            <span className="priority-dot" />
            {card.priority}
          </span>

          <span className="meta-divider">/</span>

          <span className="category-label">
            {card.category}
          </span>

          {card.needs_review && (
            <span className="review-label">
              Review needed
            </span>
          )}

          {card.message_count > 1 && (
            <span className="message-count">
              {card.message_count} messages
            </span>
          )}
        </div>
      </div>

      <ChevronRight
        size={17}
        className="conversation-chevron"
      />
    </button>
  );
}

function ConversationDetails({
  card,
  onClose,
}: {
  card: ConversationCard;
  onClose: () => void;
}) {
  const sender = senderName(
    card.senders[0] || "Unknown"
  );

  const cleanup = card.cleanup;

  return (
    <aside
      className="detail-panel"
      aria-label="Conversation details"
    >
      <div className="detail-panel-header">
        <span>Conversation details</span>

        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Close conversation details"
        >
          <X size={18} />
        </button>
      </div>

      <div className="detail-body">
        <div className="detail-sender-row">
          <div className="detail-avatar">
            {sender.charAt(0).toUpperCase()}
          </div>

          <div>
            <strong>{sender}</strong>
            <small>
              {formatDateTime(
                card.latest_received_at_ms
              )}
            </small>
          </div>
        </div>

        <h2 className="detail-subject">
          {card.subject || "(No subject)"}
        </h2>

        <div className="detail-group">
          <GroupIcon
            group={card.dashboard_group}
            size={16}
          />

          <span>
            {groupName(card.dashboard_group)}
          </span>
        </div>

        {card.needs_review && (
          <div className="review-notice">
            <CircleAlert size={18} />

            <p>
              MailBuddy is unsure about part of
              this analysis. Review the original
              email before acting.
            </p>
          </div>
        )}

        <div className="detail-section">
          <h3>Summary</h3>
          <p>{card.summary}</p>
        </div>

        <div className="detail-section">
          <h3>Classification</h3>

          <dl className="detail-definition">
            <div>
              <dt>Priority</dt>
              <dd className={`priority-${card.priority}`}>
                {card.priority}
              </dd>
            </div>

            <div>
              <dt>Category</dt>
              <dd>{card.category}</dd>
            </div>

            <div>
              <dt>Action status</dt>
              <dd>{card.action_status}</dd>
            </div>

            <div>
              <dt>Messages</dt>
              <dd>{card.message_count}</dd>
            </div>
          </dl>
        </div>

        {card.requires_action &&
          card.suggested_action && (
            <div className="detail-section">
              <h3>Suggested next step</h3>

              <div className="suggested-action">
                <CircleAlert size={17} />
                <p>{card.suggested_action}</p>
              </div>
            </div>
          )}

        <div className="detail-section">
          <h3>Action assessment</h3>
          <p>{card.action_reason}</p>
        </div>

        {cleanup && (
          <div className="detail-section">
            <h3>Cleanup recommendation</h3>

            <div className="cleanup-recommendation">
              <div className="cleanup-title">
                {cleanup.action === "keep" ? (
                  <Check size={17} />
                ) : (
                  <Archive size={17} />
                )}

                <strong>
                  {cleanup.action === "keep"
                    ? "Keep conversation"
                    : cleanup.action === "archive"
                    ? "Suggest archive"
                    : "Suggest unsubscribe"}
                </strong>
              </div>

              <p>{cleanup.reason}</p>

              {cleanup.action !== "keep" && (
                <small>
                  Recommendation only. No Gmail
                  changes have been made.
                </small>
              )}
            </div>
          </div>
        )}

        <a
          href={card.gmail_url}
          target="_blank"
          rel="noopener noreferrer"
          className="gmail-button"
        >
          Open conversation in Gmail
          <ExternalLink size={16} />
        </a>

        <p className="detail-footnote">
          AI classifications may contain errors.
          Always verify important information
          in Gmail.
        </p>
      </div>
    </aside>
  );
}

function App() {
  const [cards, setCards] =
    useState<ConversationCard[]>([]);

  const [lastAnalyzed, setLastAnalyzed] =
    useState<string | null>(null);

  const [health, setHealth] =
    useState<HealthResponse | null>(null);

  const [filter, setFilter] =
    useState<Filter>("all");

  const [search, setSearch] = useState("");

  const [selectedId, setSelectedId] =
    useState<string | null>(null);

  const [settings, setSettings] =
    useState<AnalyzeRequest>(getInitialSettings);

  const [draftSettings, setDraftSettings] =
    useState<AnalyzeRequest>(settings);

  const [settingsOpen, setSettingsOpen] =
    useState(false);

  const [analyzing, setAnalyzing] =
    useState(false);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [dashboard, status] =
          await Promise.all([
            api.conversations(),
            api.health(),
          ]);

        if (cancelled) return;

        setCards(dashboard.cards);
        setLastAnalyzed(
          dashboard.last_analyzed_at
        );
        setHealth(status);
        setError(null);
      } catch (err) {
        if (cancelled) return;

        setError(
          err instanceof Error
            ? err.message
            : "Could not load MailBuddy."
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    load();

    return () => {
      cancelled = true;
    };
  }, []);

  const counts = useMemo(() => {
    const result: Record<
      DashboardGroup,
      number
    > = {
      needs_attention: 0,
      important_updates: 0,
      low_priority: 0,
      cleanup: 0,
    };

    for (const card of cards) {
      result[card.dashboard_group] += 1;
    }

    return result;
  }, [cards]);

  const visibleCards = useMemo(() => {
    const query = search
      .trim()
      .toLowerCase();

    return cards
      .filter(
        (card) =>
          filter === "all" ||
          card.dashboard_group === filter
      )
      .filter((card) => {
        if (!query) return true;

        return [
          card.subject,
          ...card.senders,
          card.summary,
          card.category,
        ].some((value) =>
          value.toLowerCase().includes(query)
        );
      })
      .sort(
        (a, b) =>
          b.latest_received_at_ms -
          a.latest_received_at_ms
      );
  }, [cards, filter, search]);

  const selectedCard =
    cards.find(
      (card) =>
        card.thread_id === selectedId
    ) ?? null;

  async function analyzeInbox() {
    if (analyzing) return;

    setAnalyzing(true);
    setError(null);

    try {
      const response =
        await api.analyze(settings);

      setCards(response.cards);
      setLastAnalyzed(
        response.last_analyzed_at
      );

      const updatedHealth =
        await api.health();

      setHealth(updatedHealth);

      if (
        selectedId &&
        !response.cards.some(
          (card) =>
            card.thread_id === selectedId
        )
      ) {
        setSelectedId(null);
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Inbox analysis failed."
      );
    } finally {
      setAnalyzing(false);
    }
  }

  function openSettings() {
    setDraftSettings({ ...settings });
    setSettingsOpen(true);
  }

  function saveSettings() {
    setSettings({ ...draftSettings });

    try {
      localStorage.setItem(
        "mailbuddy.preferences",
        JSON.stringify(draftSettings)
      );
    } catch {
      // Still allow using the settings
      // for this browser session.
    }

    setSettingsOpen(false);
  }

  const attentionCount =
    counts.needs_attention;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <MailBuddyLogo />

        <div className="sidebar-navigation">
          <div className="nav-heading">
            Inbox
          </div>

          <button
            type="button"
            className={`nav-item ${
              filter === "all"
                ? "active"
                : ""
            }`}
            onClick={() => {
              setFilter("all");
              setSelectedId(null);
            }}
          >
            <Inbox size={18} />
            <span>All conversations</span>
            <span className="nav-count">
              {cards.length}
            </span>
          </button>

          {GROUPS.map((group) => (
            <button
              type="button"
              key={group.id}
              className={`nav-item ${
                filter === group.id
                  ? "active"
                  : ""
              }`}
              onClick={() => {
                setFilter(group.id);
                setSelectedId(null);
              }}
            >
              <GroupIcon group={group.id} />

              <span>{group.label}</span>

              <span className="nav-count">
                {counts[group.id]}
              </span>
            </button>
          ))}
        </div>

        <div className="sidebar-bottom">
          <div className="privacy-status">
            <ShieldCheck size={17} />
            <div>
              <strong>Local by design</strong>
              <span>
                Analysis stays on this device
              </span>
            </div>
          </div>

          <button
            type="button"
            className="sidebar-settings"
            onClick={openSettings}
          >
            <Settings2 size={17} />
            Preferences
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="app-topbar">
          <div className="topbar-location">
            MailBuddy
            <ChevronRight size={14} />
            <span>Inbox</span>
          </div>

          <div className="topbar-right">
            <span
              className={`connection-indicator ${
                health?.ollama_available
                  ? "connected"
                  : ""
              }`}
            />

            <span>
              {health?.ollama_available
                ? "Ollama connected"
                : "Ollama unavailable"}
            </span>
          </div>
        </header>

        <div className="workspace">
          <section className="page-header">
            <div className="page-heading">
              <div className="heading-title">
                <h1>Inbox overview</h1>

                <img
                  src="/mailbuddy.png"
                  alt=""
                  className="heading-mascot"
                />
              </div>

              <p>
                {cards.length === 0
                  ? "Your conversations will appear here after a scan."
                  : attentionCount > 0
                  ? `${attentionCount} conversation${
                      attentionCount === 1
                        ? ""
                        : "s"
                    } flagged for attention.`
                  : "Nothing currently flagged for attention."}
              </p>

              <div className="scan-metadata">
                <Clock3 size={14} />

                <span>
                  {lastAnalyzed
                    ? `Last scan: ${new Date(
                        lastAnalyzed
                      ).toLocaleString()}`
                    : "Not scanned yet"}
                </span>
              </div>
            </div>

            <div className="header-actions">
              <button
                type="button"
                className="outline-button"
                onClick={openSettings}
              >
                <SlidersHorizontal size={16} />
                Preferences
              </button>

              <button
                type="button"
                className="analyze-button"
                onClick={analyzeInbox}
                disabled={analyzing || loading}
              >
                {analyzing ? (
                  <LoaderCircle
                    size={17}
                    className="spin"
                  />
                ) : (
                  <RefreshCw size={17} />
                )}

                {analyzing
                  ? "Analyzing..."
                  : "Analyze inbox"}
              </button>
            </div>
          </section>

          <section
            className="overview-strip"
            aria-label="Conversation counts"
          >
            {GROUPS.map((group) => (
              <button
                key={group.id}
                type="button"
                className={`overview-item ${
                  filter === group.id
                    ? "active"
                    : ""
                }`}
                onClick={() => {
                  setFilter(group.id);
                  setSelectedId(null);
                }}
              >
                <span className="overview-number">
                  {counts[group.id]}
                </span>

                <span className="overview-copy">
                  <strong>{group.label}</strong>
                  <small>
                    {group.description}
                  </small>
                </span>
              </button>
            ))}
          </section>

          {error && (
            <div
              className="error-banner"
              role="alert"
            >
              <CircleAlert size={18} />

              <span>{error}</span>

              <button
                type="button"
                onClick={() => setError(null)}
                aria-label="Dismiss error"
              >
                <X size={17} />
              </button>
            </div>
          )}

          <section className="inbox-workspace">
            <div className="inbox-toolbar">
              <div className="inbox-toolbar-title">
                <h2>
                  {filter === "all"
                    ? "All conversations"
                    : groupName(filter)}
                </h2>

                <span>
                  {visibleCards.length} total
                </span>
              </div>

              <div className="toolbar-controls">
                <label className="search-field">
                  <Search size={17} />

                  <input
                    type="search"
                    value={search}
                    onChange={(event) =>
                      setSearch(
                        event.target.value
                      )
                    }
                    placeholder="Search emails"
                  />
                </label>

                <button
                  type="button"
                  className="filter-button"
                  onClick={() => {
                    setFilter("all");
                    setSearch("");
                    setSelectedId(null);
                  }}
                  title="Clear filters"
                >
                  <ArrowDownToLine size={16} />
                  Reset
                </button>
              </div>
            </div>

            <div className="inbox-content">
              <div className="conversation-list">
                {loading ? (
                  <div className="empty-state">
                    <LoaderCircle
                      className="spin"
                      size={28}
                    />
                    <p>Loading saved conversations...</p>
                  </div>
                ) : visibleCards.length === 0 ? (
                  <div className="empty-state">
                    <img
                      src="/mailbuddy.png"
                      alt=""
                      className="empty-mascot"
                    />

                    <h3>
                      {cards.length === 0
                        ? "No analysis yet"
                        : "No matching conversations"}
                    </h3>

                    <p>
                      {cards.length === 0
                        ? "Run Analyze inbox to organize your recent Gmail conversations."
                        : "Try a different search or inbox category."}
                    </p>
                  </div>
                ) : (
                  visibleCards.map((card) => (
                    <ConversationRow
                      key={card.thread_id}
                      card={card}
                      selected={
                        selectedId === card.thread_id
                      }
                      onSelect={() =>
                        setSelectedId(
                          card.thread_id
                        )
                      }
                    />
                  ))
                )}
              </div>

              {selectedCard && (
                <ConversationDetails
                  card={selectedCard}
                  onClose={() =>
                    setSelectedId(null)
                  }
                />
              )}
            </div>
          </section>

          <footer className="app-footer">
            <span>
              MailBuddy runs locally. Gmail
              stays in your Google account.
            </span>

            <span>
              No email actions are performed
              without approval.
            </span>
          </footer>
        </div>
      </main>

      {settingsOpen && (
        <div
          className="modal-overlay"
          onMouseDown={(event) => {
            if (
              event.target ===
              event.currentTarget
            ) {
              setSettingsOpen(false);
            }
          }}
        >
          <div
            className="settings-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-title"
          >
            <div className="modal-header">
              <div>
                <h2 id="settings-title">
                  Preferences
                </h2>

                <p>
                  Decide what MailBuddy should
                  pay attention to.
                </p>
              </div>

              <button
                type="button"
                className="icon-button"
                onClick={() =>
                  setSettingsOpen(false)
                }
                aria-label="Close settings"
              >
                <X size={20} />
              </button>
            </div>

            <label
              className="form-label"
              htmlFor="user-priorities"
            >
              Your priorities
            </label>

            <textarea
              id="user-priorities"
              rows={6}
              maxLength={2000}
              value={
                draftSettings.user_priorities
              }
              onChange={(event) =>
                setDraftSettings({
                  ...draftSettings,
                  user_priorities:
                    event.target.value,
                })
              }
            />

            <p className="field-description">
              Use plain language. For example:
              prioritize job interviews, school
              deadlines, or messages that need
              a reply.
            </p>

            <div className="form-grid">
              <label>
                Scan period
                <select
                  value={draftSettings.hours}
                  onChange={(event) =>
                    setDraftSettings({
                      ...draftSettings,
                      hours: Number(
                        event.target.value
                      ),
                    })
                  }
                >
                  <option value={24}>
                    Last 24 hours
                  </option>
                  <option value={48}>
                    Last 48 hours
                  </option>
                  <option value={72}>
                    Last 3 days
                  </option>
                  <option value={168}>
                    Last 7 days
                  </option>
                </select>
                <ChevronDown
                  size={15}
                  className="select-chevron"
                />
              </label>

              <label>
                Max conversations
                <select
                  value={
                    draftSettings.max_threads
                  }
                  onChange={(event) =>
                    setDraftSettings({
                      ...draftSettings,
                      max_threads: Number(
                        event.target.value
                      ),
                    })
                  }
                >
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                </select>
                <ChevronDown
                  size={15}
                  className="select-chevron"
                />
              </label>

              <label>
                Parallel workers
                <select
                  value={
                    draftSettings.max_workers
                  }
                  onChange={(event) =>
                    setDraftSettings({
                      ...draftSettings,
                      max_workers: Number(
                        event.target.value
                      ),
                    })
                  }
                >
                  <option value={1}>1</option>
                  <option value={2}>2</option>
                  <option value={3}>3</option>
                  <option value={4}>4</option>
                </select>
                <ChevronDown
                  size={15}
                  className="select-chevron"
                />
              </label>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="outline-button"
                onClick={() =>
                  setSettingsOpen(false)
                }
              >
                Cancel
              </button>

              <button
                type="button"
                className="analyze-button"
                onClick={saveSettings}
              >
                <Check size={17} />
                Save preferences
              </button>
            </div>

            <p className="modal-note">
              Settings are stored in this browser.
              They take effect on your next scan.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
