# cluster-models

A curated database of published strong-lensing models of galaxy clusters: who
modelled each cluster, with which data, whether the model can be downloaded and
from where, which programs observed it, and which lensed transients were found
behind it.

**Website: https://mbronikowski.github.io/cluster-models/**

The website is generated from the files in [`data/`](data/). Everything shown
there, the search and sky map included, comes from one YAML file per cluster.

## Contributing

Each cluster page has an *Edit this entry on GitHub* link. Edit the YAML, propose
the change, and the checks run automatically. The field reference is in
[docs/data-format.md](docs/data-format.md). A minimal model entry:

```yaml
models:
  - title: Bergamini et al. (2023)
    refs: [2023ApJ...952...84B]
    data: [JWST]
    availability: public
    links:
      - label: Model download
        url: https://www.fe.infn.it/astro/lensing/A2744_Bergamini23/
```

You can also [open an issue](https://github.com/mbronikowski/cluster-models/issues/new).

## Machine-readable data

Published with the site under `data/`: `clusters.csv`, `clusters.ecsv`
(astropy), `models.csv`, `catalogue.json` (everything), and one JSON/YAML file per
cluster. See the website's About page for examples.

## Repository layout

| path | contents |
|---|---|
| `data/` | the catalogue (YAML) |
| `schema/` | JSON Schemas for the data files |
| `cmdb/` | shared Python code: loading, checks, catalogue registry, site rendering |
| `templates/`, `static/` | website templates, styles and scripts |
| `validate.py`, `build.py` | check the data; build the site into `_site/` |
| `tools/` | helpers (new cluster, link and name checks, character fixes) |
| `tools/migration/` | the one-off conversion from the old GitHub wiki, kept for provenance |
| `docs/` | data format and the migration report |

```
pip install -r requirements.txt
python validate.py && python build.py
python -m http.server -d _site 8000
```

## Licence and citation

Data (`data/`): [CC BY 4.0](LICENSE-DATA). Code: [MIT](LICENSE). If the catalogue
helps your work, cite the original papers of the models you use and this
repository (see [CITATION.cff](CITATION.cff)).

The previous GitHub wiki has been converted into this format; see
[docs/migration-2026-10.md](docs/migration-2026-10.md).
