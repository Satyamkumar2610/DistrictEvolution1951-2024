import { fetcher } from './client';
import { DistrictMetric, HistoryItem, DistrictRanking, StateOverview } from './types';
import { EfficiencyData, RiskData } from '../../../types/analysis';

export const metricsApi = {
    getDistrictMetrics: (year: number, crop: string, metric: string, mode: string = 'historical') =>
        fetcher<DistrictMetric[]>(`metrics?year=${year}&crop=${crop}&metric=${metric}&mode=${mode}`),

    getHistory: (district: string, crop: string, state?: string) =>
        fetcher<HistoryItem[]>(`metrics/history?district=${encodeURIComponent(district)}&crop=${crop}${state ? `&state=${encodeURIComponent(state)}` : ''}`),

    getDistrictRankings: (state: string, crop: string, year: number) =>
        fetcher<DistrictRanking[]>(`analytics/district-rankings?state=${encodeURIComponent(state)}&crop=${crop}&year=${year}`),

    getEfficiency: (cdk: string, crop: string, year: number) =>
        fetcher<EfficiencyData>(`analysis/efficiency?cdk=${cdk}&crop=${crop}&year=${year}`),

    getRiskProfile: (cdk: string, crop: string) =>
        fetcher<RiskData>(`analysis/risk-profile?cdk=${cdk}&crop=${crop}`),

    getStatesList: () =>
        fetcher<{ state: string; district_count: number }[]>('states/list'),

    getStateOverview: (state: string, crop: string = 'wheat', year?: number) =>
        fetcher<StateOverview>(`states/${encodeURIComponent(state)}/overview?crop=${crop}${year ? `&year=${year}` : ''}`),
};
