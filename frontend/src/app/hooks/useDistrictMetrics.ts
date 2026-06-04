import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../services/api';
import type { DistrictMetric } from '../services/api/types';

export const useDistrictMetrics = (year: number, crop: string, metric: string, mode: string = 'historical') => {
    // React Query handles loading, data, and errors
    const { data: rawData = [], isLoading: loading } = useQuery({
        queryKey: ['districtMetrics', year, crop, metric, mode],
        queryFn: () => api.getDistrictMetrics(year, crop, metric, mode),
        staleTime: 1000 * 60 * 10, // Cache for 10 minutes
    });

    // The backend is the source of truth for map feature resolution.
    const joinedData = useMemo(() => {
        if (!rawData.length) return {};

        const join: Record<string, DistrictMetric> = {};
        let unmappedCount = 0;

        rawData.forEach((d: DistrictMetric) => {
            const featureId = d.feature_id ?? d.geo_key;
            if (featureId) {
                join[featureId] = d;
                return;
            }
            unmappedCount++;
        });

        if (unmappedCount > 0) {
            console.warn(
                `[useDistrictMetrics] ${unmappedCount} districts were missing backend feature_id values`,
            );
        }

        return join;
    }, [rawData]);

    return { joinedData, loading, rawData };
};
