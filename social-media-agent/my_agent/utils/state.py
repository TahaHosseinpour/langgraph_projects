"""State definitions for the social media agent."""

import operator
from typing import Annotated, Optional, TypedDict


class VerifiedUrl(TypedDict):
    """A URL whose content has been fetched and verified."""

    url: str  # The original link
    content: str  # Extracted text content


class VerifyState(TypedDict):
    """Input state for a single parallel verifier branch (via Send)."""

    url: str  # The link this branch is responsible for


class GeneratePostState(TypedDict):
    """Main state for the post generation workflow."""

    # Input
    links: list[str]  # Links the user wants to turn into a post

    # Verify phase (reducer because links are verified in parallel via Send)
    verified_urls: Annotated[list[VerifiedUrl], operator.add]

    # Generated content
    report: str  # Marketing report summarizing the links
    post: str  # Final post text
    image_url: Optional[str]  # Selected image, if any

    # Flow control
    condense_count: int  # How many times we condensed the post
