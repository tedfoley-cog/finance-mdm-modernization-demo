# mdm_batch_v1 (legacy)

Original 2019 batch loaders written before the PySpark pipelines existed. Still deployed as the
`ledgercore-mdm-legacy-cc-loader-*` Glue job (infra/terraform/glue.tf) because two APAC entities (JP01, AU01)
still deliver fixed-width cost center extracts that the new EBS ingest job does not parse.

Known issues:
- hard-coded 6-character slicing of the cost center code
- its own copy of tax-id normalisation (`vendor_dedupe.py`) that strips every non-alphanumeric character,
  unlike the API and warehouse versions
- writes straight to the curated dimension with `INSERT OVERWRITE`, bypassing the publish log
