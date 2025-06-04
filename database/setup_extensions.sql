-- Sarah AI Database Extensions Setup

-- Create extensions (run as superuser)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

-- Verify extensions
SELECT extname, extversion FROM pg_extension 
WHERE extname IN ('uuid-ossp', 'vector', 'timescaledb')
ORDER BY extname;