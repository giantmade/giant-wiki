"""Tests for Mermaid diagram rendering in wiki pages."""

from wiki.views import render_markdown


class TestMermaidRendering:
    """Tests for Mermaid diagram markdown extension."""

    def test_mermaid_block_rendering(self):
        """Test that mermaid code blocks are converted to div elements."""
        markdown_text = """
# Test Page

```mermaid
graph TD
    A-->B
```

Regular text.
"""
        html = render_markdown(markdown_text)
        assert '<div class="mermaid">' in html
        assert "graph TD" in html
        assert "A-->B" in html
        # Should NOT be wrapped in pre/code tags
        assert "<pre>" not in html or '<div class="mermaid">' in html.split("<pre>")[0]

    def test_regular_code_blocks_unchanged(self):
        """Test that regular code blocks still render as code."""
        markdown_text = """
```python
def hello():
    print("world")
```
"""
        html = render_markdown(markdown_text)
        assert "<pre>" in html
        assert "<code" in html  # Just check for opening code tag (may have attributes)
        assert "def hello()" in html

    def test_multiple_mermaid_blocks(self):
        """Test multiple mermaid diagrams in one page."""
        markdown_text = """
```mermaid
graph TD
    A-->B
```

Some text.

```mermaid
sequenceDiagram
    Alice->>Bob: Hello
```
"""
        html = render_markdown(markdown_text)
        assert html.count('<div class="mermaid">') == 2
        assert "graph TD" in html
        assert "sequenceDiagram" in html

    def test_mermaid_with_complex_syntax(self):
        """Test mermaid blocks with complex syntax and special characters."""
        markdown_text = """
```mermaid
sequenceDiagram
    participant Alice
    participant Bob
    Alice->>John: Hello John, how are you?
    loop Healthcheck
        John->>John: Fight against hypochondria
    end
    Note right of John: Rational thoughts!
    John-->>Alice: Great!
    John->>Bob: How about you?
    Bob-->>John: Jolly good!
```
"""
        html = render_markdown(markdown_text)
        assert '<div class="mermaid">' in html
        assert "sequenceDiagram" in html
        assert "participant Alice" in html
        assert "loop Healthcheck" in html

    def test_mixed_content(self):
        """Test mixed content with mermaid, code blocks, and tables."""
        markdown_text = """
# Test Page

Regular paragraph.

```mermaid
graph TD
    A-->B
```

## Code Section

```python
def test():
    return True
```

## Table Section

| Column 1 | Column 2 |
|----------|----------|
| Value 1  | Value 2  |

Another mermaid:

```mermaid
pie title Pets
    "Dogs" : 386
    "Cats" : 85
```
"""
        html = render_markdown(markdown_text)
        # Check mermaid blocks
        assert html.count('<div class="mermaid">') == 2
        assert "graph TD" in html
        assert "pie title Pets" in html

        # Check code blocks
        assert "<pre>" in html
        assert "def test():" in html

        # Check tables
        assert "<table>" in html
        assert "Column 1" in html

    def test_mermaid_with_whitespace_variations(self):
        """Test mermaid blocks with various whitespace patterns."""
        # Extra whitespace after mermaid keyword
        markdown_text = """
```mermaid
graph TD
    A-->B
```
"""
        html = render_markdown(markdown_text)
        assert '<div class="mermaid">' in html

    def test_empty_mermaid_block(self):
        """Test handling of empty mermaid blocks."""
        markdown_text = """
```mermaid
```
"""
        html = render_markdown(markdown_text)
        # Should still create the div, just empty
        assert '<div class="mermaid">' in html

    def test_mermaid_flowchart_types(self):
        """Test different flowchart diagram types."""
        markdown_text = """
```mermaid
flowchart LR
    A[Start] --> B{Decision}
    B -->|Yes| C[End]
    B -->|No| D[Loop]
```
"""
        html = render_markdown(markdown_text)
        assert '<div class="mermaid">' in html
        assert "flowchart LR" in html
        assert "Decision" in html

    def test_mermaid_class_diagram(self):
        """Test class diagram rendering."""
        markdown_text = """
```mermaid
classDiagram
    Animal <|-- Duck
    Animal <|-- Fish
    Animal : +int age
    Animal : +String gender
```
"""
        html = render_markdown(markdown_text)
        assert '<div class="mermaid">' in html
        assert "classDiagram" in html
        assert "Animal" in html

    def test_mermaid_state_diagram(self):
        """Test state diagram rendering."""
        markdown_text = """
```mermaid
stateDiagram-v2
    [*] --> Still
    Still --> [*]
    Still --> Moving
    Moving --> Still
```
"""
        html = render_markdown(markdown_text)
        assert '<div class="mermaid">' in html
        assert "stateDiagram-v2" in html

    def test_mermaid_gantt_chart(self):
        """Test Gantt chart rendering."""
        markdown_text = """
```mermaid
gantt
    title A Gantt Diagram
    dateFormat  YYYY-MM-DD
    section Section
    A task           :a1, 2014-01-01, 30d
    Another task     :after a1, 20d
```
"""
        html = render_markdown(markdown_text)
        assert '<div class="mermaid">' in html
        assert "gantt" in html
        assert "A Gantt Diagram" in html

    def test_mermaid_not_confused_with_other_languages(self):
        """Test that code blocks with similar names aren't affected."""
        markdown_text = """
```javascript
// This should remain a code block
const mermaid = "test";
```

```mermaid
graph TD
    A-->B
```

```python
# Another code block
mermaid_config = {}
```
"""
        html = render_markdown(markdown_text)
        # Should have one mermaid div
        assert html.count('<div class="mermaid">') == 1
        # Should have two code blocks
        assert html.count("<pre>") == 2
        assert "javascript" in html.lower() or "const mermaid" in html
        assert "mermaid_config" in html
