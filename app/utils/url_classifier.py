from __future__ import annotations

from urllib.parse import urlparse

from app.utils.url_utils import normalize_url


URL_TYPE_PATTERNS = {
    "blog": ["blog", "news", "article", "insights", "posts", "actualites", "nieuws", "artikel", "artikelen"],
    "product": ["product", "products", "item", "sku", "shop", "pricing", "produit", "produits", "produkt", "winkel"],
    "docs": ["docs", "documentation", "guide", "manual", "kb", "knowledge-base", "gids", "handleiding", "dokumentation"],
    "faq": ["faq", "faqs", "help", "support", "vragen", "hilfe", "aide"],
    "about": ["about", "company", "team", "story", "关于", "uber-uns", "ueber-uns", "a-propos", "apropos", "over-ons"],
    "contact": ["contact", "联系我们", "联系", "kontakt", "contactez", "nous-contacter", "neem-contact"],
    "case_study": ["case", "study", "portfolio", "success", "案例", "fallstudie", "referenz", "etude-de-cas", "klantverhaal"],
    "category": ["category", "categories", "collections", "topics", "tag"],
    "landing": ["landing", "solution", "solutions", "service", "services", "dienst", "diensten", "leistung", "leistungen"],
}


def classify_url_type(url: str) -> str:
    """按路径关键词给 URL 做轻量类型分类。"""
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    path = (parsed.path or "/").strip("/").lower()
    if not path:
        return "homepage"

    segments = [segment for segment in path.split("/") if segment]
    for url_type, keywords in URL_TYPE_PATTERNS.items():
        if any(keyword in segment for segment in segments for keyword in keywords):
            return url_type
    return "page"
