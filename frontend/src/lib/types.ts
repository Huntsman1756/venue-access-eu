// Domain types matching the /api/v1 contract.

export interface Participant {
  participant_id: string;
  canonical_name: string;
  country: string | null;
  lei: string | null;
  identity_status: string;
  identity_method: string | null;
  identity_confidence: number | null;
  matched_name?: string | null;
  aliases?: ParticipantAlias[];
}

export interface ParticipantAlias {
  participant_id: string;
  source_id: string;
  source_participant_key: string;
  raw_name: string;
  normalized_name: string | null;
  raw_address: string | null;
  normalized_address: string | null;
  raw_country: string | null;
  source_record_id: string | null;
}

export interface Membership {
  mic: string | null;
  market_family: string | null;
  member_code: string | null;
  member_code_normalized?: string | null;
  capacity_raw: string | null;
  membership_type_raw: string | null;
  membership_type_normalized: string | null;
  retrieved_at: string;
  snapshot_id: string;
  source_id: string;
  raw_sha256: string | null;
  source_declared_updated_at: string | null;
  parser_version: string | null;
}

export interface CheckedVenue {
  source_id: string;
  mic: string;
  market_family: string;
  status: "OBSERVED" | "NOT_OBSERVED" | "UNKNOWN";
}

export interface Venue {
  mic: string;
  operating_mic: string;
  mic_type: string;
  market_name: string;
  legal_entity_name: string | null;
  operator_lei: string | null;
  market_category: string | null;
  acronym: string | null;
  country: string | null;
  city: string | null;
  website: string | null;
  mic_status: string;
  creation_date: string | null;
  participants?: VenueParticipant[];
  segments?: Venue[];
}

export interface VenueParticipant {
  participant_id: string;
  canonical_name: string;
  lei: string | null;
  country: string | null;
  identity_status: string;
  market_family: string | null;
  member_code: string | null;
  membership_type_normalized: string | null;
}

export interface SourceHealth {
  source_id: string;
  operator: string;
  source_name: string;
  coverage_scope: string;
  latest_snapshot: string | null;
  latest_status: string | null;
  latest_attempt_at: string | null;
  latest_good_at: string | null;
  declared_updated_at: string | null;
  record_count: number | null;
}

export interface Snapshot {
  snapshot_id: string;
  source_id: string;
  retrieved_at: string;
  snapshot_status: string;
  record_count: number | null;
  segment_count: number | null;
  parse_error_count: number | null;
  unresolved_identity_count: number | null;
  raw_sha256: string | null;
  raw_bytes: number | null;
  parser_version: string | null;
  validation_report: string | null;
  source_declared_updated_at: string | null;
}

export interface ChangeEvent {
  change_id: string;
  observed_at: string;
  participant_id: string;
  membership_key: string;
  change_type: string;
  old_value: string | null;
  new_value: string | null;
  source_id: string;
  confidence: number;
  canonical_name?: string;
  lei?: string;
}

export interface SearchResult {
  firms: Participant[];
  venues: Venue[];
  member_codes: { member_code: string; mic: string | null }[];
}

export interface Evidence {
  source_id: string;
  source_participant_key: string;
  raw_name: string;
  normalized_name: string | null;
  raw_address: string | null;
  raw_country: string | null;
  source_record_id: string | null;
  status: string | null;
  method: string | null;
  confidence: number | null;
  candidate_count: number | null;
  evidence: string | null;
  resolved_at: string | null;
}

export interface OverlapResult {
  a_only: VenueParticipant[];
  both: (VenueParticipant & { member_code_a: string | null; member_code_b: string | null })[];
  b_only: VenueParticipant[];
  counts: { a: number; b: number; both: number };
}

export interface Stats {
  participants: number;
  participants_with_lei: number;
  membership_observations: number;
  segment_observations: number;
  venues: number;
  snapshots: number;
  quarantined_snapshots: number;
  unresolved: number;
}
