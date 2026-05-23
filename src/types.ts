export interface RawMortalityReport {
  id: string;
  source: string;
  dateStr: string;
  rawText: string;
}

export interface ProcessedLocation {
  originalAddress: string; // To be discarded physically!
  extractedEntity: string;  // E.g., "Main Street and 4th Avenue"
  snappedType: 'intersection' | 'block' | 'zip_centroid' | 'neighborhood' | 'grid_80m';
  snappedLabel: string;
  lat: number;
  lng: number;
}

export interface AnonymizedMortalityRecord {
  id: string;
  timestamp: string; // ISO string without specific exact hour/minutes to prevent temporal tracking
  ageGroup: string; // Grouped (e.g. "45-54"), never specific age
  gender: 'Male' | 'Female' | 'Other' | 'Undetermined' | 'Multiple' | 'Unknown';
  mannerOfDeath: 'Natural' | 'Accident' | 'Toxicological' | 'Environmental' | 'Homicide' | 'Suicide' | 'Undetermined';
  location: ProcessedLocation;
  detailsStripped: string[]; // List of PII items discarded (e.g., "Full Name: Johnathan Doe", "Exact Home Address: 342 Elm Street", "Family relations")
  isVerified: boolean;
}

export interface PostGisQuerySimulation {
  id: string;
  title: string;
  description: string;
  sqlCode: string;
  explanation: string;
  visualEffect: string;
}

export interface EthicalChecklistItem {
  id: string;
  category: 'Anonymization' | 'Consent & Legal' | 'Sourcing & Scraping' | 'Access Controls';
  question: string;
  guideline: string;
  isCompleted: boolean;
}
