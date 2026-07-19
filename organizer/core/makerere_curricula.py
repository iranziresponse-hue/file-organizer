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
certain is their real, current semester's actual timetable. What they type
in that case is saved as a SuggestedCourseUnit (organizer/models.py) so an
admin can later check it against an official source and add it here by hand.

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
        "note": "Year 3 splits into three specialization tracks (Information Technology Security, Systems Development, Information Systems Management), each with its own units -- distinct per-track units are labeled below.",
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
            "Year 3": {
                "Semester 1": [
                    "IST3101 Project I",
                    "IST3102 Network Security (IT Security track)",
                    "IST3103 Enterprise Network Management (IT Security track)",
                    "IST3104 Intrusion Detection and Incident Management (IT Security track)",
                    "IST3105 Digital Forensics Investigation (IT Security track)",
                    "IST3106 Integrative Programming and Technologies (Systems Development track)",
                    "IST3107 Intelligent Systems (Systems Development track)",
                    "IST3108 Applications Development (Systems Development / Information Systems Management track)",
                    "CSC3110 User Interface Design (Systems Development track)",
                    "IST3109 Data Warehousing and Business Intelligence (Information Systems Management track)",
                    "IST3110 Business Process Management (Information Systems Management track)",
                    "IST3111 Information Systems Architecture (Information Systems Management track)",
                ],
                "Semester 2": [
                    "IST3201 Project II",
                    "IST3203 IT Law and Ethics",
                    "IST3202 Ethical Hacking (IT Security track)",
                    "IST3204 Information Systems Audit (elective, all tracks)",
                    "IST3205 Software Systems Testing (elective, IT Security / Systems Development tracks)",
                    "IST3206 System Integration and Deployment (Systems Development track)",
                    "IST3207 Information Systems Strategy, Management and Acquisition (Information Systems Management track)",
                    "IST3208 Modelling and Simulation (elective, Information Systems Management track)",
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
        "note": "Year 2 Semester 2 onward splits into four specialization options (Procurement, HRM, Entrepreneurship, International Business) -- each option's units are labeled below.",
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
                "Semester 2": [
                    "BAM2202 Research Methodology and Design",
                    "COE2201 Marketing Management",
                    "COE2203 Financial Management",
                    "COE2208 Production and Operations Management",
                    "ECO2201 Macroeconomics",
                    "PRO2203 Warehousing and Inventory Management (Procurement option)",
                    "BHR2201 Human Resource Planning and Development (HRM option)",
                    "BAM2207 Entrepreneurship Theory (Entrepreneurship option)",
                    "BAM2208 International Business Environment (International Business option)",
                ],
                "Recess": [
                    "BAM2301 Field Attachment (Report)",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "PRO3104 Public Procurement (Procurement option)",
                    "PRO3105 Supply Chain Management (Procurement / International Business option)",
                    "PRO3106 Logistics Management (Procurement option)",
                    "PRO3102 International Procurement (Procurement option)",
                    "BAM3101 Cost Accounting (elective, Procurement option)",
                    "COE3107 Local Government Finance and Management (elective, Procurement option)",
                    "PRO3107 Procurement Risk Management (elective, Procurement option)",
                    "BHR3101 Organizational Behavior (HRM option)",
                    "BHR3102 Performance Management (HRM option)",
                    "BHR3103 Benefits and Compensation Management (HRM option)",
                    "BHR3104 Management of Change (HRM option)",
                    "BHR3105 International Human Resource Management (HRM / International Business option)",
                    "COE3116 Strategic Human Resource Management (HRM option)",
                    "DEC3105 Ethics, Public Policy and Development (HRM option)",
                    "BAM3113 Small Business Management (Entrepreneurship option)",
                    "BAM3114 Creativity and Innovation (Entrepreneurship option)",
                    "BAM3115 Managing Growth (Entrepreneurship option)",
                    "BAM3116 Intrapreneurship (Entrepreneurship option)",
                    "BAM3104 Retail Marketing (elective, Entrepreneurship option)",
                    "BAM3105 Services Marketing (elective, Entrepreneurship option)",
                    "BAM3117 Business Development Services (elective, Entrepreneurship option)",
                    "COE3108 Global Financial Systems and Markets (International Business option)",
                    "COE3118 Corporate Finance (International Business option)",
                    "BAM3107 Global Sourcing (elective, International Business option)",
                    "BAM3118 Introductory Swahili (elective, International Business option)",
                    "BAM3119 Introductory French (elective, International Business option)",
                    "COE3114 Investment and Portfolio Management (elective, International Business option)",
                ],
                "Semester 2": [
                    "PRO3204 Strategic Procurement Management (Procurement option)",
                    "BAM3213 Contracts and Negotiation Management (Procurement / International Business option)",
                    "COE3203 Strategic Management (all options)",
                    "COE3213 Corporate Governance (Procurement / Entrepreneurship / International Business option)",
                    "PRO3202 E-Procurement (elective, Procurement option)",
                    "PRO3203 Procurement Audits and Investigations (elective, Procurement option)",
                    "ECO3202 Project Planning and Management (elective, Procurement / HRM option)",
                    "BHR3201 Labour Laws and Industrial Relations (HRM option)",
                    "BHR3202 Negotiation and Conflict Management (HRM option)",
                    "BHR3204 Human Resource Information Systems (HRM option)",
                    "BHR3205 Leadership and Interpersonal Relations (elective, HRM option)",
                    "BAM3214 Feasibility Analysis and Business Planning (Entrepreneurship option)",
                    "COE3208 International Business and Finance (Entrepreneurship option)",
                    "BAM3206 E-Business (elective, Entrepreneurship option)",
                    "COE3211 Risk Management (elective, Entrepreneurship / International Business option)",
                    "BAM3207 Managing Multinational Organisations (International Business option)",
                    "COE3209 International Marketing (International Business option)",
                    "BAM3221 Intermediate Swahili (elective, International Business option)",
                    "BAM3222 Intermediate French (elective, International Business option)",
                ],
            },
        },
    },
    "Bachelor of Arts in Economics": {
        "source": "https://bams.mak.ac.ug/summary-program-structure-for-bachelor-of-arts-in-economics-beco/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "ECO1107 Introductory Microeconomics",
                    "ECO1108 Introduction to Mathematics for Economists",
                    "ECO1103 Introduction to Accounting",
                    "COE1103 Business Communication Skills",
                    "ECO1105 Political Economy",
                    "BHR1101 Principles of Human Resource Management",
                ],
                "Semester 2": [
                    "ECO1201 Principles of Development Economics",
                    "ECO1207 Introductory Macroeconomics",
                    "ECO1208 Introduction to Statistics for Economists",
                    "ECO1204 Introduction to Computing for Economists",
                    "COE1201 Principles of Marketing",
                    "COE1205 Organizational Theory and Management",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "ECO2112 Microeconomics",
                    "ECO2113 Quantitative Methods",
                    "ECO2114 Mathematical Economics",
                    "ECO2104 Computer Skills for Economists",
                    "COE2105 Entrepreneurship",
                    "ECO2115 Agricultural Production and Farm Management (elective)",
                    "ECO2106 Industrial Economics (elective)",
                    "COE2101 Human Resource Management (elective)",
                ],
                "Semester 2": [
                    "ECO2214 Macroeconomics",
                    "ECO2211 Econometrics I",
                    "ECO2212 Financial Economics",
                    "ECO2213 Research Methodology",
                    "ECO2204 Labour Economics (elective)",
                    "ECO2205 Managerial Economics (elective)",
                    "ECO2215 Agricultural Marketing and Cooperatives (elective)",
                    "ECO2210 Economics of Regulation (elective)",
                ],
                "Recess": [
                    "ECO2301 Field Attachment",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "ECO3113 Intermediate Microeconomics",
                    "ECO3112 Development Economics",
                    "ECO3103 Economic Planning and Policy",
                    "ECO3114 Econometrics II",
                    "ECO3111 Natural Resource Economics (elective)",
                    "ECO3106 International Economics (elective)",
                    "ECO3107 Transport Economics (elective)",
                    "COE3106 Financial Markets and Institutions (elective)",
                    "ECO3109 Monetary Economics (elective)",
                    "ECO3115 Game Theory (elective)",
                ],
                "Semester 2": [
                    "ECO3212 Intermediate Macroeconomics",
                    "ECO3202 Project Planning and Management",
                    "ECO3203 Ugandan Economy",
                    "ECO3206 Public Sector Economics",
                    "COE3203 Strategic Management (elective)",
                    "ECO3205 Health Economics (elective)",
                    "ECO3207 Environmental Economics (elective)",
                    "ECO3208 International Finance (elective)",
                    "ECO3213 Behavioural Economics (elective)",
                    "ECO3214 Microfinance: Theory and Practice (elective)",
                ],
            },
        },
    },
    "Bachelor of Arts in Development Economics": {
        "source": "https://bams.mak.ac.ug/summary-program-structure-for-bachelor-of-development-economics-bdec/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "ECO1107 Introductory Microeconomics",
                    "ECO1108 Introduction to Mathematics for Economists",
                    "ECO1103 Introduction to Accounting",
                    "COE1103 Business Communication Skills",
                    "ECO1105 Political Economy",
                    "ECO1104 Introduction to Sociology",
                    "ECO1106 Introduction to Ugandan Economy",
                ],
                "Semester 2": [
                    "ECO1201 Principles of Development Economics",
                    "ECO1207 Introductory Macroeconomics",
                    "ECO1208 Introduction to Statistics for Economists",
                    "ECO1204 Introduction to Computing for Economists",
                    "COE1205 Organisational Theory and Management",
                    "ECO1206 Business Law",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "DEC2106 History of Economic Thought",
                    "ECO2112 Microeconomics",
                    "ECO2113 Quantitative Methods",
                    "ECO2104 Computer Skills for Economists",
                    "COE2105 Entrepreneurship",
                    "DEC2104 Women, Gender and Development (elective)",
                    "DEC2105 Refugees and Disaster Management (elective)",
                    "ECO2115 Agricultural Production and Farm Management (elective)",
                    "ECO2106 Industrial Economics (elective)",
                ],
                "Semester 2": [
                    "DEC2201 Rural Development",
                    "DEC2203 Governance and Development",
                    "ECO2214 Macroeconomics",
                    "ECO2211 Econometrics I",
                    "ECO2213 Research Methodology",
                    "DEC2206 Land Economics (elective)",
                    "ECO2204 Labour Economics (elective)",
                    "ECO2212 Financial Economics (elective)",
                    "ECO2215 Agricultural Marketing and Cooperatives (elective)",
                ],
                "Recess": [
                    "DEC2207 Field Attachment",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "DEC3101 Poverty, Growth and Income Distribution",
                    "DEC3102 Government Development Policy",
                    "DEC3107 Public Policy Development and Analysis",
                    "ECO3112 Development Economics",
                    "DEC3103 Social Security and Welfare Economics",
                    "DEC3106 Informal Sector Economics (elective)",
                    "ECO3109 Monetary Economics (elective)",
                    "ECO3106 International Economics (elective)",
                    "ECO3111 Natural Resource Economics (elective)",
                ],
                "Semester 2": [
                    "DEC3205 Welfare Economics",
                    "DEC3202 Rural Finance",
                    "ECO3202 Project Planning and Management",
                    "ECO3203 Ugandan Economy",
                    "COE3203 Strategic Management (elective)",
                    "DEC3203 Social Sector Economics (elective)",
                    "DEC3204 Applied Tax Policy (elective)",
                    "ECO3205 Health Economics (elective)",
                    "ECO3207 Environmental Economics (elective)",
                    "ECO3214 Microfinance: Theory and Practice (elective)",
                ],
            },
        },
    },
    "Bachelor of Commerce": {
        "source": "https://bams.mak.ac.ug/summary-program-structure-for-bachelor-of-commerce/",
        "note": "Year 3 splits into Accounting/Marketing/Finance options whose course codes are listed on the source page without course titles -- left out here rather than guess the names those codes refer to. Only Years 1-2 and the recess field attachment are included.",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "BAM1105 Introduction to Business Administration",
                    "COE1101 Fundamentals Accounting Principles I",
                    "COE1103 Business Communication Skills",
                    "COE1105 Information Technology I",
                    "ECO1107 Introductory Microeconomics",
                    "PSM1101 Purchasing Principles",
                ],
                "Semester 2": [
                    "COE1201 Principles of Marketing",
                    "COE1202 Introduction to Business Mathematics",
                    "COE1204 Business Law",
                    "COE1205 Organizational Theory and Management",
                    "COE1207 Fundamental Accounting Principles II",
                    "ECO1207 Introductory Macroeconomics",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "BAM2102 Entrepreneurship Principles",
                    "COE2109 Business Statistics",
                    "COE2104 Elements of Taxation",
                    "COE2107 Company Law",
                    "COE2108 Information Technology II",
                    "ECO2112 Microeconomics",
                ],
                "Semester 2": [
                    "COE2203 Financial Management",
                    "COE2205 Cost and Management Accounting",
                    "COE2206 Human Resource Management",
                    "COE2208 Production and Operations Management",
                    "ECO2214 Macroeconomics",
                    "COE2201 Marketing Management (elective, Marketing option)",
                    "COE2209 Intermediate Accounting (elective, Accounting option)",
                    "COE2212 Banking Theory and Practice (elective, Finance option)",
                ],
                "Recess": [
                    "COE2301 Field Attachment Report",
                ],
            },
        },
    },
    "Bachelor of Statistics": {
        "source": "https://bams.mak.ac.ug/summary-program-structure-for-bachelor-of-statistics/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "STA1110 Descriptive Statistics I",
                    "STA1111 Probability Theory I",
                    "STA1104 Elementary French I (or FRA1102 Panorama of French)",
                    "CSC1100 Computer Literacy",
                    "ECO1101 Introductory Micro Economics",
                    "MTH1101 Calculus I",
                    "MTH1102 Linear Algebra I",
                ],
                "Semester 2": [
                    "STA1210 Statistical Organization and Official Statistics",
                    "STA1211 Time Series and Index Numbers",
                    "STA1212 Statistical Inference",
                    "STA1204 Elementary French II (or FRA1201 Creative Writing)",
                    "STA1213 Data Analysis I",
                    "ECO1201 Principles of Development Economics",
                    "ECO1202 Introductory Macro Economics",
                    "MTH1201 Calculus II",
                    "SAS1202 Accounting I",
                ],
                "Recess": [
                    "STA1301 Workshop on Data Processing",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "STA2110 Intermediate Statistical Methods",
                    "STA2111 Sampling Theory and Survey Design",
                    "ECO2101 Micro Economics",
                    "ECO2106 Industrial Economics",
                    "MTH2101 Real Analysis I",
                    "MTH2104 Linear Algebra II",
                    "MTH2103 Differential Equations",
                ],
                "Semester 2": [
                    "STA2210 Language Programming",
                    "STA2211 Statistical Decision Theory",
                    "SAS2212 Stochastic Modelling",
                    "STA2213 Linear Models and Design of Experiments",
                    "STA2214 Data Analysis II",
                    "ECO2206 Farm Management and Production Economics",
                    "ECO2201 Macro Economics",
                    "STA2215 Research Methods I",
                    "STA2216 Gender Statistics",
                ],
                "Recess": [
                    "STA2302 Field Attachment",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "STA3120 Advanced Statistical Methods (Multivariate Analysis and Time Series)",
                    "STA3103 National Accounts and Income Analysis",
                    "STA3121 Data Analysis III",
                    "BPS3101 Monitoring and Evaluation",
                    "STA3105 Agricultural Statistics (elective, Applied Statistics stream)",
                    "STA3106 Demographic and Social Statistics (elective, Applied Statistics stream)",
                    "STA3123 Epidemiology and Bio-Statistics (elective, Applied Statistics stream)",
                    "STA3108 Human Resource Planning and Policies (elective, Development Planning stream)",
                    "STA3110 Theory and Analysis of Economic Development (elective, Development Planning stream)",
                    "STA3122 Economic and Social Dimensions of Development (elective, Development Planning stream)",
                    "CSC3118 Introduction to Computer Architecture (elective, Statistical Computing stream)",
                    "BSE3109 Introduction to Software Engineering (elective, Statistical Computing stream)",
                    "BSE3108 Computer Networking (elective, Statistical Computing stream)",
                    "BSE1103 Systems Analysis and Design (elective, Statistical Computing stream)",
                ],
                "Semester 2": [
                    "STA3220 Industrial Statistical Modelling",
                    "STA3225 Research Project",
                    "STA3221 Econometric Methods",
                    "STA3223 Operations Research",
                    "STA3214 Industrial, Energy and Environment Statistics",
                    "BQE3203 Elements of Development Planning",
                    "STA3218 Purchasing Power Parity, External Trade and Balance of Payments (elective, Applied Statistics stream)",
                    "STA3205 Price Statistics, Distributive Trade and Services (elective, Applied Statistics stream)",
                    "STA3207 Financial Statistics (elective, Applied Statistics stream)",
                    "ECO3204 Development Economics, Planning and Policy (elective, Development Planning stream)",
                    "ECO3205 Health Economics (elective, Development Planning stream)",
                    "ECO3202 Project Planning and Management (elective, Development Planning stream)",
                    "CSC3208 Operating Systems and Data Communications (elective, Statistical Computing stream)",
                    "BIS3206 Database Management Systems (elective, Statistical Computing stream)",
                    "BIS3207 Management of Information Systems (elective, Statistical Computing stream)",
                    "BIS3208 Data Mining (elective, Statistical Computing stream)",
                ],
            },
        },
    },
    "Bachelor of Science in Actuarial Science": {
        "source": "https://bams.mak.ac.ug/summary-program-structure-for-bachelor-of-science-in-actuarial-science/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "STA1110 Descriptive Statistics I",
                    "STA1111 Probability Theory I",
                    "CSC1100 Computer Literacy",
                    "SAS1102 Introduction to Actuarial Science",
                    "ECO1101 Introductory Micro Economics",
                    "MTH1101 Calculus I",
                    "MTH1102 Linear Algebra I",
                ],
                "Semester 2": [
                    "STA1210 Statistical Organization and Official Statistics",
                    "STA1211 Time Series and Index Numbers",
                    "STA1213 Data Analysis I",
                    "SAS1202 Accounting I",
                    "ECO1201 Principles of Development Economics",
                    "ECO1202 Introductory Macro Economics",
                    "MTH1201 Calculus II",
                ],
                "Recess": [
                    "STA1301 Workshop on Data Processing",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "STA2110 Intermediate Statistical Methods",
                    "STA2111 Sampling Theory and Survey Design",
                    "SAS2104 Mathematics of Finance I",
                    "SAS2102 Life Contingencies I",
                    "ECO2101 Micro Economics",
                    "MTH2103 Differential Equations",
                    "MTH2104 Linear Algebra II",
                ],
                "Semester 2": [
                    "SAS2213 Mathematics of Finance II",
                    "SAS2202 Life Contingencies II",
                    "SAS2212 Stochastic Modeling",
                    "SAS2214 Data Analysis II",
                    "SAS2205 Law of Insurance",
                    "STA2215 Research Methods I",
                    "ECO2201 Macro Economics",
                    "SAS2201 Accounting II",
                ],
                "Recess": [
                    "SAS2301 Field Attachment",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "STA3120 Advanced Statistical Methods",
                    "SAS3110 Actuarial Mathematics",
                    "SAS3107 Actuarial Modeling",
                    "BBS3110 Principles of Financial Management",
                    "SAS3108 Risk Mathematics",
                    "SAS3109 Life Contingencies III",
                    "STA3121 Data Analysis III",
                ],
                "Semester 2": [
                    "STA3223 Operations Research",
                    "SAS3201 Investment, Stock Markets and Asset Management",
                    "SAS3202 Life Assurance, Health and General Insurance",
                    "SAS3203 Actuarial Theory of Pensions and Other Benefits",
                    "SAS3204 Financial Economics",
                    "SAS3207 Actuarial Research Project",
                    "BBS3206 Risk Management for Business",
                ],
            },
        },
    },
    "Bachelor of Science in Business Statistics": {
        "source": "https://bams.mak.ac.ug/summary-program-structure-for-bachelor-of-science-in-business-statistics/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "BBS1101 Business Administration",
                    "ECO1101 Introductory Microeconomics",
                    "MTH1102 Linear Algebra I",
                    "MTH1101 Calculus I",
                    "STA1110 Descriptive Statistics I",
                    "STA1111 Probability Theory I",
                    "CSC1100 Computer Literacy",
                ],
                "Semester 2": [
                    "BBS1201 Fundamentals of Financial Accounting",
                    "BPS1205 Basic Demographic Methods",
                    "ECO1201 Principles of Development Economics",
                    "ECO1202 Introductory Macroeconomics",
                    "BBS1203 Entrepreneurship Principles",
                    "STA1211 Time Series and Index Numbers",
                    "STA1212 Statistical Inference",
                    "STA1213 Data Analysis I",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "BBS2101 Intermediate Financial Accounting",
                    "BBS2102 Principles and Practice of Management",
                    "ECO2101 Micro Economics",
                    "BBS2103 Principles of Procurement",
                    "SAS2101 Mathematics of Finance I",
                    "STA2110 Intermediate Statistical Methods",
                    "STA2111 Sampling Theory and Survey Analysis",
                ],
                "Semester 2": [
                    "BBS2201 Introduction to Business Law",
                    "BBS2203 Introduction to E-Business",
                    "BBS2204 Fundamentals of Human Resource Management",
                    "ECO2201 Macro economics",
                    "STA2202 Statistical Decision Theory",
                    "BBS2205 Credit Risk Models",
                    "STA2214 Data Analysis II",
                    "STA2215 Research Methods I",
                ],
                "Recess": [
                    "STA2302 Field Attachment (10 weeks)",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "BBS3101 Management Accounting",
                    "BBS3110 Principles of Financial Management",
                    "BBS3111 Cost Accounting",
                    "BBS3112 Business Communication",
                    "BPS3101 Monitoring and Evaluation",
                    "ECO3108 Monetary Economics",
                    "STA3108 Human Resources Planning and Policies",
                    "STA3120 Advanced Statistical Methods",
                ],
                "Semester 2": [
                    "BBS3201 Marketing Research Techniques (elective)",
                    "BBS3203 Auditing Practices and Procedures (elective)",
                    "BBS3204 Fundamentals of Public Sector Financial Management and Accounting (elective)",
                    "BBS3205 Production and Operations Management (elective)",
                    "BBS3206 Risk Management for Business (elective)",
                    "BBS3207 Principles of Taxation (elective)",
                    "BBS3208 Fundamentals of Marketing (elective)",
                    "STA3221 Econometrics Methods (elective)",
                    "STA3203 Research Project Paper (elective)",
                ],
            },
        },
    },
    "Bachelor of Science in Population Studies": {
        "source": "https://bams.mak.ac.ug/summary-program-structure-forbachelor-of-population-studies/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "BPS1101 Introduction to Population Studies",
                    "STA1101 Descriptive Statistics",
                    "MTH1154 Pre-Calculus",
                    "BPS1104 Elements of Sociology and Anthropology",
                    "ECO1101 Introductory Micro Economics",
                    "CSC1100 Computer Literacy",
                ],
                "Semester 2": [
                    "BPS1205 Basic Demographic Methods",
                    "MTH1256 Elements of Numerical Methods",
                    "BPS1206 Introduction to Sociology of Development",
                    "BPS1208 Data Processing I",
                    "ECO1201 Principles of Development Economics",
                    "ECO1202 Introductory Macroeconomics",
                    "BPS1207 Probability Theory and Inference for Population Scientists",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "BPS2101 Population Theories",
                    "BPS2108 Demography of Uganda",
                    "BPS2103 Methods of Collecting Population Data",
                    "BPS2109 Applied Statistics",
                    "BPS2110 Data Processing II",
                    "BPS2106 Population and Poverty",
                    "BPS2107 Population Economics I",
                ],
                "Semester 2": [
                    "BPS2208 Urbanisation and Rural Development",
                    "BPS2202 Population Dynamics",
                    "BPS2204 Families and Households",
                    "BPS2209 Historical and Institutional Perspectives on Population",
                    "BPS2210 Research Methods",
                    "BPS2211 Population Economics II",
                    "BPS2207 Population and Gender",
                ],
                "Recess": [
                    "BPS2301 Field Attachment",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "BPS3110 Monitoring and Evaluation of Population Programmes",
                    "BPS3111 Population and Development",
                    "BPS3112 Communication Skills",
                    "BPS3113 Indirect Demographic Methods",
                    "BPS3114 Population and Environment (elective)",
                    "BPS3115 Population Ageing (elective)",
                    "BPS3117 Demography and Social Statistics (elective)",
                    "SAN1100C Introduction to Social Anthropology and African Studies (elective)",
                ],
                "Semester 2": [
                    "BPS3216 Research Project",
                    "BPS3210 Population and Reproductive Health",
                    "BPS3211 Population and Health Interrelationships",
                    "BPS3212 Population Estimates and Projections",
                    "BPS3214 Sexuality and Health (elective)",
                    "BPS3215 Epidemiology of Reproductive Health (elective)",
                    "STA3223 Operations Research (elective)",
                    "ECO3202 Project Planning and Management (elective)",
                    "ECO3205 Health Economics (elective)",
                ],
            },
        },
    },
    "Bachelor of Science in Quantitative Economics": {
        "source": "https://bams.mak.ac.ug/summary-program-structure-for-bachelor-of-science-in-quantitative-economics/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "BPS1104 Elements of Sociology and Anthropology",
                    "ECO1101 Introductory Microeconomics",
                    "MTH1101 Calculus 1",
                    "MTH1102 Linear Algebra 1",
                    "CSC1100 Computer Literacy",
                    "STA1110 Descriptive Statistics I",
                    "STA1111 Probability Theory I",
                ],
                "Semester 2": [
                    "ECO1201 Principles of Development Economics",
                    "ECO1202 Introductory Macroeconomics",
                    "MTH1201 Calculus II",
                    "SAS1202 Accounting I",
                    "STA1210 Official Statistics and Statistical Organisation",
                    "STA1211 Time Series and Index Numbers",
                    "STA1212 Statistical Inference",
                    "STA1213 Data Analysis I",
                    "CSK1101 Communication Skills",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "BQE2101 Mathematical Economics",
                    "ECO2101 Microeconomics",
                    "ECO2105 Marketing and Cooperatives",
                    "ECO2106 Industrial Economics",
                    "MTH2103 Differential Equations I",
                    "STA2110 Intermediate Statistical Methods",
                    "STA2111 Sampling Theory and Survey Analysis",
                ],
                "Semester 2": [
                    "ECO2201 Macroeconomics",
                    "ECO2206 Farm Management and Production Economics",
                    "SAS2212 Stochastic Modelling",
                    "STA2211 Statistical Decision Theory",
                    "STA2213 Linear Models and Design of Experiments",
                    "STA2214 Data Analysis II",
                    "STA2215 Research Methods I",
                    "STA2217 Computer Programming",
                ],
                "Recess": [
                    "STA2302 Field Attachment",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "BPS3101 Monitoring and Evaluation",
                    "BQE3105 Development Economics, Planning and Policy I",
                    "BQE3106 Resource and Environment Economics I",
                    "ECO3101 Intermediate Microeconomics",
                    "ECO3108 Monetary Economics",
                    "STA3121 Data Analysis III",
                    "STA3120 Advanced Statistical Methods",
                    "ECO3105 International Economics",
                    "STA3103 National Accounting and Income Analysis",
                ],
                "Semester 2": [
                    "ECO3201 Intermediate Macroeconomics",
                    "ECO3202 Project Planning and Management",
                    "ECO3205 Health Economics",
                    "ECO3206 Public Sector Economics",
                    "STA3221 Econometric Methods",
                    "STA3203 Research Project Paper",
                    "STA3223 Operations Research",
                ],
            },
        },
    },
    "Bachelor of Science in Electrical Engineering": {
        "source": "https://cedat.mak.ac.ug/undergraduate-programmes/bachelor-of-science-in-electrical-engineering/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "CMP1103 Information and Communication Technology",
                    "COE1103 Business Communications Skills",
                    "ELE1101 Circuit Theory",
                    "ELE1102 Physical Electronics",
                    "ELE1112 Introduction to Electrical Engineering",
                    "EMT1101 Engineering Mathematics I",
                ],
                "Semester 2": [
                    "CMP1201 Computer Programming Fundamentals",
                    "ELE1201 Introduction to Digital Electronics",
                    "ELE1202 Electrical Materials",
                    "ELE1204 Statics and Dynamics",
                    "EMT1201 Engineering Mathematics II",
                    "TEC1202 Introduction to Sociology",
                ],
                "Recess": [
                    "ELE1301 Vocation Workshop Practice",
                    "ELE1302 Electrical Engineering Drawing and Installation Practice",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "CMP2103 Object Oriented Programming",
                    "ELE2102 Electronic Circuits",
                    "ELE2103 Electromagnetics",
                    "ELE2111 Network Theory",
                    "EMT2101 Engineering Mathematics III",
                ],
                "Semester 2": [
                    "ELE2211 Electromagnetic Fields",
                    "ELE2212 Electrical Energy Systems",
                    "ELE2213 Instrumentation",
                    "EMT2201 Engineering Mathematics IV",
                    "TEC2202 Technology, Ethics and Human Rights",
                ],
                "Recess": [
                    "ELE2301 Industrial Training",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "ELE3102 Applied Analogue",
                    "ELE3113 Applied Digital Electronics",
                    "ELE3114 Electrical Machines and Drives",
                    "COE2105 Entrepreneurship (elective)",
                    "TEL3111 Communication Theory (elective)",
                    "TEL3112 Radio Wave Propagation and Antennas (elective)",
                    "LAW1104 Law of Contracts (elective)",
                ],
                "Semester 2": [
                    "ELE3202 Control Engineering",
                    "ELE3205 Electrical Machines and Drives II",
                    "ELE3211 Industrial Electronics",
                    "ELE3215 Power Systems Engineering",
                    "ELE3216 Energy Conversion and Generation",
                    "COE1102 Fundamental Accounts Principles (elective)",
                    "TEL3212 Digital Communications (elective)",
                    "TEL3213 Mobile Communications Systems (elective)",
                    "TEL3214 Computer Communication Networks (elective)",
                    "TEL3217 Systems Engineering (elective)",
                ],
                "Recess": [
                    "ELE3301 Industrial Training",
                ],
            },
            "Year 4": {
                "Semester 1": [
                    "ELE4100 Electrical Engineering Project",
                    "ELE4112 Microprocessor Based Systems",
                    "ELE4115 Power System Protection and Coordination",
                    "ELE4116 Electrical Installation Design",
                    "TEL4111 Digital Signal Processing",
                    "ELE4117 Engineering Project Management (elective)",
                    "TEL4113 Optical Communications (elective)",
                    "TEL4114 Television and Video Engineering (elective)",
                ],
                "Semester 2": [
                    "ELE4200 Electrical Engineering Project",
                    "ELE4209 High Voltage Engineering",
                    "ELE4211 VLSIC Design and Fabrication",
                    "ELE4214 Power Economics and Management",
                    "TEL4213 Radio Frequency and Microwave Engineering",
                    "COE1104 Business Management (elective)",
                    "ELE4216 Advanced Topics in Electronic Engineering (elective)",
                    "ELE4217 Advanced Topics in Power Engineering (elective)",
                    "TEL4212 Satellite Communications (elective)",
                    "TEL4215 Broadband and Advanced Communications (elective)",
                ],
            },
        },
    },
    "Bachelor of Science in Mechanical Engineering": {
        "source": "https://cedat.mak.ac.ug/undergraduate-programmes/bachelor-of-science-in-mechanical-engineering/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "EMT1101 Engineering Mathematics I",
                    "MEC1101 Engineering Drawing",
                    "MEC1102 Engineering Mechanics",
                    "MEC1103 Electrical Engineering for Mechanical Engineers",
                    "TEC1101 Communication Skills for Technology",
                ],
                "Semester 2": [
                    "EMT1201 Engineering Mathematics II",
                    "EMT1204 Information Communication Technology",
                    "MEC1202 Engineering Mechanics II",
                    "MEC1203 Thermodynamics",
                    "MEC1204 Mechanics of Materials",
                ],
                "Recess": [
                    "TEC1301 Workshop Practice",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "EMT2101 Engineering Mathematics III",
                    "MEC2101 Fluid Mechanics for Mechanical Engineers",
                    "MEC2102 Mechanics of Materials II",
                    "MEC2103 Computer Aided Design",
                    "TEC2101 Sociology for Technologists",
                ],
                "Semester 2": [
                    "MEC2201 Electrical Engineering II",
                    "MEC2202 Theory of Machine Elements",
                    "MEC2203 Computer Programming",
                    "MEC2204 Material Science and Engineering I",
                    "MEC2205 Fluid Mechanics II",
                ],
                "Recess": [
                    "MEC2301 Industrial Training",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "MEC3101 Material Science and Engineering",
                    "MEC3102 Engineering Management",
                    "MEC3103 Production Engineering I",
                    "MEC3104 Design of Machine Elements",
                    "MEC3105 Dynamic Systems Engineering",
                ],
                "Semester 2": [
                    "MEC3201 Maintenance Engineering",
                    "MEC3202 Production Engineering II",
                    "MEC3203 Product Design and Development",
                    "MEC3204 Heat Transfer",
                    "MEC3205 Control Systems Engineering",
                ],
                "Recess": [
                    "MEC3301 Industrial Training",
                ],
            },
            "Year 4": {
                "Semester 1": [
                    "MEC4101 Business Management for Mechanical Engineers",
                    "MEC4102 Applied Thermodynamics",
                    "MEC4103 Production Planning and Control",
                    "MEC4104 Mechanical Engineering Project I",
                    "MEC4105 Renewable Energy Technologies (elective)",
                    "MEC4106 Materials Handling (elective)",
                    "MEC4107 Welding Technology (elective)",
                ],
                "Semester 2": [
                    "MEC4201 Entrepreneurship for Mechanical Engineers",
                    "MEC4202 Environmental Engineering",
                    "MEC4204 Mechanical Engineering Project II",
                    "MEC4205 Air Conditioning and Refrigeration (elective)",
                    "MEC4206 Fluid Power Systems (elective)",
                    "MEC4207 Operations Research and Project Management (elective)",
                    "MEC4208 Computer Aided Engineering (elective)",
                    "MEC4209 Automotive Engineering (elective)",
                ],
            },
        },
    },
    "Bachelor of Architecture": {
        "source": "https://cedat.mak.ac.ug/undergraduate-programmes/bachelor-of-architecture/",
        "note": (
            "Year 2 Semester 1 is missing entirely from the official page itself "
            "(confirmed on two separate fetches, not a scraping error). The page also "
            "lists course code ARC3201 for both a Year 3 Semester 1 course "
            "('Architectural Design Portfolio V') and a Year 3 Semester 2 course "
            "('Architectural Design Portfolio VI') -- almost certainly a typo on the "
            "source page for one of them, reproduced as published rather than silently corrected."
        ),
        "years": {
            "Year 1": {
                "Semester 1": [
                    "ARC1101 Architectural Design Portfolio I",
                    "ARC1102 Architectural Design Fundamentals I",
                    "ARC1103 Theory of Architecture",
                    "ARC1104 Building Technology and Services I",
                    "EMT1103 Mathematics for Architecture",
                    "TEC1101 Communication Skills for Technology",
                ],
                "Semester 2": [
                    "ARC1201 Design Portfolio II",
                    "ARC1202 Architectural Design Fundamentals II",
                    "ARC1203 Theory and Design of Structures for Architects I",
                    "ARC1204 Environmental and Building Science I",
                    "ARC1205 History of Architecture I",
                ],
                "Recess": [
                    "TEC1301 Workshop Practice",
                ],
            },
            "Year 2": {
                "Semester 2": [
                    "ARC2201 Architectural Design Portfolio IV",
                    "ARC2202 Architectural Design Fundamentals IV",
                    "ARC2203 Theory and Design of Structures for Architects II",
                    "ARC2204 Environmental Building Science II",
                    "ARC2205 History of Architecture II",
                    "ARC2206 Economics for Architects",
                ],
                "Recess": [
                    "ARC2301 Industrial Training for Architects I",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "ARC3201 Architectural Design Portfolio V",
                    "ARC3102 Architectural Design Fundamentals V",
                    "ARC3103 Theory of Architecture III",
                    "ARC3104 Building Technology and Services III",
                    "ARC3105 History of Architecture III",
                    "ARC3106 Architectural Computer-Aided Design I",
                ],
                "Semester 2": [
                    "ARC3201 Architectural Design Portfolio VI",
                    "ARC3203 Theory and Design of Structures for Architects III",
                    "ARC3204 Construction Management for Architects",
                    "ARC3205 Environmental Building Science III",
                ],
                "Recess": [
                    "ARC3301 Industrial Training for Architects II",
                ],
            },
            "Year 4": {
                "Semester 1": [
                    "ARC4101 Architectural Design Portfolio VII",
                    "ARC4102 Urban and Regional Planning for Architects",
                    "ARC4104 Landscape Design",
                    "ARC4105 Housing Development and Management",
                    "ARC4106 Environment and Development for Architects",
                    "ARC4107 Computer Aided Design for Architects II",
                ],
                "Semester 2": [
                    "ARC4201 Architectural Design Portfolio VIII",
                    "ARC4202 Interior and Furniture Design",
                    "ARC4203 Building Design Economics",
                    "ARC4204 Research Methods for Architects (audited)",
                    "ARC4205 Business Law for Architects",
                    "ARC4206 Philosophy for Architects",
                ],
                "Recess": [
                    "ARC4301 Industrial Training for Architects",
                ],
            },
            "Year 5": {
                "Semester 1": [
                    "ARC5101 Architectural Project Reports",
                    "ARC5102 Professional Architectural Practice",
                    "ARC5103 Architectural Project Management",
                ],
                "Semester 2": [
                    "ARC5201 Architectural Design Thesis",
                ],
            },
        },
    },
    "Bachelor of Science in Valuation": {
        "source": "https://cedat.mak.ac.ug/undergraduate-programmes/bachelor-of-science-in-valuation/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "CSC1100 Computer Application",
                    "VAL1101 Introduction to Architectural Design and Construction Drawing",
                    "UNV1101 Communication Skills",
                    "EMT1101 Applied Mathematics",
                    "LAW1102 Administrative Law",
                    "ECO1108 Introduction to Economics",
                ],
                "Semester 2": [
                    "VAL1201 Principles of Real Estate Valuation",
                    "VAL1202 Principles of Accounting",
                    "VAL1203 Financial Mathematics",
                    "VAL1204 Land Economics",
                    "QUS1201 Construction Technology 1",
                    "LAW1203 Contract and Tort Law",
                ],
                "Recess": [
                    "VAL1301 Valuation Camp",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "VAL2101 Applied Real Estate Valuation",
                    "VAL2102 Plant and Machinery Valuation",
                    "VAL2103 Construction Materials, Fixtures and Finishes",
                    "VAL2104 Sociology for Valuers",
                    "QUS2101 Construction Technology II",
                    "COA2107 Financial Markets and Institutions",
                ],
                "Semester 2": [
                    "VAL2201 Urban Economics",
                    "VAL2202 Property Measurement Sciences",
                    "VAL2203 Land Registration for Valuers",
                    "CSC2204 Information Communication Technology for Valuers",
                    "LAW2206 Commercial Business Law for Valuers",
                    "QUS2202 Building Services (elective)",
                    "VAL2204 Maintenance Management (elective)",
                ],
                "Recess": [
                    "VAL2301 Industrial Training",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "VAL3101 Statutory and Non-Statutory Valuations",
                    "VAL3102 Property Taxation",
                    "VAL3103 Investment Appraisal I",
                    "VAL3104 Real Estate Development",
                    "VAL3105 Business Valuation",
                    "LAW3104 Real Property Law",
                ],
                "Semester 2": [
                    "VAL3201 Alternative Dispute Resolution",
                    "VAL3202 Principles of Spatial Planning",
                    "VAL3203 Investment Appraisal II",
                    "VAL3204 Real Estate Finance",
                    "VAL3205 Research Methods and Statistics",
                    "SUV3206 Geographical Information Systems",
                ],
                "Recess": [
                    "VAL3301 Industrial Training",
                ],
            },
            "Year 4": {
                "Semester 1": [
                    "VAL4101 Final Year Research Proposal",
                    "VAL4102 Special Valuations",
                    "VAL4103 Property Marketing",
                    "VAL4104 Real Estate Management",
                    "VAL4105 Building Surveying (elective)",
                    "VAL4106 Land Management and Administration (elective)",
                ],
                "Semester 2": [
                    "VAL4201 Final Year Dissertation",
                    "VAL4202 Entrepreneurship for Valuers",
                    "VAL4203 Professional Practice, Procedures, Standards, and Ethics",
                    "VAL4204 Facilities Management",
                    "VAL4205 Property Investment Analysis",
                ],
            },
        },
    },
    "Bachelor of Science in Quantity Surveying": {
        "source": "https://cedat.mak.ac.ug/undergraduate-programmes/bachelor-of-science-in-quantity-surveying/",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "CMG1101 Geophysical Environment",
                    "CSC1100 Computer Literacy",
                    "CSK1101 Communication Skills",
                    "EMT1105 Engineering Mathematics",
                    "LAW1208 Basic Law and Governance Structures",
                    "QUS1101 Introduction to Quantity Surveying",
                ],
                "Semester 2": [
                    "ARC1206 Elements of Architectural Design Fundamentals",
                    "CIV1205 Elements of Structural Analysis",
                    "LAW1206 Law of Contract for Surveyors",
                    "QUS1201 Construction Technology I",
                    "QUS1202 Construction Drawing",
                    "QUS1203 Quantity Surveying I",
                    "QUS1301 Measured Drawing",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "CMG2102 Construction Materials",
                    "ECO2104 Principles of Management",
                    "LAW2106 Law of Torts for Construction",
                    "QUS2102 Building Finishes and Fixtures",
                    "QUS2104 Construction Technology II",
                    "SOC2103 Sociology for Technology",
                ],
                "Semester 2": [
                    "LAW2202 Commercial Law for Construction",
                    "QUS2201 Quantity Surveying II",
                    "QUS2202 Building Services",
                    "QUS2203 Economics of Property and Construction",
                    "QUS2205 Cost and Value Engineering",
                    "SUV2206 Land Surveying for Construction",
                ],
                "Recess": [
                    "QUS2301 Industrial Training",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "CMG3103 Maintenance Management",
                    "COE3103 Principles of Accounting for Surveyors",
                    "LAW3109 Elements of Property Law",
                    "LAW3110 Elements of Planning Law",
                    "QUS3101 Construction Technology III",
                    "QUS3102 Housing Development and Management",
                ],
                "Semester 2": [
                    "COE3202 Entrepreneurship",
                    "LEC3204 Research Methods and Statistics",
                    "QUS3201 Quantity Surveying III",
                    "QUS3202 Construction Production Management",
                    "QUS3203 Construction Contract Administration",
                ],
                "Recess": [
                    "QUS3301 Industrial Training",
                ],
            },
            "Year 4": {
                "Semester 1": [
                    "QUS4101 Construction Technology IV",
                    "QUS4102 Operations Research Techniques",
                    "QUS4103 Building Surveying",
                    "QUS4104 Professional Practice, Procedure and Ethics",
                    "QUS4105 Construction Project Management",
                ],
                "Semester 2": [
                    "QUS4201 Final Year Research Project I and II",
                    "QUS4202 Quantity Surveying IV",
                    "QUS4203 Facilities Management",
                    "QUS4204 Analysis of Prices and Estimating",
                    "QUS4205 Arbitration and Alternative Dispute Resolution in Construction",
                ],
            },
        },
    },
    "Bachelor of Medicine and Bachelor of Surgery": {
        "source": "https://som.mak.ac.ug/academic-programs/undergraduate-programs/bachelor-of-medicine-and-bachelor-of-surgery/",
        "note": (
            "This is a 5-year programme. Years 4-5 rotate through two parallel clinical "
            "tracks (Option A / Option B) that the official page doesn't cleanly split by "
            "semester -- left out here rather than guess which rotation falls in which "
            "semester. Only Years 1-3 are included."
        ),
        "years": {
            "Year 1": {
                "Semester 1": [
                    "CHS1101 Foundations of Health Professionals Education",
                    "CHS1102 Cells, Tissues and Embryology",
                    "CHS1103 Anatomy of the Limbs",
                    "CHS1104 Physiology and Biochemistry of Blood and Body Fluids",
                    "CHS1105 Integrated Tissue Biology",
                ],
                "Semester 2": [
                    "CHS1201 Physiology and Biochemistry of Cardiovascular and Respiratory System",
                    "CHS1202 Anatomy of the Trunk",
                    "CHS1203 Renal Physiology",
                    "CHS1204 Physiology and Biochemistry of the Gastro Intestinal Tract and Metabolism",
                    "CHS1205 Foundations of Behavioural Sciences",
                    "CHS1206 Integrated Systemic Biology",
                ],
                "Recess": [
                    "CHS1301 Principles of Public Health and Disease Control",
                    "CHS1302 Principles of Health Communication",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "CHS2101 Endocrine and Reproductive Physiology",
                    "CHS2102 Anatomy of the Head and Neck",
                    "CHS2103 Anatomy and Physiology of the Central Nervous System",
                    "CHS2104 Physiology of Special Senses",
                    "CHS2105 Principles of Biomedical Sciences I",
                ],
                "Semester 2": [
                    "CHS2201 General Pharmacology and Autonomous Nervous System",
                    "CHS2202 Clinical Microbiology and Pathology",
                    "CHS2203 Principles of Biomedical Sciences II",
                    "CHS2204 Research Methods and Community Diagnosis",
                    "CHS2205 Nutrition and Health",
                ],
                "Recess": [
                    "CHS2301 Chemotherapy",
                    "CHS2302 Blood and Body Fluids Disorders",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "CHS3101 Cardiovascular and Respiratory Disorders",
                    "CHS3102 Digestive, Nutritional and Metabolic Disorders",
                    "CHS3103 Central Nervous System Disorders",
                    "CHS3104 Central Nervous System Pharmacology and Developmental Psychopathology",
                ],
                "Semester 2": [
                    "CHS3201 Endocrine Disorders",
                    "CHS3202 Reproductive and Urinary Disorders",
                    "CHS3203 Tropical Infectious Diseases",
                ],
                "Recess": [
                    "CHS3311 Principles of Health Policy, Planning, Management and Leadership",
                    "CHS3312 Proposal Development and Report Writing",
                ],
            },
        },
    },
    "Bachelor of Environmental Health Science": {
        "source": "https://sph.mak.ac.ug/program-post/bachelors-of-environmental-health-sciences-behs/",
        "note": "Fetched via a read-proxy after a direct certificate error -- worth a human spot-check against the live page.",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "EHS1102 Introduction to Human Biology",
                    "EHS1103 Principles of Biostatistics",
                    "EHS1104 Principles of Epidemiology",
                    "EHS1109 Human Environment",
                    "EHS1110 Principles of Demography",
                    "EHS1111 Public Health Microbiology",
                ],
                "Semester 2": [
                    "ENR1201 Invertebrate Resources",
                    "EHS1208 Control of Diseases of Public Health Importance",
                    "EHS1209 Hydrology and Hydraulics",
                    "EHS1210 Health Laboratory Management",
                    "EHS1211 Vector and Vermin Control",
                    "EHS1212 Communication for Behaviour Change",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "EHS2110 Community Health and Development",
                    "EHS2111 Health Fundamentals of Environmental Law",
                    "EHS2112 Research Methods",
                    "EHS2103 Environmental Pollution",
                    "EHS2108 Solid Waste Management",
                    "EHS2109 Excreta and Wastewater Management and Treatment",
                ],
                "Semester 2": [
                    "EHS2207 Food and Nutrition",
                    "EHS2208 Building Technology I",
                    "EHS2209 Food Safety Management",
                    "EHS2210 Occupational Health and Safety",
                    "EHS2211 Institutions and Public Places Health Management",
                    "EHS2212 Urban and Rural Water Supply",
                ],
                "Recess": [
                    "EHS2301 Field Training",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "EHS3101 Building Technology II",
                    "EHS3106 Town and Country Planning",
                    "EHS3107 Project Work I (Proposal Development)",
                    "EHS3108 Environmental Health Legislation",
                    "EHS3109 Food Inspection",
                    "EHS3110 Resource Management and Health Policy",
                ],
                "Semester 2": [
                    "EHS3201 Project Work II (Report Writing)",
                    "EHS3209 Building Technology III",
                    "EHS3210 Management of Public Health Emergencies",
                    "EHS3212 Traditional and Complementary Medicine",
                ],
            },
        },
    },
    "Bachelor of Chinese and Asian Studies": {
        "source": "https://chuss.mak.ac.ug/en/course/bachelor-of-chinese-and-asian-studies/",
        "note": (
            "Only Year 1 Semester 1 is itemized on the official page. Later "
            "years/semesters are described only in aggregate (\"four core plus two "
            "elective courses per semester\") without naming the actual courses, so "
            "they're left out here."
        ),
        "years": {
            "Year 1": {
                "Semester 1": [
                    "CAS1110 Introduction to the Study of Language",
                    "CAS1111 Chinese Listening Skills I",
                    "CAS1112 Chinese Reading Skills I",
                    "CAS1113 Chinese Characters I",
                    "CAS1114 Chinese Speaking Skills I",
                    "CAS1105 Comparative Study of Chinese and African Cultures (elective)",
                    "CAS1106 Gender Issues in Asia (elective)",
                    "CAS1107 Introduction to Asian Civilisation (elective)",
                ],
            },
        },
    },
    "Bachelor of Science in Agriculture": {
        "source": "https://caes.mak.ac.ug/bachelor-of-science-in-agriculture/",
        "note": (
            "The official page's Year 3 and Year 4 listings contain duplicate and "
            "inconsistent course-code entries for the same course (e.g. two different "
            "codes both labeled 'Animal Health and Hygiene') -- reproduced as published, "
            "with obvious exact duplicates removed, rather than guessing which code is correct."
        ),
        "years": {
            "Year 1": {
                "Semester 1": [
                    "SOS4101 Soil Survey and Land Evaluation",
                    "AEC1101 Introductory Microeconomics",
                    "AEN1101 Mathematics",
                    "ANS1101 Introduction to Animal Agriculture",
                    "CRS1101 Agricultural Botany and Plant Physiology",
                    "CRS1105 Introduction to Plant Microbiology",
                    "EEE1105 Gender in Agricultural Development",
                    "FST1101 Biochemistry I",
                    "SOS1104 Introduction to Soil Science",
                ],
                "Semester 2": [
                    "AEN1201 Climatology and Field Engineering",
                    "AEN1202 Introduction to Computer Applications",
                    "ANS1203 Zoology and Animal Physiology",
                    "ANS1303 Animal Production Practical Skills",
                    "CRS1202 Introduction to Entomology and Nematology",
                    "CRS1204 Introduction to Agronomy and Ecology",
                    "CRS1208 Introduction to Statistics",
                    "CRS1301 Crop Production Practical Skills",
                    "EEE1301 Agricultural Extension Education Practical Skills",
                    "SOS1202 Soil Biology I",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "AEC2103 Production Economics",
                    "AEN2101 Farm Power and Machinery",
                    "CRS2101 Biometrics",
                    "CRS2102 Annual Crops Agronomy",
                    "CRS2109 Introduction to Genetics",
                    "EEE2108 Introduction to Agricultural Extension",
                    "SOS2101 Soil Physics and Chemistry",
                ],
                "Semester 2": [
                    "AEC2201 Principles of Farm Management and Accounts",
                    "AEN2201 Farm Structures",
                    "ANS2201 Introductory Livestock Management",
                    "CRS2201 Perennial Crops Agronomy",
                    "CRS2203 Horticulture",
                    "CRS2216 Weed Science",
                    "CRS3201 Field Crops Diseases",
                    "EEE2205 Rural Sociology",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "CRS3110 Pasture Agronomy",
                    "ANS3102 Dairy Production Systems",
                    "ANS3105 Poultry Management I",
                    "CFE3109 Agroforestry",
                    "CRS3104 Principles of Plant Breeding",
                    "CRS3105 Economic Entomology and Nematology",
                    "EEE3102 Introduction to Communication and Extension Methods",
                ],
                "Semester 2": [
                    "AEC3201 Agricultural Marketing",
                    "ANS3201 Apiculture",
                    "ANS3202 Animal Health and Hygiene",
                    "ANS3203 Animal Feeds and Feeding",
                    "FST3205 Postharvest Technology",
                    "SOS3201 Soil Conservation and Land Reclamation",
                ],
            },
            "Year 4": {
                "Semester 1": [
                    "AEC4205 Rural Development",
                    "AEC4101 Agricultural Policy and Planning",
                    "AEC4102 Applied Farm Management",
                    "AEC4104 Econometrics",
                    "AEC4106 Intermediate Macroeconomics",
                    "ANS4101 Livestock and Poultry Breeding",
                    "ANS4102 Pig and Rabbit Production Systems",
                    "ANS4104 Fish Farming",
                    "CRS4101 Plant Pathology",
                    "CRS4102 Crop Physiology",
                    "CRS4105 Seed Science and Technology",
                    "CRS4106 Integrated Pest Management Systems",
                    "EEE4102 Agricultural Communication",
                    "EEE4104 Curriculum Development and Training Methods",
                    "EEE4105 Social Research Methods II",
                    "EEE4107 Adult Education",
                    "EEE4110 Participatory Approaches in Extension",
                    "SOS4102 Mineral Fertiliser Technology",
                    "SOS4107 Applied Soil Fertility and Plant Analysis",
                ],
                "Semester 2": [
                    "AEC4201 Resource and Environmental Economics",
                    "AEC4203 International Trade in Agriculture",
                    "AEC4202 Agricultural Finance",
                    "AEC4204 Introduction to Agribusiness Management",
                    "ANS4201 Applied Ruminant Nutrition",
                    "ANS4202 Beef Production and Range Management",
                    "ANS4203 Animal Physiology and Biotechnology",
                    "ANS4205 Small Ruminant Production Systems",
                    "CRS4201 Plant Breeding Technologies",
                    "CRS4202 Plant Biotechnology",
                    "CRS4205 Plant Virology and Bacteriology",
                    "EEE4201 Extension Methods",
                    "EEE4203 Organizational Management and Leadership",
                    "EEE4206 Programme Planning and Evaluation II",
                    "FOM4201 Land Use Policy and Laws",
                    "SOS4201 Applied Soil Physics",
                    "SOS4202 Biofertiliser Technology and Organic Farming",
                    "SOS4204 Soil Productivity Management and Assessment",
                    "SOS4211 Soil and Environmental Protection",
                ],
            },
        },
    },
    "Bachelor of Science in Horticulture": {
        "source": "https://caes.mak.ac.ug/bachelor-of-science-in-horticulture/",
        "note": "The official page lists only one course for Year 4 with no semester breakdown -- likely an incomplete page. Only Years 1-3 are included here.",
        "years": {
            "Year 1": {
                "Semester 1": [
                    "ABM1101 Principles of Business Economics",
                    "AEN1101 Mathematics",
                    "CRS1101 Agricultural Botany and Plant Physiology",
                    "CRS1104 Introduction to Genetics",
                ],
                "Semester 2": [
                    "ABM1203 Introduction to Agribusiness Management",
                    "HRT1201 Introduction to Horticulture",
                    "AEN1202 Climatology and Field Engineering",
                ],
            },
            "Year 2": {
                "Semester 1": [
                    "ABM2101 Principles of Farm Business Management",
                    "SOS1301 Science Practicals",
                    "HRT2104 Plant Propagation and Nursery Management",
                    "HRT2103 Greenhouse Production and Management",
                    "HRT1301 Practical Horticulture",
                    "AEN2101 Farm Power and Machinery",
                    "AEC2101 Production Economics",
                    "ABM2104 Firm Management Case Study Theory",
                ],
                "Semester 2": [
                    "SOS2201 Soil Fertility and Plant Nutrition",
                    "CRS2211 Field Crops Diseases",
                    "AEN2201 Farm Structures",
                ],
            },
            "Year 3": {
                "Semester 1": [
                    "CRS3109 Crop Physiology",
                    "HRT2301 Horticultural Industries Internship",
                    "HRT2302 Horticulture Special Project",
                    "HRT3101 Vegetable Production",
                    "HRT3102 Fruit Production",
                    "HRT3107 Spices",
                ],
                "Semester 2": [
                    "CRS3202 Pesticide Application Technology",
                    "EEE3201 Social Research Methods I",
                    "AEC3201 Agricultural Marketing",
                    "HRT3204 Floriculture, Ornamental and Landscape Horticulture",
                    "ABM3204 Agribusiness Finance",
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
