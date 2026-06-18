export type SubscriptionPlan = "free" | "pro" | "enterprise";
export type Language = "da" | "en";
export type AIProvider = "openai" | "anthropic" | "ollama" | "custom";
export type ImpactLevel = "low" | "medium" | "high";
export type Proficiency = "beginner" | "intermediate" | "advanced" | "expert";
export type GapPriority = "high" | "medium" | "low";
export type GapSection = "experiences" | "achievements" | "projects" | "skills" | "systems" | "leadership" | "certifications";

export type ApplicationStatus =
  | "draft" | "preparing" | "ready" | "submitted"
  | "screening" | "interviewing" | "offer"
  | "rejected" | "withdrawn" | "hired";

export type DocumentType =
  | "master_cv" | "cv_version" | "cover_letter"
  | "motivation_letter" | "portfolio" | "other";

// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface UserProfile {
  id: string;
  user_id: string;
  display_name: string | null;
  avatar_url: string | null;
  language: Language;
  onboarding_completed: boolean;
  created_at: string;
}

// ─── Master CV & Profil ───────────────────────────────────────────────────────

export interface MasterCVRecord {
  id: string;
  user_id: string;
  title: string;
  target_title: string | null;
  summary: string | null;
  language: Language;
  raw_content: string | null;
  is_generated: boolean;
  updated_at: string;
}

export interface CVExperience {
  id: string;
  master_cv_id: string;
  title: string;
  company: string;
  location: string | null;
  period_start: string | null;
  period_end: string | null;
  is_current: boolean;
  description: string | null;
  technologies: string[];
  achievements: string[];
}

export interface CVEducation {
  id: string;
  master_cv_id: string;
  degree: string;
  institution: string;
  period_start: string | null;
  period_end: string | null;
  description: string | null;
}

export interface CVSkill {
  id: string;
  master_cv_id: string;
  name: string;
  category: string;
  level: Proficiency | null;
}

export interface CVProject {
  id: string;
  master_cv_id: string;
  name: string;
  description: string | null;
  role: string | null;
  technologies: string[];
  outcomes: string | null;
  period_start: string | null;
  period_end: string | null;
}

export interface CVAchievement {
  id: string;
  master_cv_id: string;
  title: string;
  description: string | null;
  metric: string | null;
  impact_level: ImpactLevel;
  year: number | null;
}

export interface CVSystem {
  id: string;
  master_cv_id: string;
  name: string;
  category: string | null;
  proficiency: Proficiency;
}

export interface CVLeadership {
  id: string;
  master_cv_id: string;
  title: string;
  scope: string | null;
  direct_reports: number | null;
  responsibilities: string[];
}

export interface CVCertification {
  id: string;
  master_cv_id: string;
  name: string;
  issuer: string | null;
  issued_at: string | null;
  expires_at: string | null;
}

export interface ProfileGap {
  id: string;
  section: GapSection;
  description: string;
  priority: GapPriority;
  is_resolved: boolean;
}

export interface ProfileScoreSections {
  experiences: number;
  achievements: number;
  projects: number;
  systems: number;
  leadership: number;
  certifications: number;
  skills: number;
}

export interface ProfileScore {
  overall: number;
  sections: ProfileScoreSections;
  missing_areas: string[];
  calculated_at: string;
}

export interface FullProfile {
  master_cv: MasterCVRecord | null;
  experiences: CVExperience[];
  educations: CVEducation[];
  skills: CVSkill[];
  projects: CVProject[];
  achievements: CVAchievement[];
  systems: CVSystem[];
  leadership: CVLeadership[];
  certifications: CVCertification[];
  open_gaps: ProfileGap[];
}

// ─── Upload ───────────────────────────────────────────────────────────────────

export interface UploadResult {
  upload_id: string;
  session_id: string;
  parsed_sections: Record<string, number>;
  gaps: Array<{ section: string; description: string; priority: string }>;
  personal: {
    name?: string;
    email?: string;
    current_title?: string;
  };
}

// ─── Discovery ────────────────────────────────────────────────────────────────

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export interface DiscoverySession {
  id: string;
  status: "active" | "completed" | "archived";
  message_count: number;
  gaps_total: number;
  gaps_resolved: number;
  profile_complete: boolean;
  created_at: string;
}

// ─── Misc ─────────────────────────────────────────────────────────────────────

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

export interface Subscription {
  plan: SubscriptionPlan;
  status: "active" | "canceled" | "past_due" | "trialing";
  current_period_end: string | null;
}
