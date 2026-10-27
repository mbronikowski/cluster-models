# Data format

Everything the website shows comes from the files under `data/`. Edit them, open a
pull request, and the checks described at the end run automatically. Once the
pull request is merged, the site is rebuilt and published.

```
data/
  clusters/<slug>.yaml     one file per cluster
  transients/<slug>.yaml   one file per lensed transient or variable source
  programs.yaml            observing programs and model archives
  catalogues.yaml          catalogue designation formats (for checks and the index)
  references.yaml          labels/titles for references (optional)
  vocabulary.yaml          allowed values for availability, data, tags, ...
```

## Character rules

- **Names, designations, coordinates, IDs, references and URLs are plain ASCII.**
  No Unicode hyphens (U+2010), minus signs (U+2212), en dashes, non-breaking or
  thin spaces, or curly quotes. These are invisible in most editors and break
  scripts, searches and copy-paste.
- **Prose** (titles, notes, credits) may contain accented letters
  (`Rihtaršič`, `Martínez-Arrizabalaga`) and symbols such as `°` or `±`, but not
  the look-alike punctuation listed above.
- `python tools/fix_characters.py` replaces look-alike characters in place.

## File names (slugs)

A cluster file is named after the cluster's `name`: lower case, spaces become
`-`, `+` becomes `p` and a minus sign in coordinates becomes `m`. Dots are kept.

| name | file |
|---|---|
| `MACS J0416.1-2403` | `macs-j0416.1m2403.yaml` |
| `SPT-CL J0615-5746` | `spt-cl-j0615m5746.yaml` |
| `PLCK G165.7+67.0` | `plck-g165.7p67.0.yaml` |
| `Abell S1063` | `abell-s1063.yaml` |

`python tools/new_cluster.py "NAME" RA DEC Z` creates a correctly named file.
The page URL is `clusters/<slug>.html`.

## Cluster files

```yaml
name: MACS J2140.2-2339             # required: primary designation, page title
aka: [MS 2137-2353, MS 2137.3-2353] # designations shown under the title
designations:                       # further catalogue designations, one per line
  - ACT-CL J2140.2-2339
  - MCXC J2140.2-2339
ra: "21:40:15.10"                   # required, J2000, quoted, hh:mm:ss.s
dec: "-23:39:40.00"                 # required, J2000, quoted, explicit sign
z: 0.313                            # required
programs: [clash, venus]            # ids from data/programs.yaml

image:                              # optional
  url: https://...
  credit: Credit line (Markdown).

links:                              # optional cluster-level links
  - label: ...
    url: https://...

models: [...]                       # see below
observations: [...]                 # optional, see below
notes: |-                           # optional Markdown
  Free text about the cluster.

ignore_position_check: [SDSS J1226+2149]   # rarely needed, explain in notes
```

Nicknames that are not catalogue designations go in `common_names`, e.g.
`common_names: [Bullet Cluster]` in `1e-0657m56.yaml`. They are searchable and
shown under the title, but not checked against `data/catalogues.yaml`.

**Coordinates must be quoted.** Unquoted `00:14:21.16` is read by YAML 1.1
parsers as a base-60 *number* (861.16). The check rejects unquoted values and
declinations without a sign.

The position is the centre of the strong-lensing region: normally the BCG, or for
a merging cluster the centre used by the lens-model papers. Old catalogue
positions (for example NED's positions of Abell clusters) can be several
arcminutes off.

Every name in `name`, `aka` and `designations` must match a format in
`data/catalogues.yaml`. If a designation encodes a position (J2000 or B1950
digits, Galactic or decimal degrees), it must agree with `ra`/`dec` within that
catalogue's tolerance. This catches sign errors and designations attached to the
wrong cluster. Add a new catalogue to `data/catalogues.yaml` when needed, with an
`example` the check can test.

### Models

```yaml
models:
  - title: Bergamini et al. (2023)   # required; also the #anchor on the page
    program: glass-jwst               # optional program id (must also be in `programs`)
    refs: [2023ApJ...952...84B]       # ADS/SciX bibcode, arXiv:NNNN.NNNNN or doi:10....
    data: [JWST, HST, MUSE]           # facilities, from vocabulary.yaml
    software: Lenstool                # optional, from vocabulary.yaml
    availability: public              # public | on-request | upcoming | defunct | unavailable | unknown
    status: superseded                # optional; default current
    superseded_by: 2023ApJ...952...84B   # optional: a reference or title on the same page
    tags: [parametric]                # optional, from vocabulary.yaml
    links:                            # download links, shown as buttons
      - label: Model download
        url: https://...
    note: |-                          # optional Markdown
      Short comment, e.g. "updated with JWST data" or "experimental method".
```

Order the list as you want it shown (the site keeps the file order).

The page already shows the title, the paper, availability, data, software and tags, so
the note should only say what is specific to the model (what it is fitted to, which model
it revises, caveats such as "pre-JWST" or "superseded"). Don't open with "X created a
lens model of the cluster", and put download pages in `links` rather than in the note,
labelled "Model download" (or e.g. "Model download (Zenodo)"); a general page worth
visiting goes in `links` too, labelled "See also: ...". Leave out "shared on request"
when `availability: on-request` already says it.

References are written as ADS/SciX bibcodes, `arXiv:` identifiers or `doi:`
identifiers, never as URLs, so links can follow ADS/SciX changes in one place.
`data/references.yaml` can give a nicer label (`Bergamini et al. (2023)`) and the
title; references without an entry are shown by their identifier.

### Links inside Markdown

| write | links to |
|---|---|
| `[Bergamini et al. (2023)](ref:2023ApJ...952...84B)` | the paper (SciX, arXiv or DOI) |
| `[MACS J0416](cluster:macs-j0416.1m2403)` | another cluster page |
| `[HFF](program:hff)` | a program page |
| `[SN Refsdal](transient:sn-refsdal)` | a transient page |
| `[CLASH model](#clash-zitrin-et-al-2015)` | a model on the same page |

### Observations (optional)

```yaml
observations:
  - facility: JWST               # from vocabulary.yaml (facility)
    instrument: NIRCam
    mode: imaging                # imaging, MOS, IFU, slitless, ...
    filters: [F090W, F115W, F150W, F200W, F277W, F356W, F410M, F444W]
    program: venus               # optional id from programs.yaml
    proposal: JWST GO 6882
    note: optional
```

## Transient files

```yaml
name: SN Refsdal               # required; file name is its slug
aliases: []
class: supernova               # supernova | agn | star | other
subclass: II                   # free text, optional (e.g. Ia, IIP, CCSN)
status: confirmed              # confirmed | candidate
images: multiple               # multiple (default) | single: magnified but not multiply imaged
cluster: macs-j1149.5p2223     # required: the lensing cluster's slug
ra: "11:49:35.5"               # optional
dec: "+22:23:44.0"             # optional
z: 1.49                        # optional
discovered: 2014               # optional year
refs: [2015Sci...347.1123K]    # discovery paper first
links:                         # e.g. DDT programs
  - label: HST DDT 14199
    url: https://...
notes: |-
  Markdown.
```

Only transients lensed by a cluster (or group) in the catalogue belong here; sources lensed by
single galaxies are out of scope. The lensing cluster's page lists its transients automatically. Sources with `images: single`
are listed separately on the transients page and marked with a dashed tag on the cluster list.

## Programs (`data/programs.yaml`)

```yaml
- id: hff                      # used in cluster files
  name: Hubble Frontier Fields
  short: HFF                   # badge text
  kind: survey                 # survey | database | other
  facilities: [HST]
  url: https://...             # landing page
  archive: https://...         # optional data archive
  overview: 2017ApJ...837...97L   # optional overview paper
  links: [{label: ..., url: ...}]
  note: optional Markdown
```

Cluster pages link to program pages instead of repeating each program's links.

## Checks

`python validate.py` runs everything below; GitHub runs it on every pull request
and before every deployment.

- YAML syntax, required fields and types (JSON Schemas in `schema/`)
- the character rules above
- coordinate format and range, explicit declination sign
- file name matches the slug of `name`
- every designation matches a catalogue format and agrees with the position
- the same designation is not used by two clusters
- program, transient, cluster and anchor links resolve
- vocabulary values are known

Other tools in `tools/`:

| tool | what it does |
|---|---|
| `new_cluster.py` | creates a correctly named cluster file |
| `fix_characters.py` | replaces look-alike characters in place |
| `check_links.py` | polite link check (only new links on pull requests; `--all` by hand) |
| `check_preprints.py` | lists arXiv references that have since been published |
| `check_names_online.py` | cross-checks names against SIMBAD/NED (one request per second) |
| `wiki_moved_stubs.py` | replaces the old wiki pages with "moved" notices |

## Building the site locally

```
pip install -r requirements.txt
python validate.py
python build.py
python -m http.server -d _site 8000     # open http://localhost:8000
```
