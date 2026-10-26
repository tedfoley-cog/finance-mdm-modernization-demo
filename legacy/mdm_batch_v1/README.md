# mdm_batch_v1 (legacy)

Original 2019 batch loaders written before the PySpark pipelines existed. Still deployed as the
`ledgercore-mdm-legacy-cc-loader-*` Glue job (infra/terraform/glue.tf) because two APAC entities (JP01, AU01)
still deliver fixed-width cost center extracts that the new EBS ingest job does not parse.

Known issues:
- fixed-width slicing of the cost center code; the offsets are derived from `CC_WIDTH` (10 since MBA-3472,
  interface spec v2). JP01/AU01 must deliver the v2 layout (code fields 10 wide) before the next run
- its own copy of tax-id normalisation (`vendor_dedupe.py`) that strips every non-alphanumeric character,
  unlike the API and warehouse versions
- writes straight to the curated dimension with `INSERT OVERWRITE`, bypassing the publish log
