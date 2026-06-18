export type SubscriptionPlan = "free" | "pro" | "enterprise";
export type Language = "da" | "en";
export type AIProvider = "openai" | "anthropic" | "ollama" | "custom";

export type ApplicationStatus =
  | "draft" | "preparing" | "ready" | "submitted"
  | "screening" | "interviewing" | "offer"
  | "rejected" | "withdrawn" | "hired";

export type DocumentType =
  | "master_cv" | "cv_version" | "cover_letter"
  | "motivation_letter" | "portfolio" | "other";

export interface UserProfile {
  id: string;
  user_id: string;
  display_name: string | null;
  avatar_url: string | null;
  language: Language;
  onboarding_completed: boolean;
  created_at: string;
}

export interface Subscription {
  plan: SubscriptionPlan;
  status: "active" | "canceled" | "past_due" | "trialing";
  current_period_end: string | null;
}

export interface MasterCV {
  id: string;
  user_id: string;
  title: string;
  summary: string | null;
  experiences: CVExperience[];
  educations: CVEducation[];
  skills: CVSkill[];
  updated_at: string;
}

export interface CVExperience {
  id: string;
  title: string;
  company: string;
  period_start: string;
  period_end: string | null;
  description: string | null;
  is_current: boolean;
}

export interface CVEducation {
  id: string;
  degree: string;
  institution: string;
  period_start: string;
  period_end: string | null;
}

export interface CVSkill {
  id: string;
  name: string;
  category: string | null;
  level: string | null;
}

export interface Job {
  id: string;
  title: string;
  company: string;
  location: string | null;
  url: string | null;
  description: string | null;
  posted_at: string | null;
  source: string | null;
}

export interface ApplicationPipeline {
  id: string;
  job_id: string;
  job: Job;
  current_status: ApplicationStatus;
  priority: "low" | "medium" | "high" | "dream";
  deadline: string | null;
  created_at: string;
}

export interface DocumentVersion {
  id: string;
  document_type: DocumentType;
  version_number: number;
  title: string;
  language: Language;
  generated_by: "user" | "ai" | "ai_assisted";
  is_active: boolean;
  created_at: string;
}

export interface CareerMemory {
  id: string;
  content: string;
  memory_type: string;
  source: string;
  relevance_score: number;
  created_at: string;
}

export interface AIUsageSummary {
  total_tokens: number;
  total_cost_usd: number;
  operations_count: number;
  period_start: string;
  period_end: string;
}
