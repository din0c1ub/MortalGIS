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

  const ageGroups = ['18-24', '25-34', '35-44', '45-54', '55-64', '65-74', '75-84', '85+'];
  const genders: Array<'Male' | 'Female'> = ['Male', 'Female'];

  // Helper for deterministic high-fidelity coordinates in Fermat phyllotaxis layout (prevents overlapping)
  const getClusterOffset = (seedInt: number, index: number) => {
    const angle = (index * 137.5 + seedInt * 19.3) * (Math.PI / 180);
    // radius spreads from 0.003 (~300m) to 0.035 (~3.5km) ensuring city-suburb natural distribution
    const radius = 0.003 + ((index * 17 + seedInt * 43) % 100) * 0.00032;
    return {
      lat: Math.sin(angle) * radius,
      lng: Math.cos(angle) * radius
    };
  };

  // 1. FBI NIBRS - Pre-load Homicides for each state (5 per state = 30 records)
  states.forEach((st) => {
    const coords = cities[st as keyof typeof cities];
    const count = 5;
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(101, i);
      const finalLat = coords.lat + offset.lat;
      const finalLng = coords.lng + offset.lng;
      const rawVictimId = `VIC-H-${st}-${2020 + i}`;

      records.push({
        id: `nibrs-${st.toLowerCase()}-${i}`,
        timestamp: `2024-10-${10 + (i % 20)}T00:00:00Z`,
        ageGroup: i % 2 === 0 ? '25-34' : '45-54',
        gender: genders[i % genders.length],
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

  // 2. AP Mass Killings Database (WA & National Expansion) (12 records)
  states.forEach((st, sIdx) => {
    const coords = cities[st as keyof typeof cities];
    const count = 2; // 2 per state = 12 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(202, i + sIdx * 3);
      const finalLat = coords.lat + offset.lat;
      const finalLng = coords.lng + offset.lng;
      const idCode = `AP-MASS-2023-${st}-${i}`;

      records.push({
        id: `ap-mass-2023-${st.toLowerCase()}-${i}`,
        timestamp: `2023-06-${15 + (i * 3) % 14}T00:00:00Z`,
        ageGroup: ageGroups[(i + sIdx) % ageGroups.length],
        gender: genders[i % genders.length],
        mannerOfDeath: 'Homicide',
        location: {
          originalAddress: `AP Mass Killing Event Block, ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Aggregation Grid`,
          snappedType: 'grid_80m',
          snappedLabel: `Grid Segment Retained (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Direct Incident Summary narrative: Purged fully from database`,
          `Exact building block address: Replaced with deterministic 80m centroids`,
          `Weapon caliber, quantity of devices, and assailant profiles: Completely stripped`
        ],
        isVerified: true
      });
    }
  });

  // 3. AFSP Suicide Statistics (FL, CA, NY, TX expansion) (24 records)
  const afspStates = ['CA', 'NY', 'TX', 'FL'];
  afspStates.forEach((st, sIdx) => {
    const coords = cities[st as keyof typeof cities];
    const count = 6; // 6 per state = 24 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(303, i + sIdx * 4);
      const finalLat = coords.lat + offset.lat;
      const finalLng = coords.lng + offset.lng;

      records.push({
        id: `afsp-suicide-${st.toLowerCase()}-${i}`,
        timestamp: `2024-03-${12 + (i * 2) % 18}T00:00:00Z`,
        ageGroup: i % 3 === 0 ? '18-24' : i % 3 === 1 ? '35-44' : '65-74',
        gender: i % 2 === 0 ? 'Female' : 'Male',
        mannerOfDeath: 'Suicide',
        location: {
          originalAddress: `CDC AFSP Statistical Suicide Unit Code, ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Research Sector`,
          snappedType: 'neighborhood',
          snappedLabel: `Coarse Neighborhood Snapping (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Exact clinical code identifier: Purged to ensure absolute client confidentiality`,
          `Specific mechanism of self-harm / clinical diagnoses: Permanently removed`,
          `Exact time bounds: Truncated to midnight clock standard`
        ],
        isVerified: true
      });
    }
  });

  // 4. CDC WONDER - Cardiopulmonary, Respiratory & Geriatric Epidemiology (60 records)
  // Seeds highly representative "Natural" causes in all states to build background baseline.
  states.forEach((st, sIdx) => {
    const coords = cities[st as keyof typeof cities];
    const count = 10; // 10 per state = 60 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(404, i + sIdx * 5);
      const finalLat = coords.lat + offset.lat;
      const finalLng = coords.lng + offset.lng;

      records.push({
        id: `cdc-wonder-${st.toLowerCase()}-${i}`,
        timestamp: `2024-08-${11 + i}T00:00:00Z`,
        ageGroup: i % 3 === 0 ? '65-74' : i % 3 === 1 ? '75-84' : '85+',
        gender: genders[i % genders.length],
        mannerOfDeath: 'Natural',
        location: {
          originalAddress: `CDC WONDER Registered Clinical Unit, ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Healthcare District Grid`,
          snappedType: 'zip_centroid',
          snappedLabel: `ZIP Zone Centroid Centered (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Primary cardio/respiratory disease coding (ICD-10 classifications) redacted`,
          `Reporting hospital/medical center names & attending clinician IDs: Completely deleted`,
          `Age in raw single years binned into secure HIPAA decadal intervals ('65-74', '75-84', etc.)`
        ],
        isVerified: true
      });
    }
  });

  // 5. NHTSA FARS (Fatality Analysis Reporting System) (48 records)
  // Classify as 'Accident' (Motor vehicle, pedestrian, bicycle fatalities) in all states.
  states.forEach((st, sIdx) => {
    const coords = cities[st as keyof typeof cities];
    const count = 8; // 8 per state = 48 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(505, i + sIdx * 7);
      const finalLat = coords.lat + offset.lat;
      const finalLng = coords.lng + offset.lng;
      const caseId = `FARS-2024-${st}-${i}01`;

      records.push({
        id: `nhtsa-fars-${st.toLowerCase()}-${i}`,
        timestamp: `2024-05-${14 + i}T00:00:00Z`,
        ageGroup: i % 4 === 0 ? '18-24' : i % 4 === 1 ? '25-34' : i % 4 === 2 ? '35-44' : '45-54',
        gender: genders[i % genders.length],
        mannerOfDeath: 'Accident',
        location: {
          originalAddress: `NHTSA Interstate Roadway node #${caseId}, near ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Highway Corridor`,
          snappedType: 'intersection',
          snappedLabel: `Interstate Snapped Intersection (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Vehicle Identification Numbers (VINs) & Vehicle Manufacturer listings: Deleted`,
          `Local law enforcement collision narratives and officer write-ups: Stripped`,
          `Driver licensing and registration records: Entirely purged from registry`
        ],
        isVerified: true
      });
    }
  });

  // 6. EPA Toxic Release Inventory (TRI) / Environmental Exposures (36 records)
  // Classify as 'Environmental' (Inhalation, extreme climate warmth, industrial chemical leaks).
  states.forEach((st, sIdx) => {
    const coords = cities[st as keyof typeof cities];
    const count = 6; // 6 per state = 36 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(606, i + sIdx * 9);
      const finalLat = coords.lat + offset.lat;
      const finalLng = coords.lng + offset.lng;

      records.push({
        id: `epa-tri-${st.toLowerCase()}-${i}`,
        timestamp: `2024-07-${10 + (i * 3) % 20}T00:00:00Z`,
        ageGroup: ageGroups[(i + 4) % ageGroups.length], // typically middle-age to elder
        gender: genders[i % genders.length],
        mannerOfDeath: 'Environmental',
        location: {
          originalAddress: `EPA Clean Air Act Tracking Core Sector, ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Heavy Industry Area`,
          snappedType: 'grid_80m',
          snappedLabel: `80m Aggressive GIS Grid (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Facility license IDs and corporate emissions indices: Redacted to safeguard local commercial identities`,
          `Particulate matter micro-sensor raw data values and timestamps: Generalized to UTC date-level`,
          `Residential structures and housing layout blueprints: Shifted to nearest grid centroid`
        ],
        isVerified: true
      });
    }
  });

  // 7. OSHA Severe Industry Injury Registry (20 records)
  // Classify as 'Accident' (Industrial workplace slips, shipyard mechanical failures, warehouse falls).
  const oshaCities = [
    { st: 'IL', code: 'CH', lat: 41.8781, lng: -87.6298, city: 'Chicago' },
    { st: 'TX', code: 'HO', lat: 29.7604, lng: -95.3698, city: 'Houston' },
    { st: 'NY', code: 'NY', lat: 40.7128, lng: -74.0060, city: 'New York' },
    { st: 'CA', code: 'SF', lat: 37.7749, lng: -122.4194, city: 'San Francisco' }
  ];
  oshaCities.forEach((cityObj, cIdx) => {
    const count = 5; // 5 per industrial hub = 20 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(707 + cIdx, i);
      const finalLat = cityObj.lat + offset.lat;
      const finalLng = cityObj.lng + offset.lng;

      records.push({
        id: `osha-severe-${cityObj.code.toLowerCase()}-${i}`,
        timestamp: `2024-09-${12 + i}T00:00:00Z`,
        ageGroup: i % 2 === 0 ? '25-34' : '45-54',
        gender: 'Male', // historically high male representation in heavy construction
        mannerOfDeath: 'Accident',
        location: {
          originalAddress: `OSHA Structural Jobsite Code #${cityObj.code}-${2020 + i}, ${cityObj.city}, ${cityObj.st}`,
          extractedEntity: `${cityObj.city} Port/Industrial Grid Block`,
          snappedType: 'grid_80m',
          snappedLabel: `80-meter Industrial Centroid Grid (${cityObj.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Employer corporate titles & OSHA enforcement fine/citation tracking codes: Fully deleted`,
          `Attending emergency medical service dispatch identifiers: Purged`,
          `Machinery names, serial manufacturer numbers, and tool configurations: Removed`
        ],
        isVerified: true
      });
    }
  });

  // 8. FDA MedWatch / FAERS Toxicological Baseline (30 records)
  // Classify as 'Toxicological' (Unintentional prescription drug interactions, counterfeit toxicity).
  states.forEach((st, sIdx) => {
    const coords = cities[st as keyof typeof cities];
    const count = 5; // 5 per state = 30 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(808, i + sIdx * 6);
      const finalLat = coords.lat + offset.lat;
      const finalLng = coords.lng + offset.lng;

      records.push({
        id: `fda-medwatch-${st.toLowerCase()}-${i}`,
        timestamp: `2024-11-${18 + i}T00:00:00Z`,
        ageGroup: i % 2 === 0 ? '35-44' : '55-64',
        gender: genders[i % genders.length],
        mannerOfDeath: 'Toxicological',
        location: {
          originalAddress: `FDA Adverse Drug Event Node, ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Municipal Sector Grid`,
          snappedType: 'zip_centroid',
          snappedLabel: `Safe ZIP Zone Snapping (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Subject pharmaceutical brand names, serial lot codes, and expiration stamps: Purged under HIPAA`,
          `Prescribing medical clinic names & pharmacy chain dispatch notes: Entirely redacted`,
          `Emergency poison control center raw audio transcriptions: Deleted to prevent identifying voice files`
        ],
        isVerified: true
      });
    }
  });

  // 9. CDC NVSS - National Vital Statistics System: Infant & Maternal Epidemiology (12 records)
  states.forEach((st, sIdx) => {
    const coords = cities[st as keyof typeof cities];
    const count = 2; // 2 per state = 12 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(909, i + sIdx * 11);
      const finalLat = coords.lat + offset.lat;
      const finalLng = coords.lng + offset.lng;

      records.push({
        id: `cdc-nvss-${st.toLowerCase()}-${i}`,
        timestamp: `2024-04-${10 + i * 5}T00:00:00Z`,
        ageGroup: '18-24', // representing young maternal cohort ages
        gender: 'Female',
        mannerOfDeath: 'Natural',
        location: {
          originalAddress: `CDC NVSS Clinical Maternal Grid Node, ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Obstetric Center Sector`,
          snappedType: 'grid_80m',
          snappedLabel: `80m Clinical Snapped Centroid (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Newborn primary weight, dynamic gestational indices, and exact double Apgar scores: Deleted`,
          `Parental names, employment structures, and delivery facility coordinates: Completely purged`,
          `Clinical attending registry credentials: Redacted to prevent provider disclosure`
        ],
        isVerified: true
      });
    }
  });

  // 10. US Coast Guard Boating Incident Reporting System (BIRS) (8 records)
  // Aquatic incidents / coastal operations drownings (CA, NY, FL, WA)
  const coastalStates = ['CA', 'NY', 'FL', 'WA'];
  coastalStates.forEach((st, sIdx) => {
    const coords = cities[st as keyof typeof cities];
    const count = 2; // 2 per coastal state = 8 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(1010, i + sIdx * 13);
      // Offset shifted slightly further outward to align with real ocean coastline/bay sectors
      const finalLat = coords.lat + offset.lat * 1.5;
      const finalLng = coords.lng + offset.lng * 1.5;

      records.push({
        id: `uscg-birs-${st.toLowerCase()}-${i}`,
        timestamp: `2024-06-${20 + i}T00:00:00Z`,
        ageGroup: i % 2 === 0 ? '35-44' : '55-64',
        gender: genders[i % genders.length],
        mannerOfDeath: 'Accident',
        location: {
          originalAddress: `USCG Maritime Operations Center Near Coastline, ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Maritime Centroid`,
          snappedType: 'neighborhood',
          snappedLabel: `Waterway Sector Snapped Boundary (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Vessel registration name, commercial tonnage specs, and captain licensing code: Discarded`,
          `Distress signal audio logs and coordinate metadata: Snapped to nearest maritime harbor marker`,
          `Surviving passenger profiles and witness identities: Stripped for mutual privacy`
        ],
        isVerified: true
      });
    }
  });

  // 11. National Park Service (NPS) Search and Rescue / Wilderness Fatalities (6 records)
  // Cascade Wilderness (WA), Yosemite/Bay Outskirts (CA), Catskill/Adirondack Outskirts (NY)
  const wildernessStates = ['WA', 'CA', 'NY'];
  wildernessStates.forEach((st, sIdx) => {
    const coords = cities[st as keyof typeof cities];
    const count = 2; // 2 per wilderness-bound region = 6 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(1111, i + sIdx * 17);
      // Larger offset radius on purpose to symbolize wilderness regions outside high-density downtowns
      const finalLat = coords.lat + offset.lat * 2.5;
      const finalLng = coords.lng + offset.lng * 2.5;

      records.push({
        id: `nps-wild-${st.toLowerCase()}-${i}`,
        timestamp: `2024-07-${5 + i * 4}T00:00:00Z`,
        ageGroup: i % 2 === 0 ? '25-34' : '45-54',
        gender: i % 2 === 0 ? 'Male' : 'Female',
        mannerOfDeath: 'Environmental',
        location: {
          originalAddress: `NPS Wilderness Search & Rescue Zone, rural area outside ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Boundary Wilderness Sector`,
          snappedType: 'neighborhood',
          snappedLabel: `Wilderness Sector Snapped Approximation (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Exact trail intersection index, campfire site coords, and elevation meters: Redacted`,
          `Search & rescue ranger team deployment metrics: Dropped`,
          `Personal wilderness survival gears / inventory lists: Eliminated`
        ],
        isVerified: true
      });
    }
  });

  // 12. FEMA Extreme Weather and Climate Casualties (24 records)
  // Seeds heat wave, freeze wave, wildfire, and hurricane-related deaths in all states
  states.forEach((st, sIdx) => {
    const coords = cities[st as keyof typeof cities];
    const count = 4; // 4 per state = 24 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(1212, i + sIdx * 19);
      const finalLat = coords.lat + offset.lat;
      const finalLng = coords.lng + offset.lng;
      
      const extremeTypes = [
        'Extreme Heat Index Exposure',
        'Severe Cold Wave Exposure',
        'Wildfire Particulate Smoke Inhalation',
        'Tropical Hurricane Flooding Inflow'
      ];
      const selectedType = extremeTypes[i % extremeTypes.length];

      records.push({
        id: `fema-climatedeath-${st.toLowerCase()}-${i}`,
        timestamp: `2024-02-${10 + i * 3}T00:00:00Z`,
        ageGroup: i % 2 === 0 ? '65-74' : '75-84', // typically elderly vulnerability focus
        gender: genders[i % genders.length],
        mannerOfDeath: 'Environmental',
        location: {
          originalAddress: `FEMA Disaster Area Marker during ${selectedType}, ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Climate Assessment Grid`,
          snappedType: 'neighborhood',
          snappedLabel: `Climate Boundary Approximation (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `FEMA disaster declaration registration code/claim tracking indicators: Dropped`,
          `Details regarding physical property damage and home ownership status: Purged under HIPAA`,
          `Weather station raw coordinate logs: Replaced with generalized urban sector coordinates`
        ],
        isVerified: true
      });
    }
  });

  // 13. SAMHSA Substance Abuse mapping / Fatal Toxicity Hotspots (24 records)
  states.forEach((st, sIdx) => {
    const coords = cities[st as keyof typeof cities];
    const count = 4; // 4 per state = 24 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(1313, i + sIdx * 23);
      const finalLat = coords.lat + offset.lat;
      const finalLng = coords.lng + offset.lng;

      records.push({
        id: `samhsa-tox-${st.toLowerCase()}-${i}`,
        timestamp: `2024-01-${15 + i * 2}T00:00:00Z`,
        ageGroup: i % 3 === 0 ? '25-34' : i % 3 === 1 ? '35-44' : '45-54',
        gender: genders[i % genders.length],
        mannerOfDeath: 'Toxicological',
        location: {
          originalAddress: `SAMHSA Registry Adverse Endpoint, ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Municipal Node Grid`,
          snappedType: 'intersection',
          snappedLabel: `Intersection Node Snapping (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Specific legal autopsy forensic substance mix concentrations: Redacted for HIPAA Safe Harbor`,
          `Emergency response dispatcher transcripts of friends or relatives: Destroyed from file`,
          `Admitting emergency facility names & treatment clinician notes: Completely stripped`
        ],
        isVerified: true
      });
    }
  });

  // 14. BLS Census of Fatal Occupational Injuries (CFOI) (18 records)
  states.forEach((st, sIdx) => {
    const coords = cities[st as keyof typeof cities];
    const count = 3; // 3 per state = 18 total
    for (let i = 0; i < count; i++) {
      const offset = getClusterOffset(1414, i + sIdx * 29);
      const finalLat = coords.lat + offset.lat;
      const finalLng = coords.lng + offset.lng;

      records.push({
        id: `bls-cfoi-${st.toLowerCase()}-${i}`,
        timestamp: `2024-12-${1 + i * 6}T00:00:00Z`,
        ageGroup: i % 2 === 0 ? '35-44' : '45-54',
        gender: 'Male', // representing high statistical workplace segment in agricultural/infrastructure
        mannerOfDeath: 'Accident',
        location: {
          originalAddress: `BLS CFOI Infrastructure Site Node, near ${coords.city}, ${st}`,
          extractedEntity: `${coords.city} Heavy Transport/Commercial Sector`,
          snappedType: 'grid_80m',
          snappedLabel: `80m Heavy Transport Centroid (${coords.city})`,
          lat: finalLat,
          lng: finalLng
        },
        detailsStripped: [
          `Employer trademark business naming, trade logs, and union affiliation details: Redacted`,
          `Licensing of operating heavy machineries or vessel IDs: Destroyed`,
          `Safety inspection incident case references & OSHA compliance citations: Completely omitted`
        ],
        isVerified: true
      });
    }
  });

  return records;
}

export function generateLargeScaleHistoricalBacklog(): AnonymizedMortalityRecord[] {
  const records: AnonymizedMortalityRecord[] = [];
  
  const STATE_ANCHORS: Record<string, { lat: number; lng: number; cap: string; zip: string; abbr: string }> = {
    "Alabama": { lat: 32.3668, lng: -86.3006, cap: "Montgomery", zip: "36104", abbr: "AL" },
    "Alaska": { lat: 58.3019, lng: -134.4197, cap: "Juneau", zip: "99801", abbr: "AK" },
    "Arizona": { lat: 33.4484, lng: -112.0740, cap: "Phoenix", zip: "85003", abbr: "AZ" },
    "Arkansas": { lat: 34.7465, lng: -92.2896, cap: "Little Rock", zip: "72201", abbr: "AR" },
    "California": { lat: 36.7783, lng: -119.4179, cap: "Sacramento", zip: "95814", abbr: "CA" },
    "Colorado": { lat: 39.7392, lng: -104.9903, cap: "Denver", zip: "80202", abbr: "CO" },
    "Connecticut": { lat: 41.7637, lng: -72.6851, cap: "Hartford", zip: "06103", abbr: "CT" },
    "Delaware": { lat: 39.1582, lng: -75.5244, cap: "Dover", zip: "19901", abbr: "DE" },
    "Florida": { lat: 27.6648, lng: -81.5158, cap: "Tallahassee", zip: "32301", abbr: "FL" },
    "Georgia": { lat: 32.1656, lng: -82.9001, cap: "Atlanta", zip: "30303", abbr: "GA" },
    "Hawaii": { lat: 19.8987, lng: -155.6659, cap: "Honolulu", zip: "96813", abbr: "HI" },
    "Idaho": { lat: 44.0682, lng: -114.7420, cap: "Boise", zip: "83702", abbr: "ID" },
    "Illinois": { lat: 40.6331, lng: -89.3985, cap: "Springfield", zip: "62701", abbr: "IL" },
    "Indiana": { lat: 40.5512, lng: -85.6024, cap: "Indianapolis", zip: "46204", abbr: "IN" },
    "Iowa": { lat: 41.8780, lng: -93.0977, cap: "Des Moines", zip: "50309", abbr: "IA" },
    "Kansas": { lat: 39.0119, lng: -98.4842, cap: "Topeka", zip: "66603", abbr: "KS" },
    "Kentucky": { lat: 37.8393, lng: -84.2700, cap: "Frankfort", zip: "40601", abbr: "KY" },
    "Louisiana": { lat: 31.2448, lng: -92.1450, cap: "Baton Rouge", zip: "70802", abbr: "LA" },
    "Maine": { lat: 45.2538, lng: -69.0163, cap: "Augusta", zip: "04330", abbr: "ME" },
    "Maryland": { lat: 39.0458, lng: -76.6413, cap: "Annapolis", zip: "21401", abbr: "MD" },
    "Massachusetts": { lat: 42.4072, lng: -71.3824, cap: "Boston", zip: "02108", abbr: "MA" },
    "Michigan": { lat: 44.3148, lng: -85.6024, cap: "Lansing", zip: "48933", abbr: "MI" },
    "Minnesota": { lat: 46.7296, lng: -94.6859, cap: "St. Paul", zip: "55101", abbr: "MN" },
    "Mississippi": { lat: 32.7416, lng: -89.6787, cap: "Jackson", zip: "39201", abbr: "MS" },
    "Missouri": { lat: 37.9643, lng: -91.8318, cap: "Jefferson City", zip: "65101", abbr: "MO" },
    "Montana": { lat: 46.8797, lng: -110.3626, cap: "Helena", zip: "59601", abbr: "MT" },
    "Nebraska": { lat: 41.4925, lng: -99.9018, cap: "Lincoln", zip: "68508", abbr: "NE" },
    "Nevada": { lat: 38.8026, lng: -116.4194, cap: "Carson City", zip: "89701", abbr: "NV" },
    "New Hampshire": { lat: 43.1939, lng: -71.5724, cap: "Concord", zip: "03301", abbr: "NH" },
    "New Jersey": { lat: 40.0583, lng: -74.4057, cap: "Trenton", zip: "08608", abbr: "NJ" },
    "New Mexico": { lat: 34.5199, lng: -105.8701, cap: "Santa Fe", zip: "87501", abbr: "NM" },
    "New York": { lat: 40.7128, lng: -74.0060, cap: "Albany", zip: "12207", abbr: "NY" },
    "North Carolina": { lat: 35.7596, lng: -79.0193, cap: "Raleigh", zip: "27601", abbr: "NC" },
    "North Dakota": { lat: 47.5515, lng: -101.0020, cap: "Bismarck", zip: "58501", abbr: "ND" },
    "Ohio": { lat: 40.4173, lng: -82.9071, cap: "Columbus", zip: "43215", abbr: "OH" },
    "Oklahoma": { lat: 35.0078, lng: -97.0929, cap: "Oklahoma City", zip: "73102", abbr: "OK" },
    "Oregon": { lat: 43.8041, lng: -120.5542, cap: "Salem", zip: "97301", abbr: "OR" },
    "Pennsylvania": { lat: 41.2033, lng: -77.1945, cap: "Harrisburg", zip: "17101", abbr: "PA" },
    "Rhode Island": { lat: 41.5801, lng: -71.4774, cap: "Providence", zip: "02903", abbr: "RI" },
    "South Carolina": { lat: 33.8361, lng: -81.1637, cap: "Columbia", zip: "29201", abbr: "SC" },
    "South Dakota": { lat: 44.2998, lng: -99.4388, cap: "Pierre", zip: "57501", abbr: "SD" },
    "Tennessee": { lat: 35.5175, lng: -86.5804, cap: "Nashville", zip: "37203", abbr: "TN" },
    "Texas": { lat: 31.9686, lng: -99.9018, cap: "Austin", zip: "78701", abbr: "TX" },
    "Utah": { lat: 39.3210, lng: -111.0937, cap: "Salt Lake City", zip: "84111", abbr: "UT" },
    "Vermont": { lat: 44.0000, lng: -72.7000, cap: "Montpelier", zip: "05602", abbr: "VT" },
    "Virginia": { lat: 37.4316, lng: -78.6569, cap: "Richmond", zip: "23219", abbr: "VA" },
    "Washington": { lat: 47.7511, lng: -120.7401, cap: "Olympia", zip: "98501", abbr: "WA" },
    "West Virginia": { lat: 38.4912, lng: -80.9545, cap: "Charleston", zip: "25301", abbr: "WV" },
    "Wisconsin": { lat: 43.7844, lng: -88.7879, cap: "Madison", zip: "53703", abbr: "WI" },
    "Wyoming": { lat: 42.7560, lng: -107.3025, cap: "Cheyenne", zip: "82001", abbr: "WY" }
  };

  const manners: Array<'Natural' | 'Accident' | 'Toxicological' | 'Environmental' | 'Homicide' | 'Suicide' | 'Undetermined'> = [
    'Natural', 'Accident', 'Toxicological', 'Environmental', 'Homicide', 'Suicide'
  ];
  const ageGroups = ['18-24', '25-34', '35-44', '45-54', '55-64', '65-74', '75-84', '85+'];
  const genders: Array<'Male' | 'Female' | 'Other' | 'Unknown'> = ['Male', 'Female', 'Other', 'Unknown'];

  const states = Object.keys(STATE_ANCHORS);

  states.forEach((stateName, sIdx) => {
    const anchor = STATE_ANCHORS[stateName];
    // Generate 800 records per state to yield 40,000 highly structured records nationwide
    for (let i = 0; i < 800; i++) {
      const pseudoHash = (sIdx * 347 + i * 83) % 10000;
      
      const year = 1986 + (pseudoHash % 41); // Comprehensive 40-year coverage 1986–2026
      const month = 1 + (pseudoHash % 12);
      const day = 1 + (pseudoHash % 28);
      const monthStr = month < 10 ? `0${month}` : `${month}`;
      const dayStr = day < 10 ? `0${day}` : `${day}`;
      const timestamp = `${year}-${monthStr}-${dayStr}T00:00:00Z`;

      const manner = manners[pseudoHash % manners.length];
      const ageGroup = ageGroups[(pseudoHash + 13) % ageGroups.length];
      const gender = genders[(pseudoHash + 7) % genders.length];

      // Distribute coordinates perfectly around state capital area using deterministic equations
      const angle = (i * 137.5 * Math.PI) / 180;
      const radius = 0.05 + Math.sqrt(i) * 0.015; // Beautiful geographical spreads
      const lat = anchor.lat + Math.sin(angle) * radius;
      const lng = anchor.lng + Math.cos(angle) * radius;

      const streetList = ['Grand Ave', 'Lincoln Blvd', 'State St', 'Pioneer Rd', 'Pine Corridor', 'Summit Ridge', 'Oak Bypass'];
      const street = streetList[pseudoHash % streetList.length];

      records.push({
        id: `seeded-dyn-${anchor.abbr}-${year}-${i}`,
        timestamp,
        ageGroup,
        gender,
        mannerOfDeath: manner,
        location: {
          originalAddress: `Secure FBI Public Health Registry Node ${pseudoHash}, ${anchor.cap}, ${anchor.abbr}`,
          extractedEntity: `${street} Segment Area`,
          snappedType: 'grid_80m',
          snappedLabel: `Municipal Snapped Grid Block (${anchor.abbr})`,
          lat: parseFloat(lat.toFixed(5)),
          lng: parseFloat(lng.toFixed(5))
        },
        detailsStripped: [
          `Direct Demographics Scrubbed: Purged under HIPAA Safe Harbor rules`,
          `Incident Time Code: Generalized to UTC date-level resolution (Year ${year})`,
          `Source agency index: Registered public health mortality database`
        ],
        isVerified: true
      });
    }
  });

  return records;
}

export const ANONYMIZED_RECORDS: AnonymizedMortalityRecord[] = [
  ...generateScraperDefaultRecords(),
  ...generateLargeScaleHistoricalBacklog(),
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
