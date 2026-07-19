"""Real, per-semester course unit lists for a growing subset of Makerere
University programmes, fetched directly from each programme's own official
page (see the "source" field on each entry). This is deliberately NOT
comprehensive: Makerere has 80+ undergraduate programmes, each with its own
independently maintained curriculum page, and course units are exactly the
kind of granular, frequently-revised detail this app refuses to guess at
(see organizer/core/makerere.py's module docstring for the same principle
applied to programme names).

Where a programme below isn't listed here, or a listed programme's later
years/electives aren't fully covered, the wizard falls back to letting the
student type their own course units -- the one thing only they can know for
certain is their real, current semester's actual timetable.

Keys are the exact programme name as it appears in makerere.py's COLLEGES
data, so a lookup is a straight dictionary access. Each value maps
"Year N" -> "Semester N" -> a list of "CODE Name" strings. A "Recess"
pseudo-semester is included where the programme has recess-term courses,
since some students do want those tracked too.
"""

CURRICULA = {
    "Bachelor of Science in Computer Science": {
        "source": "https://cocis.mak.ac.ug/academics/academic-programs/undergraduate-programs/bachelor-of-science-in-computer-science/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "CSK1101 Communication Skills",
                    "CSC1102 Structured and Object-Oriented Programming",
                    "CSC1103 Computer Organization and Architecture",
                    "CSC1105 Mathematics for Computer Science",
                    "CSC1106 Digital Innovation and Computational Thinking",
                ],
                "Semester 2": [
                    "CSC1200 Operating Systems",
                    "CSC1201 Probability and Statistics",
                    "CSC1206 Software Development Project",
                    "IST1204 Systems Analysis and Design",
                    "CSC1207 Data Structures and Algorithms",
                ],
                "Recess": [
                    "CSC1304 Practical Skills Development",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "CSC2105 Discrete Mathematics",
                    "BSE2106 Computer Networks",
                    "CSC2107 Database Management Systems",
                    "CSC2114 Artificial Intelligence",
                    "CSC2118 Embedded and Real-time Systems",
                ],
                "Semester 2": [
                    "IST2203 Research Methodology",
                    "CSC2201 Introduction to Machine Learning",
                    "CSC2202 Cloud Computing",
                    "CSC2210 Automata, Complexity and Computability",
                ],
                "Recess": [
                    "CSC2303 Field Attachment",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "BAM2102 Entrepreneurship Principles",
                    "CSC3115 Advanced Programming",
                    "CSC3118 Computer Science Project I",
                    "CSC3119 User Interface Design",
                ],
                "Semester 2": [
                    "CSC3205 Compiler Design",
                    "CSC3207 Computer Security",
                    "CSC3211 Computer Science Project II",
                    "CSC3217 Emerging Trends in Computer Science",
                ],
            },
        },
    },
    "Bachelor of Science in Software Engineering": {
        "source": "https://cocis.mak.ac.ug/academics/academic-programs/undergraduate-programs/bachelor-of-science-in-software-engineering/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "BSE1106 Problem Solving and Programming Concepts",
                    "CSK1101 Communication Skills",
                    "BSE1107 Mathematics for Software Engineers",
                    "BSE1108 Technical Analysis and Design",
                    "IST1101 Foundations of Information Systems and Technology",
                ],
                "Semester 2": [
                    "BSE1206 Software Development Principles",
                    "MTH2203 Numerical Analysis I",
                    "BSE1209 Object Oriented Programming I",
                    "IST1203 Data and Information Management I",
                    "BSE1208 Introduction to Web Development",
                ],
                "Recess": [
                    "BSE1302 Software Engineering Practical Skills Project I",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "CSC2114 Artificial Intelligence",
                    "CSC2100 Data Structures and Algorithms",
                    "BSE2106 Computer Networks",
                    "BSE2105 Formal Methods",
                    "BSE2107 Object Oriented Programming II",
                ],
                "Semester 2": [
                    "CSC2200 Operating Systems",
                    "BSE2206 Data Communication",
                    "BSE2207 Emerging Web Development Technologies",
                    "BSE2208 Requirements Engineering",
                    "BSE2209 Mobile Programming Project",
                ],
                "Recess": [
                    "BSE2302 Software Engineering Practical Skills Project II",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "BSE3114 Internet of Things: Technologies and Protocols",
                    "BSE3113 Embedded Systems I",
                    "BSE3104 Software Metrics",
                    "CSC3119 User Interface Design",
                    "BSE3106 Mobile Networks and Computing (elective)",
                    "BSE3105 Software Evolution (elective)",
                ],
                "Semester 2": [
                    "BSE3210 Software Architecture and Patterns",
                    "BSE3211 Software Testing and Verification",
                    "IST2203 Research Methodology",
                    "CSC2206 Machine Learning",
                    "BSE3214 Cloud Computing and Big Data (elective)",
                    "BSE3213 Embedded Systems II (elective)",
                ],
                "Recess": [
                    "BSE3302 Field Attachment",
                ],
            },
            "Year 4": {
                "Semester 1": [
                    "BSE4100 Software Engineering Project I",
                    "BSE4106 ICT Innovation and Entrepreneurship",
                    "BSE4104 Emerging Trends in Software Engineering",
                    "BSE4105 Software Integration and Deployment",
                ],
                "Semester 2": [
                    "BSE4200 Software Engineering Project II",
                    "BSE4202 Software Security",
                    "BSE4203 Software Engineering Standards and Ethics",
                    "BSE4205 Software Quality Management",
                ],
            },
        },
    },
    "Bachelor of Information Systems and Technology": {
        "source": "https://cocis.mak.ac.ug/academics/academic-programs/undergraduate-programs/bachelor-of-information-systems-and-technology/",
        "note": "Year 3 splits into three specialization tracks (Information Technology Security, Systems Development, Information Systems Management) with different course lists per track -- not included here, only the shared Years 1-2.",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "IST1101 Foundations of Information Systems and Technology",
                    "CSK1101 Communication Skills",
                    "IST1102 Emerging Trends in Information Systems and Technology",
                    "CSC1107 Structured Programming",
                    "MTH1110 Basic Mathematics",
                ],
                "Semester 2": [
                    "IST1201 Applied Business Statistics",
                    "IST1202 Introduction to Computer Networks",
                    "IST1203 Data and Information Management I",
                    "IST1204 Systems Analysis and Design",
                    "CSC1214 Object Oriented Programming",
                ],
                "Recess": [
                    "CSC1304 Practical Skills Development",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "IST2101 Data and Information Management II",
                    "IST2102 Web Systems and Technologies I",
                    "BAM2102 Entrepreneurship Principles",
                    "IST2103 Information Systems Security and Risk Management",
                    "IST2104 Electronic Media Systems and Multimedia",
                ],
                "Semester 2": [
                    "IST2201 System Administration",
                    "IST2202 E-services",
                    "IST2203 Research Methodology",
                    "IST2204 IST Project Management",
                    "IST2205 Web Systems and Technologies II",
                ],
                "Recess": [
                    "IST2302 Field Attachment",
                ],
            },
        },
    },
    "Bachelor of Science in Civil Engineering": {
        "source": "https://cedat.mak.ac.ug/undergraduate-programmes/bachelor-of-science-in-civil-engineering/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "CIV1101 Engineering Drawing",
                    "CIV1102 Introduction to Civil Engineering",
                    "EMT1101 Engineering Mathematics I",
                    "EMT1104 Information and Communication Technology I",
                    "TEC1101 Communication Skills for Technology",
                    "CIV1103 Statics and Dynamics for Civil Engineers",
                ],
                "Semester 2": [
                    "CIV1201 Strength of Materials",
                    "CIV1202 Fluid Mechanics",
                    "CIV1203 Electrical Engineering",
                    "EMT1201 Engineering Mathematics II",
                    "EMT1202 Information and Communication Technology II",
                    "TEC1301 Workshop Practice",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "CIV2101 Theory of Structures I",
                    "CIV2102 Engineering Geology",
                    "CIV2103 Engineering Surveying I",
                    "CIV2104 Hydraulics",
                    "CIV2105 Thermodynamics for Civil Engineers",
                    "EMT2101 Engineering Mathematics III",
                    "TEC2101 Sociology for Technology",
                ],
                "Semester 2": [
                    "CIV2201 Soil Mechanics",
                    "CIV2202 Theory of Structures II",
                    "CIV2203 Civil Engineering Materials",
                    "CIV2204 Engineering Surveying II",
                    "CIV2205 Economics for Civil Engineering",
                    "EMT2201 Engineering Mathematics IV",
                ],
                "Recess": [
                    "CIV2301 Industrial Training I",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "CIV3101 Organisational Theory for Engineering",
                    "CIV3102 Design of Structures I (Concrete)",
                    "CIV3103 Highway Engineering",
                    "CIV3104 Hydrology I",
                    "CIV3105 Construction Technology",
                    "CIV3106 Environmental Chemistry",
                    "CIV3107 Principles of Quantity Surveying",
                ],
                "Semester 2": [
                    "CIV3201 Foundation Engineering",
                    "CIV3202 Group Design Project",
                    "CIV3203 Design of Structures II (Steel)",
                    "CIV3204 Water Resources Engineering I",
                    "CIV3205 Public Health Engineering I",
                ],
                "Recess": [
                    "CIV3301 Industrial Training II",
                ],
            },
            "Year 4": {
                "Semester 1": [
                    "CIV4100 Civil Engineering Project I",
                    "CIV4101 Civil Engineering Management",
                    "CIV4102 Civil Engineering Infrastructure Maintenance",
                    "CIV4103 Traffic and Transportation Engineering",
                    "CIV4104 Public Health Engineering II",
                    "CIV4105 Design of Structures III (Timber and Masonry)",
                    "CIV4106 Hydrology II",
                ],
                "Semester 2": [
                    "CIV4200 Civil Engineering Project II",
                    "CIV4201 Civil Engineering Law",
                    "CIV4202 Water Resources Engineering II",
                    "CIV4203 Civil Engineering Economy",
                    "CIV4204 Civil Engineering Environmental Quality Management",
                    "CIV4206 Introductory Dynamics of Structures",
                    "CIV4209 Human Resources Management and Entrepreneurship",
                ],
            },
        },
    },
    "Bachelor of Laws": {
        "source": "https://law.mak.ac.ug/undergraduate/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "LAW1106 Introducing Law",
                    "LAW1107 Development Studies",
                    "LAW1108 Fundamentals of Criminal Law",
                    "LAW1109 Law of Contracts I",
                    "LAW1110 Principles of Constitutional Law I",
                ],
                "Semester 2": [
                    "LAW1206 Legal Methods",
                    "LAW1207 Administrative Law I",
                    "LAW1208 Criminal Liability",
                    "LAW1209 Law of Contracts II",
                    "LAW1210 Principles of Constitutional Law II",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "LAW2106 Nature and History of Torts",
                    "LAW2107 Administrative Law II",
                    "LAW2108 Equity and Trusts",
                    "LAW2109 Law of Evidence I",
                    "LAW2110 Foundations of Land Law",
                ],
                "Semester 2": [
                    "LAW2207 Negligence, Strict Liability and Procedure in Torts",
                    "LAW2208 Social Research Methods",
                    "LAW2209 Family Law I",
                    "LAW2210 Law of Evidence II",
                    "LAW2211 Land Transactions",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "LAW3109 Family Law II",
                    "LAW3110 Law of Sale of Goods and Hire Purchase",
                    "LAW3111 Conflict of Laws (elective)",
                    "LAW3112 Principles of International Law I (elective)",
                    "LAW3113 Banking and Negotiable Instruments (elective)",
                    "LAW3114 International and Regional Human Rights (elective)",
                    "LAW3115 Civil Procedure I (elective)",
                ],
                "Semester 2": [
                    "LAW3210 Criminal Procedure",
                    "LAW3211 Law of Business Associations I",
                    "LAW3212 Environmental Law and Policy (elective)",
                    "LAW3213 Principles of International Law II (elective)",
                    "LAW3214 Human Rights in the Domestic Perspective (elective)",
                    "LAW3215 Consumer Law (elective)",
                    "LAW3217 Clinical Legal Education (elective)",
                    "LAW3218 Civil Procedure (elective)",
                ],
            },
            "Year 4": {
                "Semester 1": [
                    "LAW4112 Law of Business Associations II (elective)",
                    "LAW4113 Revenue Law and Taxation I (elective)",
                    "LAW4114 International Trade and Business (elective)",
                    "LAW4115 Health and the Law I (elective)",
                    "LAW4116 Intellectual Property Law I (elective)",
                    "LAW4118 Insurance Law (elective)",
                    "LAW4119 Labour Law I (elective)",
                ],
                "Semester 2": [
                    "LAW4202 Research Paper",
                    "LAW4214 Estate Planning (elective)",
                    "LAW4215 Revenue Law and Taxation II (elective)",
                    "LAW4216 Gender and the Law (elective)",
                    "LAW4217 Criminology and Penology (elective)",
                    "LAW4218 Insolvency (elective)",
                    "LAW4219 Computers and the Law (elective)",
                    "LAW4220 Intellectual Property Law II (elective)",
                    "LAW4221 Labour Law II (elective)",
                    "LAW4226 Health and the Law II (elective)",
                ],
            },
        },
    },
    "Bachelor of Business Administration": {
        "source": "https://bams.mak.ac.ug/summary-program-structure-for-bachelor-of-business-administration/",
        "note": "Year 2 Semester 2 onward splits into four specialization options (Procurement, HRM, Entrepreneurship, International Business) with different course lists per option -- not included here, only the shared Years 1 and Year 2 Semester 1.",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "BAM1102 Principles of Management",
                    "BAM1105 Introduction to Business Administration",
                    "COE1101 Fundamentals Accounting Principles I",
                    "COE1103 Business Communication Skills",
                    "ECO1101 Introductory Microeconomics",
                    "PSM1101 Purchasing Principles",
                ],
                "Semester 2": [
                    "BAM1204 Information and Communication Technology I",
                    "BAM1206 Business Quantitative Techniques",
                    "COE1201 Principles of Marketing",
                    "COE1203 Fundamental Accounting Principles II",
                    "COE1204 Business Law",
                    "ECO1202 Introductory Macroeconomics",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "BAM2102 Entrepreneurship Principles",
                    "BAM2103 Information and Communication Technology II",
                    "BHR2103 Principles of Human Resource Management",
                    "COE2104 Elements of Taxation",
                    "COE2107 Company Law",
                    "ECO2101 Microeconomics",
                ],
            },
        },
    },
}


def get_curriculum(program_name):
    return CURRICULA.get(program_name)


def get_course_units(program_name, primary_value, secondary_value):
    """primary_value/secondary_value are the profile's raw values, e.g.
    "Year 2" and "Semester 1" -- returns a list of "CODE Name" strings, or
    an empty list if this programme/year/semester isn't covered yet."""
    curriculum = get_curriculum(program_name)
    if not curriculum:
        return []
    year = curriculum["years"].get(primary_value)
    if not year:
        return []
    return year.get(secondary_value, [])
