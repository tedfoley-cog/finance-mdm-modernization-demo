-- Finance Data Platform landing + curated schemas for MDM golden records.
-- Deployed by infra/terraform (snowflake provider is managed by the platform team; we ship DDL only).
CREATE DATABASE IF NOT EXISTS FDP_MDM;
CREATE SCHEMA IF NOT EXISTS FDP_MDM.LANDING;
CREATE SCHEMA IF NOT EXISTS FDP_MDM.CURATED;
CREATE SCHEMA IF NOT EXISTS FDP_MDM.CONSUMPTION;
CREATE SCHEMA IF NOT EXISTS FDP_MDM.UTIL;
