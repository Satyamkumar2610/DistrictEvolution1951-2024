-- Add new climate features to the rainfall_normals table
-- to support expanded ML yield predictions.

ALTER TABLE rainfall_normals 
ADD COLUMN IF NOT EXISTS temperature_c NUMERIC(5,2),
ADD COLUMN IF NOT EXISTS soil_moisture_index NUMERIC(5,2);

-- Commenting the columns for visibility
COMMENT ON COLUMN rainfall_normals.temperature_c IS 'Annual average temperature in Celsius (derived/proxy)';
COMMENT ON COLUMN rainfall_normals.soil_moisture_index IS 'Normalized soil moisture index (0-100)';
