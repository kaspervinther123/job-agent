"""Candidate profile model."""

from pydantic import BaseModel


class CandidateProfile(BaseModel):
    """The candidate's profile for job matching."""

    name: str = "Kasper Vinther Hansen"
    email: str = "kaspervintherhansen@live.dk"
    location: str = "Aarhus, Denmark"

    education: str = """
MSc Political Science (Statskundskab), Aarhus University (Jan 2026), GPA 10/12
- Thesis: Used LLM and MLM (NLP) to analyze how CSRD legislation affected corporate greenwashing
- Focus on political data science methods
- Exchange semester at Humboldt Universität zu Berlin (2024)

BSc Political Science, Aarhus University (2020-2023), GPA 8.3/12
- Thesis: How climate considerations in public sector affect employee motivation
"""

    experience: str = """
1. Research Assistant - Institut for Statskundskab (Aug 2025 - Jan 2026)
   - Magtudredningen 2.0 project with Prof. Christopher Green-Pedersen
   - Built reusable R pipeline for Folketingets API data extraction and quality assurance

2. Project Assistant - Ramboll Management Consulting (Sep 2024 - Jan 2026)
   - Stakeholder Intelligence team
   - APV (arbejdspladsvurdering), trivselsmålinger, ledelsesevalueringer, kundetilfredshedsundersøgelser
   - Built internal analysis and reporting tools in R and Excel
   - Survey setup, data validation, visualization in R, Excel and internal tools

3. Junior Consultant - Lene Bak Consulting (Feb 2023 - Apr 2024)
   - Evaluation of Aarhus Kommune's Kultur- og Sundhedsplan (10 project evaluations)
   - Interviews with project leaders, survey design, qualitative analysis
   - External stakeholder communication with Kulturforvaltningen
   - Architecture research project with international survey

4. Phone Interviewer - Norstat (2021-2022)
   - Data collection and handling experience
"""

    skills: str = """
Technical:
- R (advanced): data analysis, visualization, API integration, package development
- Excel (advanced): data analysis, reporting tools, automation
- Python: NLP/LLM applications, data processing
- Survey tools: questionnaire design, quality assurance, validation

Methods:
- Quantitative analysis and statistics
- Qualitative evaluation and interviews
- Survey design and implementation
- Natural Language Processing / text analysis
- Policy analysis and evaluation

Domain Knowledge:
- Danish public administration (offentlig forvaltning)
- Municipal governance and state-municipal relations
- EU regulation (CSRD, sustainability reporting)
- Digitalization and AI in public sector
"""

    target_roles: str = """
Target job titles (søgeord):
- AC fuldmægtig / Akademisk fuldmægtig
- Analysekonsulent
- Konsulent / Management konsulent
- Cand.scient.pol / statskundskab stillinger
- Samfundsvidenskabelig konsulent

Preferred workplace types (score these higher):
- Styrelse (agency)
- Kommune (municipality)
- Region
- Interesseorganisation (interest organization)
- Departement
- Ministerium / Ministerie (ministry)

Strong interest in:
1. Konsulent/Analyst roles - Management consulting, public sector consulting
2. Offentlig forvaltning - Ministry positions (fuldmægtig), municipal analyst roles
3. Data/AI roles - AI systemejer, data-driven policy, digitalization
4. Generalist positions in central administration

Employment type:
- Fuldtid (full-time) only
- Both permanent positions (fastansættelse) and temporary/substitute (vikariat)

Key preferences:
- Meaningful work that makes a difference in society
- Combines technical/analytical skills with policy understanding
- Stakeholder interaction and seeing projects through to implementation
- Interest in digitalization, AI, and green transition
- Location: Hovedstaden (Copenhagen), Aarhus, or Odense
"""

    languages: str = "Danish (native), English (fluent), German (conversational)"

    def to_prompt_text(self) -> str:
        """Format profile for Claude prompt."""
        return f"""
## Candidate Profile: {self.name}

### Contact & Location
- Email: {self.email}
- Location: {self.location}
- Languages: {self.languages}

### Education
{self.education}

### Professional Experience
{self.experience}

### Skills & Competencies
{self.skills}

### Target Roles & Preferences
{self.target_roles}
"""
