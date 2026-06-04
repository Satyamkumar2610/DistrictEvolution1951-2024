"use client";

import { useCallback, Suspense } from 'react';
import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';
import TimeSlider from '../../components/TimeSlider';
import Dashboard from '../../components/Dashboard';
import { useDistrictMetrics } from '../../hooks/useDistrictMetrics';

// Dynamic import for Map
const MapInterface = dynamic(() => import('../../components/MapInterface'), {
  ssr: false,
  loading: () => (
    <div className="h-full w-full flex items-center justify-center bg-slate-950 text-white">
      <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500"></div>
    </div>
  )
});

function DistrictEvolutionApp() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Read State from URL with defaults
  const year = parseInt(searchParams.get('year') || '2001');
  const crop = searchParams.get('crop') || 'wheat';
  const metric = searchParams.get('metric') || 'yield';
  const selectedDistrict = searchParams.get('district');
  const selectedState = searchParams.get('state');
  const showRainfall = searchParams.get('rainfall') === 'true';

  // Helper to update URL
  const updateUrl = useCallback((updates: Record<string, string | number | null | boolean>) => {
    const params = new URLSearchParams(searchParams);
    Object.entries(updates).forEach(([key, value]) => {
      if (value === null) params.delete(key);
      else params.set(key, String(value));
    });
    router.push(`/explore/map?${params.toString()}`, { scroll: false });
  }, [searchParams, router]);

  // Data Fetching Hook
  const { joinedData } = useDistrictMetrics(year, crop, metric);

  // Selected Data Logic
  const selectedData = selectedDistrict ? (() => {
    if (joinedData[selectedDistrict]) return joinedData[selectedDistrict];
    const key = Object.keys(joinedData).find(k => k.startsWith(selectedDistrict + '|'));
    return key ? joinedData[key] : null;
  })() : null;

  return (
    <main className="flex h-screen w-screen bg-slate-950 overflow-hidden relative">
      {/* Sidebar Controls */}
      <Dashboard
        selectedDistrict={selectedDistrict}
        selectedState={selectedState}
        currentYear={year}
        onClose={() => updateUrl({ district: null, state: null })}
        onDistrictSelect={(selection) => updateUrl({ district: selection.district, state: selection.state })}
        currentCrop={crop}
        onCropChange={(c) => updateUrl({ crop: c })}
        currentMetric={metric}
        onMetricChange={(m) => updateUrl({ metric: m })}
        districtData={selectedData || undefined}
        showRainfallLayer={showRainfall}
        onRainfallLayerToggle={() => updateUrl({ rainfall: !showRainfall })}
        onContextChange={(ctx) => updateUrl({ district: ctx.district, year: ctx.year, crop: ctx.crop })}
      />

      {/* Main Map Area */}
      <div className="flex-1 flex flex-col h-full relative md:ml-80">
        <div className="flex-1 relative z-0">
          <MapInterface
            year={year}
            crop={crop}
            metric={metric}
            selectedDistrict={selectedDistrict}
            onDistrictSelect={(selection) => updateUrl({ district: selection.district, state: selection.state })}
            showRainfallLayer={showRainfall}
          />
        </div>

        {/* Time Slider */}
        <div className="absolute bottom-4 left-4 right-4 md:bottom-6 md:left-10 md:right-10 z-10 pointer-events-none flex justify-center">
          <div className="pointer-events-auto w-full max-w-4xl bg-slate-900/80 backdrop-blur-md border border-slate-700 p-3 md:p-4 rounded-xl shadow-2xl">
            <TimeSlider
              minYear={1966}
              maxYear={2017}
              currentYear={year}
              onChange={(y) => updateUrl({ year: y })}
            />
          </div>
        </div>
      </div>
    </main>
  );
}

export default function Home() {
  return (
    <Suspense fallback={
      <div className="h-screen w-screen flex items-center justify-center bg-slate-950 text-emerald-500 font-mono">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin"></div>
          <div className="text-sm tracking-widest uppercase">Initializing I-ASCAP...</div>
        </div>
      </div>
    }>
      <DistrictEvolutionApp />
    </Suspense>
  );
}
