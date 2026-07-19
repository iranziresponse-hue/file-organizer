"""Verified Makerere University college, school, and undergraduate programme
structure, sourced from mak.ac.ug and each college's own official site.

Colleges and schools were confirmed directly against
https://www.mak.ac.ug/study-mak/colleges-departments plus each college's
own site (cross-checked individually for School of Public Health, School
of Law, EASLIS, and the Institute of Gender and Development Studies, since
sources disagreed on where those sit). Makerere University Business School
(MUBS) is deliberately excluded: despite the name, it is a separate,
affiliated public institution, not a constituent college of Makerere.

Programme names were researched per college, directly from each college's
own "undergraduate programmes" page (caes.mak.ac.ug, bams.mak.ac.ug,
cocis.mak.ac.ug, cees.mak.ac.ug, cedat.mak.ac.ug, chs.mak.ac.ug,
chuss.mak.ac.ug, cns.mak.ac.ug, covab.mak.ac.ug, law.mak.ac.ug), or the
Academic Registrar's official 2025/26 undergraduate admissions notice where
a college's own site had no clean programme list. Programmes described on
a college's own site as "proposed," "pending approval," or "in the process
of starting" (i.e. not yet confirmed as actually running) are deliberately
left out.

Most programmes below are grouped under the school their name or governing
department obviously matches (e.g. an Engineering degree under School of
Engineering). A handful of school-level groupings are the closest
reasonable fit rather than a fact stated verbatim on an official page --
those are marked "inferred" in the comment above the entry. The programme
NAME itself is always sourced from an official page either way; only the
school it's filed under carries that caveat for a few entries. Where a
college's site did not break programmes down by school at all (CEDAT,
CEES beyond one confirmed entry, most of CHUSS), that inference is based
on matching the programme's subject area to the department list already
confirmed on the official colleges-departments page.

This module deliberately stops at the programme level. Course units per
semester are not included here: those come from the student, entered
against the exact real timetable they were actually given for the semester
they are currently in, since that is the one piece of this hierarchy that
changes every semester and that only the student can know for certain.
"""

COLLEGES = [
    {
        "code": "CAES",
        "name": "College of Agricultural and Environmental Sciences",
        "schools": [
            {
                "name": "School of Agricultural Sciences",
                "programmes": [
                    "Bachelor of Science in Agriculture",
                    "Bachelor of Science in Agricultural Land Use and Management",
                    "Bachelor of Agribusiness Management",
                    "Bachelor of Science in Horticulture",
                    "Bachelor of Agricultural and Rural Innovation",
                ],
            },
            {
                "name": "School of Forestry, Environmental and Geographical Sciences",
                "programmes": [
                    "Bachelor of Environmental Science",
                    "Bachelor of Science in Forestry",
                    "Bachelor of Geographical Sciences",
                    "Bachelor of Science in Meteorology",
                    "Bachelor of Tourism and Hospitality Management",
                ],
            },
            {
                "name": "School of Food Technology, Nutrition and Bio-engineering",
                "programmes": [
                    "Bachelor of Science in Agricultural Engineering",
                    "Bachelor of Science in Food Science and Technology",
                    "Bachelor of Science in Human Nutrition and Dietetics",
                ],
            },
        ],
    },
    {
        "code": "COBAMS",
        "name": "College of Business and Management Sciences",
        "schools": [
            {
                "name": "School of Economics",
                "programmes": [
                    "Bachelor of Arts in Economics",
                    "Bachelor of Arts in Development Economics",
                ],
            },
            {
                "name": "School of Business",
                "programmes": [
                    "Bachelor of Commerce",
                    "Bachelor of Business Administration",
                ],
            },
            {
                "name": "School of Statistics and Planning",
                "programmes": [
                    "Bachelor of Statistics",
                    "Bachelor of Science in Actuarial Science",
                    "Bachelor of Science in Business Statistics",
                    "Bachelor of Science in Population Studies",
                    "Bachelor of Science in Quantitative Economics",
                ],
            },
        ],
    },
    {
        "code": "COCIS",
        "name": "College of Computing and Information Sciences",
        "schools": [
            {
                "name": "School of Computing and Informatics Technology",
                "programmes": [
                    "Bachelor of Science in Computer Science",
                    "Bachelor of Information Systems and Technology",
                    "Bachelor of Science in Software Engineering",
                ],
            },
            {
                "name": "East African School of Library and Information Science",
                "programmes": [
                    "Bachelor of Library and Information Science",
                    "Bachelor of Records and Archives Management",
                ],
            },
        ],
    },
    {
        "code": "CEES",
        "name": "College of Education and External Studies",
        "schools": [
            {
                # CEES's own site repeats this same list on the college-wide
                # page, the "all courses" page, and the School of Education
                # page itself, with no distinct per-school breakdown beyond
                # what's noted for the other two schools below.
                "name": "School of Education",
                "programmes": [
                    "Bachelor of Arts with Education",
                    "Bachelor of Science with Education",
                    "Bachelor of Education",
                    "Bachelor of Medical Education",
                    "Bachelor of Youth Development Work",
                ],
            },
            {
                "name": "School of Distance and Lifelong Learning",
                "programmes": [
                    "Bachelor of Adult and Community Education",
                ],
            },
            {
                # Confirmed on this school's own page: postgraduate only.
                "name": "East African School of Higher Education Studies and Development",
                "programmes": [],
            },
        ],
    },
    {
        "code": "CEDAT",
        "name": "College of Engineering, Design, Art and Technology",
        "schools": [
            {
                # School-level grouping inferred from CEDAT's confirmed
                # department list (Dept of Civil and Environmental
                # Engineering, Dept of Electrical and Computer Engineering,
                # Dept of Mechanical Engineering all sit under this school),
                # not stated per-programme on CEDAT's own programmes page.
                "name": "School of Engineering",
                "programmes": [
                    "Bachelor of Science in Civil Engineering",
                    "Bachelor of Science in Electrical Engineering",
                    "Bachelor of Science in Mechanical Engineering",
                    "Bachelor of Computer and Communications Engineering",
                ],
            },
            {
                # Inferred the same way, from the Built Environment school's
                # confirmed departments (Architecture and Physical Planning,
                # Construction Economics and Management, Geomatics and Land
                # Management).
                "name": "School of the Built Environment",
                "programmes": [
                    "Bachelor of Architecture",
                    "Bachelor of Urban and Regional Planning",
                    "Bachelor of Science in Valuation",
                    "Bachelor of Science in Quantity Surveying",
                    "Bachelor of Science in Quantity Surveying and Geomatics",
                ],
            },
            {
                # Inferred from this school's confirmed departments (Fine
                # Art, Visual Communication Design and Multi-media,
                # Industrial Art and Applied Design).
                "name": "Margaret Trowell School of Industrial and Fine Art",
                "programmes": [
                    "Bachelor of Fine Art",
                    "Bachelor of Industrial and Applied Design",
                    "Bachelor of Visual Communication, Design and Multimedia",
                ],
            },
        ],
    },
    {
        "code": "CHS",
        "name": "College of Health Sciences",
        "schools": [
            {
                "name": "School of Medicine",
                "programmes": [
                    "Bachelor of Medicine and Bachelor of Surgery",
                    "Bachelor of Science in Medical Radiography",
                    "Bachelor of Science in Speech and Language Therapy",
                ],
            },
            {
                "name": "School of Biomedical Sciences",
                "programmes": [
                    "Bachelor of Science in Biomedical Engineering",
                    "Bachelor of Science in Biomedical Sciences",
                    "Bachelor of Cytotechnology",
                ],
            },
            {
                # Dentistry programmes are filed here (not under a separate
                # "School of Dentistry") to match the official college
                # structure page, which lists Dentistry as a department of
                # this school; a couple of CHS's own secondary pages
                # inconsistently show it as a separate school.
                "name": "School of Health Sciences",
                "programmes": [
                    "Bachelor of Pharmacy",
                    "Bachelor of Science in Nursing",
                    "Bachelor of Optometry",
                    "Bachelor of Dental Surgery",
                    "Bachelor of Science in Dental Laboratory Technology",
                ],
            },
            {
                "name": "School of Public Health",
                "programmes": [
                    "Bachelor of Environmental Health Science",
                ],
            },
        ],
    },
    {
        "code": "CHUSS",
        "name": "College of Humanities and Social Sciences",
        "schools": [
            {
                # Development Studies, Performing Arts and Film are
                # confirmed departments of this school.
                "name": "School of Liberal and Performing Arts",
                "programmes": [
                    "Bachelor of Development Studies",
                    "Bachelor of Arts in Theatre and Film",
                    "Bachelor of Arts in Drama and Film",
                    "Bachelor of Arts in Music",
                    "Bachelor of Defence Studies",
                ],
            },
            {
                # Journalism and Communication, European and Oriental
                # Languages are confirmed departments of this school.
                "name": "School of Languages, Literature and Communication",
                "programmes": [
                    "Bachelor of Journalism and Communication",
                    "Bachelor of Chinese and Asian Studies",
                ],
            },
            {
                # Mental Health and Community Psychology, and Educational
                # Organizational and Social Psychology are the confirmed
                # departments here; the two programmes below are filed
                # under this school by name match to those departments.
                "name": "School of Psychology",
                "programmes": [
                    "Bachelor of Community Psychology",
                    "Bachelor of Industrial and Organisational Psychology",
                ],
            },
            {
                # Social Work and Social Administration is a confirmed
                # department here (exact name match). The remaining three
                # entries are filed here as the closest reasonable fit for
                # general social-science degrees, not a confirmed per-
                # programme department match.
                "name": "School of Social Sciences",
                "programmes": [
                    "Bachelor of Social Work and Social Administration",
                    "Bachelor of Arts in Social Sciences",
                    "Bachelor of Arts in Social Development",
                    "Bachelor of Arts in Arts",
                ],
            },
            {
                # No undergraduate degree programme found for this
                # institute -- consistent with it being a graduate/research
                # unit, though no official page explicitly states this.
                "name": "Institute of Gender and Development Studies",
                "programmes": [],
            },
        ],
    },
    {
        "code": "CONAS",
        "name": "College of Natural Sciences",
        "schools": [
            {
                "name": "School of Physical Sciences",
                "programmes": [
                    "Bachelor of Science in Industrial Chemistry",
                    "Bachelor of Science in Petroleum Geoscience and Production",
                    "Bachelor of Science (Physical)",
                ],
            },
            {
                "name": "School of Biosciences",
                "programmes": [
                    "Bachelor of Science in Fisheries and Aquaculture",
                    "Bachelor of Sports Science (Exercise Science)",
                    "Bachelor of Sports Science (Sports Management)",
                    "Bachelor of Science in Conservation Biology",
                    "Bachelor of Science in Biotechnology",
                    "Bachelor of Science (Biological)",
                ],
            },
        ],
    },
    {
        "code": "COVAB",
        "name": "College of Veterinary Medicine, Animal Resources and Biosecurity",
        "schools": [
            {
                "name": "School of Veterinary Medicine and Animal Resources",
                "programmes": [
                    "Bachelor of Veterinary Medicine",
                    "Bachelor of Animal Production Technology and Management",
                    "Bachelor of Science in Wildlife Health and Management",
                    "Bachelor of Industrial Livestock and Business",
                ],
            },
            {
                "name": "School of Biosecurity, Biotechnology and Laboratory Sciences",
                "programmes": [
                    "Bachelor of Biomedical Laboratory Technology",
                ],
            },
        ],
    },
    {
        "code": "LAW",
        "name": "Makerere University School of Law",
        "schools": [
            {
                "name": "School of Law",
                "programmes": [
                    "Bachelor of Laws",
                ],
            },
        ],
    },
]


def college_choices():
    return [(c["code"], c["name"]) for c in COLLEGES]


def get_college(code):
    return next((c for c in COLLEGES if c["code"] == code), None)


def get_college_by_name(name):
    return next((c for c in COLLEGES if c["name"] == name), None)


def schools_for(college_code):
    college = get_college(college_code)
    return college["schools"] if college else []


def get_school(college_code, school_name):
    for school in schools_for(college_code):
        if school["name"] == school_name:
            return school
    return None


def as_json():
    """College/school/programme structure in a shape convenient for the
    wizard's JS to walk: {code: {name, schools: [{name, programmes}]}}."""
    return {c["code"]: {"name": c["name"], "schools": c["schools"]} for c in COLLEGES}
