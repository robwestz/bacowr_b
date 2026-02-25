"""
BACOWR v5 Data Models — Type-safe structures for the article pipeline.

Consolidated from v3-round2/serp_lens/models.py with V5 additions:
- SourceVerification (NEW): tracks verified deep links
- JobSpec: input from CSV
- Preflight: semantic analysis output
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime
import json


# === Enums ===

class IntentType(Enum):
    INFORMATIONAL = "informational"
    TRANSACTIONAL = "transactional"
    NAVIGATIONAL = "navigational"
    COMMERCIAL = "commercial"
    LOCAL = "local"


class SemanticDistance(Enum):
    IDENTICAL = "identical"      # 0.9-1.0
    CLOSE = "close"              # 0.7-0.9
    MODERATE = "moderate"        # 0.5-0.7
    DISTANT = "distant"          # 0.3-0.5
    UNRELATED = "unrelated"      # 0.0-0.3


class BridgeConfidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    RISKY = "risky"


class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# === Input ===

@dataclass
class JobSpec:
    """One row from the job_list CSV."""
    job_number: int
    publisher_domain: str
    target_url: str
    anchor_text: str


# === SERP & Semantic Models ===

@dataclass
class PAAQuestion:
    question: str
    position: int


@dataclass
class RelatedSearch:
    query: str
    position: int


@dataclass
class SERPResult:
    position: int
    title: str
    url: str
    description: str = ""
    domain: str = ""
    title_pattern: Optional[str] = None


@dataclass
class GoogleIntelligence:
    query: str
    timestamp: datetime
    paa_questions: List[PAAQuestion] = field(default_factory=list)
    related_searches: List[RelatedSearch] = field(default_factory=list)
    top_results: List[SERPResult] = field(default_factory=list)
    detected_intent: IntentType = IntentType.INFORMATIONAL
    dominant_entities: List[str] = field(default_factory=list)
    content_patterns: List[str] = field(default_factory=list)
    has_featured_snippet: bool = False
    has_knowledge_panel: bool = False
    is_ymyl: bool = False


@dataclass
class SchemaEntity:
    type: str
    name: Optional[str] = None
    description: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TargetFingerprint:
    url: str
    timestamp: datetime
    title: str = ""
    meta_description: str = ""
    h1: str = ""
    canonical_url: Optional[str] = None
    language: str = "sv"
    schema_entities: List[SchemaEntity] = field(default_factory=list)
    primary_entity_type: Optional[str] = None
    main_keywords: List[str] = field(default_factory=list)
    topic_cluster: List[str] = field(default_factory=list)
    internal_links_topics: List[str] = field(default_factory=list)
    estimated_word_count: int = 0
    has_reviews: bool = False
    has_pricing: bool = False
    is_ecommerce: bool = False


@dataclass
class PublisherProfile:
    domain: str
    timestamp: datetime
    site_name: Optional[str] = None
    site_description: Optional[str] = None
    primary_language: str = "sv"
    primary_topics: List[str] = field(default_factory=list)
    secondary_topics: List[str] = field(default_factory=list)
    recent_article_topics: List[str] = field(default_factory=list)
    category_structure: List[str] = field(default_factory=list)
    outbound_link_domains: List[str] = field(default_factory=list)
    recent_articles: list = field(default_factory=list)
    sample_size: int = 0
    confidence: float = 0.0


@dataclass
class BridgeSuggestion:
    concept: str
    rationale: str
    confidence: BridgeConfidence
    confidence_score: float
    publisher_relevance: float = 0.0
    target_relevance: float = 0.0
    suggested_angle: Optional[str] = None
    entities_to_include: List[str] = field(default_factory=list)
    entities_to_avoid: List[str] = field(default_factory=list)


@dataclass
class SemanticBridge:
    publisher_domain: str
    target_url: str
    anchor_text: str
    timestamp: datetime
    raw_distance: float
    distance_category: SemanticDistance
    suggestions: List[BridgeSuggestion] = field(default_factory=list)
    recommended_angle: Optional[str] = None
    required_entities: List[str] = field(default_factory=list)
    forbidden_entities: List[str] = field(default_factory=list)
    trust_link_topics: List[str] = field(default_factory=list)
    trust_link_avoid: List[str] = field(default_factory=list)


# === V5 NEW: Source Verification ===

@dataclass
class VerifiedSource:
    """A single trust link that has been verified by fetching the actual URL."""
    url: str
    domain: str
    fetched_at: datetime
    http_status: int
    extracted_facts: List[str]       # Specific facts/stats found on the page
    relevance_to_article: str        # How this source supports the article
    is_deep_link: bool               # True if URL has specific path (not root)
    is_verified: bool                # True if content was successfully read

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "domain": self.domain,
            "http_status": self.http_status,
            "extracted_facts": self.extracted_facts,
            "relevance": self.relevance_to_article,
            "is_deep_link": self.is_deep_link,
            "verified": self.is_verified
        }


@dataclass
class SourceVerificationResult:
    """Result of the source verification step for one job."""
    job_number: int
    verified_sources: List[VerifiedSource] = field(default_factory=list)
    rejected_urls: List[Dict[str, str]] = field(default_factory=list)  # {url, reason}
    verification_complete: bool = False


# === Pipeline Output ===

@dataclass
class Preflight:
    """Complete preflight analysis for one job — input to article generation."""
    job: JobSpec
    publisher: Optional[PublisherProfile] = None
    target: Optional[TargetFingerprint] = None
    bridge: Optional[SemanticBridge] = None
    google: Optional[GoogleIntelligence] = None
    sources: Optional[SourceVerificationResult] = None  # V5 NEW
    risk_level: RiskLevel = RiskLevel.LOW
    language: str = "sv"
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    generated_at: Optional[datetime] = None

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON for storage."""
        data = {
            "job_number": self.job.job_number,
            "publisher_domain": self.job.publisher_domain,
            "target_url": self.job.target_url,
            "anchor_text": self.job.anchor_text,
            "language": self.language,
            "risk_level": self.risk_level.value,
            "semantic_analysis": None,
            "verified_sources": None,
            "constraints": {
                "word_count": "750-900",
                "anchor_placement": "word 250-550",
                "anchor_not_in": ["first 250 words", "last 100 words"],
                "trust_links": "1-2 verified sources on article topic",
                "headings": "max 1 (title only)",
                "bullets": "none",
                "style": "grounded, specific examples, no helicopter perspective",
                "paragraphs": ">=4, 100-200 words each, fully developed thoughts"
            },
            "warnings": self.warnings,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None
        }

        if self.bridge:
            data["semantic_analysis"] = {
                "raw_distance": round(self.bridge.raw_distance, 3),
                "distance_category": self.bridge.distance_category.value,
                "recommended_angle": self.bridge.recommended_angle,
                "bridge_suggestions": [
                    {
                        "concept": s.concept,
                        "rationale": s.rationale,
                        "confidence": s.confidence.value
                    }
                    for s in self.bridge.suggestions[:3]
                ],
                "required_entities": self.bridge.required_entities,
                "forbidden_entities": self.bridge.forbidden_entities,
                "trust_link_topics": self.bridge.trust_link_topics,
                "trust_link_avoid": self.bridge.trust_link_avoid
            }

        if self.sources and self.sources.verified_sources:
            data["verified_sources"] = [
                s.to_dict() for s in self.sources.verified_sources
            ]

        return json.dumps(data, indent=indent, ensure_ascii=False)
