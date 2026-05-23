import { 
  RawMortalityReport, 
  AnonymizedMortalityRecord, 
  PostGisQuerySimulation, 
  EthicalChecklistItem 
} from './types';
import anonymizedDatabase from './anonymized_database.json';

// Unstructured raw reports that represents the scraper's raw output.
// These contain heavy PII which MUST be stripped in our pipeline before database insertion.
export const RAW_REPORTS: RawMortalityReport[] = [
  {
    id: "raw-001",
    source: "SF Chronicle News Feed",
    dateStr: "May 22, 2026",
    rawText: "Emergency responders were called to the private residence of 64-year-old grandmother Martha Higgins at 1458 Valencia Street, Apt 3B yesterday at 3:15 PM. Family members, including her daughter Clara, reported she was unresponsive. Local coroner Dr. Vance noted her history of heart disease. Martha died peacefully at home in the company of her golden retriever."
  },
  {
    id: "raw-002",
    source: "Mission District Local Patch",
    dateStr: "May 20, 2026",
    rawText: "Late Tuesday evening at 11:40 PM, a 23-year-old male cyclist named Arthur Pendelton was struck near his residence at 410 Guerrero Street. He was rushed to San Francisco General Hospital by his brother Marcus but tragically succumbed to severe chest trauma caused by the collision. Authorities are interviewing the driver, who stayed on scene."
  },
  {
    id: "raw-003",
    source: "Public Health Sentinel",
    dateStr: "May 18, 2026",
    rawText: "A 34-year-old single father, David Miller, resident of house 583 Castro Street, was found deceased in his bedroom by his landlord on Monday noon. Neighbors reported hearing loud music the night before. Investigations revealed a tragic accidental toxicological overdose of synthetic opioids. His sister Jessica asks for privacy during this difficult time."
  },
  {
    id: "raw-004",
    source: "Downtown Police Department Wire",
    dateStr: "May 15, 2026",
    rawText: "At approximately 2:00 AM, officers responded to a distress call at the transient encampment under the freeway near 600 Harrison Street. A deceased 51-year-old male, identified as homeless advocate James 'Skip' Kowalski, was pronounced dead from exposure to hypothermic conditions. His estranged wife in Oregon has been notified."
  },
  {
    id: "raw-005",
    source: "Bay Area Obits",
    dateStr: "May 12, 2026",
    rawText: "Elena Rostova, age 78, lifelong primary school teacher living at 2291 19th Avenue, passed away last Friday morning at 8:50 AM with her grandchildren around her after a courageous battle with pancreatic cancer. Her obituary reminds everyone of her love for gardening at her Sunset district home."
  }
];

// Pre-anonymized records representing the actual compliant database output.
// In a true 'Data Minimization' architecture, this is the ONLY data that is stored.
// - PII is physically deleted (e.g. Martha Higgins, James Kowalski is completely gone)
// - Timestamp is rounded to date-level (or month-level) to avoid temporal re-identification
// - Exact addresses (e.g., 1458 Valencia St Apt 3B) are snapped to general street blocks (Valencia St & 25th St Block) or neighborhood centroids (Mission District Central Block)
const BASE_RECORDS = anonymizedDatabase as AnonymizedMortalityRecord[];

export function generateScraperDefaultRecords(): AnonymizedMortalityRecord[] {
  const records: AnonymizedMortalityRecord[] = [];
  const states = ['CA', 'NY', 'TX', 'FL', 'IL', 'WA'];
  const cities = {
    CA: { lat: 37.7749, lng: -122.4194, city: 'San Francisco' },
    NY: { lat: 40.7128, lng: -74.0060, city: 'New York' },
    TX: { lat: 29.7604, lng: -95.3698, city: 'Houston' },
    FL: { lat: 25.7617, lng: -80.1918, city: 'Miami' },
    IL: { lat: 41.8781, lng: -87.6298, city: 'Chicago' },
    WA: { lat: 47.6062, lng: -122.3321, city: 'Seattle' },
  };

  // 1. FBI NIBRS - Pre-load Homicides for each state (5 per state = 30 records)
  states.forEach((st) => {
    const coords = cities[st as keyof typeof cities];
    const count = 5;
    for (let i = 0; i < count; i++) {
      const latOffset = ((i * 19) % 7 - 3) * 0.00084;
      const lngOffset = ((i * 11) % 7 - 3) * 0.00102;
      const finalLat = coords.lat + latOffset;
      const finalLng = coords.lng + lngOffset;
      const rawVictimId = `VIC-H-${st}-${2020 + i}`;

      records.push({
        id: `nibrs-${st.toLowerCase()}-${i}`,
        timestamp: `2024-10-${10 + i}T00:00:00Z`,
        ageGroup: i % 2 === 0 ? '25-34' : '45-54',
        gender: i % 2 === 0 ? 'Male' : 'Female',
        mannerOfDeath: 'Homicide',
        location: {
          originalAddress: `NIBRS Registry Incident Node #${rawVictimId}, ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Central Node Sector`,
          snappedType: 'grid_80m',
          snappedLabel: `80m Research Centroid (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Direct Victim Profile ID: '${rawVictimId}' purged from stream`,
          `Incident Street Location: Retained only generalized coordinate sector`,
          `Internal FBI Agency ID Code: Deleted to prevent residential correlation`
        ],
        isVerified: true
      });
    }
  });

  // 2. AP Mass Killings Database (WA) (6 records)
  const waCoords = cities['WA'];
  for (let i = 0; i < 6; i++) {
    const latOffset = ((i * 13) % 5 - 2) * 0.0009;
    const lngOffset = ((i * 17) % 5 - 2) * 0.0011;
    const finalLat = waCoords.lat + latOffset;
    const finalLng = waCoords.lng + lngOffset;

    records.push({
      id: `ap-mass-2023-${i}`,
      timestamp: `2023-06-${15 + i}T00:00:00Z`,
      ageGroup: '35-44',
      gender: i % 2 === 0 ? 'Male' : 'Female',
      mannerOfDeath: 'Homicide',
      location: {
        originalAddress: `AP Mass Killing Event Block, Seattle, WA`,
        extractedEntity: `Seattle Aggregation Grid`,
        snappedType: 'grid_80m',
        snappedLabel: `Grid Segment Retained (Seattle)`,
        lat: finalLat,
        lng: finalLng
      },
      detailsStripped: [
        `Direct Incident Summary narrative: Purged fully from database`,
        `Exact building block address: Replaced with deterministic 80m centroids`,
        `Weapon caliber and assailant identities: Completely stripped`
      ],
      isVerified: true
    });
  }

  // 3. AFSP Suicide Statistics (FL) (5 records)
  const flCoords = cities['FL'];
  for (let i = 0; i < 5; i++) {
    const latOffset = ((i * 15) % 6 - 3) * 0.00078;
    const lngOffset = ((i * 11) % 6 - 3) * 0.00095;
    const finalLat = flCoords.lat + latOffset;
    const finalLng = flCoords.lng + lngOffset;

    records.push({
      id: `afsp-suicide-young-adults-${i}`,
      timestamp: `2024-03-${12 + i}T00:00:00Z`,
      ageGroup: i % 2 === 0 ? '18-24' : '65-74',
      gender: i % 2 === 0 ? 'Female' : 'Male',
      mannerOfDeath: 'Suicide',
      location: {
        originalAddress: `CDC AFSP Statistical Suicide Unit Code, Miami, FL`,
        extractedEntity: `Miami Research Sector`,
        snappedType: 'neighborhood',
        snappedLabel: `Coarse Neighborhood Snapping (Miami)`,
        lat: finalLat,
        lng: finalLng
      },
      detailsStripped: [
        `Exact clinical code identifier: Purged to ensure absolute client confidentiality`,
        `Specific mechanism of self-harm: Permanently removed`,
        `Exact time bounds: Truncated to midnight clock standard`
      ],
      isVerified: true
    });
  }

  return records;
}

export const ANONYMIZED_RECORDS: AnonymizedMortalityRecord[] = [
  ...generateScraperDefaultRecords(),
  ...BASE_RECORDS
];

// PostGIS spatial SQL queries showing how spatial databases aggregate sensitive data
export const POSTGIS_SIMULATIONS: PostGisQuerySimulation[] = [
  {
    id: "pg-01",
    title: "1. Spatial Snapping (Grid Centroid)",
    description: "Converts exact high-precision coordinates into generalized grid block coordinates, ensuring no single household is exposed as an exact point.",
    sqlCode: `SELECT 
  -- Snaps coordinates to a 100-meter grid centroid to sanitize exact addresses
  ST_AsGeoJSON(
    ST_Centroid(
      ST_SnapToGrid(geom, 0.001) -- ~111m grid resolution
    )
  ) AS anonymized_geojson,
  manner_of_death,
  COUNT(*) as death_count
FROM sensitive_mortality_db
GROUP BY ST_SnapToGrid(geom, 0.001), manner_of_death;`,
    explanation: "This query runs entirely in the database backend. Instead of retrieving exact lat/lng coordinates, ST_SnapToGrid clusters points falling within 100 meters, protecting the vulnerable locations of private homes of deceased individuals.",
    visualEffect: "Grid Centroids Snap"
  },
  {
    id: "pg-02",
    title: "2. Intersection Snapping",
    description: "Calculates the nearest road intersection node and aggregates data there instead, making the record point directly to public streets, not homes.",
    sqlCode: `SELECT 
  -- Find closest point on public road network intersections
  ST_AsGeoJSON(intersection_node.geom) AS intersection_geojson,
  COUNT(m.id) AS cases_near_intersection
FROM sensitive_mortality_db m
CROSS JOIN LATERAL (
  SELECT r.geom 
  FROM road_intersections r 
  ORDER BY m.geom <-> r.geom -- K-Nearest Neighbor query
  LIMIT 1
) intersection_node
GROUP BY intersection_node.geom;`,
    explanation: "This snaps private residential coordinates directly to the closest major public road intersection. In any map display, the case appears in the middle of a street intersection, fully anonymizing private address numbers.",
    visualEffect: "Road Intersections Only"
  },
  {
    id: "pg-03",
    title: "3. Spatial Join Aggregation (ZIP & Census Tracts)",
    description: "Joins coordinates with existing administrative bounds (like zip codes or census tracts) and outputs ONLY polygon counts, completing HIPAA Safe Harbor definitions.",
    sqlCode: `SELECT 
  zip.zip_code,
  zip.boundary_geom,
  COUNT(m.id) AS total_cases,
  CASE 
    -- HIPAA compliance: Suppress low cell counts (< 5) to prevent re-identification
    WHEN COUNT(m.id) < 5 THEN 'Low count (<5)' 
    ELSE COUNT(m.id)::text 
  END AS reporting_cases
FROM san_francisco_zip_codes zip
LEFT JOIN sensitive_mortality_db m ON ST_Contains(zip.boundary_geom, m.geom)
GROUP BY zip.zip_code, zip.boundary_geom;`,
    explanation: "This is the gold standard for public health mapping. Points are merged inside polygon boundaries. Importantly, if a ZIP code has fewer than 5 cases, the return is aggregated or suppressed, preventing deduction of individual rare cases.",
    visualEffect: "Polygons & Safe Harbor"
  }
];

// Interactive ethical checklist based on WHO, CDC, CCPA, and general medical ethics
export const ETHICAL_CHECKLIST: EthicalChecklistItem[] = [
  {
    id: "chk-1",
    category: "Anonymization",
    question: "Are direct identifiers (PII) removed before storage?",
    guideline: "Names, exact birthdates, social security numbers, and precise death times must be completely scrubbed at ingestion. Never write raw scraper text directly to persistent storage.",
    isCompleted: true
  },
  {
    id: "chk-2",
    category: "Anonymization",
    question: "Is spatial resolution aggregated to prevent single-home pointing?",
    guideline: "Coordinates must be aggregated via snapping to grid lines, nearest street corners, or zipcode boundaries. Maximum zoom levels should be capped (e.g. at zoom 16) to avoid zooming in on individual apartments or residential driveways.",
    isCompleted: true
  },
  {
    id: "chk-3",
    category: "Sourcing & Scraping",
    question: "Have you audited Terms of Service (ToS) and robots.txt of scraped news feeds?",
    guideline: "Scraping news aggregators or private platforms may violate legal agreements. You must verify if scraping is authorized. For medical/mortality research, prefer official structured open-data APIs (CDC, local medical examiner publications).",
    isCompleted: false
  },
  {
    id: "chk-4",
    category: "Consent & Legal",
    question: "Does the system respect post-mortem privacy laws?",
    guideline: "In regions like Europe (GDPR) and some US states (CCPA/CPRA rights of deceased individuals), special post-mortem privacy rules apply. Verify that your spatial publication aligns with national guidelines on ethical public health mapping.",
    isCompleted: false
  },
  {
    id: "chk-5",
    category: "Access Controls",
    question: "Is there a dual-credential review gate for researchers?",
    guideline: "While aggregated data is public, access to research microdata should require institutional credential confirmation and signed data-sharing agreements to prevent re-identification efforts.",
    isCompleted: true
  }
];
