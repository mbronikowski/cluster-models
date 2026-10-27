# Contributing

Thank you for helping keep the catalogue accurate.

- **Small fixes and new models:** use *Edit this entry on GitHub* on the cluster's
  page, or edit `data/clusters/<slug>.yaml` directly, and open a pull request.
- **New cluster:** `python tools/new_cluster.py "NAME" RA DEC Z` creates the file
  with the right name; then add designations and models.
- **Not sure how to write it?** Open an issue with the reference (SciX/ADS link or
  arXiv number), the cluster and the model download link.

The field reference is in [docs/data-format.md](docs/data-format.md). Pull
requests are checked automatically (`python validate.py`), including the
character rules: names and designations must be plain ASCII, without Unicode
hyphens or minus signs.

Please cite model authors' papers rather than this catalogue alone when you use
their models.
