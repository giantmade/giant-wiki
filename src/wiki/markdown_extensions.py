"""Custom Markdown extensions for wiki pages."""

import re

from markdown.extensions import Extension
from markdown.postprocessors import Postprocessor


class MermaidExtension(Extension):
    """Markdown extension to handle Mermaid diagrams."""

    def extendMarkdown(self, md):
        """Register the Mermaid postprocessor."""
        md.postprocessors.register(MermaidPostprocessor(md), "mermaid", priority=25)


class MermaidPostprocessor(Postprocessor):
    """Postprocessor that converts <pre><code class="language-mermaid"> to <div class="mermaid">."""

    def run(self, text):
        """Process the final HTML and convert mermaid code blocks."""
        # Pattern to match <pre><code class="language-mermaid">...</code></pre>
        pattern = re.compile(
            r'<pre><code class="language-mermaid">(.*?)</code></pre>',
            re.DOTALL,
        )

        def replace_mermaid(match):
            # Get the content and unescape HTML entities
            content = match.group(1)
            # Unescape common HTML entities that markdown might have escaped
            content = content.replace("&lt;", "<")
            content = content.replace("&gt;", ">")
            content = content.replace("&amp;", "&")
            content = content.replace("&quot;", '"')
            # Return as div with mermaid class
            return f'<div class="mermaid">{content}</div>'

        return pattern.sub(replace_mermaid, text)
