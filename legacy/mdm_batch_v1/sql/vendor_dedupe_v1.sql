-- v1 duplicate report (2019). Replaced by CONSUMPTION.VW_VENDOR_DUPLICATE_CANDIDATES but still referenced by
-- the Finance Ops runbook. Note the different normalisation from UTIL.FN_NORMALIZE_TAX_ID.
SELECT UPPER(REGEXP_REPLACE(TAX_ID, '[^A-Za-z0-9]', '')) AS TAX_KEY,
       COUNT(*) AS N,
       LISTAGG(VENDOR_ID, ',') AS VENDOR_IDS
FROM FDP_MDM.LANDING.VENDOR_RAW
GROUP BY 1
HAVING COUNT(*) > 1;
