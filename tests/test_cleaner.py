from recipe_extractor.cleaner import clean_page_text


def test_cleaner_removes_navigation_and_scripts():
    html = """
    <html><body>
      <nav>Home Recipes Shop</nav>
      <main><h1>Soup</h1><p>2 cups stock</p><p>Simmer for 10 minutes.</p></main>
      <script>alert('x')</script>
    </body></html>
    """
    text = clean_page_text(html, max_chars=1000)
    assert "Soup" in text
    assert "2 cups stock" in text
    assert "Home Recipes Shop" not in text
    assert "alert" not in text
