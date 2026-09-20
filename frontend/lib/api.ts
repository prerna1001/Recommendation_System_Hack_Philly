const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8010";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...options,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, `${res.status} ${res.statusText}: ${body}`);
  }
  return res.json();
}

export type Company = { id: number; name: string; email: string };

export type Member = {
  id: number;
  name: string;
  email: string;
  linkedin_url: string;
  photo_url: string;
};

export type EventSummary = {
  id: number;
  name: string;
  date: string;
  format: string;
  venue: string;
  registered_count: number | null;
  attended_count: number | null;
  weather_tag: string | null;
  turnout_reason: string | null;
  success_assessment: string | null;
  photo_url: string | null;
  sponsor_count: number;
  relevant_connection_rate: number | null;
};

export type Sponsor = {
  id: number;
  sponsor_name: string;
  sponsor_type: string;
  contribution_type: string;
  contact_person: string;
  how_connected: string;
};

export type FeedbackRow = {
  id: number;
  respondent: string;
  rating_turnout: number;
  had_relevant_connection: number;
  connection_relevance_rating: number;
  rating_format: number;
  rating_logistics: number;
  rating_sponsor_value: number;
  free_text: string;
};

export type RubricScore = { id: number; category: string; score: number; notes: string };

export type EventDetail = {
  event: EventSummary;
  sponsors: Sponsor[];
  feedback: FeedbackRow[];
  rubric_scores: RubricScore[];
};

export type ChatMessage = {
  id: number;
  role: "organizer" | "assistant";
  content: string;
  recommendation_id: number | null;
  created_at: string;
};

export type ChatSession = {
  id: number;
  title: string | null;
  created_at: string;
  preview: string | null;
};

export const api = {
  auth: {
    signup: (company_name: string, email: string, password: string) =>
      request<Company>("/auth/signup", {
        method: "POST",
        body: JSON.stringify({ company_name, email, password }),
      }),
    login: (email: string, password: string) =>
      request<Company>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
    logout: () => request("/auth/logout", { method: "POST" }),
    me: () => request<Company>("/auth/me"),
  },

  listMembers: () => request<Member[]>("/members"),
  addMember: (member: Omit<Member, "id">) =>
    request<Member>("/members", { method: "POST", body: JSON.stringify(member) }),
  updateMember: (id: number, member: Omit<Member, "id">) =>
    request<Member>(`/members/${id}`, { method: "PUT", body: JSON.stringify(member) }),
  deleteMember: (id: number) => request(`/members/${id}`, { method: "DELETE" }),

  listEvents: () => request<EventSummary[]>("/events"),
  createEvent: (event: { name: string; date: string; format: string; venue: string }) =>
    request<EventSummary>("/events", { method: "POST", body: JSON.stringify(event) }),
  deleteEvent: (id: number) => request(`/events/${id}`, { method: "DELETE" }),
  getEvent: (id: number) => request<EventDetail>(`/events/${id}`),
  updateRetro: (id: number, retro: Partial<EventSummary>) =>
    request<EventSummary>(`/events/${id}/retro`, { method: "PUT", body: JSON.stringify(retro) }),

  addSponsor: (eventId: number, sponsor: Omit<Sponsor, "id">) =>
    request<Sponsor>(`/events/${eventId}/sponsors`, { method: "POST", body: JSON.stringify(sponsor) }),
  deleteSponsor: (sponsorId: number) => request(`/sponsors/${sponsorId}`, { method: "DELETE" }),

  listChatSessions: () => request<ChatSession[]>("/chat/sessions"),
  createChatSession: () => request<ChatSession>("/chat/sessions", { method: "POST" }),
  deleteChatSession: (id: number) => request(`/chat/sessions/${id}`, { method: "DELETE" }),

  getChatHistory: (sessionId: number) => request<ChatMessage[]>(`/chat?session_id=${sessionId}`),
  postChat: (message: string, sessionId: number) =>
    request<ChatMessage>("/chat", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId }),
    }),
  postChatFeedback: (messageId: number, liked: boolean, reason?: string) =>
    request(`/chat/${messageId}/feedback`, {
      method: "POST",
      body: JSON.stringify({ liked, reason }),
    }),
};
