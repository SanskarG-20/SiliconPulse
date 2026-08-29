"""Tests for HTML sanitization and URL cleaning (fix for raw <a href> in HackerNews)."""
from app.utils import sanitize_content, sanitize_title, clean_url, html_to_text, extract_primary_url


def test_decode_entities():
    assert sanitize_title("<em>Nvidia</em> releases open-source GPU kernel modules") == "Nvidia releases open-source GPU kernel modules"
    assert "https://www.example.com/path" in html_to_text("https:&#x2F;&#x2F;www.example.com&#x2F;path")
    assert "&amp;" not in sanitize_content("a &amp; b")


def test_strip_tracking_params():
    url = "https://www.theinformation.com/articles/nvidia?utm_campaign=article_email&utm_content=article-17723&fbclid=123"
    cleaned = clean_url(url)
    assert "utm_" not in cleaned
    assert "fbclid" not in cleaned
    assert cleaned == "https://www.theinformation.com/articles/nvidia"


def test_hn_story_text_with_anchors():
    raw = '<a href="https:&#x2F;&#x2F;www.theinformation.com&#x2F;articles&#x2F;nvidia-agrees-buy-open-source-model-repository-hugging-face-12-9-billion?utm_campaign=article_email&amp;utm_content=article-17723" rel="nofollow">https:&#x2F;&#x2F;www.theinformation.com&#x2F;articles&#x2F;nvidia-agrees-buy-op...</a> (paywalled)<p><a href="https:&#x2F;&#x2F;techcrunch.com&#x2F;2026&#x2F;08&#x2F;24&#x2F;hugging-face-reportedly-in-talks-to-be-acquired-for-13b&#x2F;" rel="nofollow">https:&#x2F;&#x2F;techcrunch.com&#x2F;2026&#x2F;08&#x2F;24&#x2F;hugging-face-reportedly-in...</a>'
    cleaned = sanitize_content(raw)
    assert "<a href" not in cleaned
    assert "&#x2F;" not in cleaned
    assert "utm_" not in cleaned
    assert "https://www.theinformation.com/articles/nvidia-agrees-buy-open-source-model-repository-hugging-face-12-9-billion" in cleaned
    assert "paywalled" in cleaned


def test_hn_malformed_truncated_anchor():
    raw = 'Letter: <a href="https:&#x2F;&#x2F;images.nvidia.com&#x2F;pdf&#x2F;Open-Weights-and-American-AI-Leadership.pdf" rel="nofollow">https:&#x2F;&#x2F;images.nvidia.com&#x2F;pdf&#x2F;Open-Weights-and-American-AI-L...&lt;/a&gt; [pdf]<p><a href="https:&#x2F;&#x2F;x.com&#x2F;JensenHuang&#x2F;status&#x2F;2080643682'
    cleaned = sanitize_content(raw)
    assert "<a href" not in cleaned
    assert "href=" not in cleaned
    assert "https://images.nvidia.com/pdf/Open-Weights-and-American-AI-Leadership.pdf" in cleaned
    # Second malformed link should also be captured without raw href fragment
    assert "https://x.com/JensenHuang/status/2080643682" in cleaned
    assert "Letter:" in cleaned


def test_hn_related_kimi():
    raw = 'Related: <i>Kimi-K3 Technical Report [pdf]</i> - <a href="https:&#x2F;&#x2F;news.ycombinator.com&#x2F;item?id=49070985">https:&#x2F;&#x2F;news.ycombinator.com&#x2F;item?id=49070985</a>'
    cleaned = sanitize_content(raw)
    assert "Kimi-K3 Technical Report" in cleaned
    assert "https://news.ycombinator.com/item?id=49070985" in cleaned
    assert "<i>" not in cleaned


def test_extract_primary_url_prefers_fallback():
    html = '<a href="https://www.theinformation.com/articles/nvidia?utm_campaign=x">link</a>'
    fallback = "https://www.businessinsider.com/nvidia-in-talks-to-buy-hugging-face-13-billion-dollars-2026-8"
    # Should prefer fallback (story_url) when valid
    assert extract_primary_url(html, fallback) == "https://www.businessinsider.com/nvidia-in-talks-to-buy-hugging-face-13-billion-dollars-2026-8"
    # When fallback empty, extract href
    assert extract_primary_url(html, "") == "https://www.theinformation.com/articles/nvidia"
