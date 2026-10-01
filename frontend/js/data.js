/* ==========================================================================
   TSCE — Seed / demo data
   --------------------------------------------------------------------------
   SOURCE OF TRUTH (from the TSCE flyer — do not change silently):
     programme names, fees, durations, campaign dates, discounts,
     contact numbers, address, website, organisation name.
   EVERYTHING ELSE here (people, IDs, scores, attendance, staff,
   testimonials, dashboard baselines) is clearly DEMO DATA.
   ========================================================================== */

const TSCE_FLYER = Object.freeze({
    name: "Trust Skill Acquisition Centre of Excellence",
    short: "TSCE",
    campaign: "Skills Acquisition Training Program 2026",
    headline: "Launch Your Tech Career This October!",
    startDate: "2026-10-12",            // Monday, 12th October 2026
    enrolmentOpens: "2026-10-01",       // Enrollment: October 1–12
    enrolmentCloses: "2026-10-12",
    earlyBirdDeadline: "2026-10-01",    // payment BEFORE 1 October 2026
    discounts: { earlybird: 15, excellence: 50, scholarshipMax: 40 },
    phones: ["0803 452 2501", "0904 439 2228", "0803 386 0784"],
    website: "www.tsce.edu.ng",
    email: "info@tsce.edu.ng",
    address: "KM8, Sokoto Road, ITN Opposite Aviation Quarters Zangon Shanu Zaria, P.O. Box 984 Zaria, Nigeria",
    city: "Zaria, Kaduna State, Nigeria",
    category: "Core Technical & Digital",
    motto: ["Empowering People", "Building Skills", "Driving Sustainable Development"],
    // Social handles as shown on the flyer footer (placeholder URLs until confirmed)
    socials: [
        { icon: "fa-facebook-f", label: "Facebook", url: "#" },
        { icon: "fa-instagram", label: "Instagram", url: "#" },
        { icon: "fa-x-twitter", label: "X (Twitter)", url: "#" },
        { icon: "fa-linkedin-in", label: "LinkedIn", url: "#" },
        { icon: "fa-youtube", label: "YouTube", url: "#" },
        { icon: "fa-tiktok", label: "TikTok", url: "#" }
    ]
});

/* ---- Programme catalogue (name / weeks / fee from flyer; rest = demo) ---- */
const PROGRAMME_CATALOGUE = [
    {
        id: "cad", code: "TSCE-CAD", name: "CAD for Architecture & Engineering", weeks: 8, fee: 50000,
        track: "Design", icon: "fa-compass-drafting", color: "#1846D6", colorBg: "#EEF3FF",
        capacity: 30, enrolled: 21, instructor: "Engr. Sani Abdulkadir",
        overview: "Master computer-aided design for architectural and engineering drawings — from 2D drafting to 3D modelling and professional plotting — using industry-standard tools.",
        outcomes: ["Produce accurate 2D architectural and engineering drawings", "Build and render 3D models of buildings and components", "Apply layers, blocks, annotation and dimensioning standards", "Prepare professional plot sheets and drawing sets"],
        modules: ["CAD Fundamentals & Interface", "2D Drafting & Precision Tools", "Layers, Blocks & Annotation", "Architectural Floor Plans", "Engineering & Mechanical Drawings", "3D Modelling", "Rendering & Visualisation", "Plotting & Final Project"],
        audience: ["Architecture and engineering students", "Draughtsmen and technicians", "Graduates seeking design roles"],
        careers: ["CAD Technician", "Architectural Draughtsman", "Design Assistant", "BIM Support Officer"],
        requirements: ["Basic computer literacy", "Interest in drawing and design", "Laptop recommended (lab access provided)"]
    },
    {
        id: "cyber-fund", code: "TSCE-CSF", name: "Cybersecurity Fundamentals", weeks: 6, fee: 45000,
        track: "Security", icon: "fa-shield-halved", color: "#DC2F45", colorBg: "#FDEEF0",
        capacity: 35, enrolled: 29, instructor: "Mal. Aminu Lawal",
        overview: "Build a strong foundation in how systems are attacked and defended. Learn security principles, threats, network security basics and safe digital practices.",
        outcomes: ["Explain the CIA triad and core security principles", "Identify common threats, malware and social engineering", "Apply basic network and endpoint security controls", "Practise safe password, email and data handling"],
        modules: ["Introduction to Cybersecurity", "Threats, Vulnerabilities & Attacks", "Network Security Basics", "Cryptography Essentials", "Endpoint & Identity Security", "Security Awareness & Final Assessment"],
        audience: ["Beginners interested in cybersecurity", "IT support staff", "Business owners protecting their data"],
        careers: ["Security Support Analyst", "IT Security Assistant", "SOC Trainee"],
        requirements: ["Basic computer literacy", "No prior security experience required"]
    },
    {
        id: "cyber-ops", code: "TSCE-CSO", name: "Cybersecurity Operations Certificate", weeks: 8, fee: 50000,
        track: "Security", icon: "fa-user-shield", color: "#B4234A", colorBg: "#FCEEF2",
        capacity: 30, enrolled: 18, instructor: "Mal. Aminu Lawal",
        overview: "Hands-on security operations: monitor, detect, analyse and respond to incidents the way a Security Operations Centre (SOC) analyst does.",
        outcomes: ["Monitor network traffic and system logs", "Detect and triage security alerts", "Follow an incident response process", "Use common SOC tools and write incident reports"],
        modules: ["SOC Roles & Operations", "Network Protocols & Traffic Analysis", "Windows & Linux Security", "Log Analysis & SIEM", "Threat Intelligence", "Intrusion Detection", "Incident Response", "Capstone: SOC Simulation"],
        audience: ["Graduates of Cybersecurity Fundamentals", "IT professionals moving into security", "Network administrators"],
        careers: ["SOC Analyst (Tier 1)", "Incident Response Assistant", "Security Monitoring Officer"],
        requirements: ["Basic networking knowledge", "Cybersecurity Fundamentals or equivalent (recommended)"]
    },
    {
        id: "data-ai", code: "TSCE-DSA", name: "Data Science & AI Literacy", weeks: 8, fee: 45000,
        track: "Data & AI", icon: "fa-brain", color: "#7C3AED", colorBg: "#F3EEFE",
        capacity: 35, enrolled: 27, instructor: "Dr. Hauwa Bello",
        overview: "Understand data and artificial intelligence practically — collect, clean, analyse and visualise data, and use AI tools responsibly for work and innovation.",
        outcomes: ["Clean, analyse and visualise real datasets", "Use spreadsheets and Python for data analysis", "Understand how machine learning models work", "Use generative AI tools productively and responsibly"],
        modules: ["Data Literacy Foundations", "Spreadsheets for Analysis", "Python for Data", "Data Cleaning & Wrangling", "Data Visualisation", "Intro to Machine Learning", "Generative AI & Prompting", "Capstone: Data Story"],
        audience: ["Students and graduates of any discipline", "Professionals who work with reports and data", "Aspiring data analysts"],
        careers: ["Data Analyst (Junior)", "Business Intelligence Assistant", "AI-enabled Operations Officer"],
        requirements: ["Basic computer literacy", "Comfort with basic mathematics"]
    },
    {
        id: "fullstack", code: "TSCE-FSE", name: "Full-Stack Software Engineering", weeks: 10, fee: 50000,
        track: "Software", icon: "fa-code", color: "#0EA5E9", colorBg: "#E7F6FE",
        capacity: 40, enrolled: 32, instructor: "Engr. Yakubu Danladi",
        overview: "Go from zero to deploying complete web applications. Learn frontend and backend development, databases, APIs and deployment through real projects.",
        outcomes: ["Build responsive websites with HTML, CSS and JavaScript", "Develop frontends and REST APIs", "Design and query databases", "Implement authentication and deploy to the cloud", "Ship a portfolio-ready capstone project"],
        modules: ["Web Development Fundamentals", "HTML & CSS", "JavaScript", "Git & GitHub", "Frontend Development", "Backend Development", "APIs", "Databases", "Authentication", "Deployment", "Final Capstone Project"],
        audience: ["Aspiring software developers", "Computer science students and graduates", "Career switchers into tech"],
        careers: ["Frontend Developer", "Backend Developer", "Full-Stack Developer", "Freelance Web Developer"],
        requirements: ["Basic computer literacy", "Laptop strongly recommended", "Commitment to weekly practice"]
    },
    {
        id: "digital-marketing", code: "TSCE-DME", name: "Digital Marketing & E-Commerce", weeks: 6, fee: 50000,
        track: "Business", icon: "fa-bullhorn", color: "#F59E0B", colorBg: "#FFF6E3",
        capacity: 35, enrolled: 24, instructor: "Mrs. Zainab Usman",
        overview: "Grow brands and sell online. Learn social media marketing, content, paid ads, SEO, analytics and how to set up and run an online store.",
        outcomes: ["Plan and run social media campaigns", "Create engaging content for digital channels", "Run paid ads and measure ROI", "Set up and manage an e-commerce store"],
        modules: ["Digital Marketing Foundations", "Social Media Marketing", "Content & Copywriting", "SEO & Search Marketing", "Paid Ads & Analytics", "E-Commerce Store Setup"],
        audience: ["Entrepreneurs and small business owners", "Marketing and sales professionals", "Content creators"],
        careers: ["Digital Marketer", "Social Media Manager", "E-Commerce Manager", "Content Strategist"],
        requirements: ["Basic computer and smartphone skills"]
    },
    {
        id: "hardware", code: "TSCE-CHE", name: "Computer Hardware Engineering", weeks: 8, fee: 50000,
        track: "Hardware", icon: "fa-microchip", color: "#12A150", colorBg: "#E9F8EF",
        capacity: 25, enrolled: 19, instructor: "Mr. Ibrahim Tanko",
        overview: "Understand computers inside-out: components, assembly, diagnostics, repair, maintenance and upgrades of desktops and laptops.",
        outcomes: ["Identify and install computer components", "Assemble, configure and upgrade PCs", "Diagnose and repair hardware faults", "Perform preventive maintenance safely"],
        modules: ["Computer Architecture", "Components & Peripherals", "PC Assembly", "BIOS/UEFI & OS Installation", "Diagnostics & Troubleshooting", "Laptop Repair", "Power & Safety", "Practical Repair Project"],
        audience: ["Aspiring hardware technicians", "IT support staff", "Entrepreneurs in computer repair"],
        careers: ["Hardware Technician", "IT Support Engineer", "Computer Repair Entrepreneur"],
        requirements: ["Basic computer literacy", "Interest in hands-on technical work"]
    },
    {
        id: "network", code: "TSCE-NET", name: "Network Engineering", weeks: 8, fee: 50000,
        track: "Networking", icon: "fa-network-wired", color: "#0B84D8", colorBg: "#E6F4FD",
        capacity: 30, enrolled: 22, instructor: "Engr. Musa Garba",
        overview: "Design, build and troubleshoot computer networks — from cabling and IP addressing to routing, switching, wireless and network security.",
        outcomes: ["Design LAN/WAN networks and IP addressing schemes", "Configure routers and switches", "Set up secure wireless networks", "Troubleshoot network connectivity"],
        modules: ["Networking Fundamentals", "Cabling & Physical Layer", "IP Addressing & Subnetting", "Switching & VLANs", "Routing Protocols", "Wireless Networking", "Network Security", "Network Design Project"],
        audience: ["IT students and graduates", "IT support staff", "Aspiring network engineers"],
        careers: ["Network Technician", "Network Administrator", "NOC Engineer"],
        requirements: ["Basic computer literacy"]
    },
    {
        id: "it-essentials", code: "TSCE-ITE", name: "IT Essentials: Computer Hardware Basics", weeks: 6, fee: 45000,
        track: "Hardware", icon: "fa-desktop", color: "#0891B2", colorBg: "#E6FBFE",
        capacity: 35, enrolled: 26, instructor: "Mr. Ibrahim Tanko",
        overview: "An entry-level programme covering computer basics, hardware, operating systems and everyday IT support skills — the perfect starting point in tech.",
        outcomes: ["Understand computer hardware and software basics", "Install and configure operating systems", "Perform basic troubleshooting", "Support users with everyday IT problems"],
        modules: ["Introduction to Computers", "Hardware Components", "Operating Systems", "Networking Basics", "Troubleshooting Fundamentals", "IT Support Practicals"],
        audience: ["Complete beginners", "Secondary school leavers", "Office staff"],
        careers: ["IT Support Assistant", "Help Desk Officer", "Computer Operator"],
        requirements: ["No prior experience required"]
    },
    {
        id: "cisco-cloud", code: "TSCE-CCT", name: "Cisco Cloud Technologies", weeks: 8, fee: 50000,
        track: "Cloud", icon: "fa-cloud", color: "#2563EB", colorBg: "#EAF1FE",
        capacity: 30, enrolled: 16, instructor: "Engr. Musa Garba",
        overview: "Learn how modern cloud infrastructure works — virtualisation, cloud service models, data-centre networking and cloud security using Cisco-aligned content.",
        outcomes: ["Explain cloud service and deployment models", "Understand virtualisation and data-centre networking", "Apply cloud security fundamentals", "Plan basic cloud migrations"],
        modules: ["Cloud Computing Concepts", "Virtualisation", "Data Centre Networking", "Cloud Storage", "Cloud Security", "Automation Basics", "Hybrid & Multi-Cloud", "Cloud Project"],
        audience: ["Network and IT professionals", "Graduates interested in cloud careers"],
        careers: ["Cloud Support Associate", "Cloud Network Technician", "Infrastructure Engineer (Junior)"],
        requirements: ["Basic networking knowledge recommended"]
    },
    {
        id: "aws-db", code: "TSCE-AWS", name: "AWS Database Management", weeks: 8, fee: 50000,
        track: "Cloud", icon: "fa-database", color: "#F97316", colorBg: "#FFF1E7",
        capacity: 30, enrolled: 20, instructor: "Dr. Hauwa Bello",
        overview: "Design, deploy and manage databases on Amazon Web Services — relational and NoSQL — including backups, security, performance and scaling.",
        outcomes: ["Design relational database schemas and write SQL", "Deploy and manage databases on AWS", "Configure backups, security and monitoring", "Choose between relational and NoSQL solutions"],
        modules: ["Database Fundamentals", "SQL Essentials", "AWS Cloud Basics", "Amazon RDS", "Amazon DynamoDB", "Security & IAM", "Backup, Monitoring & Performance", "Database Project"],
        audience: ["Developers and IT professionals", "Data and cloud enthusiasts"],
        careers: ["Database Administrator (Junior)", "Cloud Database Associate", "Data Engineer (Trainee)"],
        requirements: ["Basic computer literacy", "Some exposure to data or programming helpful"]
    }
];

/* ---- Deterministic demo data generator ---- */
const SeedData = (() => {
    // Small seeded PRNG so demo data is identical on every reset.
    function rng(seed) {
        return function () {
            seed |= 0; seed = seed + 0x6D2B79F5 | 0;
            let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
            t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
            return ((t ^ t >>> 14) >>> 0) / 4294967296;
        };
    }
    const r = rng(20261012);
    const pick = (arr) => arr[Math.floor(r() * arr.length)];
    const between = (a, b) => Math.round(a + r() * (b - a));
    const pad = (n, l = 5) => String(n).padStart(l, "0");
    const iso = (d) => new Date(d).toISOString();
    const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };

    const states = ["Kaduna", "Kano", "Katsina", "Zamfara", "Sokoto", "Niger", "FCT", "Plateau", "Bauchi", "Kaduna"];
    const lgas = { Kaduna: ["Zaria", "Sabon Gari", "Kaduna North", "Giwa", "Igabi"], Kano: ["Nassarawa", "Fagge", "Tarauni"], Katsina: ["Katsina", "Funtua"], Zamfara: ["Gusau"], Sokoto: ["Sokoto North"], Niger: ["Minna"], FCT: ["AMAC", "Bwari"], Plateau: ["Jos North"], Bauchi: ["Bauchi"] };
    const quals = ["SSCE", "OND", "NCE", "HND", "B.Sc", "B.Eng", "SSCE", "OND"];
    const insts = ["Ahmadu Bello University, Zaria", "Nuhu Bamalli Polytechnic, Zaria", "Federal College of Education, Zaria", "Kaduna Polytechnic", "Government Secondary School, Zaria", "Barewa College, Zaria", "Kaduna State University", "Federal Government College, Kaduna"];
    const prefixes = ["0803", "0806", "0813", "0816", "0703", "0706", "0810", "0903", "0906", "0805", "0807", "0815", "0905", "0802", "0808", "0812", "0701", "0708", "0902", "0901"];
    const phone = () => `${pick(prefixes)} ${between(100, 999)} ${between(1000, 9999)}`;
    const email = (f, l) => `${f}.${l}@example.com`.toLowerCase();
    const grade = (s) => s >= 80 ? "A" : s >= 70 ? "B" : s >= 60 ? "C" : s >= 50 ? "D" : "F";

    // Cohorts (demo)
    const COHORTS = {
        jul: { name: "July 2026 Cohort", start: "2026-06-01" },
        aug: { name: "August 2026 Cohort", start: "2026-08-03" },
        sep: { name: "September 2026 Cohort", start: "2026-09-07" },
        oct: { name: "October 2026 Cohort", start: TSCE_FLYER.startDate }
    };
    const TODAY = new Date("2026-09-25T09:00:00");

    // Students — 20 records (demo). [first, last, gender, programme, idNo, cohort, discount]
    const studentRows = [
        ["Amina", "Yusuf", "Female", "fullstack", 124, "aug", "earlybird"],
        ["Muhammad", "Ibrahim", "Male", "cyber-fund", 131, "aug", "excellence"],
        ["Fatima", "Abdullahi", "Female", "data-ai", 145, "aug", "earlybird"],
        ["Abdulrahman", "Musa", "Male", "network", 152, "aug", "scholarship"],
        ["Maryam", "Sani", "Female", "digital-marketing", 108, "jul", "earlybird"],
        ["Usman", "Bello", "Male", "cad", 113, "aug", null],
        ["Zainab", "Ahmad", "Female", "fullstack", 127, "aug", "excellence"],
        ["Ibrahim", "Suleiman", "Male", "cyber-ops", 133, "aug", "earlybird"],
        ["Hafsat", "Mohammed", "Female", "aws-db", 138, "aug", null],
        ["Bashir", "Abdullahi", "Male", "hardware", 141, "aug", "earlybird"],
        ["Aisha", "Lawal", "Female", "cisco-cloud", 147, "aug", "scholarship"],
        ["Yusuf", "Garba", "Male", "it-essentials", 102, "jul", "earlybird"],
        ["Khadija", "Umar", "Female", "data-ai", 149, "aug", null],
        ["Sadiq", "Aliyu", "Male", "fullstack", 155, "aug", "earlybird"],
        ["Halima", "Idris", "Female", "digital-marketing", 158, "aug", null],
        ["Nuhu", "Danjuma", "Male", "network", 160, "aug", "earlybird"],
        ["Rukayya", "Shehu", "Female", "cad", 163, "aug", "scholarship"],
        ["Chinedu", "Okafor", "Male", "cyber-fund", 166, "aug", null],
        ["Blessing", "Adeyemi", "Female", "aws-db", 169, "aug", "earlybird"],
        ["Emeka", "Nwosu", "Male", "hardware", 105, "jul", "excellence"]
    ];

    const discountPct = (type) => type === "earlybird" ? 15 : type === "excellence" ? 50 : type === "scholarship" ? between(2, 4) * 10 : 0;
    const discountName = (type) => ({ earlybird: "Early Bird Discount", excellence: "Excellence Award", scholarship: "Performance Scholarship" }[type] || "None");
    const channels = ["card", "card", "transfer", "virtual"];
    const txRef = (date, n) => {
        const d = new Date(date);
        return `TSCE-ZP-${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}-${pad(n, 6)}`;
    };

    function build() {
        const programmes = PROGRAMME_CATALOGUE.map((p) => ({
            ...p, category: TSCE_FLYER.category, status: "Active",
            schedules: ["Weekday Morning (9:00am – 12:00pm)", "Weekday Afternoon (1:00pm – 4:00pm)", "Weekend (Sat & Sun, 10:00am – 3:00pm)"],
            createdAt: iso("2026-05-01")
        }));
        const P = Object.fromEntries(programmes.map((p) => [p.id, p]));

        const students = [], applications = [], payments = [], attendance = [], results = [], scholarships = [], users = [];
        let txSeq = 1180;

        /* --- Enrolled / completed students --- */
        studentRows.forEach(([first, last, gender, pid, no, cohortKey, disc], i) => {
            const prog = P[pid];
            // Longer programmes run in the August cohort; 6–8 week programmes in September (still in session)
            const cohort = COHORTS[cohortKey === "aug" && prog.weeks < 10 ? "sep" : cohortKey];
            const start = new Date(cohort.start);
            const end = addDays(start, prog.weeks * 7 - 3);
            const completed = end < TODAY;
            const id = `TSCE/2026/${pad(no)}`;
            const appId = `TSCE/APP/2026/${pad(no)}`;
            const pct = discountPct(disc);
            const discountAmt = Math.round(prog.fee * pct / 100);
            const paid = prog.fee - discountAmt;
            const appDate = addDays(start, -between(12, 30));
            const paidDate = addDays(appDate, between(0, 3));
            const ref = txRef(paidDate, ++txSeq);
            const em = email(first, last);
            const st = pick(states);
            const isAmina = i === 0;

            // Progress / performance
            let progress;
            if (completed) progress = 100;
            else {
                const elapsed = (TODAY - start) / (prog.weeks * 7 * 864e5);
                progress = Math.min(96, Math.round(elapsed * 100 + between(-6, 4)));
            }
            if (isAmina) progress = 78;

            // Module-level progress
            const nMods = prog.modules.length;
            let moduleProgress;
            if (isAmina) moduleProgress = [100, 100, 100, 100, 100, 100, 100, 100, 60, 0, 0];
            else {
                const doneExact = progress / 100 * nMods;
                moduleProgress = prog.modules.map((_, m) => m + 1 <= Math.floor(doneExact) ? 100 : m < doneExact ? Math.round((doneExact - m) * 100) : 0);
            }

            const student = {
                id, appId, userEmail: em, firstName: first, lastName: last, middleName: "", gender,
                phone: isAmina ? "0803 214 5567" : phone(), email: em,
                dob: `${between(1996, 2006)}-${String(between(1, 12)).padStart(2, "0")}-${String(between(1, 28)).padStart(2, "0")}`,
                state: st, lga: pick(lgas[st] || ["Zaria"]), address: `${between(2, 48)} ${pick(["Gaskiya Road", "Kofar Doka", "Samaru", "Tudun Wada", "PZ Road", "Kongo", "Hanwa", "GRA", "Sabon Gari"])}, Zaria`,
                qualification: pick(quals), institution: pick(insts),
                programmeId: pid, cohort: cohort.name, schedule: prog.schedules[i % 3],
                startDate: iso(start), endDate: iso(end), instructor: prog.instructor,
                progress, moduleProgress, status: completed ? "Completed" : "Active",
                paymentStatus: "Paid", amountPaid: paid, discountType: disc, discountPct: pct,
                certificateNo: `TSCE/CERT/2026/${pad(no)}`,
                certificateStatus: completed ? "Issued" : "Not Issued",
                certificateIssuedAt: completed ? iso(addDays(end, 5)) : null,
                emergencyContact: `${pick(["Alhaji", "Mallam", "Mrs.", "Hajiya"])} ${last} · ${phone()}`,
                createdAt: iso(paidDate)
            };
            if (isAmina) Object.assign(student, { dob: "2001-04-17", state: "Kaduna", lga: "Zaria", address: "14 Gaskiya Road, Samaru, Zaria", qualification: "B.Sc", institution: "Ahmadu Bello University, Zaria", schedule: prog.schedules[0] });
            students.push(student);

            users.push({ email: em, password: "student123", role: "student", name: `${first} ${last}`, studentId: id });

            applications.push({
                id: appId, firstName: first, middleName: "", lastName: last, gender, dob: student.dob,
                phone: student.phone, email: em, address: student.address, state: student.state, lga: student.lga,
                qualification: student.qualification, institution: student.institution, gradYear: between(2019, 2025),
                waecStatus: "Available", waecYear: disc === "excellence" ? between(2020, 2024) : between(2015, 2024),
                numAs: disc === "excellence" ? between(5, 8) : between(1, 4),
                programmeId: pid, schedule: student.schedule, intake: cohort.name,
                fee: prog.fee, discountType: disc, discountPct: pct, discountAmount: discountAmt, amountPayable: paid,
                awardRequest: disc === "excellence" || disc === "scholarship" ? disc : null,
                paymentStatus: "Paid", status: "Enrolled", txRef: ref, studentId: id,
                createdAt: iso(appDate), paidAt: iso(paidDate),
                history: [
                    { at: iso(appDate), text: "Application submitted online" },
                    { at: iso(paidDate), text: `Payment of ₦${paid.toLocaleString()} confirmed via Zainpay`, ok: true },
                    { at: iso(addDays(paidDate, 2)), text: "Application reviewed and accepted", ok: true },
                    { at: iso(addDays(paidDate, 3)), text: `Enrolled as ${id}`, ok: true }
                ]
            });

            payments.push({
                id: ref, ref, applicationId: appId, studentId: id, name: `${first} ${last}`, email: em,
                programmeId: pid, amount: paid, fee: prog.fee, discount: discountAmt, gateway: "Zainpay",
                channel: pick(channels), status: "SUCCESS", description: `${prog.name} — tuition`,
                createdAt: iso(paidDate), verifiedAt: iso(paidDate)
            });

            if (disc === "excellence" || disc === "scholarship") {
                scholarships.push({
                    id: `SCH-${pad(scholarships.length + 1, 4)}`, applicationId: appId, studentId: id,
                    name: `${first} ${last}`, programmeId: pid, type: disc,
                    requestedPct: disc === "excellence" ? 50 : 40, awardedPct: pct, status: "Approved",
                    evidence: disc === "excellence" ? `WAEC ${applications.at(-1).waecYear} — ${applications.at(-1).numAs} A's (verified)` : `Intake exam score: ${between(78, 94)}%`,
                    reviewedBy: "Admissions Office", createdAt: iso(appDate), reviewedAt: iso(addDays(appDate, 2))
                });
            }

            /* Attendance: Mon/Wed/Fri sessions from cohort start (max 20 per student, until today/end) */
            const sessionEnd = completed ? end : TODAY;
            let d = new Date(start), count = 0;
            const sessions = [];
            while (d <= sessionEnd) {
                const dow = d.getDay();
                if (dow === 1 || dow === 3 || dow === 5) sessions.push(new Date(d));
                d = addDays(d, 1);
            }
            const recent = sessions.slice(-24);
            const absentRate = isAmina ? 0 : between(3, 14) / 100;
            recent.forEach((sd, k) => {
                const modIdx = Math.min(nMods - 1, Math.floor((sd - start) / (prog.weeks * 7 * 864e5) * nMods));
                let status = r() < absentRate ? "Absent" : r() < 0.06 ? "Late" : "Present";
                if (isAmina) status = (k === 5 || k === 17) ? "Absent" : "Present";   // 22 of 24 sessions ≈ 92%
                attendance.push({ id: `ATT-${id}-${k}`, studentId: id, programmeId: pid, date: iso(sd), session: prog.modules[modIdx], status });
                count++;
            });

            /* Results (assessments) for completed/in-progress modules */
            const aminaScores = [88, 86, 79, 91, 82, 74, 86, 85];   // avg ≈ 84%
            prog.modules.forEach((mod, m) => {
                if (moduleProgress[m] < 100) return;
                const score = isAmina ? aminaScores[m] : between(58, 95);
                results.push({
                    id: `RES-${id}-${m}`, studentId: id, programmeId: pid, module: mod,
                    type: m === nMods - 1 ? "Capstone Project" : pick(["Practical Assignment", "Module Test", "Project"]),
                    score, grade: grade(score), status: "Published",
                    date: iso(addDays(start, Math.round((m + 1) * prog.weeks * 7 / nMods))),
                    remark: score >= 85 ? "Excellent work" : score >= 70 ? "Very good" : score >= 60 ? "Good — keep practising" : "Fair"
                });
            });
        });

        /* --- 15 new applications for the October 2026 cohort (demo) --- */
        const newApps = [
            ["Maryam", "Abubakar", "Female", "fullstack", "Enrolled", "SUCCESS", "earlybird", null],
            ["Umar", "Faruk", "Male", "cyber-fund", "Accepted", "SUCCESS", "earlybird", null],
            ["Hauwa", "Jibril", "Female", "data-ai", "Under Review", "SUCCESS", "earlybird", "excellence"],
            ["Aliyu", "Hassan", "Male", "network", "Paid", "SUCCESS", "earlybird", "scholarship"],
            ["Safiya", "Kabir", "Female", "digital-marketing", "Pending", "PENDING", "earlybird", null],
            ["Abdullahi", "Sa'ad", "Male", "cad", "Paid", "SUCCESS", null, "scholarship"],
            ["Jamila", "Tijjani", "Female", "fullstack", "Under Review", "SUCCESS", "earlybird", "excellence"],
            ["Kabiru", "Adamu", "Male", "hardware", "Pending", "FAILED", "earlybird", null],
            ["Nafisa", "Ismail", "Female", "aws-db", "Accepted", "SUCCESS", "earlybird", null],
            ["Tunde", "Bakare", "Male", "cisco-cloud", "Rejected", "REFUNDED", null, null],
            ["Esther", "Danladi", "Female", "it-essentials", "Paid", "SUCCESS", "earlybird", "scholarship"],
            ["Mustapha", "Yakubu", "Male", "cyber-ops", "Pending", null, null, "excellence"],
            ["Ruqayya", "Mahmud", "Female", "data-ai", "Paid", "SUCCESS", "earlybird", null],
            ["Ahmad", "Shuaibu", "Male", "fullstack", "Under Review", "SUCCESS", "earlybird", "scholarship"],
            ["Grace", "Audu", "Female", "network", "Pending", "PENDING", null, null]
        ];
        newApps.forEach(([first, last, gender, pid, status, pay, disc, award], i) => {
            const prog = P[pid];
            const no = 201 + i;
            const appId = `TSCE/APP/2026/${pad(no)}`;
            const created = new Date(2026, 8, 3 + i, 9 + (i % 8), (i * 13) % 60);
            const pct = discountPct(disc);
            const discountAmt = Math.round(prog.fee * pct / 100);
            const payable = prog.fee - discountAmt;
            const paidDate = addDays(created, i % 3 === 0 ? 0 : 1);
            const em = email(first, last.replace("'", ""));
            const st = pick(states);
            const ref = pay ? txRef(paidDate, ++txSeq) : null;
            const paymentStatus = pay === "SUCCESS" || pay === "REFUNDED" ? "Paid" : pay === "PENDING" ? "Pending" : pay === "FAILED" ? "Failed" : "Unpaid";
            const waecYear = award === "excellence" ? between(2021, 2025) : between(2016, 2025);
            const numAs = award === "excellence" ? between(5, 7) : between(1, 4);

            const history = [{ at: iso(created), text: "Application submitted online" }];
            if (pay === "SUCCESS" || pay === "REFUNDED") history.push({ at: iso(paidDate), text: `Payment of ₦${payable.toLocaleString()} confirmed via Zainpay`, ok: true });
            if (pay === "FAILED") history.push({ at: iso(paidDate), text: "Payment attempt failed (card declined)" });
            if (pay === "PENDING") history.push({ at: iso(paidDate), text: "Bank transfer initiated — awaiting confirmation" });
            if (status === "Under Review") history.push({ at: iso(addDays(paidDate, 1)), text: "Moved to review by Admissions Office" });
            if (status === "Accepted") history.push({ at: iso(addDays(paidDate, 2)), text: "Application accepted", ok: true });
            if (status === "Rejected") history.push({ at: iso(addDays(paidDate, 2)), text: "Application rejected — programme capacity reached; refund issued" });

            let studentId = null;
            if (status === "Enrolled") {
                studentId = `TSCE/2026/${pad(no)}`;
                history.push({ at: iso(addDays(paidDate, 3)), text: `Enrolled as ${studentId}`, ok: true });
                students.push({
                    id: studentId, appId, userEmail: em, firstName: first, lastName: last, middleName: "", gender, phone: phone(), email: em,
                    dob: `${between(1998, 2006)}-0${between(1, 9)}-1${between(0, 9)}`, state: st, lga: pick(lgas[st] || ["Zaria"]),
                    address: `${between(2, 40)} Kongo Road, Zaria`, qualification: pick(quals), institution: pick(insts),
                    programmeId: pid, cohort: COHORTS.oct.name, schedule: prog.schedules[1],
                    startDate: iso(COHORTS.oct.start), endDate: iso(addDays(COHORTS.oct.start, prog.weeks * 7 - 3)), instructor: prog.instructor,
                    progress: 0, moduleProgress: prog.modules.map(() => 0), status: "Active", paymentStatus: "Paid",
                    amountPaid: payable, discountType: disc, discountPct: pct, certificateNo: `TSCE/CERT/2026/${pad(no)}`,
                    certificateStatus: "Not Issued", certificateIssuedAt: null, emergencyContact: `Mallam ${last} · ${phone()}`, createdAt: iso(paidDate)
                });
                users.push({ email: em, password: "student123", role: "student", name: `${first} ${last}`, studentId });
            }

            applications.push({
                id: appId, firstName: first, middleName: "", lastName: last, gender,
                dob: `${between(1997, 2007)}-${String(between(1, 12)).padStart(2, "0")}-${String(between(1, 28)).padStart(2, "0")}`,
                phone: phone(), email: em, address: `${between(2, 60)} ${pick(["Samaru", "Tudun Jukun", "Kwarbai", "Muchia", "Dogarawa"])}, Zaria`,
                state: st, lga: pick(lgas[st] || ["Zaria"]), qualification: pick(quals), institution: pick(insts),
                gradYear: between(2019, 2025), waecStatus: "Available", waecYear, numAs,
                programmeId: pid, schedule: prog.schedules[i % 3], intake: COHORTS.oct.name,
                fee: prog.fee, discountType: disc, discountPct: pct, discountAmount: discountAmt, amountPayable: payable,
                awardRequest: award, paymentStatus, status, txRef: ref, studentId,
                createdAt: iso(created), paidAt: pay === "SUCCESS" || pay === "REFUNDED" ? iso(paidDate) : null, history
            });

            if (pay) {
                payments.push({
                    id: ref, ref, applicationId: appId, studentId, name: `${first} ${last}`, email: em, programmeId: pid,
                    amount: payable, fee: prog.fee, discount: discountAmt, gateway: "Zainpay", channel: pay === "PENDING" ? "transfer" : pick(channels),
                    status: pay, description: `${prog.name} — tuition`, createdAt: iso(paidDate),
                    verifiedAt: pay === "SUCCESS" || pay === "REFUNDED" ? iso(paidDate) : null,
                    failureReason: pay === "FAILED" ? "Card declined by issuing bank (51 — insufficient funds)" : null,
                    refundedAt: pay === "REFUNDED" ? iso(addDays(paidDate, 3)) : null
                });
            }

            if (award) {
                const approved = status === "Accepted" && award === "excellence";
                scholarships.push({
                    id: `SCH-${pad(scholarships.length + 1, 4)}`, applicationId: appId, studentId,
                    name: `${first} ${last}`, programmeId: pid, type: award,
                    requestedPct: award === "excellence" ? 50 : 40, awardedPct: approved ? 50 : null, status: approved ? "Approved" : "Pending",
                    evidence: award === "excellence" ? `WAEC ${waecYear} — ${numAs} A's (declared)` : `Intake exam scheduled — ${pick(["3 Oct", "5 Oct", "7 Oct"])} 2026`,
                    interviewScore: award === "scholarship" && i % 2 === 0 ? between(72, 93) : null,
                    reviewedBy: approved ? "Admissions Office" : null, createdAt: iso(created), reviewedAt: approved ? iso(addDays(created, 2)) : null
                });
            }
        });

        /* --- Staff (10, demo) --- */
        const staff = [
            ["STF-001", "Dr. Abubakar Sadiq", "Director / Admin", "Management", "admin@tsce.edu.ng", "admin"],
            ["STF-002", "Hajiya Rabi Isa", "Admissions Officer", "Admissions", "admissions@tsce.edu.ng", "staff"],
            ["STF-003", "Mr. Kamal Shehu", "Bursar", "Finance", "bursary@tsce.edu.ng", "staff"],
            ["STF-004", "Engr. Yakubu Danladi", "Lead Instructor — Software", "Academics", "y.danladi@tsce.edu.ng", "staff"],
            ["STF-005", "Mal. Aminu Lawal", "Instructor — Cybersecurity", "Academics", "a.lawal@tsce.edu.ng", "staff"],
            ["STF-006", "Dr. Hauwa Bello", "Instructor — Data & Cloud", "Academics", "h.bello@tsce.edu.ng", "staff"],
            ["STF-007", "Engr. Musa Garba", "Instructor — Networking & Cloud", "Academics", "m.garba@tsce.edu.ng", "staff"],
            ["STF-008", "Mrs. Zainab Usman", "Instructor — Digital Marketing", "Academics", "z.usman@tsce.edu.ng", "staff"],
            ["STF-009", "Mr. Ibrahim Tanko", "Instructor — Hardware", "Academics", "i.tanko@tsce.edu.ng", "staff"],
            ["STF-010", "Engr. Sani Abdulkadir", "Instructor — CAD", "Academics", "s.abdulkadir@tsce.edu.ng", "staff"]
        ].map(([id, name, title, dept, em, role], i) => ({
            id, name, title, department: dept, email: em, role, phone: phone(), status: i === 9 ? "On Leave" : "Active", joined: iso(new Date(2024 + (i % 2), (i * 2) % 12, 3 + i))
        }));
        users.push({ email: "admin@tsce.edu.ng", password: "admin123", role: "admin", name: "Dr. Abubakar Sadiq", staffId: "STF-001" });
        users.push({ email: "admissions@tsce.edu.ng", password: "staff123", role: "staff", name: "Hajiya Rabi Isa", staffId: "STF-002" });
        // Applicant (has applied, not yet paid) — demonstrates applicant role routing
        users.push({ email: "mustapha.yakubu@example.com", password: "applicant123", role: "applicant", name: "Mustapha Yakubu", applicationId: "TSCE/APP/2026/00212" });

        /* --- Announcements (10, demo) --- */
        const announcements = [
            ["October Cohort Orientation", "Orientation for all newly admitted students will hold before the commencement of classes. Attendance is compulsory; please come with your admission slip and a valid ID.", "Students", true, "2026-09-22", "Event"],
            ["Early-Bird Discount Ends 30 September", "Pay before 1 October 2026 to enjoy a 15% early-bird discount on all programmes. Complete your application and payment online.", "Public", true, "2026-09-20", "Admissions"],
            ["Excellence Award: Upload Your WAEC Result", "Applicants who sat WAEC from 2020 to date with 5 A's or more qualify for a 50% Excellence Award. Upload your result for verification.", "Public", false, "2026-09-18", "Scholarship"],
            ["Intake Examination & Interview Schedule", "Scholarship candidates (up to 40%) will sit the intake examination on 3, 5 and 7 October. Check your email for your assigned slot.", "Public", false, "2026-09-16", "Admissions"],
            ["Full-Stack Capstone Project Briefing", "Full-Stack Software Engineering students: capstone project briefs will be released on Monday. Form teams of 3 by Friday.", "Students", false, "2026-09-15", "Academic"],
            ["Computer Lab Extended Hours", "The main computer lab will now open until 7:00pm on weekdays for practice sessions. Bring your student ID.", "Students", false, "2026-09-12", "Facilities"],
            ["Staff Meeting — Q4 Planning", "All instructors and admin staff: Q4 planning meeting holds on Thursday at 2:00pm in the boardroom.", "Staff", false, "2026-09-10", "Internal"],
            ["TSCE Partners with Local Tech Hubs", "TSCE is building partnerships with technology hubs in Kaduna State to create internship pathways for graduates.", "Public", false, "2026-09-05", "News"],
            ["July Cohort Certificates Ready", "Certificates for the July 2026 cohort are ready. Graduates can view and verify their certificates in the student portal.", "Students", false, "2026-08-28", "Certificates"],
            ["Draft: Graduation Ceremony Plans", "Planning notes for the December graduation ceremony — venue, guests and programme of events.", "Staff", false, "2026-09-24", "Event", "Draft"]
        ].map(([title, body, audience, pinned, date, tag, status], i) => ({
            id: `ANN-${pad(i + 1, 3)}`, title, body, audience, pinned, tag, status: status || "Published",
            author: i % 3 === 0 ? "Admissions Office" : i % 3 === 1 ? "Academic Office" : "Management", createdAt: iso(date + "T10:00:00")
        }));

        /* --- Notifications (demo) --- */
        const notifications = [];
        const note = (to, title, body, type, date, read = false) => notifications.push({ id: `NTF-${pad(notifications.length + 1, 4)}`, to, title, body, type, read, createdAt: iso(date) });
        note("amina.yusuf@example.com", "Application received", "Your application has been received.", "application", "2026-07-10T10:00:00", true);
        note("amina.yusuf@example.com", "Payment successful", "Your payment was successful. Ref: " + payments[0].ref, "payment", "2026-07-11T11:30:00", true);
        note("amina.yusuf@example.com", "Result published", "Your assessment result for Databases has been published.", "result", "2026-09-21T15:00:00");
        note("amina.yusuf@example.com", "Capstone briefing", "Capstone project briefs will be released on Monday.", "announcement", "2026-09-15T09:00:00");
        note("amina.yusuf@example.com", "Lab hours extended", "The computer lab now opens until 7:00pm on weekdays.", "announcement", "2026-09-12T09:00:00", true);
        note("muhammad.ibrahim@example.com", "Scholarship approved", "Your scholarship application has been approved (Excellence Award — 50%).", "scholarship", "2026-07-28T12:00:00", true);
        note("muhammad.ibrahim@example.com", "Result published", "Your assessment result has been published.", "result", "2026-09-19T12:00:00");
        note("staff", "New application", "Grace Audu applied for Network Engineering.", "application", "2026-09-17T16:10:00");
        note("staff", "Payment pending", "Bank transfer from Safiya Kabir awaiting confirmation.", "payment", "2026-09-08T10:00:00");
        note("staff", "Scholarship review", "3 scholarship requests are awaiting review.", "scholarship", "2026-09-20T09:00:00");
        note("staff", "Payment failed", "Kabiru Adamu's card payment failed.", "payment", "2026-09-11T14:00:00", true);

        /* --- Support tickets (demo) --- */
        const tickets = [
            { id: "TKT-1042", to: "amina.yusuf@example.com", subject: "Access to recorded JavaScript session", category: "Learning", status: "Resolved", createdAt: iso("2026-08-24T10:00:00"), reply: "The recording is now available under Learning → Resources." },
            { id: "TKT-1068", to: "amina.yusuf@example.com", subject: "Capstone team formation", category: "Academic", status: "Open", createdAt: iso("2026-09-22T12:00:00"), reply: null }
        ];

        /* --- Settings --- */
        const settings = {
            institution: { name: TSCE_FLYER.name, short: TSCE_FLYER.short, address: TSCE_FLYER.address, phone: TSCE_FLYER.phones.join(", "), website: TSCE_FLYER.website, email: TSCE_FLYER.email },
            admissions: { opens: TSCE_FLYER.enrolmentOpens, closes: TSCE_FLYER.enrolmentCloses, cohortDate: TSCE_FLYER.startDate, earlyBirdDeadline: TSCE_FLYER.earlyBirdDeadline, intake: COHORTS.oct.name, acceptingApplications: true },
            payments: { gateway: "Zainpay", environment: "sandbox", currency: "NGN", refPrefix: "TSCE-ZP", allowCard: true, allowTransfer: true, allowVirtual: true, autoVerify: true },
            notifications: { email: true, sms: true, push: false, paymentAlerts: true, applicationAlerts: true },
            // Historical / archived-cohort baselines so the management dashboard reflects all-time figures (demo)
            baselines: { applications: 0, paid: 0, active: 0, pending: 0, revenue: 0 },
            counters: { app: 215, tx: txSeq, student: 215 }
        };

        // Baselines calibrated so the demo dashboard opens at the headline figures (324 / 247 / 218 / 77 / ₦11.85m)
        const liveApps = applications.length;
        const livePaid = applications.filter((a) => a.paymentStatus === "Paid").length;
        const liveActive = students.filter((s) => s.status === "Active").length;
        const livePending = applications.filter((a) => ["Pending", "Under Review"].includes(a.status)).length;
        const liveRevenue = payments.filter((p) => p.status === "SUCCESS").reduce((s, p) => s + p.amount, 0);
        settings.baselines = { applications: 324 - liveApps, paid: 247 - livePaid, active: 218 - liveActive, pending: 77 - livePending, revenue: 11850000 - liveRevenue };

        const enquiries = [];
        return { programmes, students, applications, payments, attendance, results, scholarships, staff, users, announcements, notifications, tickets, settings, enquiries };
    }

    const testimonials = [
        { name: "Amina Yusuf", role: "Full-Stack Software Engineering", quote: "Within weeks I went from basic HTML to building a complete web app with a database. The practical projects made everything click." },
        { name: "Muhammad Ibrahim", role: "Cybersecurity Fundamentals", quote: "The labs were hands-on from day one. I now understand how attacks happen and how organisations defend themselves." },
        { name: "Maryam Sani", role: "Digital Marketing & E-Commerce", quote: "I launched my online store during the programme. My sales on social media have more than doubled since graduating." }
    ];

    return { build, testimonials, COHORTS };
})();
