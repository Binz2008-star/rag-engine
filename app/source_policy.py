"""
SourcePolicy module - centralizes all source-specific logic for Phase 2 generalization.

This module provides:
- Source metadata abstraction (entity_type, format, quality_score)
- Configurable scoring weights
- Centralized source priors (soft, not hard injection)
- All source-specific boosts in one place
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


class EntityType(Enum):
    """Normalized entity types for sources."""
    COMPANY_PROFILE = "company_profile"
    CV = "cv"
    BIO = "bio"
    OTHER = "other"


class Format(Enum):
    """Normalized format types for sources."""
    PDF = "pdf"
    HTML = "html"
    MD = "md"
    DOCX = "docx"
    TXT = "txt"
    OTHER = "other"


@dataclass
class SourceMetadata:
    """Normalized metadata for a source."""
    entity_type: EntityType
    format: Format
    canonical_source: str
    quality_score: float = 0.8  # 0.0-1.0
    aliases: Tuple[str, ...] = field(default_factory=tuple)


@dataclass
class ScoringConfig:
    """Configurable scoring weights for hybrid retrieval."""
    semantic_weight: float = 0.65
    lexical_weight: float = 0.20
    metadata_weight: float = 0.10
    source_prior_weight: float = 0.05


@dataclass
class SourcePrior:
    """Soft source prior (not hard injection)."""
    source_pattern: str
    prior: float  # e.g., 1.10, 1.05, 0.95
    reason: str


@dataclass
class SourceBoost:
    """Source-specific boost (to be weakened gradually)."""
    source_pattern: str
    multiplier: float
    keywords: Tuple[str, ...]
    phase: str  # "bias", "boost", "rescue", "force"
    reason: str
    is_hard: bool = False  # True = hard injection, False = soft boost


class SourcePolicy:
    """
    Centralizes all source-specific logic.

    This is the single place to:
    - See every hack
    - Weaken them gradually
    - Measure impact cleanly
    """

    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()
        self._source_metadata: Dict[str, SourceMetadata] = self._build_source_metadata()
        self._source_priors: List[SourcePrior] = self._build_source_priors()
        self._source_boosts: List[SourceBoost] = self._build_source_boosts()

    def _build_source_metadata(self) -> Dict[str, SourceMetadata]:
        """Build normalized metadata for all sources."""
        return {
            "ECO_Company_Profile.pdf": SourceMetadata(
                entity_type=EntityType.COMPANY_PROFILE,
                format=Format.PDF,
                canonical_source="ECO_Company_Profile.pdf",
                quality_score=0.9,
                aliases=("eco_company_profile", "eco", "eco-technology"),
            ),
            "Roben_Edwan_Deliveroo_Tailored_CV.txt": SourceMetadata(
                entity_type=EntityType.CV,
                format=Format.TXT,
                canonical_source="Roben_Edwan_Deliveroo_Tailored_CV.txt",
                quality_score=0.95,
                aliases=("tailored_cv", "deliveroo_tailored", "cv", "roben", "robin"),
            ),
            "Roben_Edwan_CV.pdf": SourceMetadata(
                entity_type=EntityType.CV,
                format=Format.PDF,
                canonical_source="Roben_Edwan_CV.pdf",
                quality_score=0.85,
                aliases=("cv_pdf", "roben_cv"),
            ),
            "Roben_Edwan_CV_Final.docx": SourceMetadata(
                entity_type=EntityType.CV,
                format=Format.DOCX,
                canonical_source="Roben_Edwan_CV_Final.docx",
                quality_score=0.85,
                aliases=("cv_final", "cv_docx"),
            ),
            "Robin_Edwan_Executive_Bio.pdf": SourceMetadata(
                entity_type=EntityType.BIO,
                format=Format.PDF,
                canonical_source="Robin_Edwan_Executive_Bio.pdf",
                quality_score=0.8,
                aliases=("executive_bio", "bio", "robin_bio"),
            ),
            "Robin_Edwan_Executive_Bio_.pdf": SourceMetadata(
                entity_type=EntityType.BIO,
                format=Format.PDF,
                canonical_source="Robin_Edwan_Executive_Bio_.pdf",
                quality_score=0.8,
                aliases=("executive_bio_dup", "bio_dup"),
            ),
            "ECO Technology Environmental Protection Services L.L.C..md": SourceMetadata(
                entity_type=EntityType.COMPANY_PROFILE,
                format=Format.MD,
                canonical_source="ECO_Technology.md",
                quality_score=0.7,
                aliases=("eco_md", "eco_llc", "eco_technology"),
            ),
            "ecotech_company_profile.html": SourceMetadata(
                entity_type=EntityType.COMPANY_PROFILE,
                format=Format.HTML,
                canonical_source="ecotech_company_profile.html",
                quality_score=0.7,
                aliases=("eco_html", "ecotech"),
            ),
        }

    def _build_source_priors(self) -> List[SourcePrior]:
        """Build soft source priors (not hard injection)."""
        return [
            SourcePrior(
                source_pattern="ECO_Company_Profile.pdf",
                prior=1.10,
                reason="Primary company profile - high quality PDF",
            ),
            SourcePrior(
                source_pattern="Roben_Edwan_Deliveroo_Tailored_CV.txt",
                prior=1.10,
                reason="Primary CV - tailored, high quality",
            ),
            SourcePrior(
                source_pattern="Robin_Edwan_Executive_Bio.pdf",
                prior=0.95,
                reason="Executive bio - lower priority than CV",
            ),
        ]

    def _build_source_boosts(self) -> List[SourceBoost]:
        """
        Build all source-specific boosts (to be weakened gradually).

        These are the current hardcoded rules that need to be removed in Phase 2.
        """
        return [
            # ── Hard injection (to be removed first) ─────────────────────────────
            SourceBoost(
                source_pattern="Roben_Edwan_Deliveroo_Tailored_CV.txt",
                multiplier=10.0,
                keywords=(),
                phase="force",
                reason="CV injection - hard guarantee (PHASE 2: REMOVE)",
                is_hard=True,
            ),
            SourceBoost(
                source_pattern="ECO_Company_Profile.pdf",
                multiplier=10.0,
                keywords=(),
                phase="force",
                reason="ECO injection - hard guarantee (PHASE 2: REMOVE)",
                is_hard=True,
            ),

            # ── Boost phase (to be weakened) ───────────────────────────────────────
            SourceBoost(
                source_pattern="eco_company_profile",
                multiplier=1.20,
                keywords=("company", "profile", "eco"),
                phase="boost",
                reason="Company profile query → prefer ECO profile (PHASE 2: WEAKEN)",
                is_hard=False,
            ),
            SourceBoost(
                source_pattern="tailored_cv",
                multiplier=1.20,
                keywords=("education", "educational", "background", "skills", "tailored"),
                phase="boost",
                reason="CV-specific query → prefer tailored CV (PHASE 2: WEAKEN)",
                is_hard=False,
            ),
            SourceBoost(
                source_pattern="tailored_cv",
                multiplier=1.18,
                keywords=("degree", "mba", "bachelor", "university"),
                phase="boost",
                reason="Degree query → prefer tailored CV (PHASE 2: WEAKEN)",
                is_hard=False,
            ),

            # ── Bias phase (to be weakened) ────────────────────────────────────────
            SourceBoost(
                source_pattern="eco_company_profile",
                multiplier=1.08,
                keywords=("eco", "environment"),
                phase="bias",
                reason="ECO intent → light bias (PHASE 2: WEAKEN)",
                is_hard=False,
            ),
            SourceBoost(
                source_pattern="tailored_cv",
                multiplier=1.08,
                keywords=("education", "skills", "certificate", "experience"),
                phase="bias",
                reason="CV intent → light bias (PHASE 2: WEAKEN)",
                is_hard=False,
            ),
            SourceBoost(
                source_pattern="executive_bio",
                multiplier=0.95,
                keywords=(),
                phase="bias",
                reason="Executive bio → light penalty (PHASE 2: WEAKEN)",
                is_hard=False,
            ),

            # ── Rescue phase (to be weakened) ──────────────────────────────────────
            SourceBoost(
                source_pattern="tailored_cv",
                multiplier=1.12,
                keywords=("education", "skills", "certificate", "certification",
                          "work history", "تعليم", "مهارات", "شهادات", "خبرة", "وظائف"),
                phase="rescue",
                reason="CV intent → rescue from ECO dominance (PHASE 2: WEAKEN)",
                is_hard=False,
            ),
            SourceBoost(
                source_pattern="eco_company_profile",
                multiplier=0.96,
                keywords=("education", "skills", "certificate", "certification",
                          "work history", "تعليم", "مهارات", "شهادات", "خبرة", "وظائف"),
                phase="rescue",
                reason="CV intent → penalize ECO (PHASE 2: WEAKEN)",
                is_hard=False,
            ),
        ]

    def get_metadata(self, source: str) -> Optional[SourceMetadata]:
        """Get normalized metadata for a source."""
        source_lower = source.lower()
        for canonical, meta in self._source_metadata.items():
            if source == canonical:
                return meta
            if any(alias in source_lower for alias in meta.aliases):
                return meta
        # Default metadata for unknown sources
        return SourceMetadata(
            entity_type=EntityType.OTHER,
            format=Format.OTHER,
            canonical_source=source,
            quality_score=0.5,
        )

    def get_source_prior(self, source: str) -> float:
        """Get soft source prior (not hard injection)."""
        source_lower = source.lower()
        for prior in self._source_priors:
            if prior.source_pattern.lower() in source_lower:
                return prior.prior
        return 1.0  # No prior

    def get_applicable_boosts(self, source: str, query: str, phase: str) -> List[SourceBoost]:
        """Get applicable source boosts for a given source, query, and phase."""
        source_lower = source.lower()
        query_lower = query.lower()
        applicable = []

        for boost in self._source_boosts:
            if boost.phase != phase:
                continue

            # Check if source matches pattern
            if boost.source_pattern.lower() not in source_lower:
                continue

            # Check if keywords match (if any)
            if boost.keywords:
                if not any(kw in query_lower for kw in boost.keywords):
                    continue

            applicable.append(boost)

        return applicable

    def get_hard_injection_sources(self, intent: str) -> List[str]:
        """
        Get sources that have hard injection (to be removed in Phase 2).

        This is for tracking only - the actual injection should be removed.
        """
        hard_sources = []
        for boost in self._source_boosts:
            if boost.is_hard and boost.phase == "force":
                hard_sources.append(boost.source_pattern)
        return hard_sources

    def compute_soft_score(
        self,
        semantic_score: float,
        lexical_score: float = 0.0,
        source: str = "",
    ) -> float:
        """
        Compute soft score using configurable weights.

        This replaces hard multipliers with soft priors.
        """
        metadata = self.get_metadata(source) or SourceMetadata(
            entity_type=EntityType.OTHER,
            format=Format.OTHER,
            canonical_source=source,
            quality_score=0.5,
        )
        prior = self.get_source_prior(source)

        # Normalize scores to 0-1 range
        semantic_norm = min(semantic_score, 1.0)
        lexical_norm = min(lexical_score, 1.0)
        metadata_norm = metadata.quality_score

        # Weighted combination
        weighted = (
            semantic_norm * self.config.semantic_weight
            + lexical_norm * self.config.lexical_weight
            + metadata_norm * self.config.metadata_weight
        )

        # Apply soft prior
        final = weighted * prior

        return final

    def get_all_hacks(self) -> Dict[str, List[SourceBoost]]:
        """
        Get all hacks organized by category for tracking.

        Returns:
            Dict with keys: "hard_injection", "boost", "bias", "rescue"
        """
        hacks = {
            "hard_injection": [],
            "boost": [],
            "bias": [],
            "rescue": [],
        }

        for boost in self._source_boosts:
            if boost.is_hard:
                hacks["hard_injection"].append(boost)
            elif boost.phase in hacks:
                hacks[boost.phase].append(boost)

        return hacks

    def weaken_boost(self, source_pattern: str, phase: str, factor: float = 0.5) -> None:
        """
        Weaken a boost by a factor (for gradual removal).

        Args:
            source_pattern: Source pattern to weaken
            phase: Phase to weaken
            factor: Multiplicative factor (0.5 = halve the boost)
        """
        for boost in self._source_boosts:
            if boost.phase == phase and source_pattern in boost.source_pattern.lower():
                boost.multiplier = 1.0 + (boost.multiplier - 1.0) * factor

    def remove_hard_injection(self) -> None:
        """Remove all hard injection rules (for Phase 2)."""
        self._source_boosts = [
            boost for boost in self._source_boosts
            if not (boost.is_hard and boost.phase == "force")
        ]
