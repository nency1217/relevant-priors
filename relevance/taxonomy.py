"""Radiology body-region and modality taxonomy.

Maps free-text study description tokens to canonical regions. Tuned against
the public eval split — keywords below include the abbreviated, lowercase,
and typo'd forms that show up in real RIS-exported descriptions
(e.g. "MAM" not just "MAMMO", "SPNE" typo, "CNTRST" for contrast).

Adjacency philosophy: the labeled data treats most "anatomically nearby"
regions as NOT relevant to each other. We keep adjacency only for pairs
the labels actually support:

  - cardiac <-> chest  (echo and chest CT cross-inform)
  - abdomen <-> pelvis (almost always co-imaged in CT)
  - intra-spine        (cspine/tspine/lspine all link)
  - intra-extremity    (proximal/distal joints in same limb)
  - intra-head         (brain/sinus/orbit/etc.)
  - PET / wholebody -> everything (full-body coverage)

We deliberately do NOT mark chest <-> abdomen, chest <-> tspine, or
breast <-> chest as adjacent — those generated thousands of false
positives against the public truth.
"""

# Canonical regions -> list of substring keywords. Matched against an
# uppercased, space-padded copy of the description, so " ABD " matches
# " ABD " but not "ABDUCTION".
REGION_KEYWORDS = {
    # ---- Head / neuro ----
    "brain": [
        "BRAIN", "CEREBRAL", "CEREBELLUM", "INTRACRANIAL", "STROKE",
        " CVA", " TIA", "ENCEPHAL", " EEG", "MRA HEAD", "CTA HEAD",
    ],
    "head": ["HEAD", "SKULL XR", "SKULL X-RAY", "CRANIAL", "CRANIUM"],
    "face": ["FACE", "FACIAL", "MAXILLOFACIAL", "MANDIBLE", "MAXILLA"],
    "sinus": ["SINUS", "SINUSES", "PARANASAL"],
    "orbit": ["ORBIT", "ORBITAL"],
    "iac": [" IAC", "INTERNAL AUDITORY", "TEMPORAL BONE"],
    "pituitary": ["PITUITARY", "SELLA"],
    "tmj": [" TMJ", "TEMPOROMANDIBULAR"],

    # ---- Neck ----
    "neck": [
        " NECK", "SOFT TISSUE NECK", "THYROID", "PAROTID", "LARYNX",
        "MRA NECK", "CTA NECK",
    ],

    # ---- Spine ----
    # NOTE: " L SPINE" must include the leading space — without it the
    # bare keyword "L SPINE" false-matches "cervicAL SPINE". Same for C/T.
    "cspine": [
        "C-SPINE", " C SPINE", "CERVICAL SPINE", "CSPINE", "C-SPN", " CSPN",
        "CERV SPINE", "CERVICAL SPNE", " C SPN",
    ],
    "tspine": [
        "T-SPINE", " T SPINE", "THORACIC SPINE", "TSPINE", "THORACIC SPN",
        " T SPN", "T-SPN",
    ],
    "lspine": [
        "L-SPINE", " L SPINE", "LUMBAR SPINE", "LSPINE", "LUMBOSACRAL",
        "LUMBAR SPNE", "LUMBAR SPN", " L SPN", "LS SPINE",
        "LUMBAR PUNCTURE", " LUMBAR ",
    ],
    "spine": ["SPINE", "VERTEBRAL", "MYELOGRAM", "SCOLIOSIS", " SPNE"],
    "sacrum": ["SACRUM", "SACRAL", "COCCYX", "SACROILIAC", "SI JOINT"],

    # ---- Chest / cardiac ----
    "chest": [
        "CHEST", " THORAX", " LUNG", "PULMONARY", "PUL PERFUSION",
        "MEDIASTINUM", "STERNUM", "THORACENTESIS",
    ],
    "cardiac": [
        "CARDIAC", "HEART", "CORONARY", " ECHO", "ECHOCARDIOGRA",
        "ECHOGRAM", " TTE", " TEE",
        "MYO PERF", "MYOCARDIAL", "NMMYO", "NM MYO",
        " MUGA", "STRESS TEST", "CALCIUM SCORE", "CORONARY CALC",
        " FFR ", "CT FFR",
    ],

    # ---- Abdomen ----
    "abdomen": [
        "ABDOMEN", "ABDOMINAL", "ABDOMINL", " ABD ", " ABD,",
        "ABD/", "ABD_",
        "LIVER", "HEPATIC", "SPLEEN", "PANCREAS",
        "KIDNEY", "RENAL", "NEPHROSTOMY", "NEPHRO", "UROGRAM",
        "GALLBLADDER", "BILIARY", "CHOLANGIO", "CHOLECYST",
        "GASTRIC", "STOMACH", "DUODEN",
        "SMALL BOWEL", "ENTEROGRAPHY", "ENTEROGRAM",
        "PERITONEAL", "RETROPERITONEAL", "PARACENTESIS",
        "GI SERIES", "BARIUM",
        "ESOPHAG", "COOKIE SWALLOW", "MODIFIED BARIUM", "SWALLOW",
        "LOOPOGRAM",
    ],

    # ---- Pelvis ----
    "pelvis": [
        "PELVIS", "PELVIC", " PEL ", " PEL,", "/PEL", "_PEL",
        "BLADDER", "PROSTATE", "UTERUS", "OVARY", "ADNEXA",
        "TRANSVAGINAL", "ENDOVAGINAL", "OB ULTRASOUND", " OB US",
        "TRANSRECTAL", " GYN",
    ],

    # ---- Upper extremity ----
    "shoulder": ["SHOULDER", "CLAVICLE", "SCAPULA", "AC JOINT", "GLENOID"],
    "humerus": ["HUMERUS", "UPPER ARM"],
    "elbow": ["ELBOW"],
    "forearm": ["FOREARM", " RADIUS ", " ULNA "],
    "wrist": ["WRIST", "CARPAL", "SCAPHOID"],
    "hand": [" HAND", "FINGER", "THUMB", "METACARPAL"],
    "upper_extremity_vascular": [
        "UP VENOUS", "UE VENOUS", "VENOUS UE",
        "UPPER EXTREMITY DOPPLER", "ARM DOPPLER", "VAS UE",
        "UE DOPPLER", "UPPER EXT DOPPL",
    ],

    # ---- Lower extremity ----
    "hip": [" HIP", "ACETABULUM"],
    "femur": ["FEMUR", " THIGH "],
    "knee": ["KNEE", "PATELLA"],
    "tibfib": ["TIB FIB", "TIB-FIB", "TIBIA", "FIBULA", "LOWER LEG"],
    "ankle": ["ANKLE"],
    "foot": [" FOOT", " FEET", " TOE", "CALCANEUS", "METATARSAL"],
    "lower_extremity_vascular": [
        "LE VENOUS", "VENOUS LE", "VENOUS LEG", "BILAT LEGS",
        " LE BI ", " LE DOPPLER", "LEG DOPPLER", "VAS LE",
        "VAS VENOUS", "VENOUS DOPPLER", "VENOUS IMAGING",
        "LOWER EXT DOPPL", "LOWER EXTREMITY DOPPLER",
    ],

    # ---- Breast ----
    # Many of these descriptions don't contain "MAM" or "BREAST" but are
    # 95-100% relevant when the current study is mammography — folded in
    # after label-distribution analysis on the public split.
    "breast": [
        " MAM ", " MAM,", "MAM ", "MAM/", " MAM-",
        "MAMM", "MAMMO", "MAMMOGRAM", "MAMMOGRAPHY",
        "TOMO BREAST", "BREAST", "TOMOSYNTHESIS", "R2 MAMMO",
        "ULTRASOUND BILAT SCREEN", "ULTRASOUND LT DIAG TARGET",
        "ULTRASOUND RT DIAG TARGET", "DIGITAL SCREENER",
        "STANDARD SCREENING - COMBO", "STANDARD SCREENING - CONVEN",
        "STANDARD SCREENING COMBO",
    ],

    # ---- Vascular (central) ----
    "vascular_chest": [
        "CTA CHEST", "PE PROTOCOL", "PULMONARY EMBOLISM",
        "AORTA CHEST", "AORTIC ARCH", "MRA CHEST",
    ],
    "vascular_abd": [
        "CTA ABDOMEN", "AORTA ABDOMEN", " AAA ", " AAA,",
        "RUNOFF", "MRA ABDOMEN",
    ],
    "carotid": ["CAROTID"],

    # ---- Whole-body / oncology ----
    "pet": [" PET", "POSITRON", " F18", " FDG"],
    "wholebody": [
        "WHOLE BODY", "SKELETAL SURVEY", "BONE SCAN",
        "SKULL TO THIGH", "SKULLTHIGH", "SKULL-THIGH",
        "EYES TO THIGH", "EYE TO THIGH",
    ],

    # ---- Bone density (own region: serial DEXA priors are relevant) ----
    "dexa": ["BONE DENSITY", "DEXA", " DXA", "DENSITOMETRY", "APPENDICULAR SKELETON"],

    # ---- Generic extremity (covers "CT LE LT", "CT LOWER EXTREM", etc.) ----
    "lower_extremity_generic": [
        " LE LT", " LE RT", " LE BI", "LOWER EXTREM", "LOWER EXT ",
        "LOWER RGT EXTREM", "LOWER LFT EXTREM",
    ],
    "upper_extremity_generic": [
        " UE LT", " UE RT", " UE BI", "UPPER EXTREM", "UPPER EXT ",
        "UPPER RGT EXTREM", "UPPER LFT EXTREM",
        "UPPR RGT EXTREM", "UPPR LFT EXTREM", "UPPR EXTREM",
    ],

    # ---- Ribs (mostly imaged with chest) ----
    "ribs": [" RIBS", " RIB ", " RIB,"],
}

# Adjacency pruned aggressively after analyzing public split FPs.
# NOTE: cardiac <-> chest is NOT included as a blanket adjacency. The labels
# treat (echo vs chest XR) as not relevant but (echo vs chest CT/MRI) as
# relevant. The predictor handles this with a modality-aware check.
ADJACENT_REGIONS = {
    "vascular_chest": {"chest", "cardiac"},

    # Lone abdomen <-> lone pelvis is only 8% True in the labels — they
    # are NOT adjacent. Direct overlap still fires for {abdomen,pelvis}
    # against either single region via plain intersect.
    "abdomen": {"vascular_abd"},
    "pelvis": {"vascular_abd", "sacrum", "hip"},
    "vascular_abd": {"abdomen", "pelvis"},

    # Spine segments do NOT cross-link in the labels — cspine vs lspine
    # is 0% relevant, cspine<->tspine and tspine<->lspine are ~36% relevant.
    # lspine <-> pelvis is also only 20% relevant; remove that too.
    "cspine": {"spine", "neck"},
    "tspine": {"spine"},
    "lspine": {"spine", "sacrum"},
    "spine": {"cspine", "tspine", "lspine", "sacrum"},
    "sacrum": {"lspine", "pelvis", "spine"},

    "head": {"brain", "face", "sinus", "orbit", "neck", "iac",
             "pituitary", "tmj"},
    "brain": {"head", "pituitary", "iac"},
    "face": {"head", "sinus", "orbit", "tmj"},
    "sinus": {"head", "face"},
    "orbit": {"head", "face"},
    "iac": {"head", "brain"},
    "pituitary": {"head", "brain"},
    "tmj": {"head", "face"},

    # Carotid US is its own thing — labels do not consider it relevant to
    # plain CT head or MRI brain. Keep it linked to neck only.
    "neck": {"head", "cspine", "carotid"},
    "carotid": {"neck"},

    "shoulder": {"humerus", "upper_extremity_generic"},
    "humerus": {"shoulder", "elbow", "upper_extremity_generic"},
    "elbow": {"humerus", "forearm", "upper_extremity_generic"},
    "forearm": {"elbow", "wrist", "upper_extremity_generic"},
    "wrist": {"forearm", "hand", "upper_extremity_generic"},
    "hand": {"wrist", "upper_extremity_generic"},
    "upper_extremity_generic": {
        "shoulder", "humerus", "elbow", "forearm", "wrist", "hand",
        "upper_extremity_vascular",
    },
    "upper_extremity_vascular": {"upper_extremity_generic"},

    "hip": {"pelvis", "femur", "lower_extremity_generic"},
    "femur": {"hip", "knee", "lower_extremity_generic"},
    "knee": {"femur", "tibfib", "lower_extremity_generic"},
    "tibfib": {"knee", "ankle", "lower_extremity_generic"},
    "ankle": {"tibfib", "foot", "lower_extremity_generic"},
    "foot": {"ankle", "lower_extremity_generic"},
    "lower_extremity_generic": {
        "hip", "femur", "knee", "tibfib", "ankle", "foot",
        "lower_extremity_vascular",
    },
    "lower_extremity_vascular": {"lower_extremity_generic"},

    # Ribs are imaged together with chest XR/CT.
    "ribs": {"chest"},
    "chest": {"vascular_chest", "ribs"},

    # PET / wholebody cover the major body cavities only — labels do not
    # treat PET as relevant to mammo, breast, or DEXA.
    "pet": {"chest", "abdomen", "pelvis", "cspine", "tspine", "lspine",
            "spine", "sacrum", "vascular_chest", "vascular_abd",
            "head", "brain", "neck", "wholebody"},
    "wholebody": {"chest", "abdomen", "pelvis", "cspine", "tspine", "lspine",
                  "spine", "sacrum", "head", "brain", "neck", "pet"},
}

MODALITY_KEYWORDS = {
    "MRI":   ["MRI", " MR ", " MRA ", " MRV ", "MAGNETIC RESONANCE"],
    "CT":    [" CT ", " CT,", " CT-", "/CT", "COMPUTED TOMOGRAPHY",
              " CTA ", " CTV "],
    "XR":    [" XR ", "X-RAY", "XRAY", " X RAY", "RADIOGRAPH",
              " 2 VIEW", " 3 VIEW", " 1V ", " 2V ", " 3V ", "FRONTAL"],
    "US":    ["ULTRASOUND", " US ", "SONOGRAM", "DOPPLER", " ECHO"],
    "MAMMO": ["MAMMO", "MAMMOGRAM", "MAMMOGRAPHY", " MAM ", "TOMO BREAST"],
    "PET":   [" PET", "POSITRON", " F18", " FDG"],
    "NM":    ["NUCLEAR", "BONE SCAN", " HIDA", "SCINTIGRAPHY", " MUGA",
              " NM ", "MYO PERF", "NMMYO"],
    "FLUORO": ["FLUORO", "FLUOROSCOPY", "BARIUM", "ESOPHAG"],
    "DEXA":  ["DEXA", "BONE DENSITY", "DENSITOMETRY"],
}
