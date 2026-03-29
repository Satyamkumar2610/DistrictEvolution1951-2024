import { fetcher } from './client';
import { StateSummary, SplitDistrict, AnalysisResult, AnalyticsSummary, SplitImpactQueryParams, SplitImpactResult, SplitSpecializationResult } from './types';
import { DiversificationData, YieldTrendData, YoyGrowthData, CropCorrelationData } from '../../../types/analysis';

export const analyticsApi = {
    getSummary: async () => {
        const res = await fetcher<StateSummary>('analysis/split-impact/summary');
        return { ...res, states: [...res.states].sort() };
    },

    getSplitEvents: (state: string) =>
        fetcher<SplitDistrict[]>(`analysis/split-impact/districts?state=${encodeURIComponent(state)}`),

    getAnalysis: (params: SplitImpactQueryParams) => {
        const searchParams = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
            searchParams.append(key, String(value));
        });
        return fetcher<AnalysisResult>(`analysis/split-impact/analysis?${searchParams.toString()}`);
    },

    getDiversification: (cdk: string, year: number) =>
        fetcher<DiversificationData>(`analytics/diversification?cdk=${encodeURIComponent(cdk)}&year=${year}`),

    getCropShift: (cdk: string) =>
        fetcher<{ cdk: string; timeline: Array<{ year: number; total_area: number; shannon_index: number; simpson_index: number; dominant_crop: string; dominant_share: number; crop_mix: Record<string, number> }> }>(`analytics/crop-shift?cdk=${cdk}`),

    getYieldGap: (state: string, crop: string, startYear: number, endYear: number) =>
        fetcher<{ state: string; crop: string; period: string; convergence_timeline: Array<{ year: number; frontier_yield: number; state_avg_yield: number; avg_gap: number }>; district_rankings: Array<{ cdk: string; district_name: string; avg_gap: number; latest_gap: number; avg_yield: number; gap_trend: number; status: string; rank: number }> }>(`analytics/yield-gap?state=${encodeURIComponent(state)}&crop=${crop}&start_year=${startYear}&end_year=${endYear}`),

    getYieldTrend: (cdk: string, crop: string) =>
        fetcher<YieldTrendData>(`analytics/yield-trend?cdk=${cdk}&crop=${crop}`),

    getSplitImpact: (parentCdk: string, childCdks: string[], splitYear: number, crop: string) =>
        fetcher<SplitImpactResult>(`analytics/split-impact?parent_cdk=${parentCdk}&child_cdks=${childCdks.join(',')}&split_year=${splitYear}&crop=${crop}`),

    getSplitSpecialization: (parentCdk: string, childCdks: string[], splitYear: number) =>
        fetcher<SplitSpecializationResult>(`analytics/split-specialization?parent_cdk=${parentCdk}&child_cdks=${childCdks.join(',')}&split_year=${splitYear}`),

    getCropCorrelations: (state: string, year: number, crops?: string[]) =>
        fetcher<CropCorrelationData>(`analytics/crop-correlations?state=${encodeURIComponent(state)}&year=${year}${crops ? `&crops=${crops.join(',')}` : ''}`),

    getAnalyticsSummary: (cdk: string, year: number) =>
        fetcher<AnalyticsSummary>(`analytics/summary?cdk=${cdk}&year=${year}`),

    getYoyGrowth: (cdk: string, crop: string, startYear: number = 1990, endYear: number = 2020) =>
        fetcher<YoyGrowthData>(`analytics/yoy-growth?cdk=${cdk}&crop=${crop}&start_year=${startYear}&end_year=${endYear}`)
};
