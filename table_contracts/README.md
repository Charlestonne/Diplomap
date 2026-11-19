# Table contracts

One YAML file per table or view of the warehouse: grain, columns, keys and business rules. A contract changed after its
validation goes through a PR reviewed by its producer and its consumer.

This file holds the decisions and the key numbers the contracts rely on, one section per owner.

## GDELT (P2)

Measured on the spike week (17–23 Dec 2024, 672 files) with `warehouse/profiling/gdelt_profiling.ipynb`; section numbers
in brackets. The rules built on them, with their options and effect on volume, are in
`warehouse/profiling/gdelt_rules.md` and applied by `warehouse/staging/gdelt.sql`.

| Measure | Value | Section |
| --- | ---: | --- |
| Raw events | 813,679 | first cell |
| Unreadable lines | 0 | load metrics |
| Exact duplicate `GlobalEventID` | 0 | [6] |
| Both actor country codes present | 25.2 % | [2] |
| At least one actor country missing | 74.8 % | [2] |
| … of which the actor geography could fill it (upper bound) | 51.1 % of all events | [2] |
| International organisations facing a country | 0.5 % | [2b] |
| Country codes missing from `DB/CAMEO.country.txt` | 1 (`SSD`, 629 mentions) | [2c] |
| Event reported the same day (`Day` = `DATEADDED` date) | 97.8 % | [3] |
| Event reported within 30 days | 99.2 % | [3] |
| Root events (`IsRootEvent = 1`) | 57.1 % | [4] |
| `NumMentions` median / 90th percentile | 4 / 10 | [5] |
| `NumSources` 90th percentile | 1 | [5] |
| Distinct country pairs; share of the top 100 | 4,193; 49.4 % | [7] |
| **Events after the four rules (`stg_gdelt_event`)** | **68,987 (8.5 %)** | [9] |

The unresolved country codes are listed for P3 in `warehouse/profiling/unresolved_country_codes.csv`.
