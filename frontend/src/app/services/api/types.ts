export type AnalysisMode = 'before_after' | 'entity_comparison';

export interface SummaryStats {
    state: string;
    total: number;
    total_districts: number;
    changed: number;
    boundary_changes: number;
    coverage: number;
    data_coverage: string;
    comparability: string;
}

export interface StateSummary {
    states: string[];
    stats: Record<string, SummaryStats>;
}

export interface SplitDistrict {
    id: string;
    parent_name: string;
    parent_district: string;
    parent_cdk: string | null;
    split_year: number;
    children_districts: string[];
    children_names: string[];
    children_cdks: Array<string | null>;
    state: string;
    resolved_count: number;
    total_count: number;
    parent_has_agri: boolean;
    children_has_agri: boolean[];
}

export interface AnalysisSeries {
    id: string;
    label: string;
    style?: 'solid' | 'dashed' | 'dotted';
}

export type AnalysisTimelinePoint = { year: number } & Record<string, number | null>;

export interface AnalysisUncertaintyBounds {
    lower: number;
    upper: number;
    method?: string;
    confidence?: number;
}

export interface AnalysisPeriodStats {
    mean: number;
    variance: number;
    cv: number;
    cagr: number;
    n_observations: number;
}

export interface AnalysisImpactStats {
    absolute_change: number;
    pct_change: number;
    uncertainty?: AnalysisUncertaintyBounds | null;
}

export interface AnalysisFragmentationInsight {
    index: number;
    child_count: number;
    interpretation: string;
}

export interface AnalysisDivergenceInsight {
    score: number;
    interpretation: string;
    best_performer?: string | null;
    best_yield: number;
    worst_performer?: string | null;
    worst_yield: number;
    spread: number;
}

export interface AnalysisConvergenceInsight {
    trend: string;
    rate: number;
    interpretation: string;
}

export interface AnalysisEffectSizeInsight {
    cohens_d: number;
    interpretation: string;
    confidence: number;
}

export interface AnalysisCounterfactualInsight {
    projected_yield: number;
    method: string;
    actual_yield: number;
    attribution_pct: number;
    interpretation: string;
}

export interface AnalysisChildPerformanceInsight {
    cdk: string;
    name?: string | null;
    mean_yield: number;
    cv: number;
    cagr: number;
    observations: number;
    rank: number;
}

export interface SplitInsights {
    fragmentation: AnalysisFragmentationInsight;
    divergence: AnalysisDivergenceInsight;
    convergence: AnalysisConvergenceInsight;
    effect_size: AnalysisEffectSizeInsight;
    counterfactual: AnalysisCounterfactualInsight;
    children_performance: AnalysisChildPerformanceInsight[];
    warnings: string[];
}

export interface AnalysisAdvancedStats {
    pre: AnalysisPeriodStats;
    post: AnalysisPeriodStats;
    impact: AnalysisImpactStats;
    insights?: SplitInsights | null;
}

export interface AnalysisMeta {
    split_year: number;
    mode: AnalysisMode;
    metric: string;
    variable: string;
    parent_cdk: string;
    children_cdks: string[];
}

export interface AnalysisProvenance {
    dataset_version: string;
    boundary_version: string;
    query_hash: string;
    generated_at: string;
    harmonization_method?: string | null;
    warnings: string[];
}

export interface SplitImpactQueryParams {
    parent: string;
    children: string;
    splitYear: number;
    crop: string;
    metric: string;
    mode: AnalysisMode;
}

export interface AnalysisResult {
    data?: AnalysisTimelinePoint[];
    series?: AnalysisSeries[];
    advancedStats?: AnalysisAdvancedStats;
    advanced_stats?: AnalysisAdvancedStats;
    meta?: AnalysisMeta;
    provenance?: AnalysisProvenance;
    [key: string]: unknown;
}

export interface SplitImpactChildWindow {
    yields: number[];
    avg: number;
}

export interface SplitImpactBeforeWindow {
    average: number;
    years: number[];
    yields: number[];
}

export interface SplitImpactAfterWindow {
    combined_average: number;
    by_child: Record<string, SplitImpactChildWindow>;
}

export interface SplitImpactAssessment {
    absolute_change: number;
    percent_change: number;
    assessment: 'positive' | 'negative' | 'neutral' | string;
}

export interface SplitImpactResult {
    parent_cdk: string;
    child_cdks: string[];
    split_year: number;
    crop: string;
    before: SplitImpactBeforeWindow;
    after: SplitImpactAfterWindow;
    impact: SplitImpactAssessment;
}

export interface SplitSpecializationChild {
    cdk: string;
    mix: Record<string, number>;
}

export interface SplitSpecializationResult {
    split_year: number;
    crops: string[];
    parent: {
        name: string;
        cdk: string;
        pre_mix: Record<string, number>;
    };
    children: Record<string, SplitSpecializationChild>;
    divergence_scores: Record<string, number>;
}

export interface DistrictMetric {
    cdk: string;
    state: string;
    district: string;
    value: number;
    metric: string;
    method: string;
    feature_id?: string;
    geo_key?: string;
}

export interface DistrictRanking {
    rank: number;
    district: string;
    value: number;
    cdk?: string;
}

export interface RainfallData {
    annual: number;
    seasonal: {
        monsoon_jjas: number;
        pre_monsoon_mam: number;
        post_monsoon_ond: number;
        winter_jf: number;
    };
}

export interface HistoryItem {
    year: number;
    [key: string]: number;
}

export interface AnalyticsSummary {
    summary: string;
    stats: Record<string, number>;
}

export interface SimulationResult {
    result: {
        baseline_yield: number;
        slope: number;
        data_points: { year: number; rain: number; yield: number }[];
        r_squared: number;
    };
}

export interface PredictionFactor {
    name: string;
    key: string;
    importance: number;
    coefficient: number;
    contribution: number;
    direction: string;
    description: string;
}

export interface PredictionV2Data {
    predicted_yield: number;
    baseline_yield: number;
    confidence_lower: number;
    confidence_upper: number;
    slope_rain: number;
    mean_rain: number;
    r_squared: number;
    adjusted_r_squared: number;
    rmse: number;
    sample_size: number;
    feature_count: number;
    method: string;
    factors: PredictionFactor[];
    model_equation: string;
    methodology: string;
    data_quality_notes: string[];
    data_points: { rain: number; yield: number; district: string }[];
    regression_line: { x: number; y: number }[];
}

export interface PredictionV2Result {
    district: string;
    state: string;
    crop: string;
    year: number;
    prediction: PredictionV2Data;
}

export interface ForecastPoint {
    year: number;
    predicted_yield: number;
    lower_bound: number;
    upper_bound: number;
    confidence: number;
}

export interface YieldForecastResult {
    cdk: string;
    crop: string;
    historical_years: number;
    method: string;
    trend_direction: string;
    forecasts: ForecastPoint[];
    model_stats: Record<string, number | string>;
}

export interface CropRecommendation {
    crop: string;
    score: number;
    efficiency: number;
    current_yield: number;
    state_average: number;
    current_area: number;
    trend_pct: number;
    recommendation: string;
}

export interface CropRecommendationsResult {
    cdk: string;
    district: string;
    state: string;
    recommendations: CropRecommendation[];
}

export interface StateOverview {
    state: string;
    year: number;
    crop: string;
    total_districts: number;
    districts_with_data: number;
    year_range: { min: number | null; max: number | null };
    avg_yield: number;
    total_area: number;
    total_production: number;
    top_performers: { district_name: string; cdk: string; yield_value: number }[];
    bottom_performers: { district_name: string; cdk: string; yield_value: number }[];
    available_crops: string[];
}

export interface SearchResult {
    query: string;
    total: number;
    results: {
        cdk?: string;
        name: string;
        state: string;
        result_type: 'district' | 'state';
        start_year?: number;
        end_year?: number;
        district_count?: number;
    }[];
}

export interface HighRiskResult {
    high_risk_districts: {
        cdk: string;
        state: string;
        district_name: string;
        risk_score: number;
        risk_level: string;
        factors: string[];
    }[];
    total_scanned: number;
}

export interface DistrictReport {
    district?: { name: string; state: string };
    crop: string;
    statistics?: { mean_yield: number; max_yield: number; min_yield: number; cv_yield: number | null };
    state_benchmark?: { avg_yield: number; efficiency: number };
    yearly_data?: { year: number; yield?: number; area?: number; production?: number }[];
}

export interface AnomalyAnomaly {
    type: string;
    severity: string;
    description: string;
    details?: Record<string, unknown>;
}

export interface DistrictAnomaliesData {
    risk_alert?: {
        district_name: string;
        risk_level: string;
        risk_score: number;
        factors: string[];
    };
    anomalies: AnomalyAnomaly[];
}

export interface StateAnomaliesData {
    districts_scanned: number;
    total_anomalies: number;
    high_risk_count: number;
    districts: { cdk: string; district_name: string; anomaly_count: number; risk_score: number; risk_level: string }[];
}

export type AnyApiResponse = 
  | StateSummary 
  | SplitDistrict[] 
  | AnalysisResult 
  | DistrictMetric[] 
  | DistrictRanking[] 
  | RainfallData 
  | HistoryItem[] 
  | AnalyticsSummary 
  | SimulationResult 
  | PredictionV2Result 
  | YieldForecastResult
  | CropRecommendationsResult
  | StateOverview 
  | SearchResult 
  | HighRiskResult
  | DistrictReport
  | DistrictAnomaliesData
  | StateAnomaliesData;

export interface LineageCoverageItem {
    district_name: string;
    cdk: string;
    years_with_data: number;
    start_year: number;
    end_year: number;
}

export interface LineageCoverage {
    state: string;
    districts: number;
    coverage: LineageCoverageItem[];
}

export interface SplitEvent {
    state_name: string;
    split_year: number;
    parent_district: string;
    child_district: string;
    parent_cdk: string;
    child_cdk: string;
    source: string;
}

export interface ProvenanceTracking {
    district: { district_name: string; cdk: string; state: string };
    data_coverage: { years_with_data: number; total_records: number; min_year: number; max_year: number };
    lineage_events: SplitEvent[];
}
