#!/usr/bin/env python3
"""One-off conversion of the GitHub wiki (cluster-models.wiki.git) into data/.

Kept in the repository for provenance; it is not part of the build.

    git clone https://github.com/mbronikowski/cluster-models.wiki.git /tmp/wiki
    python tools/migration/migrate_wiki.py /tmp/wiki

Inputs besides the wiki (cached, so the script runs offline):
  tools/migration/simbad_refs.json   titles/DOIs of cited bibcodes (SIMBAD TAP)
  tools/migration/arxiv_refs.json    titles/journal refs of cited arXiv preprints
  tools/migration/venus_targets.json VENUS (JWST GO 6882) fixed targets matched to clusters

Every automatic or hand-made change is written to tools/migration/migration-log.json.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cmdb import yamlio  # noqa: E402
from cmdb.text import anchor_id, clean_lookalikes, slugify  # noqa: E402

LOG: list[dict] = []


def log(cluster, kind, detail, before=None, after=None):
    LOG.append({"cluster": cluster, "kind": kind, "detail": detail,
                "before": before, "after": after})


# =============================================================================
# Hand-reviewed corrections
# =============================================================================

NAME_FIXES = {
    "MS1008.1-1224": "MS 1008.1-1224",
    "eMACSJ1341.9-2442": "eMACS J1341.9-2442",
}
COMMON_NAMES = {"Bullet Cluster", "El Gordo", "PSZ1-G311"}
ADDED_COMMON_NAMES = {
    "Abell 2744": ["Pandora's Cluster"],
    "1RXS J060313.4+421231": ["Toothbrush Cluster"],
    "ACT-CL J0603.9-3557": ["Carousel Lens"],
}
DROP_DESIGNATIONS = {
    "RCS2 032727-132623": "duplicate of RCS2 J032727-132623 (missing 'J')",
}
# Values where the Home table and the cluster page disagreed. Default: page value.
VALUE_CHOICES = {
    ("ACT-CL J0327.4-1326", "dec"): ("-13:26:23.65",
        "Dec sign missing on both Home and page; designations ACT-CL J0327.4-1326 and "
        "RCS2 J032727-132623 (and SIMBAD/NED) put the cluster at -13:26"),
    ("ACT-CL J0327.4-1326", "z"): ("0.564",
        "Home 0.560 (ACT photometric estimate) vs page 0.564 (spectroscopic, SIMBAD)"),
    ("MACS J0451.9+0006", "z"): ("0.430", "Home 0.434 vs page 0.430 (SIMBAD: 0.430)"),
    ("SDSS J1723+3411", "ra"): ("17:23:36.50", "Home RA truncated to whole seconds"),
    ("SDSS J1723+3411", "dec"): ("+34:11:55.90",
        "Home +34:11:59.37 vs page +34:11:55.90; NED gives +34:11:54.6 (page closer)"),
}
TEXT_FIXES = [
    (None, "Lagatutta et al.", "Lagattuta et al.", "author name typo (Lagattuta)"),
    (None, "Bonamago et al.", "Bonamigo et al.", "author name typo (Bonamigo)"),
    ("Abell 370", "[Wenlei et al. (2022)]", "[Chen et al. (2022)]",
     "first author is Wenlei Chen; 'Wenlei' is the given name"),
    ("Abell 1689", "solution for Abell 1869", "solution for Abell 1689", "cluster number typo"),
]
TITLE_FIXES = {
    "Zitrin 2017": "Zitrin (2017)",
    "Lagatutta et al. (2017)": "Lagattuta et al. (2017)",
    "Bonamago et al. (2018)": "Bonamigo et al. (2018)",
}
IGNORE_POSITION_CHECK = {
    "SDSS J1226+2152": ["SDSS J1226+2149"],
}
NOTE_OVERRIDES = {
    "SDSS J1226+2152": (
        "This field includes two separate cluster cores about 2.5' apart, both of which act "
        "as strong lenses (see e.g. [Oguri et al. 2012](ref:2012MNRAS.420.3213O)): the "
        "northern core (SDSS J1226+2152, this entry's position) and the southern core "
        "(SDSS J1226+2149)."),
}

# =============================================================================
# Programs and resources (data/programs.yaml)
# =============================================================================

PROGRAMS = [
    dict(id="clash", name="Cluster Lensing And Supernova survey with Hubble", short="CLASH",
         kind="survey", facilities=["HST"], url="https://www.stsci.edu/~postman/CLASH/Home.html",
         archive="https://archive.stsci.edu/prepds/clash/", overview="2012ApJS..199...25P",
         links=[{"label": "Information for astronomers",
                 "url": "https://www.stsci.edu/~postman/CLASH/for_astronomers.html"}]),
    dict(id="clash-vlt", name="CLASH-VLT", short="CLASH-VLT", kind="survey", facilities=["VLT"],
         url="https://sites.google.com/site/vltclashpublic/home",
         links=[{"label": "Lens models (INFN Ferrara lensing group)",
                 "url": "https://www.fe.infn.it/astro/lensing/"}]),
    dict(id="hff", name="Hubble Frontier Fields", short="HFF", kind="survey", facilities=["HST"],
         url="https://outerspace.stsci.edu/display/HPR/HST+Frontier+Fields",
         archive="https://archive.stsci.edu/prepds/frontier/", overview="2017ApJ...837...97L",
         links=[{"label": "Lens models and acknowledgement information",
                 "url": "https://archive.stsci.edu/prepds/frontier/lensmodels/"}]),
    dict(id="buffalo", name="Beyond Ultra-deep Frontier Fields And Legacy Observations",
         short="BUFFALO", kind="survey", facilities=["HST"], url="https://buffalo.ipac.caltech.edu/",
         archive="https://archive.stsci.edu/hlsp/buffalo", overview="2020ApJS..247...64S",
         note="Targets the six Hubble Frontier Fields clusters."),
    dict(id="relics", name="Reionization Lensing Cluster Survey", short="RELICS", kind="survey",
         facilities=["HST"], url="https://relics.stsci.edu/",
         archive="https://archive.stsci.edu/hlsp/relics", overview="2019ApJ...884...85C"),
    dict(id="sgas", name="Sloan Digital Sky Survey Giant Arcs Survey", short="SGAS", kind="survey",
         facilities=["HST"], url="https://archive.stsci.edu/hlsp/sgas",
         archive="https://archive.stsci.edu/hlsp/sgas", overview="2020ApJS..247...12S",
         note="Overview reference: the HST lens models of 37 SGAS clusters."),
    dict(id="locuss", name="Local Cluster Substructure Survey", short="LoCuSS", kind="survey",
         facilities=["HST"], url="https://www.sr.bham.ac.uk/locuss/home.php",
         overview="2010MNRAS.404..325R",
         note="Overview reference: strong-lensing analysis of 20 LoCuSS clusters."),
    dict(id="glass-jwst", name="GLASS-JWST Early Release Science program", short="GLASS-JWST",
         kind="survey", facilities=["JWST"], url="https://glass.astro.ucla.edu/ers/",
         archive="https://archive.stsci.edu/hlsp/glass-jwst", overview="2022ApJ...935..110T"),
    dict(id="uncover", name="UNCOVER JWST Treasury survey", short="UNCOVER", kind="survey",
         facilities=["JWST"], url="https://jwst-uncover.github.io/", overview="2024ApJ...974...92B"),
    dict(id="canucs", name="CAnadian NIRISS Unbiased Cluster Survey", short="CANUCS",
         kind="survey", facilities=["JWST"], url="https://niriss.github.io/",
         archive="https://archive.stsci.edu/hlsp/canucs", overview="2022PASP..134b5002W",
         links=[{"label": "Data Release 1", "url": "https://niriss.github.io/data_release1.html"},
                {"label": "DR1 lens models",
                 "url": "https://www.canfar.net/storage/vault/list/canucs/CANUCS_DR1/lensing"}]),
    dict(id="pearls", name="Prime Extragalactic Areas for Reionization and Lensing Science",
         short="PEARLS", kind="survey", facilities=["JWST"],
         url="https://sites.google.com/view/jwstpearls", overview="2023AJ....165...13W"),
    dict(id="slice", name="Strong LensIng and Cluster Evolution", short="SLICE", kind="survey",
         facilities=["JWST"], overview="2025arXiv250317498C",
         note="JWST snapshot survey of strong-lensing clusters; models are being released on the "
              "[LAM Strong Lensing Cluster Atlas](program:lam-atlas)."),
    dict(id="venus", name="Vast Exploration for Nascent, Unexplored Sources", short="VENUS",
         kind="survey", facilities=["JWST"], proposal="JWST GO 6882",
         url="https://www.stsci.edu/jwst-program-info/download/jwst/pdf/6882/",
         note="Membership from the program's fixed-target list (JWST GO 6882)."),
    dict(id="templates", short="TEMPLATES", kind="survey", facilities=["JWST"],
         name="Targeting Extremely Magnified Panchromatic Lensed Arcs and their Extended Star "
              "formation",
         url="https://archive.stsci.edu/hlsp/templates"),
    dict(id="alcs", name="ALMA Lensing Cluster Survey", short="ALCS", kind="survey",
         facilities=["ALMA"], url="https://www.ioa.s.u-tokyo.ac.jp/ALCS/",
         overview="2024ApJS..275...36F"),
    dict(id="muse-lensing", name="MUSE lensing-cluster data release", short="MUSE DR",
         kind="survey", facilities=["VLT"],
         url="https://cral-perso.univ-lyon1.fr/labo/perso/johan.richard/MUSE_data_release/",
         overview="2021A&A...646A..83R",
         note="MUSE/VLT observations of lensing clusters, with mass models, published on "
              "Johan Richard's data-release page."),
    dict(id="lam-atlas", name="LAM Strong Lensing Cluster Atlas", short="SL Atlas",
         kind="database", url="https://data.lam.fr/sl-cluster-atlas/home"),
    dict(id="lenstool", name="Lenstool website (archived models)", short="Lenstool",
         kind="database", url="https://projets.lam.fr/projects/lenstool/wiki"),
]

PROGRAM_PATTERNS = [
    (r"Reionization Lensing Cluster Survey|^RELICS$", "relics"),
    (r"^CLASH\b|Cluster Lensing And Supernova survey with Hubble \(CLASH\)$", "clash"),
    (r"^Hubble Frontier Fields$", "hff"),
    (r"^Sloan Digital Sky Survey Giant Arcs Survey$", "sgas"),
    (r"Strong LensIng and Cluster Evolution", "slice"),
    (r"CAnadian NIRISS Unbiased Cluster Survey", "canucs"),
    (r"^LoCuSS$", "locuss"),
]
PROGRAM_SHORT = {p["id"]: p["short"] for p in PROGRAMS}

PROGRAM_BOILERPLATE_URLS = {
    "https://relics.stsci.edu/", "https://archive.stsci.edu/hlsp/relics",
    "https://ui.adsabs.harvard.edu/abs/2019ApJ...884...85C/abstract",
    "https://www.stsci.edu/~postman/CLASH/for_astronomers.html",
    "https://www.stsci.edu/~postman/CLASH/Home.html", "https://archive.stsci.edu/prepds/clash/",
    "https://outerspace.stsci.edu/display/HPR/HST+Frontier+Fields",
    "https://archive.stsci.edu/prepds/frontier/",
    "https://archive.stsci.edu/prepds/frontier/lensmodels/",
    "https://niriss.github.io/index.html", "https://niriss.github.io/data_release1.html",
    "https://archive.stsci.edu/hlsp/canucs", "https://www.sr.bham.ac.uk/locuss/home.php",
    "https://cral-perso.univ-lyon1.fr/labo/perso/johan.richard/MUSE_data_release/",
}

# Official target lists (memberships not implied by a model section)
OFFICIAL_MEMBERS = {
    "buffalo": (["Abell 2744", "MACS J0416.1-2403", "MACS J0717.5+3745", "MACS J1149.5+2223",
                 "Abell S1063", "Abell 370"], "BUFFALO targets the six HFF clusters"),
    "slice": (["SPT-CL J0546-5345"], "Allingham et al. (2025) is a SLICE paper (arXiv title)"),
}

# =============================================================================
# Sections rewritten by hand (non-formulaic program sections)
# =============================================================================

MANUAL_SECTIONS = {
    ("Abell 2744", "GLASS-JWST Program"): dict(
        title="GLASS-JWST: Bergamini et al. (2023)", program="glass-jwst",
        refs=["2023ApJ...952...84B"], data=["JWST"], availability="public",
        links=[{"label": "Model download",
                "url": "https://www.fe.infn.it/astro/lensing/A2744_Bergamini23/"}],
        note=""),
    ("Abell 2744", "JWST UNCOVER Program"): dict(
        title="UNCOVER: Furtak et al. (2023)", program="uncover",
        refs=["2023MNRAS.523.4568F", "2024arXiv240803920P"], data=["JWST"], availability="public",
        links=[{"label": "Lens model v2.0 (UNCOVER DR4)",
                "url": "https://jwst-uncover.github.io/DR4.html#LensingMaps"},
               {"label": "Older model versions",
                "url": "https://drive.google.com/drive/folders/1Lc7uveJr_ZNIcvAQYVfAeRF8Qr68D_5p"}],
        note="Please cite [Furtak et al. (2023)](ref:2023MNRAS.523.4568F) and "
             "[Price et al. (2024)](ref:2024arXiv240803920P) when using this model."),
    ("Abell 2744", "Bergamini et al. (2023)"): dict(
        refs=["2023A&A...670A..60B"], availability="public", status="superseded",
        links=[{"label": "Model download",
                "url": "https://www.fe.infn.it/astro/lensing/A2744_Bergamini22/"}],
        note="Pre-_JWST_ model, now considered obsolete (see "
             "[P. Bergamini's page](https://www.fe.infn.it/astro/lensing/))."),
    ("ACT-CL J0102-4915", "JWST's PEARLS"): dict(
        title="PEARLS: Diego et al. (2023)", program="pearls", refs=["2023A&A...672A...3D"],
        data=["JWST"], availability="public",
        links=[{"label": "Model download (via the PEARLS website)",
                "url": "https://arizonastateuniversity10.app.box.com/s/3uaxcs83lv996n1sbuy3brzr2nv85ns9"}],
        note=""),
    ("Abell 383", "VENUS"): dict(
        title="VENUS: Golubchik et al. (2026)", program="venus", refs=["2026A&A...710A.226G"],
        data=["JWST"], availability="unknown",
        note="Updated version of the [CLASH model](#clash-zitrin-et-al-2015); the lens model is "
             "not the main focus of the paper."),
    ("MACS J0257.1-2325", "VENUS"): dict(
        title="VENUS: Nakane et al. (2025)", program="venus", refs=["2025arXiv251114483N"],
        data=["JWST"], availability="unknown", tags=["multiple-models"],
        note="Two lens models are presented."),
    ("MACS J1931.8-2635", "VENUS"): dict(
        title="VENUS: Allingham et al. (2026)", program="venus", refs=["2026ApJ..1005..215A"],
        data=["JWST"], availability="public", tags=["parametric"],
        links=[{"label": "Model download (Zenodo)", "url": "https://doi.org/10.5281/zenodo.18646525"}],
        note="Parametric model accompanying the discovery of the lensed supernova "
             "[SN Eos](transient:sn-eos) at z = 5.13 "
             "([Coulter et al. 2026](ref:2026arXiv260104156C))."),
    ("SDSS J1226+2152", "Sharon et al. (2022)"): dict(
        program="templates", refs=["2022arXiv220705709S"], data=["HST"], availability="public",
        links=[{"label": "Lens model (MAST TEMPLATES page)",
                "url": "https://archive.stsci.edu/hlsp/templates"}],
        note="Model of the northern core, prepared for the [TEMPLATES](program:templates) program."),
    ("SDSS J1226+2152", "Tejos et al. (2021)"): dict(
        program="templates", refs=["2021MNRAS.507..663T"], availability="public",
        links=[{"label": "Lens model (MAST TEMPLATES page)",
                "url": "https://archive.stsci.edu/hlsp/templates"}],
        note="Model of the northern core."),
    ("SDSS J1723+3411", "TEMPLATES"): dict(
        title="TEMPLATES: Florian et al. (2021)", program="templates",
        refs=["2021ApJ...916...50F", "2020ApJS..247...12S"], availability="public",
        links=[{"label": "Lens model (MAST TEMPLATES page)",
                "url": "https://archive.stsci.edu/hlsp/templates"}],
        note="Studied by [Florian et al. (2021)](ref:2021ApJ...916...50F) and "
             "[Sharon et al. (2020)](ref:2020ApJS..247...12S) in preparation for the "
             "TEMPLATES program."),
    ("RXC J0600.1-2007", "ALMA Lensing Cluster Survey"): dict(
        title="ALCS: Fujimoto et al. (2021)", program="alcs", refs=["2021ApJ...911...99F"],
        availability="unknown", tags=["multiple-models"],
        note="Several lens models of the cluster, built as part of the ALMA Lensing Cluster Survey."),
    ("SPT-CL J0546-5345", "Allingham et al. (2025)"): dict(
        title="SLICE: Allingham et al. (2025)", program="slice", data=["JWST"]),
    ("Abell 370", "Niemiec et al. (2023)"): dict(
        program="buffalo", refs=["2023MNRAS.524.2883N"], data=["HST"], availability="public",
        tags=["weak-lensing"],
        links=[{"label": "Download script for all model types (MAST)",
                "url": "https://archive.stsci.edu/hlsps/buffalo/download_scripts/"
                       "hlsp_buffalo_hst_multi_abell370_multi_v1.0_catalogs-download.sh"}],
        note="Strong+weak-lensing model based on [BUFFALO](program:buffalo) observations. Scripts "
             "for individual model types are also available on the BUFFALO MAST page."),
}

# Data/facility corrections where the paper title (SIMBAD/arXiv) shows JWST data.
JWST_EXTRA = {
    ("SMACS J0723.3-7327", "Mahler et al. (2023)"): "title: Precision Modeling of JWST's First Cluster Lens",
    ("PLCK G165.7+67.0", "Frye et al. (2024)"): "title: The JWST Discovery of ... SN H0pe",
    ("MACS J0138.0-2155", "Suyu et al. (2025)"): "SN Encore time delays from JWST imaging",
    ("Abell 370", "Diego et al. (2025)"): "arXiv title: JWST lens model for A370",
    ("1E 0657-56", "Cho et al. (2025)"): "arXiv title: Joint JWST-DECam Lensing ...",
    ("XLSSC 122", "Finner et al. (2025)"): "title: JWST Discovery of Strong Lensing ...",
}

SOFTWARE_PATTERNS = [
    (r"\bGRALE\b", "GRALE"), (r"\bLENSTOOL\b|\bLenstool\b", "Lenstool"),
    (r"\bGLAFIC\b|\bglafic\b", "glafic"), (r"light-traces-mass|\bLTM\b", "LTM"),
]
TAG_PATTERNS = [
    (r"free-form|freeform|non-parametric strong lens|GRALE", "free-form"),
    (r"(?<!non-)\bparametric\b", "parametric"),
    (r"\bhybrid\b", "hybrid"),
    (r"weak lensing|weak-lensing|strong\+weak|strong and weak", "weak-lensing"),
    (r"Hubble constant|time-delay cosmography|\bH0\b", "time-delay-cosmography"),
    (r"preliminary|tentative|underconstrained", "preliminary"),
    (r"new non-parametric method|method of validating", "method-test"),
    (r"series of models|several lensing models|seven modeling approaches|multiple lens models"
     r"|two lens models|three different models|array of free-form|two grid-based lens models"
     r"|cored and non-cored models|two-clump, three-clump|comparison of independent", "multiple-models"),
]

# =============================================================================
# Lensed transients / variable sources (data/transients/)
# =============================================================================

TRANSIENTS = [
    dict(name="SN Refsdal", **{"class": "supernova"}, status="confirmed",
         cluster="MACS J1149.5+2223",
         refs=["2015Sci...347.1123K", "2016ApJ...822...78G", "2021ApJ...919...54Z"],
         notes="Multiply-imaged supernova behind MACS J1149.5+2223, the first one discovered "
               "([Kelly et al. 2015](ref:2015Sci...347.1123K))."),
    dict(name="SN Requiem", **{"class": "supernova"}, subclass="Ia (likely)", status="confirmed",
         cluster="MACS J0138.0-2155", refs=["2021NatAs...5.1118R", "arXiv:2509.12319"],
         notes="Multiply-imaged supernova in the galaxy MRG-M0138, which later also hosted "
               "[SN Encore](transient:sn-encore). Forecasts of its reappearance: "
               "[Suyu et al. (2025)](ref:arXiv:2509.12319)."),
    dict(name="SN Encore", **{"class": "supernova"}, subclass="Ia", status="confirmed",
         cluster="MACS J0138.0-2155",
         refs=["2024ApJ...967L..37P", "2025arXiv250912301P", "arXiv:2509.12319"],
         notes="Second multiply-imaged supernova in MRG-M0138 (z ~ 2), after "
               "[SN Requiem](transient:sn-requiem). Time-delay H0 measurement: "
               "[Pierel et al. (2025)](ref:2025arXiv250912301P) and "
               "[Suyu et al. (2025)](ref:arXiv:2509.12319)."),
    dict(name="SN H0pe", **{"class": "supernova"}, subclass="Ia", status="confirmed",
         cluster="PLCK G165.7+67.0", refs=["2024ApJ...961..171F"],
         notes="Triply-imaged Type Ia supernova discovered in JWST imaging "
               "([Frye et al. 2024](ref:2024ApJ...961..171F))."),
    dict(name="SN Eos", **{"class": "supernova"}, subclass="II", status="confirmed",
         cluster="MACS J1931.8-2635", z=5.13,
         refs=["2026arXiv260104156C", "2026ApJ..1005..215A"],
         notes="Spectroscopically confirmed, multiply-imaged supernova at z = 5.13 "
               "([Coulter et al. 2026](ref:2026arXiv260104156C)); the VENUS lens model of "
               "[Allingham et al. (2026)](ref:2026ApJ..1005..215A) accompanies the discovery."),
    dict(name="SN 2022riv", **{"class": "supernova"}, status="confirmed",
         cluster="MACS J2129.4-0741", refs=["2022TNSAN.169....1K"],
         notes="Multiply-imaged supernova reported in a TNS AstroNote."),
    dict(name="Abell 370 archival SN", **{"class": "supernova"},
         subclass="red-supergiant progenitor (shock cooling)", status="confirmed",
         cluster="Abell 370", refs=["2022Natur.611..256C"],
         notes="Archival multiply-imaged supernova in _Hubble Space Telescope_ images, at z ~ 3 "
               "([Chen et al. 2022](ref:2022Natur.611..256C))."),
    dict(name="SPT-CL J0516-5755 SN candidate", **{"class": "supernova"}, status="candidate",
         cluster="SPT-CL J0516-5755", refs=["2025arXiv250317498C"],
         notes="Candidate multiply-imaged supernova reported by the SLICE team "
               "([Cerny et al. 2025](ref:2025arXiv250317498C))."),
    dict(name="SDSS J1004+4112 quasar", **{"class": "quasar"}, status="confirmed",
         cluster="SDSS J1004+4112",
         refs=["2003Natur.426..810I", "2022ApJ...937...35F", "2023ApJ...959..134N",
               "2024A&A...682A.187M"],
         notes="Quadruply-imaged quasar with a 14.6 arcsec image separation "
               "([Inada et al. 2003](ref:2003Natur.426..810I)); used for time-delay H0 "
               "measurements."),
    dict(name="SDSS J1029+2623 quasar", **{"class": "quasar"}, status="confirmed",
         cluster="SDSS J1029+2623", refs=["2022ApJ...926...86A", "2023ApJ...959..134N"],
         notes="Multiply-imaged quasar with a measured time delay (see e.g. "
               "[Acebron et al. 2022](ref:2022ApJ...926...86A))."),
    dict(name="SDSS J2222+2745 quasar", **{"class": "quasar"}, status="confirmed",
         cluster="SDSS J2222+2745",
         refs=["2017ApJ...835....5S", "2022A&A...668A.142A", "2023ApJ...959..134N"],
         notes="Sextuply-imaged quasar ([Sharon et al. 2017](ref:2017ApJ...835....5S))."),
    dict(name="SDSS J0909+4449 quasar", **{"class": "quasar"}, status="confirmed",
         cluster="SDSS J0909+4449", refs=["2018MNRAS.481L.136S"],
         notes="Large-separation, triply-imaged quasar at z ~ 2.8 "
               "([Shu et al. 2018](ref:2018MNRAS.481L.136S))."),
    dict(name="SDSS J1326+4806 quasar", **{"class": "quasar"}, status="confirmed",
         cluster="SDSS J1326+4806", refs=["2019MNRAS.489.4741S"],
         notes="Multiply-imaged quasar; [Shu et al. (2019)](ref:2019MNRAS.489.4741S) built a "
               "simple lens model to test the lensing interpretation."),
    dict(name="COOL J0335-1927 quasar", **{"class": "quasar"}, status="confirmed",
         cluster="COOL J0335-1927", z=3.27, refs=["2023ApJ...954L..38N"],
         notes="Lensed quasar at z = 3.27 ([Napier et al. 2023](ref:2023ApJ...954L..38N))."),
    dict(name="COOL J0542-2125 quasar", **{"class": "quasar"}, status="confirmed",
         cluster="COOL J0542-2125", refs=["2023ApJ...946...63M"],
         notes="Quasar with a 25.9 arcsec image separation, lensed by a merging cluster "
               "([Martinez et al. 2023](ref:2023ApJ...946...63M))."),
    dict(name="MACS J0035.4-2015 AGN", **{"class": "quasar"}, subclass="AGN", status="confirmed",
         cluster="MACS J0035.4-2015", z=2.06, refs=["2023MNRAS.522.5142F"],
         notes="Variable AGN at z = 2.06, triply imaged "
               "([Furtak et al. 2023](ref:2023MNRAS.522.5142F))."),
    dict(name="WH J040011.7-270711 quasar candidate", **{"class": "quasar"}, status="candidate",
         cluster="WH J040011.7-270711", refs=["2025A&A...698A..29B"],
         notes="Candidate strongly lensed quasar with an 18 arcsec image separation "
               "([Bazzanini et al. 2025](ref:2025A&A...698A..29B))."),
]
# Cluster notes fully replaced by transient pages (the cluster page links them).
NOTES_ABSORBED = {t["cluster"] for t in TRANSIENTS}

# =============================================================================
# Parsing
# =============================================================================

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")


def clean(text, cluster, where):
    new, changes = clean_lookalikes(text)
    if changes:
        kinds = Counter(f"U+{ord(a):04X}->{b!r}" for a, b in changes)
        log(cluster, "characters", f"{where}: " + ", ".join(f"{k} x{n}" for k, n in kinds.items()))
    return new


def ads_ref(url):
    m = re.match(r"https?://(?:ui\.)?adsabs\.harvard\.edu/abs/([^/?#]+)", url)
    if m:
        ident = urllib.parse.unquote(m.group(1))
        if ident.lower().startswith("arxiv:"):
            return "arXiv:" + ident.split(":", 1)[1]
        return ident
    m = re.match(r"https?://(?:ui\.)?adsabs\.harvard\.edu/doi/(.+)$", url)
    if m:
        return "doi:" + urllib.parse.unquote(m.group(1))
    return None


def parse_home(wiki: Path):
    rows = OrderedDict()
    for line in (wiki / "Home.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ["):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = re.match(r"\[(.*?)\]\((.*?)\)", cells[0])
        rows[m.group(2)] = {"name": m.group(1), "ra": cells[1], "dec": cells[2], "z": cells[3],
                            "names": cells[4], "notes": cells[5] if len(cells) > 5 else ""}
    return rows


def parse_page(path: Path):
    text = path.read_text(encoding="utf-8")
    pre, _, rest = text.partition("| **Quick Information**")
    qi = {}
    for m in re.finditer(r"^\| \*\*(.+?)\*\*\s*\|(.*)\|\s*$", rest, re.M):
        qi[m.group(1).strip()] = m.group(2).strip()
    image = None
    img = re.search(r"!\[[^\]]*\]\((\S+?)\)", pre)
    if img:
        credit = " ".join(ln.strip() for ln in pre[img.end():].splitlines()
                          if ln.strip() and ln.strip() != "---")
        image = {"url": img.group(1), "credit": credit}
    body = rest.split("# Publications and models", 1)[1]
    models_part, _, tail = body.partition("\n# Additional information")
    addl = tail.partition("# Comments & Discussion")[0]
    sections, current = [], None
    for line in models_part.splitlines():
        if line.startswith("## "):
            current = {"title": line[3:].strip(), "lines": []}
            sections.append(current)
        elif current is not None and line.strip() != "---":
            current["lines"].append(line)
    for s in sections:
        s["body"] = re.sub(r" {2,}", " ", re.sub(r"\s*\n\s*", " ", "\n".join(s.pop("lines")).strip()))
    addl = "\n".join(ln for ln in addl.splitlines() if ln.strip() != "---").strip()
    return {"qi": qi, "image": image, "sections": sections, "additional": addl}


def split_names(text):
    out = []
    for raw in re.split(r"[;,]", text):
        raw = raw.strip()
        if raw:
            out.append((raw.strip("*").strip(), raw.startswith("**") and raw.endswith("**")))
    return out


def label_of(label):
    """'Coe et al. 2019' / 'Bergamini et al. (2023)' -> 'Name et al. (YYYY)' or None."""
    lab = label.strip().strip("()")
    m = re.match(r"^(.+?),? \(?(\d{4}[a-z]?)(?:, preprint)?\)?$", lab)
    if m and re.match(r"^[A-Z]", m.group(1)) and not re.match(
            r"^(Model|Publication|Program|here)", m.group(1)):
        return f"{m.group(1).rstrip(',')} ({m.group(2)})"
    return None


def best_label(counter: Counter):
    good = Counter()
    for label, n in counter.items():
        lab = label_of(label)
        if lab:
            good[lab] += n
    return good.most_common(1)[0][0] if good else None


# =============================================================================
# Section conversion
# =============================================================================

def detect_program(cluster, title, body):
    for pat, prog in PROGRAM_PATTERNS:
        if re.search(pat, title):
            return prog
    if title in ("MUSE/VLT", "Richard et al. (2021)", "Thai et al. (2023)") and \
            "/MUSE_data_release/models/" in body:
        return "muse-lensing"
    if "CLASH-VLT lens model webpage" in body:
        return "clash-vlt"
    return None


def section_refs(title, raw_links, body):
    year = re.search(r"\((\d{4})\)", title)
    surname = re.split(r"[ ,&(]", title.split(":")[-1].strip())[0]
    refs = []
    for label, url in raw_links:
        r = ads_ref(url)
        if not r or r in refs or url in PROGRAM_BOILERPLATE_URLS:
            continue
        ctx = body[:body.find(url)][-70:].lower()
        by_author = surname and label.startswith(surname) and (not year or year.group(1) in label)
        by_context = any(k in ctx for k in (
            "publication", "model description", "model reference", "model overview",
            "please cite", "presented by", "modeled by", "modelled by"))
        if by_author or by_context:
            refs.append(r)
    return refs


BOILERPLATE_SENTENCES = [
    r"^The cluster was (observed|analysed|analyzed|studied) (as part of|by) the",
    r"^Models created as part of the Reionization",
    r"^Program (page|website|overview|data products)", r"^\[Program website\]",
    r"^MAST webpage", r"^Program MAST webpage", r"^Data Release 1",
    r"^(Lens )?[Mm]odels? (available|download)", r"^Lens model available",
    r"^The lens model is in two parts", r"^Models available for download",
    r"^\[Model description\]\(ref:", r"^Model description(:| by)",
    r"^Model download available on the \[Lenstool\]",
    r"^The resulting lens models are available on the \[program webpage\]",
    r"^Model overview for .* by \[", r"^Publication: \[",
    r"^This (pre-_JWST_ )?model by \[(Richard et al\. \(2021\)|Thai et al\. \(2023\))\]",
    r"^Lens model by \[Richard et al\. \(2021\)\]", r"^Model reference: \[",
    r"^The cluster was modeled using MUSE/VLT data and published on",
    r"^The cluster was modeled by \[Sharon et al\. \(2020\)\]",
]


def strip_program_boilerplate(cluster, program, title, note, raw_links):
    links = []
    for label, url in raw_links:
        if url in PROGRAM_BOILERPLATE_URLS or ads_ref(url):
            continue
        lab = label.strip()
        if program == "relics":
            lab = "Lens models (MAST)" if lab == "here" else f"Lens models, {lab} part (MAST)"
        elif program == "clash":
            lab = "Lens models (MAST)"
        elif program == "hff":
            lab = "Lens models from all HFF teams (MAST)"
        elif program == "sgas":
            lab = "Lens models (MAST SGAS page)"
        elif program == "canucs":
            lab = "CANUCS DR1 lens models"
        elif program == "locuss":
            lab = "Model download (Lenstool website)"
        elif program == "muse-lensing":
            if "data.lam.fr" in url:
                continue
            lab = "Mass model"
        links.append({"label": lab, "url": url})
    keep = []
    for sent in re.split(r"(?<=[.)])\s+(?=[A-Z\[])", note):
        st = sent.strip()
        if any(re.match(p, st) for p in BOILERPLATE_SENTENCES):
            extra = []
            if "but has not been described in a paper" in st:
                when = re.search(r"\(as of ([^)]+)\)", st)
                extra.append("Not described in a paper" + (f" as of {when.group(1)}." if when else "."))
            if "this cluster's model is not available" in st:
                extra.append("This cluster's model was not released because it is poorly constrained.")
            if "pre-_JWST_" in st:
                extra.append("Pre-_JWST_ model.")
            if "Also listed in the" in st:
                extra.append("Also listed in the [LAM Strong Lensing Cluster Atlas](program:lam-atlas).")
            if "A recent model description was published by" in st:
                extra.append(st[st.find("A recent model description"):])
            if "previously studied by" in st:
                extra.append(st[st.find("The cluster's lensing properties were previously"):])
            keep.extend(extra)
            log(cluster, "boilerplate-dropped", f"{program} section '{title}'", st,
                " ".join(extra) or None)
        else:
            keep.append(st)
    return " ".join(keep).strip(), links


class Converter:
    def __init__(self, page_to_name, references):
        self.page_to_name = page_to_name
        self.references = references

    def text(self, cluster, text, anchors, where):
        text = clean(text, cluster, where)
        for c, old, new, reason in TEXT_FIXES:
            if (c is None or c == cluster) and old in text:
                text = text.replace(old, new)
                log(cluster, "text-fix", reason, old, new)

        def repl(m):
            label, url = m.group(1), m.group(2)
            ref = ads_ref(url)
            if ref:
                self.references[ref][label] += 1
                return f"[{label}](ref:{ref})"
            if url.startswith("#"):
                key = re.sub("-+", "-", url[1:].lower())
                if key in anchors:
                    return f"[{label}](#{anchor_id(anchors[key])})"
                log(cluster, "link-dropped", f"anchor {url} not found on page", m.group(0), label)
                return label
            if not re.match(r"^[a-z]+://", url):
                tgt = clean_lookalikes(url)[0].lower()
                if tgt in self.page_to_name:
                    return f"[{label}](cluster:{slugify(self.page_to_name[tgt])})"
                log(cluster, "link-dropped", f"unknown wiki page {url}", m.group(0), label)
                return label
            return m.group(0)

        return LINK_RE.sub(repl, text).strip()

    def section(self, cluster, s, anchors, final_titles):
        orig_title = clean(s["title"], cluster, "section title")
        title = final_titles[s["title"]]
        body = clean_lookalikes(s["body"])[0]
        raw_links = LINK_RE.findall(body)
        program = detect_program(cluster, TITLE_FIXES.get(orig_title, orig_title), body)
        note = self.text(cluster, s["body"], anchors, f"model '{orig_title}'")
        refs = section_refs(TITLE_FIXES.get(orig_title, orig_title), raw_links, body)
        if not refs and program is None:
            first = [ads_ref(u) for _, u in raw_links if ads_ref(u)]
            refs = first[:1]
        model = {"title": title, "program": program}
        links = []
        if program in ("relics", "clash", "hff", "sgas", "canucs", "locuss", "muse-lensing"):
            note, links = strip_program_boilerplate(cluster, program, orig_title, note, raw_links)
            if program == "hff":
                note = ("Models from several independent teams; see the [HFF program page]"
                        "(program:hff) for credits and acknowledgement requirements.")
        elif program == "slice":
            note = ("The model will be released on the "
                    "[LAM Strong Lensing Cluster Atlas](program:lam-atlas).")
        model["refs"] = refs

        data = []
        nb = body.replace("_", "")
        if (re.search(r"\bJWST\b", nb) and not re.search(r"pre-JWST", nb)) or program in (
                "glass-jwst", "uncover", "canucs", "pearls", "venus", "slice"):
            data.append("JWST")
        elif (cluster, orig_title) in JWST_EXTRA:
            data.append("JWST")
            log(cluster, "data-added", f"JWST ({JWST_EXTRA[(cluster, orig_title)]})", None, orig_title)
        if re.search(r"\bHST\b|Hubble Space Telescope|\bHFF\b|Frontier Fields", nb) or program in (
                "clash", "hff", "relics", "buffalo", "sgas", "locuss", "muse-lensing"):
            data.append("HST")
        for word, fac in (("MUSE", "MUSE"), ("Euclid", "Euclid"), ("ALMA", "ALMA"),
                          ("Atacama Large", "ALMA"), ("Gemini", "Gemini"), ("Keck", "Keck")):
            if (word in nb or (fac == "MUSE" and program == "muse-lensing")) and fac not in data:
                data.append(fac)
        model["data"] = data

        for pat, sw in SOFTWARE_PATTERNS:
            if re.search(pat, body):
                model["software"] = sw
                break

        b = body.lower()
        if program == "slice" or "will be released" in b:
            avail = "upcoming"
        elif "not available" in b:
            avail = "unavailable"
        elif "defunct" in b and not re.search(r"can be found in|available on|available for", b):
            avail = "defunct"
        elif "request" in b:
            avail = "on-request"
        elif links or re.search(
                r"available for download|available here|model available|models available|"
                r"model download|lens model download|can be downloaded|is available on|"
                r"publicly available|mass model \[here\]|download link|lists a model|"
                r"provide locations for components|available on github|available on the|"
                r"available for direct download|model link", b):
            avail = "public"
        else:
            avail = "unknown"
        model["availability"] = avail

        if re.search(r"superseded|obsolete", b):
            model["status"] = "superseded"
            m = re.search(r"superseded by \[[^\]]*\]\((#[^)]+)\)", body, re.I)
            if m:
                model["_superseded_by_title"] = anchors.get(re.sub("-+", "-", m.group(1)[1:].lower()))

        tags = []
        for pat, tag in TAG_PATTERNS:
            if re.search(pat, body, re.I) and tag not in tags:
                tags.append(tag)
        model["tags"] = tags
        model["links"] = links
        model["note"] = note

        manual = MANUAL_SECTIONS.get((cluster, orig_title))
        if manual:
            model.update(manual)
            log(cluster, "manual-section", "section rewritten by hand", orig_title, model["title"])
        if not model.get("program"):
            model.pop("program", None)
        return model


def final_section_titles(cluster, sections, references_hint):
    """Program sections become 'PROGRAM: First-author et al. (year)' or 'PROGRAM'."""
    titles = {}
    for s in sections:
        t = clean_lookalikes(s["title"])[0]
        t = TITLE_FIXES.get(t, t)
        body = clean_lookalikes(s["body"])[0]
        program = detect_program(cluster, t, body)
        if (cluster, t) in MANUAL_SECTIONS and "title" in MANUAL_SECTIONS[(cluster, t)]:
            new = MANUAL_SECTIONS[(cluster, t)]["title"]
        elif ":" in t:
            new = t
        elif program in ("relics", "clash", "sgas", "canucs", "locuss", "slice"):
            refs = section_refs(t, LINK_RE.findall(body), body)
            lab = None
            for lbl, url in LINK_RE.findall(body):
                if refs and ads_ref(url) == refs[0]:
                    lab = label_of(lbl)
                    if lab:
                        break
            if program == "slice":
                lab = "Cerny et al. (2025)"
            new = f"{PROGRAM_SHORT[program]}: {lab}" if lab else PROGRAM_SHORT[program]
        elif program == "muse-lensing" and t == "MUSE/VLT":
            refs = section_refs(t, LINK_RE.findall(body), body)
            m = re.search(r"Model reference: \[([^\]]+)\]", body)
            new = f"MUSE: {label_of(m.group(1))}" if m else "MUSE data release"
        else:
            new = t
        if new != s["title"]:
            log(cluster, "title", "section title", s["title"], new)
        titles[s["title"]] = new
    return titles


# =============================================================================
# Main
# =============================================================================

def build(wiki: Path):
    home = parse_home(wiki)
    pages = {clean_lookalikes(p.stem)[0].lower(): p for p in wiki.glob("*.md")
             if p.name not in ("Home.md", "Program-list.md") and not p.name.startswith("_")}
    assert len(pages) == len(home) == 167, (len(pages), len(home))

    page_to_name = {}
    for target, row in home.items():
        nm = clean_lookalikes(row["name"])[0]
        page_to_name[clean_lookalikes(target)[0].lower()] = NAME_FIXES.get(nm, nm)

    references = defaultdict(Counter)
    conv = Converter(page_to_name, references)
    clusters = []
    for target, row in home.items():
        page = parse_page(pages[clean_lookalikes(target)[0].lower()])
        qi = page["qi"]
        name0 = clean(row["name"], row["name"], "Home name")
        name = NAME_FIXES.get(name0, name0)
        if name != name0:
            log(name, "name", "designation spacing normalised", name0, name)
        qi_name = NAME_FIXES.get(clean(qi["Cluster Name"], name, "page name"),
                                 clean_lookalikes(qi["Cluster Name"])[0])
        if qi_name != name:
            log(name, "name-mismatch", "page title differs from Home table (Home used)", qi_name, name)

        vals = {}
        for fld, qkey in (("ra", "RA"), ("dec", "DEC"), ("z", "Redshift")):
            h = clean(row[fld], name, f"Home {fld}").strip()
            p = clean(qi[qkey], name, f"page {fld}").strip()
            choice = VALUE_CHOICES.get((name, fld))
            if choice:
                log(name, "value-choice", choice[1], f"Home {h} / page {p}", choice[0])
                vals[fld] = choice[0]
                continue
            same = h == p
            if not same and fld != "z":
                same = h.rstrip("0").rstrip(".") == p.rstrip("0").rstrip(".") or \
                    re.sub(r"0+$", "", h) == re.sub(r"0+$", "", p)
            if not same and fld == "z":
                same = float(h) == float(p)
            if not same:
                log(name, "value-choice", f"{fld}: Home and page differ; page value kept "
                    "(more precise)", f"Home {h}", p)
            vals[fld] = p
        dec = vals["dec"]
        if not dec.startswith(("+", "-")):
            log(name, "coordinate-format", "explicit '+' added to declination", dec, "+" + dec)
            dec = "+" + dec
        ra = vals["ra"]
        if re.match(r"^\d{2}:\d{2}:\d{2}$", ra) is None and re.match(r"^\d{2}:\d{2}:\d{2}\.\d+$", ra) is None:
            raise SystemExit(f"bad RA {ra} for {name}")

        home_names = split_names(clean(row["names"], name, "Home other names"))
        page_names = split_names(clean(qi["Alternate names"], name, "page alternate names"))
        if [n for n, _ in home_names] != [n for n, _ in page_names]:
            log(name, "names-merged", "Home and page alternate names differ (union kept)",
                "; ".join(n for n, _ in page_names), "; ".join(n for n, _ in home_names))
        merged = OrderedDict()
        for n, bold in home_names + page_names:
            merged[n] = merged.get(n, False) or bold
        common, aka, desig = list(ADDED_COMMON_NAMES.get(name, [])), [], []
        for extra in ADDED_COMMON_NAMES.get(name, []):
            log(name, "common-name-added", "well-established nickname added", None, extra)
        for n, bold in merged.items():
            n2 = NAME_FIXES.get(n, n)
            if n2 != n:
                log(name, "name", "designation spacing normalised", n, n2)
            if n2 in DROP_DESIGNATIONS:
                log(name, "designation-dropped", DROP_DESIGNATIONS[n2], n2, None)
            elif n2 == name:
                continue
            elif n2 in COMMON_NAMES:
                common.append(n2)
            elif bold:
                aka.append(n2)
            else:
                desig.append(n2)

        final_titles = final_section_titles(name, page["sections"], references)
        anchors = {re.sub("-+", "-", anchor_id(clean_lookalikes(s["title"])[0])): final_titles[s["title"]]
                   for s in page["sections"]}
        models = [conv.section(name, s, anchors, final_titles) for s in page["sections"]]
        # resolve superseded_by -> first ref of the target model
        by_title = {m["title"]: m for m in models}
        for m in models:
            tgt = m.pop("_superseded_by_title", None)
            if tgt and by_title.get(tgt, {}).get("refs"):
                m["superseded_by"] = by_title[tgt]["refs"][0]

        notes = conv.text(name, page["additional"], {}, "notes")
        if name in NOTE_OVERRIDES:
            log(name, "notes", "cluster notes rewritten (merged Home + page notes)", notes,
                NOTE_OVERRIDES[name])
            notes = NOTE_OVERRIDES[name]
        elif name in NOTES_ABSORBED:
            log(name, "notes", "note moved to a lensed-transient entry", notes, None)
            notes = ""
        home_note = clean(row["notes"], name, "Home notes")
        if home_note and name not in NOTES_ABSORBED and name not in NOTE_OVERRIDES:
            log(name, "notes", "Home-table note dropped (same content as page note)", home_note, None)

        image = None
        if page["image"]:
            image = {"url": page["image"]["url"],
                     "credit": conv.text(name, page["image"]["credit"], {}, "image credit")}

        programs = []
        for m in models:
            if m.get("program") and m["program"] not in programs:
                programs.append(m["program"])
        clusters.append({
            "name": name, "common_names": common, "aka": aka, "designations": desig,
            "ra": ra, "dec": dec, "z": float(vals["z"]), "programs": programs, "image": image,
            "models": models, "notes": notes,
            "ignore_position_check": IGNORE_POSITION_CHECK.get(name, []),
        })
    return clusters, references


def add_official_members(clusters):
    by_name = {c["name"]: c for c in clusters}
    for prog, (names, reason) in OFFICIAL_MEMBERS.items():
        for n in names:
            if prog not in by_name[n]["programs"]:
                by_name[n]["programs"].append(prog)
                log(n, "program-added", reason, None, prog)
    venus = json.load(open(HERE / "venus_targets.json"))
    for num, target, cname, sep in venus:
        assert sep < 2.0, (target, cname, sep)
        names = [cname]
        if target == "A3192":   # pointing centred on MACS J0358.8-2955, 2.5' from A3192
            names = ["Abell 3192", "MACS J0358.8-2955"]
        for n in names:
            if "venus" not in by_name[n]["programs"]:
                by_name[n]["programs"].append("venus")
                log(n, "program-added", f"VENUS fixed target {target} (JWST GO 6882)", None, "venus")
    order = [p["id"] for p in PROGRAMS]
    for c in clusters:
        c["programs"].sort(key=order.index)


def clean_title(t):
    t = clean_lookalikes(t)[0]
    t = re.sub(r"\{\\em\s*([^}]*)\}", r"\1", t)
    t = t.replace("{theta}", "theta").replace("{mu}", "mu").replace("{approx}", "~")
    t = t.replace("{\\geq}", ">=").replace("{~}", "~").replace("{\\em", "")
    t = re.sub(r"\s+", " ", t).strip().rstrip(".")
    return t


def build_references(references):
    simbad = json.load(open(HERE / "simbad_refs.json"))["found"]
    arxiv = json.load(open(HERE / "arxiv_refs.json"))
    used = set(references)
    for t in TRANSIENTS:
        used.update(t["refs"])
    for p in PROGRAMS:
        if p.get("overview"):
            used.add(p["overview"])
    out = {}
    for ref in sorted(used, key=str.lower):
        entry = {}
        lab = best_label(references.get(ref, Counter()))
        if lab:
            entry["label"] = lab
        if ref in simbad:
            _, title, doi, year = simbad[ref]
            entry["title"] = clean_title(title)
            if doi:
                entry["doi"] = doi
        elif ref in arxiv:
            a = arxiv[ref]
            entry["title"] = clean_title(a["title"])
            if a.get("doi"):
                entry["doi"] = a["doi"]
            if a.get("journal_ref"):
                entry["published"] = clean_lookalikes(a["journal_ref"])[0]
                log(None, "preprint-published", f"{ref} has been published", None, a["journal_ref"])
        out[ref] = entry
    # labels for overview papers without a wiki link text
    defaults = {
        "2012ApJS..199...25P": "Postman et al. (2012)", "2017ApJ...837...97L": "Lotz et al. (2017)",
        "2022ApJ...935..110T": "Treu et al. (2022)", "2024ApJ...974...92B": "Bezanson et al. (2024)",
        "2022PASP..134b5002W": "Willott et al. (2022)", "2023AJ....165...13W": "Windhorst et al. (2023)",
        "2020ApJS..247...64S": "Steinhardt et al. (2020)", "2024ApJS..275...36F": "Fujimoto et al. (2024)",
        "arXiv:2509.12319": "Suyu et al. (2025)",
    }
    for ref, lab in defaults.items():
        if ref in out and "label" not in out[ref]:
            out[ref]["label"] = lab
    return out


def write_all(clusters, refs_out):
    data = ROOT / "data"
    cdir = data / "clusters"
    for old in cdir.glob("*.yaml"):
        old.unlink()
    for c in clusters:
        rec = {k: v for k, v in c.items()}
        for m in rec["models"]:
            for k in [k for k, v in m.items() if v in (None, [], "")]:
                del m[k]
        path = cdir / f"{slugify(c['name'])}.yaml"
        assert not path.exists(), path
        path.write_text(yamlio.dump_cluster(rec), encoding="utf-8")

    tdir = data / "transients"
    for old in tdir.glob("*.yaml"):
        old.unlink()
    for t in TRANSIENTS:
        rec = dict(t)
        rec["cluster"] = slugify(t["cluster"])
        (tdir / f"{slugify(t['name'])}.yaml").write_text(yamlio.dump_transient(rec), encoding="utf-8")

    header = ("# Programs and resources referenced by cluster and model entries.\n"
              "# Field reference: docs/data-format.md")
    keys = ["id", "name", "short", "kind", "facilities", "proposal", "url", "archive", "overview",
            "links", "note"]
    (data / "programs.yaml").write_text(yamlio.dump_list_file(header, PROGRAMS, keys), encoding="utf-8")

    lines = ["# Reference metadata, keyed by ADS bibcode, 'arXiv:NNNN.NNNNN' or 'doi:...'.",
             "# label: how the reference is shown; title/doi: from SIMBAD or arXiv.",
             "# Entries are optional: unknown references are shown by their identifier.", ""]
    for ref, e in refs_out.items():
        lines.append(f"{yamlio.scalar(ref)}:")
        for k in ("label", "title", "doi", "published"):
            if k in e:
                lines.append(f"  {k}: {yamlio.scalar(e[k])}")
        if not e:
            lines[-1] = f"{yamlio.scalar(ref)}: {{}}"
    (data / "references.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    wiki_dir = Path(sys.argv[1])
    clusters, references = build(wiki_dir)
    add_official_members(clusters)
    refs_out = build_references(references)
    write_all(clusters, refs_out)
    json.dump(LOG, open(HERE / "migration-log.json", "w"), indent=1, ensure_ascii=False)
    n_models = sum(len(c["models"]) for c in clusters)
    print(f"{len(clusters)} clusters, {n_models} model entries, {len(TRANSIENTS)} transients, "
          f"{len(PROGRAMS)} programs, {len(refs_out)} references, {len(LOG)} log entries")
