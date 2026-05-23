import { useState, useEffect } from 'react';
import { ANONYMIZED_RECORDS } from './data';
import { AnonymizedMortalityRecord } from './types';
import GisMap from './components/GisMap';
import DataPipeline from './components/DataPipeline';
import PostGisSandbox from './components/PostGisSandbox';
import EthicsCenter from './components/EthicsCenter';
import { 
  Map, 
  Cpu, 
  Database, 
  Scale, 
  Clock, 
  Filter, 
  Layers, 
  Trash2, 
  CheckCircle2, 
  Info,
  Calendar,
  ChevronRight,
  TrendingUp,
  Activity
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

export default function App() {
  const [activeTab, setActiveTab] = useState<'map' | 'pipeline' | 'postgis' | 'ethics'>('map');
  const [viewMode, setViewMode] = useState<'public' | 'admin'>('public');
  const [records, setRecords] = useState<AnonymizedMortalityRecord[]>(ANONYMIZED_RECORDS);
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null);
  const [filterManner, setFilterManner] = useState<string>('All');
  const [filterAge, setFilterAge] = useState<string>('All');
  const [filterDecade, setFilterDecade] = useState<string>('All');
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest');
  const [aggregationLevel, setAggregationLevel] = useState<'grid_80m' | 'intersection' | 'zip_centroid' | 'neighborhood'>('grid_80m');

  // Enforce 80m Grid Snapping for public users and reset active restricted tabs
  useEffect(() => {
    if (viewMode === "public") {
      setAggregationLevel("grid_80m");
      if (activeTab === "pipeline" || activeTab === "postgis") {
        setActiveTab("map");
      }
    }
  }, [viewMode, activeTab]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [utcTime, setUtcTime] = useState<string>('2026-05-23 11:22:36 UTC');

  // Sync real-time UTC mock ticking
  useEffect(() => {
    const interval = setInterval(() => {
      const now = new Date();
      setSelectedRecordId(null); // Clear selected record on filters split
      setUtcTime(now.toUTCString().replace('GMT', 'UTC'));
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  // Filtered and Sorted Records based on user sidebar inputs
  const filteredRecords = records
    .filter(rec => {
      const mannerMatch = filterManner === 'All' || rec.mannerOfDeath === filterManner;
      const ageMatch = filterAge === 'All' || rec.ageGroup === filterAge;
      
      const year = new Date(rec.timestamp).getFullYear();
      const decade = `${Math.floor(year / 10) * 10}s`;
      const decadeMatch = filterDecade === 'All' || decade === filterDecade;
      
      return mannerMatch && ageMatch && decadeMatch;
    })
    .sort((a, b) => {
      const dateA = new Date(a.timestamp).getTime();
      const dateB = new Date(b.timestamp).getTime();
      return sortOrder === 'newest' ? dateB - dateA : dateA - dateB;
    });

  // Action: Add simulated live de-identified item to dashboard
  const handleAddNewRecord = (newRecord: AnonymizedMortalityRecord) => {
    setRecords(prev => [newRecord, ...prev]);
    // Auto-select and refocus on Map View to watch the new point render
    setSelectedRecordId(newRecord.id);
    setActiveTab('map');
  };

  // Reset Records back to baseline
  const handleResetRecords = () => {
    setRecords(ANONYMIZED_RECORDS);
    setSelectedRecordId(null);
  };

  return (
    <div className="min-h-screen bg-[#050505] text-zinc-300 flex flex-col font-sans" id="main-app-container">
      {/* Top Banner Status Bar */}
      <header className="h-14 border-b border-zinc-800 flex items-center justify-between px-6 bg-zinc-950/50 select-none">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-rose-600 shadow-[0_0_8px_rgba(225,29,72,0.8)] animate-pulse shrink-0"></div>
          <h1 className="text-sm font-extrabold tracking-[0.15em] uppercase text-zinc-100 font-sans">
            MortalGIS // Secure Spatial Analytics
          </h1>
        </div>

        {/* View Mode Selector */}
        <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 p-0.5 rounded-lg text-[10px] font-mono">
          <button
            id="view-mode-public-btn"
            onClick={() => setViewMode("public")}
            className={`px-2.5 py-1 font-bold rounded-md transition-all cursor-pointer ${
              viewMode === "public"
                ? "bg-rose-950/40 text-rose-300 border border-rose-900/40"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            PUBLIC PORTAL
          </button>
          <button
            id="view-mode-admin-btn"
            onClick={() => setViewMode("admin")}
            className={`px-2.5 py-1 font-bold rounded-md transition-all cursor-pointer ${
              viewMode === "admin"
                ? "bg-zinc-800 text-amber-500 border border-zinc-700"
                : "text-zinc-550 hover:text-zinc-350"
            }`}
          >
            ADMIN CONSOLE
          </button>
        </div>

        {/* System Telemetry Badges */}
        <div className="flex items-center gap-6 text-xs">
          <div className="hidden sm:flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-widest text-zinc-500">System Time:</span>
            <span className="text-[10px] font-mono text-zinc-400" id="utc-time-telemetry">{utcTime}</span>
          </div>
          <div className="hidden sm:block h-4 w-px bg-zinc-800"></div>
          
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-widest text-zinc-500">System Status:</span>
            <span className="text-[10px] uppercase tracking-widest text-emerald-500 font-bold">Anonymized</span>
          </div>
          <div className="h-4 w-px bg-zinc-800"></div>
          <div className="text-[11px] font-mono text-zinc-400">V.2.4.0-STABLE</div>
        </div>
      </header>

      {/* Primary Workspace Navigation Tabs */}
      <nav className="bg-zinc-950 border-b border-zinc-900 px-6 flex items-center gap-2 overflow-x-auto select-none">
        <button
          id="tab-map-view"
          onClick={() => setActiveTab("map")}
          className={`py-4 px-4 text-xs font-mono tracking-wider font-bold transition-all relative flex items-center gap-2 border-b-2 cursor-pointer ${
            activeTab === "map" 
              ? "border-rose-500 text-rose-400 font-extrabold" 
              : "border-transparent text-zinc-500 hover:text-zinc-300"
          }`}
        >
          <Map className="w-4 h-4" />
          GIS MAP SYSTEM
        </button>

        {viewMode === "admin" && (
          <>
            <button
              id="tab-pipeline-view"
              onClick={() => setActiveTab("pipeline")}
              className={`py-4 px-4 text-xs font-mono tracking-wider font-bold transition-all relative flex items-center gap-2 border-b-2 cursor-pointer ${
                activeTab === "pipeline" 
                  ? "border-rose-500 text-rose-400 font-extrabold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              <Cpu className="w-4 h-4" />
              AUTOMATED SCRAPER DAEMON
            </button>

            <button
              id="tab-postgis-view"
              onClick={() => setActiveTab("postgis")}
              className={`py-4 px-4 text-xs font-mono tracking-wider font-bold transition-all relative flex items-center gap-2 border-b-2 cursor-pointer ${
                activeTab === "postgis" 
                  ? "border-rose-500 text-rose-400 font-extrabold" 
                  : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              <Database className="w-4 h-4" />
              POSTGIS SQL SHELL
            </button>
          </>
        )}

        <button
          id="tab-ethics-view"
          onClick={() => setActiveTab("ethics")}
          className={`py-4 px-4 text-xs font-mono tracking-wider font-bold transition-all relative flex items-center gap-2 border-b-2 cursor-pointer ${
            activeTab === "ethics" 
              ? "border-rose-500 text-rose-400 font-extrabold" 
              : "border-transparent text-zinc-500 hover:text-zinc-300"
          }`}
        >
          <Scale className="w-4 h-4" />
          ETHICS & COMPLIANCE SCORE
        </button>
      </nav>

      {/* Main Workspace Area (Grid structure) */}
      <main className="flex-1 p-6 max-w-7xl w-full mx-auto flex flex-col gap-6">
        
        {/* Conditional Layout for MAP Tab */}
        {activeTab === 'map' && (
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start animate-fade-in" id="map-tab-view">
            
            {/* Sidebar Controls Panel (left pane) */}
            <div className="xl:col-span-4 flex flex-col gap-6">
              
              {/* Dynamic Filtering Panel */}
              <section className="bg-zinc-950 p-5 rounded-2xl border border-zinc-805 shadow-xl">
                <div className="flex items-center gap-1.5 mb-4 border-b border-zinc-900 pb-2">
                  <Filter className="w-4 h-4 text-rose-500" />
                  <h2 className="text-xs font-bold text-zinc-100 uppercase tracking-widest font-mono">
                    Filter Controls
                  </h2>
                </div>

                <div className="space-y-4">
                  {/* Manner of Death Filter */}
                  <div>
                    <label className="block text-[10px] font-mono text-zinc-500 font-bold uppercase tracking-wider mb-1.5">
                      Manner of Case
                    </label>
                    <select
                      id="filter-manner-select"
                      value={filterManner}
                      onChange={(e) => setFilterManner(e.target.value)}
                      className="w-full text-xs bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-xl p-2.5 transition-all focus:bg-zinc-900 focus:border-rose-500/50 focus:outline-hidden text-zinc-300 font-medium cursor-pointer"
                    >
                      <option value="All">All Categories</option>
                      <option value="Natural">Natural</option>
                      <option value="Accident">Accident</option>
                      <option value="Toxicological">Toxicological</option>
                      <option value="Environmental">Environmental</option>
                    </select>
                  </div>

                  {/* Age Group Filter */}
                  <div>
                    <label className="block text-[10px] font-mono text-zinc-500 font-bold uppercase tracking-wider mb-1.5">
                      Age Bracket Grouping
                    </label>
                    <select
                      id="filter-age-select"
                      value={filterAge}
                      onChange={(e) => setFilterAge(e.target.value)}
                      className="w-full text-xs bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-xl p-2.5 transition-all focus:bg-zinc-900 focus:border-rose-500/50 focus:outline-hidden text-zinc-300 font-medium cursor-pointer"
                    >
                      <option value="All">All Age Groups</option>
                      <option value="18-24">18-24 Cohort</option>
                      <option value="25-34">25-34 Cohort</option>
                      <option value="45-54">45-54 Cohort</option>
                      <option value="65-74">65-74 Cohort</option>
                      <option value="75-84">75-84 Cohort</option>
                    </select>
                  </div>

                  {/* Decade / Historical Era Filter */}
                  <div>
                    <label className="block text-[10px] font-mono text-zinc-500 font-bold uppercase tracking-wider mb-1.5 flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5 text-rose-500" />
                      Historical Era (Decade)
                    </label>
                    <select
                      id="filter-decade-select"
                      value={filterDecade}
                      onChange={(e) => setFilterDecade(e.target.value)}
                      className="w-full text-xs bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-xl p-2.5 transition-all focus:bg-zinc-900 focus:border-rose-500/50 focus:outline-hidden text-zinc-300 font-medium cursor-pointer"
                    >
                      <option value="All">All Eras</option>
                      <option value="2020s">2020s (Modern Records)</option>
                      <option value="2010s">2010s Era</option>
                      <option value="2000s">2000s Era</option>
                      <option value="1990s">1990s Era (Legacy Archive)</option>
                      <option value="1980s">1980s Era (Legacy Archive)</option>
                    </select>
                  </div>

                  {/* Date Chronological Sorter */}
                  <div>
                    <label className="block text-[10px] font-mono text-zinc-500 font-bold uppercase tracking-wider mb-1.5 flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5 text-rose-500" />
                      Chronological Order
                    </label>
                    <select
                      id="sort-order-select"
                      value={sortOrder}
                      onChange={(e) => setSortOrder(e.target.value as 'newest' | 'oldest')}
                      className="w-full text-xs bg-zinc-900 border border-zinc-800 hover:border-zinc-700 rounded-xl p-2.5 transition-all focus:bg-zinc-900 focus:border-rose-500/50 focus:outline-hidden text-zinc-300 font-medium cursor-pointer"
                    >
                      <option value="newest">Newest Records First</option>
                      <option value="oldest">Oldest Records First</option>
                    </select>
                  </div>

                  {/* Active Aggregation Level Toggle */}
                  <div>
                    <label className="block text-[10px] font-mono text-zinc-500 font-bold uppercase tracking-wider mb-2 flex items-center gap-1">
                      <Layers className="w-3.5 h-3.5 text-zinc-500" />
                      Map Aggregation Algorithm
                    </label>

                    {viewMode === "public" ? (
                      <div className="bg-emerald-950/20 border border-emerald-900/30 p-3 rounded-xl">
                        <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-mono uppercase font-bold">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                          80m Grid Snapping Enforced
                        </div>
                        <p className="text-[10px] text-zinc-400 leading-normal mt-1 font-normal">
                          All spatial coordinates are snapped to a high-resolution 80m physical grid in accordance with HIPAA safe harbor de-identification rules.
                        </p>
                      </div>
                    ) : (
                      <>
                        <div className="grid grid-cols-2 gap-1.5" id="spatial-toggle-block">
                          <button
                            onClick={() => setAggregationLevel("grid_80m")}
                            className={`px-3 py-2 text-[10px] font-mono font-bold tracking-wider rounded-lg border transition-all cursor-pointer ${
                              aggregationLevel === "grid_80m"
                                ? "border-rose-950/50 bg-rose-950/20 text-rose-200 ring-1 ring-rose-500/30"
                                : "border-zinc-800 bg-zinc-900/50 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                            }`}
                          >
                            80M GRID
                          </button>
                          <button
                            onClick={() => setAggregationLevel("intersection")}
                            className={`px-3 py-2 text-[10px] font-mono font-bold tracking-wider rounded-lg border transition-all cursor-pointer ${
                              aggregationLevel === "intersection"
                                ? "border-rose-950/50 bg-rose-950/20 text-rose-200 ring-1 ring-rose-500/30"
                                : "border-zinc-800 bg-zinc-900/50 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                            }`}
                          >
                            CORNER NODE
                          </button>
                          <button
                            onClick={() => setAggregationLevel("zip_centroid")}
                            className={`px-3 py-2 text-[10px] font-mono font-bold tracking-wider rounded-lg border transition-all cursor-pointer ${
                              aggregationLevel === "zip_centroid"
                                ? "border-rose-950/50 bg-rose-950/20 text-rose-200 ring-1 ring-rose-500/30"
                                : "border-zinc-800 bg-zinc-900/50 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                            }`}
                          >
                            ZIP CENTROID
                          </button>
                          <button
                            onClick={() => setAggregationLevel("neighborhood")}
                            className={`px-3 py-2 text-[10px] font-mono font-bold tracking-wider rounded-lg border transition-all cursor-pointer ${
                              aggregationLevel === "neighborhood"
                                ? "border-rose-950/50 bg-rose-950/20 text-rose-200 ring-1 ring-rose-500/30"
                                : "border-zinc-800 bg-zinc-900/50 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                            }`}
                          >
                            NEIGHBORHOOD
                          </button>
                        </div>
                        <span className="block text-[9px] text-zinc-550 mt-2 italic leading-tight">
                          Adjusts coordinates physically to prevent exact pointing.
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </section>

              {/* Committed Record Lists Pane */}
              <section className="bg-zinc-950 p-5 rounded-2xl border border-zinc-800 shadow-xl flex-1 flex flex-col justify-between max-h-[310px]">
                <div>
                  <div className="flex justify-between items-center mb-3">
                    <span className="text-xs font-bold text-zinc-300 uppercase tracking-widest font-mono">
                      Active Ingest Records ({filteredRecords.length})
                    </span>
                    {records.length > baselineSize && (
                      <button
                        onClick={handleResetRecords}
                        className="text-[9.5px] font-mono text-rose-400 hover:text-rose-300 hover:underline flex items-center gap-1 cursor-pointer"
                      >
                        <Trash2 className="w-3 h-3 text-rose-400" /> RESET LIVE
                      </button>
                    )}
                  </div>

                  <div className="space-y-1.5 overflow-y-auto max-h-[220px] pr-1">
                    {filteredRecords.map((item) => (
                      <button
                        key={item.id}
                        id={`list-record-row-${item.id}`}
                        onClick={() => setSelectedRecordId(item.id === selectedRecordId ? null : item.id)}
                        className={`w-full text-left p-2.5 rounded-xl border text-[11px] transition-all flex items-center justify-between cursor-pointer ${
                          selectedRecordId === item.id
                            ? 'bg-rose-950/20 border-rose-900/50 font-bold text-rose-200 ring-1 ring-rose-500/30'
                            : 'bg-zinc-900/40 border-zinc-900/60 text-zinc-400 hover:bg-zinc-900/80 hover:border-zinc-800'
                        }`}
                      >
                        <div className="flex items-center gap-2 truncate">
                          <span className={`w-2 h-2 rounded-full shrink-0 ${
                            item.mannerOfDeath === 'Natural' ? 'bg-emerald-500' :
                            item.mannerOfDeath === 'Accident' ? 'bg-blue-500' :
                            item.mannerOfDeath === 'Toxicological' ? 'bg-rose-500' : 'bg-amber-500'
                          }`} />
                          <span className="font-mono text-[9px] text-zinc-500 bg-zinc-950 rounded px-1 selection:bg-none border border-zinc-800/80">
                            {item.id.startsWith('custom') ? 'SCRAPE' : 'BASE'}
                          </span>
                          <span className="font-mono text-[9px] bg-rose-950/40 text-rose-300 rounded px-1 border border-rose-900/40 shrink-0 font-bold">
                            {new Date(item.timestamp).getFullYear()}
                          </span>
                          <span className="font-sans font-medium text-zinc-300 truncate max-w-[110px]">{item.location.extractedEntity}</span>
                        </div>
                        <ChevronRight className={`w-3.5 h-3.5 transition-transform ${selectedRecordId === item.id ? 'rotate-90 text-rose-500' : 'text-zinc-500'}`} />
                      </button>
                    ))}
                    {filteredRecords.length === 0 && (
                      <div className="text-center py-10 font-sans text-zinc-550 text-xs">
                        No compliant records matching active parameters.
                      </div>
                    )}
                  </div>
                </div>
              </section>
            </div>

            {/* Map Area Column (Right pane) */}
            <div className="xl:col-span-8 flex flex-col gap-6">
              
              {/* Interactive Leaflet Map Instance */}
              <GisMap
                records={filteredRecords}
                selectedRecordId={selectedRecordId}
                onSelectRecord={setSelectedRecordId}
                spatialAggregationLevel={aggregationLevel}
              />

              {/* Selected point metadata expander */}
              <AnimatePresence mode="wait">
                {selectedRecordId ? (
                  <motion.div
                    key={`pane-${selectedRecordId}`}
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 15 }}
                    className="bg-zinc-950 p-5 rounded-2xl border border-zinc-800 shadow-xl grow"
                  >
                    {(() => {
                      const rec = records.find(r => r.id === selectedRecordId);
                      if (!rec) return null;
                      return (
                        <div className="grid grid-cols-1 md:grid-cols-12 gap-5" id="record-metadata-viewer">
                          {/* Left meta */}
                          <div className="md:col-span-5 border-r border-zinc-900 md:pr-5">
                            <span className="block text-[9px] font-mono text-zinc-500 uppercase tracking-widest mb-1">
                              SECURE COMPLIANT METADATA
                            </span>
                            <h3 className="text-sm font-bold text-zinc-100 tracking-tight flex items-center gap-1.5 mb-3.5">
                              <CheckCircle2 className="w-5 h-5 text-emerald-500 animate-pulse" />
                              Point Ledger Details
                            </h3>

                            <div className="space-y-2 text-xs">
                              <div className="flex justify-between border-b border-zinc-900/60 pb-1.5">
                                <span className="text-zinc-500 font-mono text-[10px]">RECORD ID:</span>
                                <span className="font-mono text-[10.5px] text-zinc-300">{rec.id}</span>
                              </div>
                              <div className="flex justify-between border-b border-zinc-900/60 pb-1.5">
                                <span className="text-zinc-500 font-mono text-[10px]">COMPLIANT TIMELINE:</span>
                                <span className="font-mono font-bold text-amber-400">
                                  {new Date(rec.timestamp).toLocaleDateString(undefined, { year: 'numeric', month: 'short' })} (Anonymized)
                                </span>
                              </div>
                              <div className="flex justify-between border-b border-zinc-900/60 pb-1.5">
                                <span className="text-zinc-500 font-mono text-[10px]">AGE BRACKET:</span>
                                <span className="font-mono font-bold bg-rose-950/30 text-rose-300 border border-rose-900/40 px-1.5 py-0.2 rounded text-[10px]">
                                  {rec.ageGroup} Cohort
                                </span>
                              </div>
                              <div className="flex justify-between border-b border-zinc-900/60 pb-1.5">
                                <span className="text-zinc-500 font-mono text-[10px]">COARSE GENDER:</span>
                                <span className="font-sans font-medium text-zinc-300">{rec.gender}</span>
                              </div>
                              <div className="flex justify-between border-b border-zinc-900/60 pb-1.5">
                                <span className="text-zinc-500 font-mono text-[10px]">MANNER OF DEATH:</span>
                                <span className="font-sans font-semibold text-zinc-200">{rec.mannerOfDeath}</span>
                              </div>
                            </div>
                          </div>

                          {/* Right meta - direct scrubbing metrics */}
                          <div className="md:col-span-7 flex flex-col justify-between">
                            <div>
                              <span className="text-[9px] font-mono text-rose-500 uppercase tracking-wider mb-2 font-black flex items-center gap-1">
                                <span className="w-1.5 h-1.5 bg-rose-500 rounded-full animate-heartbeat"></span> 
                                Physical PII Stripping Diagnostics
                              </span>
                              <p className="text-[11px] text-zinc-400 leading-normal mb-3">
                                The following sensitive elements were intercepted and permanently purged from server memory at transaction boundary.
                              </p>

                              <div className="flex flex-wrap gap-1.5 max-h-[84px] overflow-y-auto">
                                {rec.detailsStripped.map((item, index) => (
                                  <span key={index} className="px-2 py-0.5 bg-rose-950/20 border border-rose-900/40 rounded-md text-[9.5px] font-mono text-rose-300 block">
                                    ✕ {item}
                                  </span>
                                ))}
                              </div>
                            </div>

                            <div className="flex items-center gap-2 bg-emerald-950/15 p-2.5 rounded-xl border border-emerald-900/35 mt-3">
                              <Info className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                              <span className="text-[10px] text-zinc-400 leading-tight">
                                Aggregated under spatial coordinates: <strong>Lat {rec.location.lat.toFixed(4)}, Lng {rec.location.lng.toFixed(4)}</strong> ({rec.location.extractedEntity}).
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })()}
                  </motion.div>
                ) : (
                  <div className="bg-zinc-950 p-5 rounded-2xl border border-zinc-800 shadow-xl flex items-center gap-3.5 select-none animate-fade-in text-zinc-300">
                    <div className="p-2 bg-zinc-900 text-rose-500 border border-zinc-800 rounded-xl">
                      <TrendingUp className="w-5 h-5 animate-pulse" />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-zinc-100 uppercase tracking-wide">
                        Statistical Centroids Workspace
                      </h4>
                      <p className="text-[11px] text-zinc-400 leading-normal mt-0.5 font-normal">
                        Select any plotted coordinate circle on the OSM viewport layer to monitor its granular safe epidemiological ledgers.
                      </p>
                    </div>
                  </div>
                )}
              </AnimatePresence>
            </div>
          </div>
        )}

        {/* Tab 2: Minimization Ingestion Pipeline */}
        {activeTab === 'pipeline' && (
          <DataPipeline 
            onProcessCustomRecord={handleAddNewRecord} 
            isLoading={isLoading}
            setIsLoading={setIsLoading}
          />
        )}

        {/* Tab 3: PostGIS Sandbox */}
        {activeTab === 'postgis' && (
          <PostGisSandbox />
        )}

        {/* Tab 4: Ethical Compliance Scores */}
        {activeTab === 'ethics' && (
          <EthicsCenter isEditable={viewMode === 'admin'} />
        )}

      </main>

      {/* Footer Branding block */}
      <footer className="bg-zinc-950 border-t border-zinc-900 py-4 px-6 text-center select-none mt-auto">
        <p className="text-[9px] text-zinc-600 font-mono tracking-wider">
          RESEARCH GIS PLATFORM | DEVELOPED COMPLIANT WITH HIPAA SAFE HARBOR & THE JOINT COMMISSION CLINICAL METRICS
        </p>
      </footer>
    </div>
  );
}

const baselineSize = ANONYMIZED_RECORDS.length;
