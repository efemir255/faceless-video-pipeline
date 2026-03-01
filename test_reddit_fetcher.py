from reddit_fetcher import detect_series, fetch_series_parts

def test_detect_series():
    titles = [
        ("The haunting of Hill House Part 1", 1),
        ("My scary story [Pt 2]", 2),
        ("Chapter 5: The beginning", 5),
        ("Something happens (Ch. 3)", 3),
        ("Just a normal story", None),
        ("Part of the plan", None), # Should not match if no digit
    ]

    for title, expected in titles:
        result = detect_series(title)
        print(f"Title: '{title}' -> Part: {result} (Expected: {expected})")
        assert result == expected

if __name__ == "__main__":
    try:
        test_detect_series()
        print("\nSeries detection tests passed!")
    except AssertionError as e:
        print(f"\nSeries detection tests failed!")
