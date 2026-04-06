import { buildPublicApiV1Url } from './config';

export interface CommodityInfo {
    name: string;
    normalized: string;
    record_count: number;
    states_count: number;
    latest_date: string | null;
    avg_price: number | null;
}

export interface PriceTrendPoint {
    date: string;
    avg_modal_price: number;
    min_price: number | null;
    max_price: number | null;
    record_count: number;
}

export interface PriceTrend {
    state: string;
    commodity: string;
    period_start: string | null;
    period_end: string | null;
    data_points: PriceTrendPoint[];
    avg_price: number | null;
    price_change_pct: number | null;
}

export interface MSPRate {
    crop: string;
    season: string;
    year: number;
    msp_price: number;
    grade: string | null;
    unit: string;
}

export interface MSPComparisonItem {
    district: string;
    market: string | null;
    avg_modal_price: number;
    msp_price: number;
    price_vs_msp_ratio: number;
    premium_or_deficit_pct: number;
    status: 'Above MSP' | 'At MSP' | 'Below MSP';
}

export interface MSPComparisonResponse {
    state: string;
    crop: string;
    year: number;
    msp: MSPRate;
    districts: MSPComparisonItem[];
    state_avg_modal_price: number | null;
    state_avg_ratio: number | null;
    districts_above_msp: number;
    districts_below_msp: number;
    source: string;
}


export async function fetchAvailableCommodities(): Promise<CommodityInfo[]> {
    const response = await fetch(buildPublicApiV1Url('/market/commodities'), { cache: 'no-store' });
    if (!response.ok) {
        throw new Error(`Failed to fetch commodities: ${response.statusText}`);
    }
    return response.json();
}

export async function fetchPriceTrends(state: string, commodity: string, days: number = 30): Promise<PriceTrend> {
    const url = new URL(buildPublicApiV1Url('/market/trends'));
    url.searchParams.append('state', state);
    url.searchParams.append('commodity', commodity);
    url.searchParams.append('days', days.toString());

    const response = await fetch(url.toString(), { cache: 'no-store' });
    if (!response.ok) {
        throw new Error(`Failed to fetch price trends: ${response.statusText}`);
    }
    return response.json();
}

export async function fetchMSPComparison(state: string, crop: string, year?: number): Promise<MSPComparisonResponse> {
    const url = new URL(buildPublicApiV1Url('/market/msp-comparison'));
    url.searchParams.append('state', state);
    url.searchParams.append('crop', crop);
    if (year) {
        url.searchParams.append('year', year.toString());
    }

    const response = await fetch(url.toString(), { cache: 'no-store' });
    if (!response.ok) {
        throw new Error(`Failed to fetch MSP comparison: ${response.statusText}`);
    }
    return response.json();
}
