"""Configuration management."""

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class CompanySource(BaseModel):
    """A company career page to scrape."""

    name: str
    url: str
    sector: str


class ScraperConfig(BaseModel):
    """Configuration for scrapers."""

    jobindex_enabled: bool = True
    jobindex_search_terms: list[str] = Field(
        default_factory=lambda: ["konsulent", "analytiker", "fuldmægtig", "data"]
    )
    jobindex_location: str = "Danmark"

    jobnet_enabled: bool = True
    jobnet_search_terms: list[str] = Field(
        default_factory=lambda: ["konsulent", "analytiker", "fuldmægtig"]
    )

    company_pages: list[CompanySource] = Field(default_factory=list)


class ScoringConfig(BaseModel):
    """Configuration for relevance scoring."""

    min_relevance: int = 60
    batch_size: int = 10


class EmailConfig(BaseModel):
    """Configuration for email sending."""

    to_address: str = "kaspervintherhansen@live.dk"
    from_address: str = "Job Agent <jobs@resend.dev>"


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # API Keys
    anthropic_api_key: str = ""
    resend_api_key: str = ""
    adzuna_app_id: Optional[str] = None
    adzuna_api_key: Optional[str] = None

    # Paths
    db_path: str = "data/jobs.db"
    config_path: str = "config.yaml"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


def get_default_company_pages() -> list[CompanySource]:
    """Get the default list of company career pages to scrape."""
    return [
        # Konsulent
        CompanySource(name="Implement Consulting Group", url="https://implementconsultinggroup.com/join-us", sector="konsulent"),
        CompanySource(name="Epinion", url="https://epinionglobal.com/da/karriere/", sector="konsulent"),
        CompanySource(name="Deloitte Denmark", url="https://www.deloitte.com/dk/en/careers/content/search-jobs.html", sector="konsulent"),
        CompanySource(name="PwC Denmark", url="https://www.pwc.dk/da/karriere/jobsoegning.html", sector="konsulent"),
        CompanySource(name="EY Denmark", url="https://www.ey.com/en_dk/careers/job-search", sector="konsulent"),
        CompanySource(name="Rambøll", url="https://www.ramboll.com/careers?locations=denmark", sector="konsulent"),
        CompanySource(name="VIVE", url="https://www.vive.dk/da/om-vive/ledige-stillinger/", sector="konsulent"),
        CompanySource(name="Analyse & Tal", url="https://www.ogtal.dk/jobs", sector="konsulent"),

        # Offentlig
        CompanySource(name="KL", url="https://www.kl.dk/om-kl/ledige-stillinger", sector="offentlig"),
        CompanySource(name="Komponent", url="https://www.komponent.dk/job", sector="offentlig"),
        CompanySource(name="Aarhus Kommune", url="https://aarhus.dk/job", sector="offentlig"),
        CompanySource(name="Finansministeriet", url="https://fm.dk/karriere/ledige-stillinger/", sector="offentlig"),
        CompanySource(name="Indenrigs- og Sundhedsministeriet", url="https://www.ism.dk/job-og-karriere", sector="offentlig"),
        CompanySource(name="Kulturministeriet", url="https://kum.dk/job-og-karriere", sector="offentlig"),
        CompanySource(name="Digitaliseringsstyrelsen", url="https://digst.dk/job/ledige-stillinger/", sector="offentlig"),
        CompanySource(name="Beskæftigelsesministeriet", url="https://www.bm.dk/karriere/ledige-stillinger", sector="offentlig"),

        # Interesseorganisation
        CompanySource(name="Dansk Erhverv", url="https://www.danskerhverv.dk/om-dansk-erhverv/ledige-stillinger/", sector="interesseorganisation"),
        CompanySource(name="Dansk Industri", url="https://www.danskindustri.dk/om-di/job-i-di/ledige-jobs/", sector="interesseorganisation"),
        CompanySource(name="Datatilsynet", url="https://www.datatilsynet.dk/karriere", sector="interesseorganisation"),

        # Velgørende
        CompanySource(name="Novo Nordisk Fonden", url="https://novonordiskfonden.dk/en/careers-and-jobs/", sector="velgoerende"),
        CompanySource(name="Rockwool Fonden", url="https://rockwoolfonden.dk/ledige-stillinger/", sector="velgoerende"),

        # Virksomhed
        CompanySource(name="Novo Nordisk", url="https://www.novonordisk.com/careers/find-a-job.html?countries=Denmark", sector="virksomhed"),
        CompanySource(name="LEGO", url="https://www.lego.com/da-dk/careers", sector="virksomhed"),
        CompanySource(name="Vestas", url="https://careers.vestas.com/?locale=da_DK", sector="virksomhed"),
    ]


# Global settings instance
settings = Settings()
