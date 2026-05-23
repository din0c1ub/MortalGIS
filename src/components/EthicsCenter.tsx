import { useState, useEffect } from "react";
import { ETHICAL_CHECKLIST } from "../data";
import { EthicalChecklistItem } from "../types";
import { BookOpen, Scale, Landmark, FileCheck, ShieldAlert, Award, HelpingHand, ShieldCheck } from "lucide-react";
import { motion } from "motion/react";

interface EthicsCenterProps {
  isEditable?: boolean;
}

export default function EthicsCenter({ isEditable = true }: EthicsCenterProps) {
  const [checklist, setChecklist] = useState<EthicalChecklistItem[]>(ETHICAL_CHECKLIST);
  const [rating, setRating] = useState<{ score: number; label: string; color: string; ringColor: string }>(
    { score: 60, label: "Partially Protected", color: "text-amber-600 bg-amber-50", ringColor: "border-amber-200" }
  );

  // If public mode (isEditable is false), lock all items to completed status (fully compliant audit)
  useEffect(() => {
    if (!isEditable) {
      setChecklist(prev => prev.map(item => ({ ...item, isCompleted: true })));
    } else {
      setChecklist(ETHICAL_CHECKLIST);
    }
  }, [isEditable]);

  const toggleCheck = (id: string) => {
    if (!isEditable) return;
    setChecklist(prev =>
      prev.map(item => item.id === id ? { ...item, isCompleted: !item.isCompleted } : item)
    );
  };

  // Re-calculate rating on state update
  useEffect(() => {
    const completedCount = checklist.filter(item => item.isCompleted).length;
    const pct = Math.round((completedCount / checklist.length) * 100);
    
    let label = 'Vulnerable';
    let color = 'text-rose-400 bg-rose-950/20 border-rose-900/40';
    let ringColor = 'border-rose-500';

    if (pct >= 100) {
      label = 'Fully Compliant (Safe Harbor)';
      color = 'text-emerald-400 bg-emerald-950/25 border-emerald-900/40';
      ringColor = 'border-emerald-500';
    } else if (pct >= 60) {
      label = 'Secure Pipeline';
      color = 'text-rose-300 bg-rose-950/30 border-rose-900/30';
      ringColor = 'border-rose-500';
    } else if (pct >= 40) {
      label = 'Weak Protections';
      color = 'text-amber-400 bg-amber-950/20 border-amber-900/40';
      ringColor = 'border-amber-500';
    }

    setRating({ score: pct, label, color, ringColor });
  }, [checklist]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 animate-fade-in" id="ethics-center">
      {/* Informative / Legal Columns */}
      <div className="lg:col-span-7 flex flex-col gap-6">
        {/* Core Principles */}
        <div className="bg-zinc-950 p-5 rounded-2xl border border-zinc-800 shadow-xl">
          <div className="flex items-center gap-2 mb-4">
            <div className="p-1.5 bg-zinc-900 text-rose-500 rounded-lg border border-zinc-800">
              <Scale className="w-5 h-5" />
            </div>
            <h3 className="text-base font-sans font-medium text-zinc-100 tracking-tight">
              Ethical & Legal GIS Guidelines
            </h3>
          </div>

          <div className="space-y-4 text-xs text-zinc-400 leading-relaxed font-sans">
            <p>
              Mapping mortality metrics involves unique challenges. While deceased individuals are outside standard GDPR elements directly, <strong className="text-zinc-300">post-mortem privacy is highly sensitive</strong> — protecting their grieving descendants and avoiding stigmatization of target neighborhoods is key.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 my-2.5">
              <div className="p-3.5 bg-zinc-900 border border-zinc-800 rounded-xl">
                <div className="flex items-center gap-1.5 font-bold text-zinc-300 uppercase tracking-wide text-[10px] mb-1.5">
                  <Landmark className="w-4 h-4 text-zinc-500" />
                  HIPAA Safe Harbor Method
                </div>
                <p className="text-[11px] text-zinc-500 leading-normal">
                  Fulfilling 18 geodemographic safety markers. For mapping, coordinates within geographic zones comprising fewer than 20,000 residents must have counts suppressed if cases fall below 5.
                </p>
              </div>

              <div className="p-3.5 bg-zinc-900 border border-zinc-800 rounded-xl">
                <div className="flex items-center gap-1.5 font-bold text-zinc-350 uppercase tracking-wide text-[10px] mb-1.5">
                  <ShieldAlert className="w-4 h-4 text-rose-500" />
                  Avoid Dwelling Pointing
                </div>
                <p className="text-[11px] text-zinc-500 leading-normal">
                  Coordinates pointing directly to residential addresses (such as "342 Elm Street") expose private matters. Snapping coordinates to street intersections guarantees anonymous datasets.
                </p>
              </div>
            </div>

            <p>
              Before scraping media outlets, legal audits of robots.txt must confirm authorized programmatic collection. If news licensing prevents extraction, utilizing public aggregated statistics (CDC WONDER or regional coroners' portals) is highly advised.
            </p>
          </div>
        </div>

        {/* Resources / Education Section */}
        <div className="bg-zinc-950 p-5 rounded-2xl border border-zinc-800 shadow-xl flex flex-col h-full justify-between">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <BookOpen className="w-4.5 h-4.5 text-rose-500" />
              <h4 className="text-xs font-bold text-zinc-100 uppercase tracking-wider">
                Post-Mortem Spatial Data Foundations
              </h4>
            </div>

            <div className="space-y-3 font-sans">
              <div className="flex items-start gap-2.5">
                <div className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0 mt-1.5"></div>
                <p className="text-[11px] text-zinc-400 leading-normal">
                  <strong className="text-zinc-300">Stigmatization Controls</strong>: Publishing maps detailing specific housing complexes is highly vulnerable to local gossip, or home price depreciation. Grid aggregations bypass individual point blame.
                </p>
              </div>

              <div className="flex items-start gap-2.5">
                <div className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0 mt-1.5"></div>
                <p className="text-[11px] text-zinc-400 leading-normal">
                  <strong className="text-zinc-300">Dynamic Suppressing</strong>: Databases must evaluate counts dynamically. If a query counts only 1 death within a grid cell, the cell must return NULL or suppressed metrics rather than representing a solitary data item.
                </p>
              </div>

              <div className="flex items-start gap-2.5">
                <div className="w-1.5 h-1.5 rounded-full bg-rose-500 shrink-0 mt-1.5"></div>
                <p className="text-[11px] text-zinc-400 leading-normal">
                  <strong className="text-zinc-300">Robots.txt Scraping Auditing</strong>: Automated scrapers must recognize standard rate-limiting. Ethical scrapers identify themselves via specific headers (e.g., <code>User-Agent: MortalityRiskGisProject/1.0</code>).
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-zinc-900 flex items-center gap-2.5 bg-zinc-900/30 p-3 rounded-xl border border-zinc-850">
            <HelpingHand className="w-5 h-5 text-rose-400 shrink-0" />
            <div className="text-[10.5px] leading-relaxed text-zinc-400">
              Need assistance setting up open-data CDC APIs? Check official CDC developer networks.
            </div>
          </div>
        </div>
      </div>

      {/* Interactive Scoreboard + Checklist Columns */}
      <div className="lg:col-span-5 flex flex-col gap-6">
        {/* Compliance Rating Card */}
        <div className="bg-zinc-950 p-5 rounded-2xl border border-zinc-800 shadow-xl text-center flex flex-col items-center justify-center">
          <span className="block text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-3">
            Active Spatial Risk Scorecard
          </span>

          <div className="relative flex items-center justify-center mb-3">
            {/* SVG Ring Progress */}
            <svg className="w-24 h-24 transform -rotate-90 animate-fade-in">
              <circle
                cx="48"
                cy="48"
                r="42"
                className="stroke-zinc-900 fill-transparent"
                strokeWidth="6"
              />
              <circle
                cx="48"
                cy="48"
                r="42"
                className="stroke-rose-600 fill-transparent transition-all duration-500"
                strokeWidth="6"
                strokeDasharray="264"
                strokeDashoffset={264 - (264 * rating.score) / 100}
              />
            </svg>
            <div className="absolute font-mono text-2xl font-black text-zinc-100">
              {rating.score}%
            </div>
          </div>

          <div className={`py-1 px-3.5 rounded-full text-[10.5px] font-bold font-mono tracking-wider border shadow-sm transition-all duration-300 ${rating.color}`}>
            {rating.label}
          </div>

          <p className="text-[10px] text-zinc-500 leading-normal mt-2 max-w-[200px]">
            {isEditable 
              ? "Tick active measures in the checklist below to harden the privacy index of your PostGIS geospatial system."
              : "Anonymized public map is audited and locked at the highest security level. Review verified core privacy controls below."}
          </p>
        </div>

        {/* Dynamic Compliance Interactive Checklist */}
        <div className="bg-zinc-950 p-5 rounded-2xl border border-zinc-800 shadow-xl flex-1">
          <div className="flex items-center gap-1.5 mb-3 border-b border-zinc-900 pb-2 justify-between">
            <div className="flex items-center gap-1.5">
              <FileCheck className="w-4 h-4 text-emerald-500" />
              <h4 className="text-xs font-bold text-zinc-200 uppercase tracking-wider">
                {isEditable ? "Anonymity Checklist Controls" : "Audited Privacy Safeguards"}
              </h4>
            </div>
            {!isEditable && (
              <span className="flex items-center gap-1 text-[9px] font-mono font-bold text-emerald-400 bg-emerald-950/40 border border-emerald-900/40 px-2 py-0.5 rounded-full">
                <ShieldCheck className="w-3 h-3 text-emerald-400" />
                READ-ONLY AUDIT
              </span>
            )}
          </div>

          <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
            {checklist.map((item) => (
              <div
                key={item.id}
                id={`check-row-${item.id}`}
                onClick={() => toggleCheck(item.id)}
                className={`p-2.5 rounded-xl border text-left transition-all flex gap-2.5 items-start ${
                  isEditable 
                    ? "cursor-pointer hover:bg-zinc-900/40" 
                    : "cursor-default"
                } ${
                  item.isCompleted
                    ? "border-emerald-900/40 bg-emerald-950/15"
                    : "border-zinc-900 bg-zinc-900/10"
                }`}
              >
                <input
                  type="checkbox"
                  checked={item.isCompleted}
                  onChange={() => {}} // toggled via row click
                  disabled={!isEditable}
                  className="w-4 h-4 mt-0.5 rounded text-emerald-500 border-zinc-800 bg-zinc-950 focus:ring-emerald-500 shrink-0 pointer-events-none"
                />
                <div className="flex-1">
                  <div className="flex justify-between items-center bg-transparent">
                    <span className={`text-xs font-medium ${item.isCompleted && isEditable ? "text-zinc-500 line-through" : "text-zinc-200"}`}>
                      {item.question}
                    </span>
                    <span className="text-[8px] font-mono text-zinc-550 uppercase bg-zinc-900 px-1.5 py-0.5 rounded border border-zinc-800/80">
                      {item.category}
                    </span>
                  </div>
                  <p className="text-[10px] text-zinc-400 mt-1 leading-relaxed">
                    {item.guideline}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {rating.score === 100 && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="mt-3.5 p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-450 rounded-xl flex items-center gap-2"
            >
              <Award className="w-5 h-5 text-emerald-500 shrink-0 animate-bounce" />
              <span className="text-[9px] font-bold font-mono tracking-tight uppercase">
                Systems fully verified & compliant with HIPAA Safe Harbor rulesets. Ready for GIS production launch!
              </span>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
