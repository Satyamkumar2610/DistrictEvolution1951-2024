import { fetcher } from './client';
import { SplitEvent, ProvenanceTracking, LineageCoverage } from './types';

export const lineageApi = {
    getUnmappedSplits: () =>
        fetcher<{ district: string; state: string; year: number; role: string }[]>('lineage/unmapped'),

    getLineageHistory: (state?: string) =>
        fetcher<SplitEvent[]>(`lineage/history${state ? `?state=${encodeURIComponent(state)}` : ''}`),

    getDataTracking: (cdk: string) =>
        fetcher<ProvenanceTracking>(`lineage/tracking?cdk=${cdk}`),

    getStateCoverage: (state: string) =>
        fetcher<LineageCoverage>(`lineage/coverage?state=${encodeURIComponent(state)}`),
};
