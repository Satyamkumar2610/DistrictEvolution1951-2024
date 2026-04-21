import { fetcher } from './client';

// ---- Types ----

export interface ClimateShockAttribution {
    year: number;
    actual_yield: number;
    expected_yield: number;
    deviation_pct: number;
    z_score: number;
    attributed_events: { type: string; severity: string; metric_value: number; description: string }[];
    confidence: number;
    interpretation: string;
}

export interface ClimateShocksResult {
    cdk: string;
    name: string | null;
    crop: string;
    period: string;
    total_shock_years: number;
    most_damaging_event_type: string | null;
    avg_loss_per_shock_pct: number;
    event_frequency: Record<string, number>;
    attributions: ClimateShockAttribution[];
    warnings: string[];
    ai_narrative?: string | null;
}

export interface ForecastValidationStep {
    train_end_year: number;
    forecast_year: number;
    actual: number;
    predicted: number;
    error_pct: number;
    within_ci: boolean;
}

export interface ForecastValidationResult {
    cdk: string;
    crop: string;
    method: string;
    trustworthiness_grade: string;
    metrics: {
        rmse: number;
        mae: number;
        mape: number;
        bias: number;
        coverage_pct: number;
        directional_accuracy: number;
        n_steps: number;
        best_year: number | null;
        worst_year: number | null;
    };
    interpretation: string;
    steps: ForecastValidationStep[];
    warnings: string[];
    ai_narrative?: string | null;
}

export interface YieldFrontierDistrict {
    cdk: string;
    name: string;
    observed_yield: number;
    frontier_yield: number;
    technical_efficiency: number;
    yield_gap_pct: number;
    rank: number;
}

export interface YieldFrontierResult {
    crop: string;
    year: number;
    model_stats: {
        n_districts: number;
        sigma_v: number;
        sigma_u: number;
        gamma: number;
        mean_te: number;
    };
    frontier_interpretation: string;
    district_results: YieldFrontierDistrict[];
    warnings: string[];
    ai_narrative?: string | null;
}

export interface ResilienceDistrictResult {
    cdk: string;
    name: string;
    resilience_score: number;
    grade: string;
    rank: number;
    interpretation: string;
}

export interface ResilienceCompositeResult {
    region: string;
    n_districts: number;
    n_components: number;
    total_variance_explained: number;
    mean_score: number;
    variable_contributions: Record<string, number>;
    district_results: ResilienceDistrictResult[];
    warnings: string[];
}

export interface CropCalendarPhase {
    phase: string;
    month: number;
    ndvi_value: number;
}

export interface CropCalendarDeviation {
    event: string;
    detected_month: number;
    reference_month: number;
    deviation_months: number;
    risk_level: string;
    description: string;
}

export interface CropCalendarResult {
    cdk: string;
    year: number;
    crop: string | null;
    peak_ndvi_month: number;
    peak_ndvi_value: number;
    growing_season_length: number;
    detected_phases: CropCalendarPhase[];
    deviations: CropCalendarDeviation[];
    warnings: string[];
}

// ---- API Methods ----

export const intelligenceApi = {
    getClimateShocks: (cdk: string, crop: string) =>
        fetcher<ClimateShocksResult>(`intelligence/climate-shocks?cdk=${encodeURIComponent(cdk)}&crop=${encodeURIComponent(crop)}`),

    getForecastValidation: (cdk: string, crop: string) =>
        fetcher<ForecastValidationResult>(`intelligence/forecast-validation?cdk=${encodeURIComponent(cdk)}&crop=${encodeURIComponent(crop)}`),

    getYieldFrontier: (state: string, crop: string, year: number) =>
        fetcher<YieldFrontierResult>(`intelligence/yield-frontier?state=${encodeURIComponent(state)}&crop=${crop}&year=${year}`),

    getResilienceComposite: (state: string, crop: string) =>
        fetcher<ResilienceCompositeResult>(`intelligence/resilience-composite?state=${encodeURIComponent(state)}&crop=${crop}`),

    getCropCalendar: (cdk: string, crop: string, year: number) =>
        fetcher<CropCalendarResult>(`intelligence/crop-calendar?cdk=${cdk}&crop=${encodeURIComponent(crop)}&year=${year}`),
};
