import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { AnonymizedMortalityRecord } from '../types';

interface GisMapProps {
  records: AnonymizedMortalityRecord[];
  selectedRecordId: string | null;
  onSelectRecord: (id: string | null) => void;
  spatialAggregationLevel: 'grid_80m' | 'intersection' | 'zip_centroid' | 'neighborhood';
  mapCenterOverride?: [number, number] | null;
  onBoundsChange?: (bounds: { north: number; south: number; east: number; west: number }) => void;
}

export default function GisMap({
  records,
  selectedRecordId,
  onSelectRecord,
  spatialAggregationLevel,
  onBoundsChange,
  mapCenterOverride
}: GisMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersRef = useRef<any[]>([]);
  const lastFittedRecordsIdRef = useRef<string>('');
  const [activeLayer, setActiveLayer] = useState<'standard' | 'grayscale'>('grayscale');

  // Helper to get color code based on manner of death
  const getMannerOfColor = (manner: string) => {
    switch (manner) {
      case 'Natural': return '#10b981'; // Green
      case 'Accident': return '#3b82f6'; // Blue
      case 'Toxicological': return '#ef4444'; // Red
      case 'Environmental': return '#f59e0b'; // Amber
      case 'Homicide': return '#ec4899'; // Pink
      case 'Suicide': return '#a855f7'; // Purple
      default: return '#6b7280'; // Gray
    }
  };

  // Helper to get tailwind class for manner of death
  const getMannerBgTag = (manner: string) => {
    switch (manner) {
      case 'Natural': return 'bg-emerald-500 border border-emerald-600 shadow-emerald-500/20';
      case 'Accident': return 'bg-blue-500 border border-blue-600 shadow-blue-500/20';
      case 'Toxicological': return 'bg-rose-500 border border-rose-600 shadow-rose-500/20';
      case 'Environmental': return 'bg-amber-500 border border-amber-600 shadow-amber-500/20';
      case 'Homicide': return 'bg-pink-500 border border-pink-600 shadow-pink-500/20';
      case 'Suicide': return 'bg-purple-500 border border-purple-600 shadow-purple-500/20';
      default: return 'bg-zinc-500 border border-zinc-600 shadow-zinc-500/20';
    }
  };

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Create Leaflet Map centered on San Francisco
    const map = L.map(mapContainerRef.current, {
      center: [37.760, -122.435],
      zoom: 13,
      minZoom: 3,
      maxZoom: 15, // ETHICAL SAFEGUARD: Prevent zooming in to identify individual houses
      preferCanvas: true, // Hardware-accelerated Canvas layer for vector vectors
      zoomControl: true,
      scrollWheelZoom: true,
    });

    // Add standard OSM tile layer
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
      subdomains: 'abcd',
      maxZoom: 20
    }).addTo(map);

    mapInstanceRef.current = map;

    // ── Live viewport filter ─────────────────────────────────────────────────
    // Fire onBoundsChange whenever the user pans or zooms so the parent can
    // filter records to only those visible inside the current map viewport.
    const fireBounds = () => {
      if (!onBoundsChange) return;
      const b = map.getBounds();
      onBoundsChange({
        north: b.getNorth(),
        south: b.getSouth(),
        east:  b.getEast(),
        west:  b.getWest(),
      });
    };
    map.on('moveend', fireBounds);
    map.on('zoomend', fireBounds);
    // Fire once on mount so the initial viewport is registered
    fireBounds();


    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [onBoundsChange]);

  // Update Tile Layer if grayscale is toggled
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Clear existing tiles
    map.eachLayer((layer) => {
      if (layer instanceof L.TileLayer) {
        map.removeLayer(layer);
      }
    });

    const url = activeLayer === 'grayscale'
      ? 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png'
      : 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';

    const attribution = activeLayer === 'grayscale'
      ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
      : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; CARTO';

    L.tileLayer(url, { attribution, maxZoom: 15 }).addTo(map);
  }, [activeLayer]);

  // Update Markers when records or selectedRecordId or aggregation level changes
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    // Clear existing markers
    markersRef.current.forEach(m => map.removeLayer(m));
    markersRef.current = [];

    records.forEach((record) => {
      const { lat, lng } = record.location;
      const color = getMannerOfColor(record.mannerOfDeath);
      const isSelected = record.id === selectedRecordId;

      // Spatial shifting simulator depending on the sidebar selection
      // This visualizes how snapping changes the positions physically
      let finalLat = lat;
      let finalLng = lng;

      if (spatialAggregationLevel === 'grid_80m') {
        const gridLatSize = 0.00072; // ~80m latitude spacing
        const gridLngSize = 0.00091; // ~80m longitude spacing at SF latitude
        finalLat = Math.round(lat / gridLatSize) * gridLatSize;
        finalLng = Math.round(lng / gridLngSize) * gridLngSize;
      } else if (spatialAggregationLevel === 'zip_centroid') {
        // Generic high-fidelity ZIP code centroid grouping: snap to 1.1km grid cells (0.01 deg)
        finalLat = Math.round(lat * 100) / 100;
        finalLng = Math.round(lng * 100) / 100;
      } else if (spatialAggregationLevel === 'neighborhood') {
        // Generic neighborhood/municipal grouping: snap to 5.5km grid cells (0.05 deg)
        finalLat = Math.round(lat * 20) / 20;
        finalLng = Math.round(lng * 20) / 20;
      }

      // Render as a high-performance CircleMarker on Leaflet's Canvas overlay
      const marker = L.circleMarker([finalLat, finalLng], {
        radius: isSelected ? 8 : 4.5,
        fillColor: color,
        color: isSelected ? '#ffffff' : '#1e1b4b', // Cosmic blue borders
        weight: isSelected ? 3 : 1.2,
        fillOpacity: isSelected ? 1.0 : 0.85
      })
      .addTo(map)
      .on('click', () => {
        onSelectRecord(record.id);
      });

      // Add a customized, non-identifying tooltip popup
      const popupContent = `
        <div class="p-2.5 font-sans min-w-[170px]" id="popup-${record.id}">
          <div class="flex items-center gap-1.5 mb-1">
            <span class="w-2.5 h-2.5 rounded-full inline-block" style="background-color: ${color}"></span>
            <span class="font-bold text-gray-900 text-sm tracking-tight">${record.mannerOfDeath} Case</span>
          </div>
          <div class="text-[11px] text-gray-500 uppercase font-mono tracking-wider space-y-0.5">
            <div>Age Group: ${record.ageGroup}</div>
            <div>Gender: ${record.gender}</div>
            <div class="text-indigo-600 mt-1 font-semibold normal-case">${record.location.extractedEntity}</div>
          </div>
          <div class="mt-1.5 pt-1 border-t border-gray-100 text-[10px] text-emerald-600 font-medium flex items-center gap-1">
            <span>🛡️ Aggregated Point</span>
          </div>
        </div>
      `;

      marker.bindPopup(popupContent, {
        closeButton: true,
        className: 'custom-leaflet-popup'
      });

      markersRef.current.push(marker);
    });

    // Auto-fit to bounds if records span a wide geographic area and we don't have a single selected record
    const recordIdsStr = records.map(r => r.id).sort().join(',');
    if (records.length > 0 && !selectedRecordId && !mapCenterOverride && lastFittedRecordsIdRef.current !== recordIdsStr) {
      const lats = records.map(r => r.location.lat);
      const lngs = records.map(r => r.location.lng);
      const minLat = Math.min(...lats);
      const maxLat = Math.max(...lats);
      const minLng = Math.min(...lngs);
      const maxLng = Math.max(...lngs);

      // If the spread is large (i.e. spans more than simple San Francisco city boundaries)
      if (maxLat - minLat > 1.0 || maxLng - minLng > 1.0) {
        try {
          map.fitBounds([
            [minLat, minLng],
            [maxLat, maxLng]
          ], {
            padding: [40, 40],
            maxZoom: 6, // Don't zoom in too close for national/statewide view
            animate: true
          });
          lastFittedRecordsIdRef.current = recordIdsStr;
        } catch (e) {
          console.warn("Bounds fitting failed", e);
        }
      }
    }

  }, [records, selectedRecordId, spatialAggregationLevel, onSelectRecord, mapCenterOverride]);

  // Handle zooming / panning to selected record
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !selectedRecordId) return;

    const record = records.find(r => r.id === selectedRecordId);
    if (!record) return;

    let targetLat = record.location.lat;
    let targetLng = record.location.lng;

    // Match map shift offsets if zipcode aggregate is picked
    if (spatialAggregationLevel === 'grid_80m') {
      const gridLatSize = 0.00072;
      const gridLngSize = 0.00091;
      targetLat = Math.round(record.location.lat / gridLatSize) * gridLatSize;
      targetLng = Math.round(record.location.lng / gridLngSize) * gridLngSize;
    } else if (spatialAggregationLevel === 'zip_centroid') {
      targetLat = Math.round(record.location.lat * 100) / 100;
      targetLng = Math.round(record.location.lng * 100) / 100;
    } else if (spatialAggregationLevel === 'neighborhood') {
      targetLat = Math.round(record.location.lat * 20) / 20;
      targetLng = Math.round(record.location.lng * 20) / 20;
    }

    map.setView([targetLat, targetLng], 14, {
      animate: true,
      duration: 0.8
    });

    // Find and trigger popup on the specific marker
    const index = records.findIndex(r => r.id === selectedRecordId);
    if (index !== -1 && markersRef.current[index]) {
      markersRef.current[index].openPopup();
    }
  }, [selectedRecordId, records, spatialAggregationLevel]);

  // Handle center override (e.g., zip code search centering)
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mapCenterOverride) return;

    map.setView(mapCenterOverride, 13, {
      animate: true,
      duration: 0.8
    });
  }, [mapCenterOverride]);

  return (
    <div className="relative w-full h-[540px] rounded-2xl overflow-hidden border border-zinc-850 shadow-2xl bg-zinc-950" id="gis-map-component">
      {/* Absolute Header Overlay */}
      <div className="absolute top-3 left-3 z-[1000] bg-zinc-950/90 backdrop-blur-md py-1.5 px-3 rounded-lg shadow-sm border border-zinc-800 flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-500 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-600"></span>
        </span>
        <span className="text-[10px] font-mono font-bold text-zinc-300 tracking-wider select-none uppercase">
          GIS ENGINE: ACTIVE (OSM VOYAGER)
        </span>
      </div>

      {/* Map style toggles (Top-Right) */}
      <div className="absolute top-3 right-3 z-[1000] flex bg-zinc-950/90 backdrop-blur-md rounded-lg shadow-sm border border-zinc-800 p-0.5">
        <button
          id="map-style-standard"
          onClick={() => setActiveLayer('standard')}
          className={`px-2.5 py-1 rounded-md text-[10px] font-mono tracking-wider font-bold transition-all cursor-pointer ${
            activeLayer === 'standard' 
              ? 'bg-zinc-850 text-zinc-100 shadow-sm border border-zinc-700' 
              : 'text-zinc-500 hover:text-zinc-300'
          }`}
        >
          LIGHT MAP
        </button>
        <button
          id="map-style-dark"
          onClick={() => setActiveLayer('grayscale')}
          className={`px-2.5 py-1 rounded-md text-[10px] font-mono tracking-wider font-bold transition-all cursor-pointer ${
            activeLayer === 'grayscale' 
              ? 'bg-zinc-850 text-zinc-100 shadow-sm border border-zinc-700' 
              : 'text-zinc-500 hover:text-zinc-300'
          }`}
        >
          DARK MAP
        </button>
      </div>

      {/* Interactive Map Canvas */}
      <div ref={mapContainerRef} className="w-full h-full z-10" id="leaflet-map-canvas" />

      {/* Map Legend Overlay */}
      <div className="absolute bottom-4 right-4 z-[1000] bg-zinc-950/95 backdrop-blur-md p-3 rounded-xl shadow-md border border-zinc-800 max-w-[190px] font-sans md:block hidden select-none">
        <div className="text-[9px] font-mono uppercase font-black text-zinc-500 tracking-wider mb-2 border-b border-zinc-900 pb-1">
          🛡️ Manner of Death
        </div>
        <div className="space-y-1.5">
          <div className="flex items-center gap-2 text-xs text-zinc-300 font-medium">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 border border-emerald-600"></span>
            <span>Natural</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-300 font-medium">
            <span className="w-2.5 h-2.5 rounded-full bg-blue-500 border border-blue-600"></span>
            <span>Accident</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-300 font-medium">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 border border-rose-600"></span>
            <span>Toxicological</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-zinc-300 font-medium">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500 border border-amber-600"></span>
            <span>Environmental</span>
          </div>
        </div>
        <div className="mt-2 text-[9px] text-rose-300 leading-tight bg-rose-950/20 border border-rose-900/30 p-1.5 rounded font-mono">
          ▲ Capped zoom (15 max) to prevent single-home detection.
        </div>
      </div>
    </div>
  );
}
