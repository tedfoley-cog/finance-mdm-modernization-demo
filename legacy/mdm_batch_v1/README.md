# mdm_batch_v1 (legacy)

Original 2019 batch loaders written before the PySpark pipelines existed. Still deployed as the
`ledgercore-mdm-legacy-cc-loader-*` Glue job (infra/terraform/glue.tf) because two APAC entities (JP01, AU01)
still deliver fixed-width cost center extracts that the new EBS ingest job does not parse.

Known issues:
- hard-coded 6-character slicing of the cost center code
- ~~its own copy of tax-id normalisation~~ retired in MBA-3473 (TD-01): `vendor_dedupe.py` and
  `sql/vendor_dedupe_v1.sql` are deleted and no longer shipped with the Glue job (`--extra-py-files` removed).
  The Finance Ops duplicate report should use `FDP_MDM.CONSUMPTION.VW_VENDOR_DUPLICATE_CANDIDATES`.
- writes straight to the curated dimension with `INSERT OVERWRITE`, bypassing the publish log
