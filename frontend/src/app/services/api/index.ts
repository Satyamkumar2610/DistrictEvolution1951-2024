import { fetcher, ApiError } from './client';
import { analyticsApi } from './analytics';
import { metricsApi } from './metrics';
import { lineageApi } from './lineage';
import { 
    SimulationResult, PredictionV2Result, SearchResult, HighRiskResult, RainfallData, DistrictReport, DistrictAnomaliesData, StateAnomaliesData, YieldForecastResult, CropRecommendationsResult
} from './types';
import { CorrelationData } from '../../../types/analysis';

export * from './types';
export { ApiError, fetcher };

export const api = {
    // Re-export grouped domains
    ...analyticsApi,
    ...metricsApi,
    ...lineageApi,

    // --- Search ---
    getDistrictsByState: (state: string) =>
        fetcher<{ total: number; items: { cdk: string; name: string; state: string }[] }>(`districts?state=${encodeURIComponent(state)}`),

    searchDistricts: (query: string, type: string = 'all') =>
        fetcher<SearchResult>(`search?q=${encodeURIComponent(query)}&type=${type}`),

    // --- Climate & Environment ---
    getWaterStress: (state: string, year: number) =>
        fetcher<{ state: string; year: number; districts: Array<{ district_name: string; cdk: string; total_area: number; water_intensive_area: number; water_intensive_share: number; annual_rainfall: number; mismatch_score: number; category: string; crop_breakdown: Record<string, number> }> }>(`climate/water-stress?state=${encodeURIComponent(state)}&year=${year}`),

    getRainfall: (district: string, state: string, year: number) =>
        fetcher<RainfallData>(`climate/rainfall?district=${encodeURIComponent(district)}&state=${encodeURIComponent(state)}&year=${year}`),

    getClimateCorrelation: (state: string, crop: string, year: number) =>
        fetcher<CorrelationData>(`climate/correlation?state=${encodeURIComponent(state)}&crop=${crop}&year=${year}`),

    // --- Simulation & Prediction ---
    runSimulation: (district: string, state: string, crop: string, year: number) =>
        fetcher<SimulationResult>(`simulation?district=${encodeURIComponent(district)}&state=${encodeURIComponent(state)}&crop=${crop}&year=${year}`),

    runPredictionV2: (district: string, state: string, crop: string, year: number) =>
        fetcher<PredictionV2Result>(`simulation/v2?district=${encodeURIComponent(district)}&state=${encodeURIComponent(state)}&crop=${crop}&year=${year}`),

    // --- Spatial / Contagion ---
    getSpatialContagion: (cdk: string, crop: string, startYear: number, endYear: number) =>
        fetcher<{ target: { cdk: string; name: string; cagr: number }; regional_avg_cagr: number; spillover_category: string; period: string; crop: string; neighbors: Array<{ cdk: string; name: string; state: string; cagr: number }> }>(`spatial/contagion?cdk=${cdk}&crop=${crop}&start_year=${startYear}&end_year=${endYear}`),

    // --- Anomaly Detection ---
    getDistrictAnomalies: (cdk: string) =>
        fetcher<DistrictAnomaliesData>(`anomalies/district/${cdk}`),

    getStateAnomalies: (state: string, limit: number = 20) =>
        fetcher<StateAnomaliesData>(`anomalies/state/${encodeURIComponent(state)}?limit=${limit}`),

    getHighRiskDistricts: (limit: number = 10) =>
        fetcher<HighRiskResult>(`anomalies/high-risk?limit=${limit}`),

    // --- Forecast ---
    getYieldForecast: (cdk: string, crop: string, horizon: number = 3) =>
        fetcher<YieldForecastResult>(`forecast/${cdk}/${crop}?horizon=${horizon}`),

    getCropRecommendations: (cdk: string, topN: number = 5) =>
        fetcher<CropRecommendationsResult>(`forecast/${cdk}/recommend?top_n=${topN}`),

    // --- Reports ---
    getDistrictReport: (cdk: string, crop: string = 'wheat', format: string = 'json') =>
        fetcher<DistrictReport>(`reports/district-profile?cdk=${cdk}&crop=${crop}&format=${format}`),
};
