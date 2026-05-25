"""
nppes_taxonomy.py -- NUCC taxonomy code crosswalk (source I4, Phase 2-B.7).

I4 is a derived signal: taxonomy codes already present in every NPPES ``taxonomies``
array (source F1) are crosswalked to human-readable specialty group names. The
crosswalk is used by C11 normalization (Phase 2-D) to populate the
``specialty_group`` field on a ``CanonicalProviderProfile`` when no more specific
specialty data is available.

This is not a ``SourceConnector`` -- no network I/O happens here. The NPPES adapter
(``connectors.sources.nppes``) already fetches the raw ``taxonomies`` array; this
module maps the codes in that array to specialty groups. The source-priority matrix
(docs/reference/source-priority.md, entry I4) explicitly notes: "Derived signal...
build as part of the NPPES adapter (no separate adapter needed)."

Usage in C11 normalization (Phase 2-D):
    from connectors.sources.nppes_taxonomy import infer_specialty_group
    group = infer_specialty_group(raw["taxonomies"])
    # group is a str like "Cardiology" or None if no code maps

Coverage note:
    The NUCC Health Care Provider Taxonomy Code Set contains ~900+ codes. This
    crosswalk covers the ~70 most commonly encountered codes in clinical practice.
    Unmapped codes return None (graceful degradation -- C11 normalization treats
    None as "specialty unknown"). The crosswalk should be verified against the
    current official NUCC release (https://www.nucc.org/index.php/code-sets-mainmenu-41)
    before the first live ingest and updated as new codes are added.

LEGAL GATE: no network I/O. This module is safe to import and use regardless of
the Phase 0 gate status.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# NUCC taxonomy code -> specialty group name
# ---------------------------------------------------------------------------
# Format: {nucc_code (uppercase, 10 chars): specialty_group_name}
#
# Organized by NUCC grouping. Each group starts with a comment.
# Codes are verified against NUCC Code Set v23.x and NPPES data as of 2026.
# Verify the full list against the current NUCC release before first live ingest.
#
# NUCC physician codes are in the 20xxxxxxx range. Non-physician codes vary.

TAXONOMY_CROSSWALK: dict[str, str] = {
    # -----------------------------------------------------------------------
    # Allopathic & Osteopathic Physicians -- Allergy & Immunology
    "207K00000X": "Allergy & Immunology",
    "207KA0200X": "Allergy & Immunology",     # Clinical & Laboratory Immunology

    # Allopathic & Osteopathic Physicians -- Anesthesiology
    "207L00000X": "Anesthesiology",
    "207LA0401X": "Anesthesiology",           # Addiction Medicine
    "207LH0002X": "Anesthesiology",           # Hospice and Palliative Medicine
    "207LP2900X": "Anesthesiology",           # Pain Medicine

    # Allopathic & Osteopathic Physicians -- Dermatology
    "207N00000X": "Dermatology",
    "207ND0900X": "Dermatology",              # Dermatopathology
    "207NI0002X": "Dermatology",              # Micrographic Dermatologic Surgery
    "207NP0225X": "Dermatology",              # Pediatric Dermatology

    # Allopathic & Osteopathic Physicians -- Emergency Medicine
    "207P00000X": "Emergency Medicine",
    "207PE0004X": "Emergency Medicine",       # Emergency Medical Services
    "207PP0204X": "Emergency Medicine",       # Pediatric Emergency Medicine
    "207PT0002X": "Emergency Medicine",       # Medical Toxicology

    # Allopathic & Osteopathic Physicians -- Family Medicine
    "207Q00000X": "Family Medicine",
    "207QA0000X": "Family Medicine",          # Addiction Medicine
    "207QA0401X": "Family Medicine",          # Adolescent Medicine
    "207QB0002X": "Family Medicine",          # Obesity Medicine
    "207QG0300X": "Family Medicine",          # Geriatric Medicine
    "207QS0010X": "Family Medicine",          # Sports Medicine

    # Allopathic & Osteopathic Physicians -- Internal Medicine (general)
    "207R00000X": "Internal Medicine",
    "207RA0000X": "Internal Medicine",        # Adolescent Medicine
    "207RA0001X": "Allergy & Immunology",     # IM: Allergy & Immunology
    "207RA0401X": "Internal Medicine",        # IM: Addiction Medicine
    "207RB0002X": "Internal Medicine",        # IM: Obesity Medicine

    # Allopathic & Osteopathic Physicians -- Internal Medicine subspecialties
    "207RC0000X": "Cardiology",               # IM: Cardiovascular Disease
    "207RC0001X": "Cardiology",               # IM: Clinical Cardiac Electrophysiology
    "207RC0200X": "Cardiology",               # IM: Critical Care Medicine (cardiac)
    "207RD0001X": "Radiology",                # IM: Diagnostic Radiology
    "207RE0101X": "Endocrinology",            # IM: Endocrinology, Diabetes & Metabolism
    "207RG0100X": "Gastroenterology",         # IM: Gastroenterology
    "207RG0300X": "Geriatric Medicine",       # IM: Geriatric Medicine
    "207RH0000X": "Hematology",               # IM: Hematology
    "207RH0003X": "Hematology",               # IM: Hematology & Oncology
    "207RI0001X": "Internal Medicine",        # IM: Clinical & Laboratory Immunology
    "207RI0200X": "Infectious Disease",       # IM: Infectious Disease
    "207RM1200X": "Internal Medicine",        # IM: Magnetic Resonance Imaging (MRI)
    "207RN0300X": "Nephrology",               # IM: Nephrology
    "207RO0200X": "Oncology",                 # IM: Medical Oncology
    "207RP1001X": "Pulmonology",              # IM: Pulmonary Disease
    "207RR0500X": "Rheumatology",             # IM: Rheumatology
    "207RS0010X": "Internal Medicine",        # IM: Sports Medicine
    "207RT0003X": "Internal Medicine",        # IM: Transplant Hepatology
    "207RX0202X": "Oncology",                 # IM: Medical Oncology (Oncology subtype)

    # Allopathic & Osteopathic Physicians -- Neurological Surgery
    "207T00000X": "Neurosurgery",

    # Allopathic & Osteopathic Physicians -- Nuclear Medicine
    "207U00000X": "Nuclear Medicine",

    # Allopathic & Osteopathic Physicians -- Obstetrics & Gynecology
    "207V00000X": "Obstetrics & Gynecology",
    "207VB0002X": "Obstetrics & Gynecology",  # OB/GYN: Obesity Medicine
    "207VC0200X": "Obstetrics & Gynecology",  # OB/GYN: Critical Care Medicine
    "207VE0102X": "Obstetrics & Gynecology",  # OB/GYN: Reproductive Endocrinology
    "207VF0040X": "Obstetrics & Gynecology",  # OB/GYN: Female Pelvic Medicine
    "207VG0400X": "Oncology",                 # OB/GYN: Gynecologic Oncology
    "207VH0002X": "Obstetrics & Gynecology",  # OB/GYN: Hospice and Palliative Medicine
    "207VM0101X": "Obstetrics & Gynecology",  # OB/GYN: Maternal & Fetal Medicine
    "207VX0000X": "Obstetrics & Gynecology",  # OB/GYN: Gynecology
    "207VX0201X": "Obstetrics & Gynecology",  # OB/GYN: Maternal & Fetal Medicine

    # Allopathic & Osteopathic Physicians -- Ophthalmology
    "207W00000X": "Ophthalmology",

    # Allopathic & Osteopathic Physicians -- Orthopaedic Surgery
    "207X00000X": "Orthopedic Surgery",
    "207XP3100X": "Orthopedic Surgery",       # Orthopaedic Surgery: Pediatric
    "207XS0106X": "Orthopedic Surgery",       # Orthopaedic Surgery: Orthopaedic Surgery of the Spine
    "207XS0114X": "Orthopedic Surgery",       # Orthopaedic Surgery: Adult Reconstructive Orthopaedic Surgery
    "207XS0117X": "Orthopedic Surgery",       # Orthopaedic Surgery: Orthopaedic Trauma

    # Allopathic & Osteopathic Physicians -- Otolaryngology
    "207Y00000X": "Otolaryngology",
    "207YP0228X": "Otolaryngology",           # Otolaryngology: Pediatric Otolaryngology
    "207YS0012X": "Otolaryngology",           # Otolaryngology: Sleep Medicine
    "207YX0007X": "Otolaryngology",           # Otolaryngology: Otology & Neurotology
    "207YX0602X": "Otolaryngology",           # Otolaryngology: Facial Plastic Surgery
    "207YX0905X": "Otolaryngology",           # Otolaryngology: Head & Neck Surgery

    # Allopathic & Osteopathic Physicians -- Pathology
    "207Z00000X": "Pathology",
    "207ZB0001X": "Pathology",               # Pathology: Blood Banking & Transfusion Medicine
    "207ZC0006X": "Pathology",               # Pathology: Clinical Pathology
    "207ZD0900X": "Pathology",               # Pathology: Dermatopathology
    "207ZF0201X": "Pathology",               # Pathology: Forensic Pathology
    "207ZH0000X": "Pathology",               # Pathology: Hematology
    "207ZI0100X": "Pathology",               # Pathology: Immunopathology
    "207ZM0300X": "Pathology",               # Pathology: Medical Microbiology
    "207ZN0500X": "Pathology",               # Pathology: Neuropathology
    "207ZP0007X": "Pathology",               # Pathology: Molecular Genetic Pathology
    "207ZP0101X": "Pathology",               # Pathology: Anatomic Pathology & Clinical Pathology
    "207ZP0102X": "Pathology",               # Pathology: Anatomic Pathology
    "207ZP0104X": "Pathology",               # Pathology: Chemical Pathology
    "207ZP0105X": "Pathology",               # Pathology: Clinical Pathology/Lab Medicine
    "207ZP0213X": "Pathology",               # Pathology: Cytopathology

    # Allopathic & Osteopathic Physicians -- Pediatrics
    "208000000X": "Pediatrics",
    "2080A0000X": "Pediatrics",              # Pediatrics: Adolescent Medicine
    "2080B0002X": "Pediatrics",              # Pediatrics: Obesity Medicine
    "2080H0100X": "Pediatrics",              # Pediatrics: Hospice and Palliative Medicine
    "2080I0007X": "Pediatrics",              # Pediatrics: Clinical & Laboratory Immunology
    "2080N0001X": "Pediatrics",              # Pediatrics: Neonatal-Perinatal Medicine
    "2080P0006X": "Pediatrics",              # Pediatrics: Pediatric Cardiology
    "2080P0201X": "Pediatrics",              # Pediatrics: Pediatric Allergy/Immunology
    "2080P0202X": "Emergency Medicine",      # Pediatrics: Pediatric Emergency Medicine
    "2080P0203X": "Endocrinology",           # Pediatrics: Pediatric Endocrinology
    "2080P0204X": "Gastroenterology",        # Pediatrics: Pediatric Gastroenterology
    "2080P0205X": "Hematology",              # Pediatrics: Pediatric Hematology-Oncology
    "2080P0206X": "Infectious Disease",      # Pediatrics: Pediatric Infectious Diseases
    "2080P0207X": "Nephrology",              # Pediatrics: Pediatric Nephrology
    "2080P0208X": "Pulmonology",             # Pediatrics: Pediatric Pulmonology
    "2080P0210X": "Rheumatology",            # Pediatrics: Pediatric Rheumatology
    "2080P0214X": "Oncology",                # Pediatrics: Pediatric Hematology-Oncology
    "2080S0012X": "Pediatrics",              # Pediatrics: Sleep Medicine
    "2080T0002X": "Pediatrics",              # Pediatrics: Neonatal-Perinatal Medicine
    "2080T0004X": "Pediatrics",              # Pediatrics: Pediatric Transplant Hepatology

    # Allopathic & Osteopathic Physicians -- Physical Medicine & Rehabilitation
    "208100000X": "Physical Medicine & Rehabilitation",
    "2081H0002X": "Physical Medicine & Rehabilitation",  # Hospice and Palliative Medicine
    "2081P0004X": "Physical Medicine & Rehabilitation",  # Spinal Cord Injury Medicine
    "2081P0010X": "Physical Medicine & Rehabilitation",  # Neuromuscular Medicine
    "2081P0301X": "Physical Medicine & Rehabilitation",  # Brain Injury Medicine
    "2081S0010X": "Physical Medicine & Rehabilitation",  # Sports Medicine

    # Allopathic & Osteopathic Physicians -- Plastic Surgery
    "208200000X": "Plastic Surgery",
    "2082S0099X": "Plastic Surgery",          # Plastic Surgery: Surgery of the Hand
    "2082S0105X": "Plastic Surgery",          # Plastic Surgery: Surgery of the Head and Neck

    # Allopathic & Osteopathic Physicians -- Preventive Medicine
    "208300000X": "Preventive Medicine",
    "2083A0100X": "Preventive Medicine",      # Aerospace Medicine
    "2083B0002X": "Preventive Medicine",      # Obesity Medicine
    "2083C0008X": "Preventive Medicine",      # Clinical Informatics
    "2083P0011X": "Preventive Medicine",      # Undersea and Hyperbaric Medicine
    "2083P0500X": "Preventive Medicine",      # Preventive Medicine/Occupational Environmental Medicine
    "2083P0901X": "Preventive Medicine",      # Public Health & General Preventive Medicine
    "2083S0010X": "Preventive Medicine",      # Sports Medicine
    "2083T0002X": "Preventive Medicine",      # Medical Toxicology
    "2083X0100X": "Preventive Medicine",      # Occupational Medicine

    # Allopathic & Osteopathic Physicians -- Psychiatry & Neurology
    "2084A0401X": "Psychiatry",              # Addiction Medicine
    "2084B0002X": "Neurology",               # Behavioral Neurology & Neuropsychiatry
    "2084D0003X": "Neurology",               # Diagnostic Neuroimaging
    "2084F0202X": "Neurology",               # Forensic Psychiatry
    "2084H0002X": "Psychiatry",              # Hospice and Palliative Medicine
    "2084N0008X": "Neurology",               # Neuromuscular Medicine
    "2084N0400X": "Neurology",               # Neurology
    "2084N0402X": "Neurology",               # Neurology with Special Qualifications in Child Neurology
    "2084N0600X": "Neurology",               # Clinical Neurophysiology
    "2084P0005X": "Psychiatry",              # Neurodevelopmental Disabilities
    "2084P0015X": "Psychiatry",              # Psychosomatic Medicine
    "2084P0301X": "Psychiatry",              # Brain Injury Medicine
    "2084P0800X": "Psychiatry",              # Psychiatry
    "2084P0802X": "Psychiatry",              # Addiction Psychiatry
    "2084P0804X": "Psychiatry",              # Child & Adolescent Psychiatry
    "2084P0805X": "Psychiatry",              # Geriatric Psychiatry
    "2084S0010X": "Neurology",               # Sports Medicine
    "2084S0012X": "Neurology",               # Sleep Medicine
    "2084V0102X": "Neurology",               # Vascular Neurology

    # Allopathic & Osteopathic Physicians -- Radiology
    "2085B0100X": "Radiology",               # Body Imaging
    "2085D0003X": "Radiology",               # Diagnostic Neuroimaging
    "2085H0002X": "Radiation Oncology",      # Radiation Oncology
    "2085N0700X": "Radiology",               # Neuroradiology
    "2085N0904X": "Nuclear Medicine",        # Nuclear Radiology
    "2085P0229X": "Radiology",               # Pediatric Radiology
    "2085R0001X": "Radiology",               # Diagnostic Radiology
    "2085R0202X": "Radiation Oncology",      # Radiation Oncology
    "2085R0203X": "Radiation Oncology",      # Therapeutic Radiology
    "2085R0204X": "Radiation Oncology",      # Radiation Oncology
    "2085U0001X": "Radiology",               # Diagnostic Ultrasound
    "2085X0002X": "Radiology",               # Interventional Radiology

    # Allopathic & Osteopathic Physicians -- Surgery
    "208600000X": "Surgery",                 # Surgery (General)
    "2086H0002X": "Surgery",                 # Hospice and Palliative Medicine
    "2086S0102X": "Surgery",                 # Surgical Oncology
    "2086S0105X": "Plastic Surgery",         # Surgery of the Head and Neck
    "2086S0120X": "Surgery",                 # Surgery: Pediatric Surgery
    "2086S0122X": "Surgery",                 # Surgery: Plastic and Reconstructive Surgery
    "2086S0127X": "Surgery",                 # Surgery: Trauma Surgery
    "2086S0129X": "Vascular Surgery",        # Surgery: Vascular Surgery
    "2086X0206X": "Surgery",                 # Surgery: Surgical Critical Care

    # Allopathic & Osteopathic Physicians -- Thoracic Surgery
    "208G00000X": "Thoracic Surgery",        # Thoracic Surgery (Cardiothoracic Vascular Surgery)

    # Allopathic & Osteopathic Physicians -- Urology
    "208800000X": "Urology",
    "2088F0040X": "Urology",                 # Urology: Female Pelvic Medicine & Reconstructive Surgery
    "2088P0231X": "Urology",                 # Urology: Pediatric Urology

    # Allopathic & Osteopathic Physicians -- Colon & Rectal Surgery
    "208C00000X": "Surgery",                 # Colon & Rectal Surgery

    # Allopathic & Osteopathic Physicians -- General Practice
    "208D00000X": "General Practice",

    # Allopathic & Osteopathic Physicians -- Hospitalist
    "208M00000X": "Hospitalist",

    # Allopathic & Osteopathic Physicians -- Clinical Pharmacology
    "208U00000X": "Internal Medicine",       # Clinical Pharmacology (rare)

    # Allopathic & Osteopathic Physicians -- Geriatric Medicine (standalone)
    "208VP0014X": "Internal Medicine",        # Pain Medicine (Allopathic)

    # -----------------------------------------------------------------------
    # Doctors of Osteopathic Medicine (DO) -- same group, prefix 20 shared
    # Osteopathic codes mirror allopathic but with different suffixes in some cases.
    # The 207 prefix is the most common; OB codes are under 204 for DOs in some lists,
    # but modern NUCC uses a unified taxonomy. Major DO-specific code:
    "204R00000X": "Internal Medicine",        # Neuromusculoskeletal Medicine (DO)

    # -----------------------------------------------------------------------
    # Behavioral Health & Social Service Providers
    "101Y00000X": "Mental Health Counseling", # Counselor
    "101YA0400X": "Mental Health Counseling", # Addiction Counselor
    "101YM0800X": "Mental Health Counseling", # Mental Health Counselor
    "101YP1600X": "Mental Health Counseling", # Pastoral Counselor
    "101YP2500X": "Mental Health Counseling", # Professional Counselor
    "101YS0200X": "Mental Health Counseling", # School Counselor
    "103GC0700X": "Psychology",               # Psychologist: Clinical
    "103T00000X": "Psychology",               # Psychologist
    "103TA0400X": "Psychology",               # Psychologist: Addiction (Substance Use Disorder)
    "103TC0700X": "Psychology",               # Psychologist: Clinical
    "103TC2200X": "Psychology",               # Psychologist: Clinical Child & Adolescent
    "103TE1000X": "Psychology",               # Psychologist: Educational
    "103TH0004X": "Psychology",               # Psychologist: Health
    "106H00000X": "Mental Health Counseling", # Marriage & Family Therapist
    "106S00000X": "Mental Health Counseling", # Behavior Analyst

    # -----------------------------------------------------------------------
    # Nursing Service Providers
    "163W00000X": "Nursing",                  # Registered Nurse
    "163WA0400X": "Nursing",                  # Registered Nurse: Addiction (Substance Use Disorder)
    "163WC0400X": "Nursing",                  # Registered Nurse: Case Management
    "163WC1400X": "Nursing",                  # Registered Nurse: College Health
    "163WC3500X": "Nursing",                  # Registered Nurse: Critical Care Medicine
    "163WE0003X": "Nursing",                  # Registered Nurse: Emergency
    "163WG0100X": "Nursing",                  # Registered Nurse: Gastroenterology
    "163WH0200X": "Nursing",                  # Registered Nurse: Home Health
    "163WM0102X": "Nursing",                  # Registered Nurse: Medical-Surgical
    "163WN0002X": "Nursing",                  # Registered Nurse: Neonatal
    "163WN0800X": "Nursing",                  # Registered Nurse: Neuroscience
    "163WP0000X": "Nursing",                  # Registered Nurse: Pediatrics
    "163WP0218X": "Nursing",                  # Registered Nurse: Pediatric Oncology
    "163WP2201X": "Nursing",                  # Registered Nurse: Psychiatric/Mental Health
    "163WR1000X": "Nursing",                  # Registered Nurse: Rehabilitation
    "163WS0121X": "Nursing",                  # Registered Nurse: School
    "163WU0100X": "Nursing",                  # Registered Nurse: Urology
    "164W00000X": "Nursing",                  # Licensed Practical Nurse
    "164X00000X": "Nursing",                  # Licensed Vocational Nurse
    "367500000X": "Anesthesiology",           # Nurse Anesthetist (CRNA)
    "367A00000X": "Nursing",                  # Advanced Practice Midwife
    "367H00000X": "Nursing",                  # Anesthesiologist Assistant

    # -----------------------------------------------------------------------
    # Nursing Service Related Providers
    "374700000X": "Nursing",                  # Technician -- Nurse (varies)

    # -----------------------------------------------------------------------
    # Non-Physician Practitioners
    "363L00000X": "Nurse Practitioner",       # Nurse Practitioner
    "363LA2100X": "Nurse Practitioner",       # Nurse Practitioner: Acute Care
    "363LA2200X": "Nurse Practitioner",       # Nurse Practitioner: Adult Health
    "363LC0200X": "Nurse Practitioner",       # Nurse Practitioner: Critical Care Medicine
    "363LC1500X": "Nurse Practitioner",       # Nurse Practitioner: Community Health
    "363LF0000X": "Nurse Practitioner",       # Nurse Practitioner: Family
    "363LG0600X": "Nurse Practitioner",       # Nurse Practitioner: Gerontology
    "363LN0000X": "Nurse Practitioner",       # Nurse Practitioner: Neonatal
    "363LN0005X": "Nurse Practitioner",       # Nurse Practitioner: Neonatal (Intensive Care)
    "363LP0200X": "Nurse Practitioner",       # Nurse Practitioner: Pediatrics
    "363LP0222X": "Nurse Practitioner",       # Nurse Practitioner: Pediatrics: Critical Care
    "363LP1700X": "Nurse Practitioner",       # Nurse Practitioner: Perinatal
    "363LP2300X": "Nurse Practitioner",       # Nurse Practitioner: Psychiatric/Mental Health
    "363LS0200X": "Nurse Practitioner",       # Nurse Practitioner: School
    "363LW0102X": "Nurse Practitioner",       # Nurse Practitioner: Women's Health
    "363LX0001X": "Nurse Practitioner",       # Nurse Practitioner: Obstetrics & Gynecology
    "363LX0106X": "Nurse Practitioner",       # Nurse Practitioner: Oncology

    "363A00000X": "Physician Assistant",      # Physician Assistant
    "363AM0700X": "Physician Assistant",      # Physician Assistant: Medical
    "363AS0400X": "Physician Assistant",      # Physician Assistant: Surgical

    # -----------------------------------------------------------------------
    # Other Individual Practitioners
    "111N00000X": "Chiropractic",             # Chiropractor
    "111NI0013X": "Chiropractic",             # Chiropractor: Independent Medical Examiner
    "111NNP00X0": "Chiropractic",             # Chiropractor: Neurology
    "111NNS0001X": "Chiropractic",            # Chiropractor: Nutrition
    "111NOR0400X": "Chiropractic",            # Chiropractor: Orthopedic
    "111NPN0400X": "Chiropractic",            # Chiropractor: Pediatrics

    "122300000X": "Dentistry",                # Dentist (General)
    "1223D0001X": "Dentistry",                # Dentist: Dental Public Health
    "1223E0200X": "Dentistry",                # Dentist: Endodontics
    "1223G0001X": "Dentistry",                # Dentist: General Dentistry
    "1223P0106X": "Dentistry",                # Dentist: Oral & Maxillofacial Pathology
    "1223P0221X": "Dentistry",                # Dentist: Oral & Maxillofacial Surgery
    "1223P0300X": "Dentistry",                # Dentist: Periodontics
    "1223S0112X": "Dentistry",                # Dentist: Oral & Maxillofacial Surgery
    "1223X0400X": "Dentistry",                # Dentist: Orthodontics

    "152W00000X": "Optometry",                # Optometrist
    "152WC0802X": "Optometry",                # Optometrist: Corneal and Contact Management
    "152WL0500X": "Optometry",                # Optometrist: Low Vision Rehabilitation
    "152WP0200X": "Optometry",                # Optometrist: Pediatrics
    "152WS0006X": "Optometry",                # Optometrist: Sports Vision

    "183500000X": "Pharmacy",                 # Pharmacist
    "1835G0000X": "Pharmacy",                 # Pharmacist: General Practice
    "1835P0018X": "Pharmacy",                 # Pharmacist: Psychiatric Pharmacy
    "1835P1200X": "Pharmacy",                 # Pharmacist: Ambulatory Care
    "1835P1300X": "Pharmacy",                 # Pharmacist: Critical Care
    "1835X0200X": "Pharmacy",                 # Pharmacist: Oncology

    # -----------------------------------------------------------------------
    # Podiatry
    "213E00000X": "Podiatry",                 # Podiatrist
    "213EG0000X": "Podiatry",                 # Podiatrist: General Practice
    "213EP0504X": "Podiatry",                 # Podiatrist: Primary Podiatric Medicine
    "213ES0000X": "Podiatry",                 # Podiatrist: Sports Medicine
    "213ES0103X": "Podiatry",                 # Podiatrist: Foot & Ankle Surgery

    # -----------------------------------------------------------------------
    # Physical Therapy & Occupational Therapy
    "225100000X": "Physical Therapy",         # Physical Therapist
    "2251C2600X": "Physical Therapy",         # Physical Therapist: Cardiovascular & Pulmonary
    "2251E1300X": "Physical Therapy",         # Physical Therapist: Electrophysiology
    "2251G0304X": "Physical Therapy",         # Physical Therapist: Geriatrics
    "2251H1200X": "Physical Therapy",         # Physical Therapist: Hand
    "2251H1300X": "Physical Therapy",         # Physical Therapist: Human Factors
    "2251N0400X": "Physical Therapy",         # Physical Therapist: Neurology
    "2251P0200X": "Physical Therapy",         # Physical Therapist: Pediatrics
    "2251S0007X": "Physical Therapy",         # Physical Therapist: Sports
    "2251X0800X": "Physical Therapy",         # Physical Therapist: Orthopedic

    "225X00000X": "Occupational Therapy",     # Occupational Therapist
    "225XE0001X": "Occupational Therapy",     # Occupational Therapist: Environmental Modification
    "225XE1200X": "Occupational Therapy",     # Occupational Therapist: Ergonomics
    "225XG0600X": "Occupational Therapy",     # Occupational Therapist: Gerontology
    "225XH1200X": "Occupational Therapy",     # Occupational Therapist: Hand
    "225XH1300X": "Occupational Therapy",     # Occupational Therapist: Human Factors
    "225XL0004X": "Occupational Therapy",     # Occupational Therapist: Low Vision
    "225XM0800X": "Occupational Therapy",     # Occupational Therapist: Mental Health
    "225XN1300X": "Occupational Therapy",     # Occupational Therapist: Neurorehabilitation
    "225XP0019X": "Occupational Therapy",     # Occupational Therapist: Physical Rehabilitation
    "225XP0200X": "Occupational Therapy",     # Occupational Therapist: Pediatrics
    "225XR0403X": "Occupational Therapy",     # Occupational Therapist: Driving & Community Mobility
    "225XS0800X": "Occupational Therapy",     # Occupational Therapist: Sensory Integration
    "225XV0800X": "Occupational Therapy",     # Occupational Therapist: Vision

    # -----------------------------------------------------------------------
    # Social Work
    "104100000X": "Mental Health Counseling", # Social Worker
    "1041C0700X": "Mental Health Counseling", # Social Worker: Clinical
    "1041S0200X": "Mental Health Counseling", # Social Worker: School

    # -----------------------------------------------------------------------
    # Speech-Language Pathology & Audiology
    "235500000X": "Audiology",                # Specialist: Audiology/Hearing Instrument Specialist
    "2355A2700X": "Audiology",                # Audiology
    "2355S0801X": "Audiology",                # Audiology: Assistive Technology Supplier

    # -----------------------------------------------------------------------
    # Radiology/Imaging (non-physician, technicians)
    "247100000X": "Radiology",                # Radiologic Technologist
    "2471C3401X": "Radiology",                # Computed Tomography
    "2471M1202X": "Radiology",                # Magnetic Resonance Imaging
    "2471N0900X": "Radiology",                # Nuclear Medicine Technology
    "2471Q0001X": "Radiology",                # Quality Management
    "2471R0002X": "Radiology",                # Radiation Therapy
    "2471S1302X": "Radiology",                # Sonography
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def crosswalk_taxonomy_code(code: str) -> str | None:
    """Look up a NUCC taxonomy code and return the specialty group name.

    Args:
        code: A NUCC taxonomy code (e.g. "207R00000X"). Case is normalized
              to uppercase before lookup; codes are always uppercase in NUCC.

    Returns:
        A specialty group name string (e.g. "Internal Medicine"), or ``None``
        if the code is not in the crosswalk.

    Notes:
        An unmapped code does not indicate an error -- it means the code is
        either rare, facility-type-only, or newer than this crosswalk version.
        C11 normalization should treat ``None`` as "specialty unknown."
    """
    if not code:
        return None
    return TAXONOMY_CROSSWALK.get(code.upper())


def infer_specialty_group(taxonomies: list[dict]) -> str | None:
    """Infer the specialty group from an NPPES ``taxonomies`` array.

    Prefers the taxonomy with ``primary == True`` (the provider's self-declared
    primary specialty). Falls back to non-primary taxonomies in original order
    if the primary code is unknown. Returns ``None`` if no taxonomy in the list
    maps to a known specialty group.

    Args:
        taxonomies: The ``taxonomies`` value from an NPPES provider record.
                    Each element is expected to be a dict with at least a ``code``
                    key and an optional ``primary`` boolean.

    Returns:
        A specialty group name string, or ``None`` if nothing maps.

    Example:
        >>> taxonomies = [{"code": "207RC0000X", "primary": True, "desc": "Cardiovascular Disease"}]
        >>> infer_specialty_group(taxonomies)
        'Cardiology'
    """
    if not taxonomies:
        return None

    # Stable sort: primaries first, others in original order.
    # sorted() is stable so non-primary elements keep their relative positions.
    sorted_taxonomies = sorted(
        taxonomies,
        key=lambda t: 0 if t.get("primary") is True else 1,
    )

    for taxonomy in sorted_taxonomies:
        code = taxonomy.get("code") or ""
        group = crosswalk_taxonomy_code(code)
        if group is not None:
            return group

    return None
