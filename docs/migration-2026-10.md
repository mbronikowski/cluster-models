# Wiki migration report (October 2026)

In October 2026 the [GitHub wiki](https://github.com/mbronikowski/cluster-models/wiki) was
converted into the data files in [`data/`](../data/). This report explains what changed on
the way: how the content was restructured, which values were corrected and on what
evidence, and what was checked but left alone. Every individual change is recorded in
[`tools/migration/migration-log.json`](../tools/migration/migration-log.json).

## Summary

| | Wiki | Now |
|---|---|---|
| Clusters | 167 pages and the Home table | 167 files in `data/clusters/` |
| Lens models | sections on the cluster pages | 322 model entries |
| Lensed transients | notes on 16 cluster pages | 17 files in `data/transients/` |
| Programs | the Program list page (11 programs) | 18 entries in `data/programs.yaml` |
| References | ADS, arXiv and DOI links in the text | 162 entries in `data/references.yaml` |
| Names | Home table and page headers | 519 names from 59 catalogues |

Corrections: 10 positions, 15 redshifts, 14 designations, one model moved to another
entry, and four typos. They are listed below with the evidence.

## Reproducing the conversion

```
git clone https://github.com/mbronikowski/cluster-models.wiki.git /tmp/wiki
python tools/migration/migrate_wiki.py /tmp/wiki
```

The conversion used wiki commit `67d51e2` (10 September 2026), the latest at the time.
The script rewrites `data/clusters/`, `data/transients/`, `data/programs.yaml`,
`data/references.yaml` and the log. Every hand-made decision is a table at the top of the
script, so a rerun gives the same files. It runs offline: reference titles from SIMBAD,
arXiv metadata and the VENUS target list are cached next to it.

From now on the YAML files are the source. Edit them directly; rerunning the script would
overwrite those edits.

## How the content was restructured

**Programs.** 350 sentences repeated a program's description on every cluster page of that
program (RELICS, SGAS, CLASH, LoCuSS, the MUSE releases, CANUCS, HFF). They were dropped,
and each cluster links to its program page instead. Download links specific to a cluster,
such as its MAST model directory, were kept as buttons on the model.

**Model titles.** 109 section titles were shortened or made consistent, for example
`Reionization Lensing Cluster Survey (RELICS)` became `RELICS` and `Zitrin 2017` became
`Zitrin (2017)`. A program section that describes one paper is titled like
`CLASH: Zitrin et al. (2015)`. Fourteen sections that mixed a program and a paper were
rewritten by hand (`manual-section` in the log). Titles are also the anchors on the page,
and links between sections were updated to match.

**Model fields read from the text.** These are best guesses from the wiki's wording and are
worth a skim:

- `data` (JWST, HST, MUSE, ...) comes from words in the section and from the program; every
  RELICS model has HST, for example. Six models were flagged JWST from their paper titles:
  Cho et al. (2025), Diego et al. (2025) on Abell 370, Suyu et al. (2025), Mahler et al.
  (2023), Frye et al. (2024) and Finner et al. (2025).
- `availability` is `upcoming` for SLICE and for "will be released", `unavailable` for "not
  available", `defunct` for a dead link without a replacement, `on-request` for "upon
  request", and `public` when there is a download link or the text says so. Everything else
  is `unknown` (118 models).
- `status: superseded` where the text says a model was superseded (3 models). `software`
  and `tags` come from keywords.

**Lensed transients.** The 16 cluster notes about multiply imaged supernovae and quasars
became 17 transient entries, because MACS J0138.0-2155 hosts two supernovae: 8 supernovae
(one a candidate) and 9 quasars or AGN (one a candidate). Each cluster page lists its
transients automatically. The entries have no DDT or program links yet, because the wiki
had none.

**Program membership.** Memberships were completed from official target lists: VENUS (the
fixed targets of JWST GO 6882) for 57 more clusters, BUFFALO for the five Frontier Fields
clusters that lacked it, and SLICE for SPT-CL J0546-5345.

**Names.** The Home table's and the page's alternate names were merged. Names in bold on the
wiki became `aka` (shown under the title), the rest `designations`. Four well-known
nicknames were added as `common_names`: Pandora's Cluster (Abell 2744), Toothbrush Cluster
(1RXS J060313.4+421231), Carousel Lens (ACT-CL J0603.9-3557) and Baby Bullet
(MACS J0025.4-1222). Two page names gained a missing space, `MS 1008.1-1224` and
`eMACS J1341.9-2442`; [`tools/wiki_moved_stubs.py`](../tools/wiki_moved_stubs.py) maps their
old wiki pages.

**Links.** ADS links became bibcodes (`ref:2023ApJ...952...84B`), so the site can send them
to ADS or SciX from one place. The NED and SIMBAD links by name were replaced by coordinate
searches built from the position, which also avoids NED's handling of `+` in names.

**Characters.** Unicode hyphens (U+2010) in 61 wiki file names and 8 cluster names, a minus
sign (U+2212) in Abell S1063's RXC designation, non-breaking hyphens (U+2011) in two SPT
model sections and a thin space (U+2009) on SDSS J0909+4449 were replaced by plain ASCII.

**Images.** Wikimedia now rejects non-standard thumbnail widths (HTTP 400), so the four
cluster images (Abell 370, Abell 2744, MACS J0416.1-2403, SMACS J0723.3-7327) use the
standard 960 px thumbnails.

## Corrections

Every position, redshift and name was cross-checked against SIMBAD through CDS Sesame
(`tools/check_names_online.py`, one request per second). Where the wiki and SIMBAD
disagreed, the value was looked up in the lens-model papers on the page or in other
published measurements, and corrected when the literature was clear.

### Positions

Most of the old positions match NED's positions for one of the cluster's catalogue names:
old catalogue positions, which can be arcminutes from the cluster core. The new position
is the centre of the strong-lensing region, normally the BCG.

| Cluster | Wiki | Now | Shift | New position |
|---|---|---|---|---|
| ACT-CL J0327.4-1326 | Dec 13:26:23.65 | Dec -13:26:23.65 | sign | the sign was missing on the Home table and the page; both designations and SIMBAD place the cluster at -13 deg |
| Abell 267 | 01:52:52.20 +01:02:46.00 | 01:52:42.0 +01:00:25.5 | 3.5' | BCG (redMaPPer RM J015242.0+010025.5; WHL agrees) |
| Abell 963 | 10:17:13.90 +39:01:31.00 | 10:17:03.6 +39:02:49.4 | 2.4' | BCG (redMaPPer; WHL 2012 and SIMBAD agree). The old position was the WHL 2009 centre, on another galaxy |
| Abell 1423 | 11:57:22.50 +33:39:18.00 | 11:57:17.26 +33:36:37.4 | 2.9' | BCG from the CLASH overview (Postman et al. 2012) |
| Abell 1489 | 12:12:32.04 +27:29:19.1 | 12:12:18.48 +27:32:55.1 | 4.7' | RM J121218.5+273255.1, the lens modelled by Zitrin et al. (2020) |
| Abell 1758a | 13:32:32.10 +50:30:37.0 | 13:32:44.80 +50:32:24.0 | 2.7' | X-ray centre of Abell 1758N (MCXC J1332.7+5032), between the two BCGs that RELICS observed. The old position is that of the whole Abell 1758 complex |
| Abell 2163 | 16:15:34.13 -06:07:26.3 | 16:15:48.95 -06:08:41.4 | 3.9' | BCG of the A2163-A1 core, the centre of the Rescigno et al. (2020) model. The old position was outside both RELICS pointings |
| MACS J2135.2-0102 | 21:35:00.00 -01:02:17.00 | 21:35:12.2 -01:02:55.8 | 3.1' | BCG (redMaPPer; WHL agrees), where Zitrin & Broadhurst (2016) find the multiple images. The old position is the Planck SZ position |
| RXC J0032.1+1808 | 00:32:04.81 +18:09:03.5 | 00:32:11.0 +18:07:49.0 | 1.9' | the centre used by RELICS and by Acebron et al. (2020) for this bimodal cluster |
| SDSS J1723+3411 | Home 17:23:36 +34:11:59.37 | 17:23:36.50 +34:11:55.90 | 7'' | the page's value; the Home table's RA was truncated and NED is closer to the page |

### Redshifts

A cluster's redshift here is a reference value, mostly taken from NED; each model's paper
gives the one it used. Only differences larger than 0.01 were looked into.

| Cluster | Wiki | Now | Evidence |
|---|---|---|---|
| Abell 68 | 0.268 | 0.255 | SLICE (Cerny et al. 2025) 0.2546; SIMBAD 0.249 |
| Abell 267 | 0.0596 | 0.230 | Smith et al. (2005), the model on the page; SIMBAD 0.2297 |
| Abell 1489 | 0.280 | 0.351 | Zitrin et al. (2020) 0.35; SIMBAD 0.3506 |
| Abell S1063 | 0.37 | 0.348 | CLASH overview (Postman et al. 2012); Caminha et al. (2016) |
| ACT-CL J0327.4-1326 | 0.560 (Home), 0.564 (page) | 0.564 | SLICE 0.564 |
| MACS J0451.9+0006 | 0.434 (Home), 0.430 (page) | 0.430 | SIMBAD 0.430 |
| MACS J0553.4-3342 | 0.43 | 0.427 | 0.4270 from spectroscopy, Ebeling, Qi & Richard (2017); RELICS lists 0.430, SLICE 0.412 |
| MACS J0744.8+3927 | 0.675 | 0.698 | Zitrin et al. (2011); SIMBAD 0.697 (spectroscopic). The CLASH overview lists 0.686 |
| MACS J0940.9+0744 | 0.348 | 0.335 | MUSE atlas (Richard et al. 2021), the model on the page; SIMBAD 0.3372 |
| MACS J1532.8+3021 | 0.345 | 0.362 | the BCG's SDSS spectrum, 0.36205; SIMBAD 0.3615. The wiki's 0.345 is the value in the CLASH overview |
| MACS J2129.4-0741 | 0.57 | 0.589 | Zitrin et al. (2011), Jauzac et al. (2021) and SLICE; SIMBAD 0.587-0.588. The wiki's 0.570 is the CLASH overview value |
| MACS J2211.7-0349 | 0.426 | 0.397 | SLICE 0.397; SIMBAD 0.396 |
| PLCK G004.5-19.5 | 0.519 | 0.516 | Sifón et al. (2014): 0.516 ± 0.002 from six members. 0.519 is close to the BCG's 0.5199 |
| RXC J0032.1+1808 | 0.374 | 0.396 | Acebron et al. (2020), the model on the page, 0.3956; RELICS 0.396 |
| SMACS J2332.4-5358 | 0.415 | 0.402 | SPT spectroscopy (Ruel et al. 2014; Bleem et al. 2015) |

Five SDSS clusters (J0150+2725, J1156+1911, J1336-0331, J1439+1208, J1723+3411) had a
rounded redshift on the Home table; the page's more precise value was kept.

### Designations

| Cluster | Change | Reason |
|---|---|---|
| Abell 773 | `PLCKESZ G166.13+43.39e` to `PLCKESZ G166.13+43.39` | stray trailing letter |
| SMACS J2332.4-5358 | `PSZ2 G325.99-59.4` to `PSZ2 G325.99-59.48` | truncated latitude |
| ZwCl 0847.2+3617 | `PLANCK 0631` to `PSZ1 0631` | `PLANCK 0631` resolves nowhere; NED resolves `PSZ1 0631` to this cluster |
| Abell 963 | `WHL J101713.9+390131` to `WHL J101703.6+390249` | the WHL 2009 entry is centred on another galaxy; the WHL 2012 entry for the same cluster is on the BCG |
| MS 1008.1-1224 | `MS1008.1-1224` to `MS 1008.1-1224` | missing space (page renamed) |
| eMACS J1341.9-2442 | `eMACSJ1341.9-2442` to `eMACS J1341.9-2442` | missing space (page renamed) |
| MACS J0717.5+3745 | removed `PLCKESZ G056.80+36.30` | it encodes the position of Abell 2244, 102 deg away; NED attaches it to MACS J0717 by mistake |
| Abell 267 | removed `ZwCl 0151.5+0052` | a separate NED object 18' away |
| Abell 267 | removed `SDSS CE J028.239771+01.055582` | centred 4.9' from the BCG; SIMBAD does not cross-identify it with Abell 267 |
| MACS J1322.8+3138 | removed `GHO132029+3155` | malformed duplicate of `GHO 1320+3155` |
| ACT-CL J0327.4-1326 | removed `RCS2 032727-132623` | duplicate of `RCS2 J032727-132623` |
| Abell 1423 | removed `ACO 1423` | the same catalogue entry as the name (see "Abell and ACO" below) |
| Abell 1758a | added `MCXC J1332.7+5032` | the source of the corrected position |
| MACS J0358.8-2955 | `RXC J0358.8-2955` moved here from Abell 3192 | the X-ray cluster is MACS J0358.8-2955 (MCXC J0358.9-2955, z = 0.425) |

The Home table and the page listed different alternate names for RXC J0018.5+1626 and
SDSS J2222+2745; both lists were merged. MACS J1354.6+7715's page was titled
PSZ2 G118.46+39.32; the Home table's name was used.

### Abell 3192 and MACS J0358.8-2955

The two clusters overlap on the sky, 2.5' apart: Abell 3192 at z = 0.168 lies in front of
the more massive MACS J0358.8-2955 at z = 0.425. RELICS observed the field under the name
Abell 3192, but its pointing and lens model are centred on MACS J0358.8-2955 (Coe et al.
2019, Table 1, note e). The RELICS model therefore moved from the Abell 3192 entry to
MACS J0358.8-2955, which already listed the SLICE and Hsu et al. (2013) models. Abell 3192
keeps its entry, without models and with a note pointing to MACS J0358.8-2955. SIMBAD
merges the two clusters into one object, which is why it reports z = 0.425 for Abell 3192.

### Text

`Lagatutta` to `Lagattuta` and `Bonamago` to `Bonamigo` (author names); `Wenlei et al.
(2022)` to `Chen et al. (2022)` (Wenlei is the first author's given name); and `solution
for Abell 1869` to `Abell 1689` on the Abell 1689 page.

## Checked and left as in the wiki

**Redshifts.**

- Abell 1703 (0.282): the lens-model papers use 0.28 (e.g. Limousin et al. 2008). SIMBAD's
  adopted 0.2586 (Allen et al. 1992) is the outlier among its measurements, which otherwise
  lie at 0.283-0.284.
- SPT-CL J0304-5404 (0.794): this is ACT DR5's 0.7947. The SPT catalogues give 0.73-0.81,
  all photometric; no spectroscopic redshift turned up.
- XLSSC 122 (1.98): spectroscopic, as used by Finner et al. (2025). SIMBAD's 1.99 comes from
  the XXL catalogue.
- MACS J0358.8-2955 (0.425): SLICE and the MCXC use 0.425; Hsu et al. (2013) measured 0.428.

**Positions 1-2' from the BCG.** Abell 1835 and Abell 773 were left at first; they were
moved after launch (see "Follow-up corrections" below).

**Names that SIMBAD, NED and VizieR do not resolve (48).** 33 are SGAS names such as
`SDSS J0004-0103`, which name lens systems rather than catalogue entries. The rest are
informal or historical names (`MS 2137-2353`, `CL 1358+62`, `MS 1512+36`,
`RX J2129.4+0009`, `RXS J060313.4+4212`, `COOL J0335-1927`, ...). They stay, because they are
the names used in the papers.

**SIMBAD names not added.** SIMBAD lists `ACO 1758A` and `ACO 1758N` for Abell 1758a,
`AC 114 Northern` for Abell S1077 and `Vidal 14` for SPT-CL J0049-2440.

**One distant resolution.** `NSCS J121229+273051`, an optical detection of Abell 1489,
resolves 4.7' from the corrected Abell 1489 position. It is kept: optical detections can
be offset by that much.

**Abell and ACO.** Abell, Corwin & Olowin (1989) kept Abell's numbering, so `ACO 1423` and
`Abell 1423` are the same cluster, and the search treats them as one name. The southern
supplementary list (`Abell S1063`, `ACO S 1063`) is numbered separately.

## Preprints that have since been published

`tools/check_preprints.py` lists arXiv references that now have a journal reference. At the
migration these six were still cited by their arXiv identifier; they were switched to the
journal versions after launch (see "Follow-up corrections" below):

| Reference | Published |
|---|---|
| Cerny et al. (2025), SLICE, `2025arXiv250317498C` | ApJ 1001, 60 (2026) |
| Diego et al. (2025), `2025arXiv250611207D` | A&A 703, A207 (2025) |
| Limousin et al. (2025), `2025arXiv250616034L` | A&A 703, A10 (2025) |
| Allingham et al. (2025), `2025arXiv250708949A` | ApJL 990, 1 (2025) |
| Suyu et al. (2025), `arXiv:2509.12319` | A&A 708, A291 (2026) |
| Mistele & Durakovic (2024), `2024arXiv240807026M` | The Open Journal of Astrophysics, doi:10.33232/001c.127612 |

## Follow-up corrections (16 October 2026)

A second cross-check after launch compared every position with the cluster centres in the
CLASH overview (Postman et al. 2012), the MUSE lensing atlas (Richard et al. 2021), the
SLICE lens models (Cerny et al. 2026) and the RELICS overview (Coe et al. 2019), and with
the BCG-based catalogues (redMaPPer, WHL) that SIMBAD cross-identifies.

**Positions moved to the BCG or the strong-lensing core.**

| Cluster | Was | Now | Shift | Source |
|---|---|---|---|---|
| Abell 1835 | 14:01:02.28 +02:53:48.4 | 14:01:02.07 +02:52:43.2 | 1.1' | BCG (SIMBAD; WHL J140102.1+025242) |
| Abell 773 | 09:17:59.40 +51:42:23.00 | 09:17:53.4 +51:43:37.5 | 1.6' | BCG (redMaPPer, WHL); the old value was NED's position for ZwCl 0914.5+5156 |
| SMACS J2031.8-4036 | 20:31:47.84 -40:36:54.76 | 20:31:53.26 -40:37:30.8 | 1.2' | BCG, the reference position of the MUSE-atlas and SLICE models |
| MACS J0138.0-2155 | 01:38:00.0 -21:55:00 | 01:38:03.77 -21:55:31.7 | 1.0' | BCG (Ertl et al. 2025); the old value was the catalogue name written out |
| Abell 611 | 08:00:58.68 +36:02:48.80 | 08:00:56.83 +36:03:24.1 | 0.7' | CLASH centre; redMaPPer and WHL agree |
| MACS J1347.5-1144 | 13:47:32.00 -11:45:42.0 | 13:47:30.59 -11:45:10.1 | 0.6' | CLASH centre; the MUSE atlas agrees within 1'' |
| MACS J1931.8-2635 | 19:31:48.00 -26:35:00.00 | 19:31:49.66 -26:34:34.0 | 0.6' | CLASH centre; SIMBAD agrees |
| RXC J0600.1-2007 | 06:00:16.97 -20:06:16.1 | 06:00:08.17 -20:08:08.85 | 2.8' | the southern core studied by RELICS and ALCS, at the "South BCG" of Furtak et al. (2024); the old position was in the north-eastern structure they found (explained on the page) |

eMACS J1341.9-2442 moved 1.4' to its BCG (13:42:00.2 -24:42:01, Zalesky & Ebeling 2020),
found while adding the eMACS clusters; its old position came from its catalogue name.

Left alone: 1E 0657-56, RX J0152.7-1357 and the Frontier Fields clusters, whose positions
lie between sub-clusters or at the centre used by the lens models.

**References.** Nine preprints were replaced by their journal versions: the six above, and
Price et al. (2025, `2025ApJ...982...51P`), Smith et al. (2025, `2025ApJ...991..142S`) and
Cho et al. (2026, `2026ApJ..1005...28C`). Labels follow the publication year, so
`Cerny et al. (2025)` is now `Cerny et al. (2026)`, as are Suyu, Cho and (2024 to 2025)
Price, and the model titles and page anchors changed with them. Mistele & Durakovic (2024)
has no ADS bibcode in SIMBAD yet and is cited by its DOI.

**Other changes.** The Zitrin et al. (2020) model of Abell 1489 is now `defunct`: its
download page has been offline since 2024 and the model files were not archived; the same
release's images and catalogues are still online and linked. Abell 1758a gained the common
name Abell 1758N, and RXC J0600.1-2007 the nickname Anglerfish Cluster (Furtak et al. 2024).

**Checked, nothing to change.** Model titles agree with their reference labels; the
remaining redshift differences with SIMBAD are those discussed above; seven RELICS clusters
(Abell 520, Abell 665, Abell 1300, PLCK G138.61-10.84, PLCK G308.3-20.2, RXC J1514.9-1523,
SPT-CL J0254-5857) are absent because RELICS published no lens models for them.

**Later fixes (16 October 2026).** SN 2022riv was attached to MACS J2129.4-0741; it is
behind RX J2129.7+0005 (Dhanasingham et al. 2026) and moved there. The Abell S1077 (AC 114)
model listed in the LAM atlas as Limousin et al. (2025), whose paper was not yet out, is
now Limousin et al. (2026, A&A 711, A143). Pierel et al. (2025) is now its journal version,
Pierel et al. (2026, `2026ApJ...998..219P`). ALCS membership now covers all 33 clusters in
Table 1 of Fujimoto et al. (2024), not only RXC J0600.1-2007.

**Labels (16 October 2026).** Where two references shared a label they now carry a/b/c
suffixes (e.g. `Zitrin et al. (2011a)`), and model titles and anchors changed with them.
The lensed-AGN entries were renamed from "... quasar" to "... AGN", so their pages moved
(e.g. `transients/sdss-j1004p4112-agn.html`).

**MUSE release and RELICS (16 October 2026).** Both were checked against their sources.
The MUSE release page lists 19 clusters; the Abell S1063 model there had been credited to
Richard et al. (2021), but that atlas does not include the cluster, and Thai et al. (2023)
credit the model to Beauchesne et al. (2024). MACS J0600.1-2008 (RXC J0600.1-2007) was
missing from the release membership; its model directory is empty. The RELICS entries were
compared with the MAST lens-model README and directories: the El Gordo entry cited Diego et
al. (2020), a separate WSLAP+ model, instead of Cerny et al. (2018), and the two are now
separate entries. Every RELICS entry now says which codes MAST provides models for, and the
WHL 0137 models cite Welch et al. (2022), where they are described.

## Open items

- **Availability.** 118 models are `unknown`, because the wiki only says "the cluster was
  modelled by ...". Filling these in is the most useful clean-up.
- **Links.** The first full link check (October 2026) found one dead model link (Abell 1489,
  now marked `defunct`). The GLASS-JWST website's TLS
  certificate has expired, and the glafic page at SLAC fails certificate checks in
  scripts. The LAM Strong Lensing Cluster Atlas and the Lenstool wiki refuse automated
  requests, so the checker cannot confirm them. The two FTP links (Abell 1722,
  MACS J2135.2-0102) are not checked, and the wiki already called them defunct.
- **Transients.** The lensed supernovae and AGN list their DD programs and the papers
  centred on them, and singly-imaged, cluster-magnified supernovae are included with
  `images: single` (October 2026). Not yet included: caustic-crossing stars, the z = 2.22
  SN Ia behind MOO J1014+0038 (cluster not in the catalogue), and galaxy-scale lenses.
- **Observations.** Each cluster can list instruments, filters and programs
  (`observations:`), but the wiki had none.
- **Missing clusters.** Some well-studied strong lenses are not listed yet, for example
  several eMACS clusters with published models.
- **After launch,** replace the wiki pages with "moved" notices using
  [`tools/wiki_moved_stubs.py`](../tools/wiki_moved_stubs.py).
