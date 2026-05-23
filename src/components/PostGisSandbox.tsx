import { useState } from 'react';
import { POSTGIS_SIMULATIONS } from '../data';
import { Database, Copy, Check, Info, FileCode2, Sliders, ShieldCheck } from 'lucide-react';

export default function PostGisSandbox() {
  const [selectedIdx, setSelectedIdx] = useState<number>(0);
  const [copied, setCopied] = useState<boolean>(false);
  const [gridDistance, setGridDistance] = useState<number>(150); // Metres grid
  const selectedQuery = POSTGIS_SIMULATIONS[selectedIdx];

  const handleCopy = () => {
    navigator.clipboard.writeText(selectedQuery.sqlCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  // Calculate simulated re-identification risk based on grid resolution
  // If resolution is high (e.g., 5-10 meters), household risk is dangerous.
  // If resolution is low (e.g., 300+ meters), household risk is extremely safe.
  const calculateRiskFactor = (meters: number) => {
    if (meters < 20) return { label: 'CRITICAL', color: 'text-rose-400 bg-rose-950/20 border-rose-900/40', desc: 'Points represent exact single family homes. Fatal privacy compromise risk.' };
    if (meters < 80) return { label: 'ELEVATED RISK', color: 'text-amber-400 bg-amber-950/20 border-amber-900/40', desc: 'Could identify specific buildings or small complexes in rural sectors.' };
    if (meters < 200) return { label: 'MINIMIZED (SAFE)', color: 'text-rose-400 bg-rose-950/10 border-rose-900/30', desc: 'Conforms to street-block level aggregates. Standard compliant range.' };
    return { label: 'EXCEPTIONAL', color: 'text-emerald-400 bg-emerald-950/20 border-emerald-900/30', desc: 'Broad regional centroid. High anonymity, low precision.' };
  };

  const risk = calculateRiskFactor(gridDistance);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in" id="postgis-sandbox">
      {/* Side Select Column */}
      <div className="lg:col-span-4 flex flex-col gap-4">
        <div className="bg-zinc-950 p-5 rounded-2xl border border-zinc-800 shadow-xl">
          <div className="flex items-center gap-2 mb-4">
            <div className="p-1.5 bg-zinc-900 text-rose-500 rounded-lg border border-zinc-800">
              <Database className="w-5 h-5" />
            </div>
            <h3 className="text-base font-sans font-medium text-zinc-100 tracking-tight">
              PostGIS Spatial Queries
            </h3>
          </div>

          <p className="text-xs text-zinc-400 leading-relaxed mb-4">
            Managing spatial anonymity efficiently is achieved directly inside the SQL query layer. Select a query below to inspect real PostGIS functions commonly employed for data sanitation.
          </p>

          <div className="space-y-2">
            {POSTGIS_SIMULATIONS.map((sim, idx) => (
              <button
                key={sim.id}
                id={`postgis-sim-btn-${sim.id}`}
                onClick={() => setSelectedIdx(idx)}
                className={`w-full text-left p-3 rounded-xl border text-xs transition-all flex flex-col gap-1 cursor-pointer ${
                  selectedIdx === idx
                    ? 'border-rose-900/50 bg-rose-950/20 text-rose-200 ring-1 ring-rose-500/30 font-semibold shadow-sm'
                    : 'bg-zinc-900/30 border-transparent text-zinc-400 hover:bg-zinc-900 hover:border-zinc-800 hover:text-zinc-200'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`font-sans font-semibold ${selectedIdx === idx ? 'text-rose-200' : 'text-zinc-300'}`}>{sim.title}</span>
                  {selectedIdx === idx && <span className="text-[9px] bg-rose-950/40 text-rose-300 border border-rose-850/40 font-mono font-bold px-1.5 py-0.2 rounded">SELECTED</span>}
                </div>
                <span className="text-[11px] text-zinc-500 font-normal leading-normal">{sim.description}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Dynamic Risk Tuning Slider */}
        <div className="bg-zinc-950 p-5 rounded-2xl border border-zinc-800 shadow-xl">
          <div className="flex items-center gap-2 mb-3">
            <Sliders className="w-4.5 h-4.5 text-rose-500" />
            <h4 className="text-xs font-bold text-zinc-100 uppercase tracking-wider">
              Anonymity Grid Resoluter
            </h4>
          </div>

          <p className="text-[11px] text-zinc-400 leading-normal mb-4">
            Tweak the database spatial grid bounding bounds (in meters) to evaluate individual household re-identification indicators.
          </p>

          <div className="mb-4">
            <div className="flex justify-between items-center mb-1 text-xs">
              <span className="font-mono text-zinc-550">GRID SIZE:</span>
              <span className="font-bold text-zinc-200">{gridDistance} meters</span>
            </div>
            <input
              type="range"
              min="10"
              max="500"
              step="10"
              value={gridDistance}
              onChange={(e) => setGridDistance(parseInt(e.target.value))}
              className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-rose-600"
            />
            <div className="flex justify-between text-[9px] text-zinc-500 font-mono mt-1">
              <span>10m (High Risk)</span>
              <span>250m</span>
              <span>500m (Broad Zone)</span>
            </div>
          </div>

          <div className={`p-3.5 rounded-xl border flex items-start gap-2.5 transition-all duration-300 ${risk.color}`}>
            <Info className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <div className="text-[10px] font-mono font-bold tracking-wider">RISK METRIC: {risk.label}</div>
              <p className="text-[11px] mt-0.5 leading-relaxed font-sans">{risk.desc}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Editor & Explanation Column */}
      <div className="lg:col-span-8 flex flex-col gap-4">
        {/* SQL Code Editor Display */}
        <div className="bg-zinc-950 rounded-2xl border border-zinc-800 shadow-xl overflow-hidden flex flex-col justify-between">
          <div className="bg-zinc-950 p-3.5 border-b border-zinc-850 flex justify-between items-center">
            <div className="flex items-center gap-2">
              <FileCode2 className="w-4 h-4 text-zinc-500" />
              <span className="text-xs font-mono font-bold text-zinc-300 animate-pulse">
                SQL / POSTGIS SHELL SCHEMA
              </span>
            </div>
            <button
              onClick={handleCopy}
              className="p-1 px-3 bg-zinc-900 border border-zinc-800 hover:bg-zinc-855 text-zinc-400 hover:text-white rounded-lg text-xs font-sans flex items-center gap-1.5 transition-all cursor-pointer"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-emerald-400 font-bold">Copied!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy SQL</span>
                </>
              )}
            </button>
          </div>

          <div className="p-4 overflow-x-auto bg-black">
            <pre className="text-[10.5px] md:text-xs text-rose-300 font-mono leading-relaxed select-all">
              {selectedQuery.sqlCode}
            </pre>
          </div>

          <div className="bg-zinc-950/70 p-4 border-t border-zinc-850/80">
            <span className="block text-[10px] font-mono text-zinc-500 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
              <ShieldCheck className="w-4.5 h-4.5 text-rose-400" />
              How this query secures sensitive data:
            </span>
            <p className="text-xs text-zinc-400 font-sans leading-relaxed">
              {selectedQuery.explanation}
            </p>
          </div>
        </div>

        {/* Dynamic Database Table Representation */}
        <div className="bg-zinc-950 p-5 rounded-2xl border border-zinc-800 shadow-xl">
          <h4 className="text-xs font-bold text-zinc-300 uppercase tracking-wider mb-3 font-sans">
            Simulated PostGIS Compliant JSON Records
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-zinc-900 bg-zinc-900/30 text-zinc-400 font-mono">
                  <th className="p-2 text-[10px] uppercase font-bold tracking-wider">GeoJSON Shape (ST_AsGeoJSON)</th>
                  <th className="p-2 text-[10px] uppercase font-bold tracking-wider">Manner Group</th>
                  <th className="p-2 text-[10px] uppercase font-bold tracking-wider">Case Frequency</th>
                  <th className="p-2 text-[10px] uppercase font-bold tracking-wider text-rose-400 bg-rose-950/10">Anonymization Type</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 text-zinc-300">
                <tr>
                  <td className="p-2 font-mono text-[10px] text-amber-500 truncate max-w-[200px]" title='{"type":"Point","coordinates":[-122.4208,37.7516]}'>
                    {`{"type":"Point","coordinates":[-122.4208,37.7516]}`}
                  </td>
                  <td className="p-2 text-zinc-350 font-sans">Natural</td>
                  <td className="p-2 text-zinc-100 font-bold">12</td>
                  <td className="p-2"><span className="text-emerald-450 bg-emerald-950/30 border border-emerald-900/30 px-2 py-0.5 rounded font-medium font-sans text-[10.5px]">Grid Snapped (ST_SnapToGrid)</span></td>
                </tr>
                <tr>
                  <td className="p-2 font-mono text-[10px] text-amber-500 truncate max-w-[200px]" title='{"type":"Point","coordinates":[-122.4239,37.7645]}'>
                    {`{"type":"Point","coordinates":[-122.4239,37.7645]}`}
                  </td>
                  <td className="p-2 text-zinc-350 font-sans">Accident</td>
                  <td className="p-2 text-zinc-100 font-bold">1</td>
                  <td className="p-2"><span className="text-rose-450 bg-rose-950/30 border border-rose-900/30 px-2 py-0.5 rounded font-medium font-sans text-[10.5px]">Street Intersection (KNN Road Join)</span></td>
                </tr>
                <tr>
                  <td className="p-2 font-mono text-[10px] text-amber-500 truncate max-w-[200px]" title='{"type":"Polygon","coordinates":[[[-122.45,37.73],[-122.40,37.73]...]]}'>
                    {`{"type":"Polygon","coordinates":[[[-122.45, 37.73]...]]}`}
                  </td>
                  <td className="p-2 text-zinc-350 font-sans">Toxicological</td>
                  <td className="p-2 text-zinc-100 font-bold">58</td>
                  <td className="p-2"><span className="text-blue-405 bg-blue-950/30 border border-blue-900/30 px-2 py-0.5 rounded font-medium font-sans text-[10.5px]">ZIP Boundary Polygon Join</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
